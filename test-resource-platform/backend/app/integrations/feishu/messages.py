import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant.llm import LlmClientError, create_llm_client
from app.assistant.service import AssistantError, run_assistant_message
from app.core.config import get_settings
from app.credentials.crypto import CredentialCipher, CredentialDecryptionError
from app.integrations.feishu.cards import (
    build_confirmation_card,
    build_free_machines_card,
    build_home_card,
    build_machines_card,
    build_my_leases_card,
    build_operation_result_card,
)
from app.integrations.feishu.client import (
    FeishuClientError,
    send_feishu_card_reply,
    send_feishu_text_reply,
)
from app.integrations.feishu.models import (
    FeishuApp,
    FeishuBindingCode,
    FeishuCardActionEvent,
    FeishuMessageEvent,
    FeishuMessageHandledStatus,
    FeishuUserBinding,
)
from app.leases.schemas import ResourceLeaseCreateRequest, ResourceLeaseExtendRequest
from app.leases.service import (
    LeaseNotActiveError,
    LeaseNotFoundError,
    LeaseNotOwnedError,
    MachineNotAvailableError,
    MachineNotFoundError,
    ResourceAlreadyLeasedError,
    ResourcePoolDisabledError,
    create_resource_lease,
    extend_resource_lease,
    list_active_machine_occupancy,
    list_user_leases,
    release_resource_lease,
)
from app.resources.models import MachineResource, ResourceAdminStatus, ResourcePool
from app.resources.service import list_machine_resources


class FeishuMessageAppNotFoundError(Exception):
    pass


class FeishuMessageDispatchError(Exception):
    pass


class FeishuCardActionValue(BaseModel):
    action: Literal[
        "show_free_machines",
        "show_machines",
        "show_my_leases",
        "confirm_lease",
        "execute_lease",
        "confirm_extend",
        "execute_extend",
        "confirm_release",
        "execute_release",
        "cancel",
    ]
    resource_code: str | None = Field(default=None, max_length=128)
    lease_id: str | None = Field(default=None, max_length=64)
    duration_minutes: int = Field(default=60, ge=1, le=10080)
    purpose: str = Field(default="feishu-card", min_length=1, max_length=500)


@dataclass(frozen=True)
class FeishuInboundMessage:
    feishu_app_id: int
    message_id: str
    chat_id: str
    sender_open_id: str
    message_type: str
    text: str
    raw_event: dict


@dataclass(frozen=True)
class FeishuCardAction:
    feishu_app_id: int
    operator_open_id: str
    action_value: dict
    raw_event: dict
    action_id: str | None = None


@dataclass(frozen=True)
class FeishuMessageResult:
    reply_text: str | None
    duplicate: bool
    reply_card: dict | None = None


@dataclass(frozen=True)
class FeishuMessageDispatchResult:
    reply_text: str | None
    duplicate: bool
    reply_sent: bool
    reply_card: dict | None = None


def dispatch_feishu_inbound_message(
    session: Session,
    inbound: FeishuInboundMessage,
    cipher: CredentialCipher,
) -> FeishuMessageDispatchResult:
    result = handle_feishu_inbound_message(session, inbound)
    if result.duplicate or not result.reply_text:
        return FeishuMessageDispatchResult(
            reply_text=result.reply_text,
            duplicate=result.duplicate,
            reply_sent=False,
            reply_card=result.reply_card,
        )

    app = session.get(FeishuApp, inbound.feishu_app_id)
    if app is None:
        raise FeishuMessageAppNotFoundError
    try:
        app_secret = cipher.decrypt(app.encrypted_app_secret) or ""
        if result.reply_card is not None:
            send_feishu_card_reply(
                app.platform_type,
                app.app_id,
                app_secret,
                inbound.message_id,
                result.reply_card,
            )
        else:
            send_feishu_text_reply(
                app.platform_type,
                app.app_id,
                app_secret,
                inbound.message_id,
                result.reply_text,
            )
    except (CredentialDecryptionError, FeishuClientError, RuntimeError) as exc:
        mark_message_event_error(session, inbound, str(exc))
        raise FeishuMessageDispatchError(str(exc)) from exc

    return FeishuMessageDispatchResult(
        reply_text=result.reply_text,
        duplicate=False,
        reply_sent=True,
        reply_card=result.reply_card,
    )


def handle_feishu_card_action(
    session: Session,
    action: FeishuCardAction,
) -> FeishuMessageResult:
    if action.action_id:
        existing = session.scalar(
            select(FeishuCardActionEvent).where(
                FeishuCardActionEvent.feishu_app_id == action.feishu_app_id,
                FeishuCardActionEvent.action_event_id == action.action_id,
            )
        )
        if existing is not None:
            reply_card = (
                json.loads(existing.reply_card_json)
                if existing.reply_card_json is not None
                else None
            )
            return FeishuMessageResult(
                reply_text=existing.reply_text,
                duplicate=True,
                reply_card=reply_card,
            )

    result = execute_feishu_card_action(session, action)
    if action.action_id:
        session.add(
            FeishuCardActionEvent(
                feishu_app_id=action.feishu_app_id,
                action_event_id=action.action_id,
                operator_open_id=action.operator_open_id,
                action_name=str(action.action_value.get("action") or ""),
                raw_event_json=json.dumps(action.raw_event, ensure_ascii=False),
                reply_text=result.reply_text,
                reply_card_json=(
                    json.dumps(result.reply_card, ensure_ascii=False)
                    if result.reply_card is not None
                    else None
                ),
            )
        )
        session.flush()
    return result


def execute_feishu_card_action(
    session: Session,
    action: FeishuCardAction,
) -> FeishuMessageResult:
    try:
        value = FeishuCardActionValue.model_validate(action.action_value)
    except ValidationError:
        return FeishuMessageResult(reply_text="暂不支持该卡片操作。", duplicate=False)

    inbound = FeishuInboundMessage(
        feishu_app_id=action.feishu_app_id,
        message_id="card-action",
        chat_id="card-action",
        sender_open_id=action.operator_open_id,
        message_type="interactive",
        text="",
        raw_event=action.raw_event,
    )
    user = bound_platform_user(session, inbound)
    if user is None:
        return FeishuMessageResult(
            reply_text="请先绑定平台用户后再操作资源。可以先发送 /whoami 查看当前飞书 open_id。",
            duplicate=False,
        )

    if value.action in {"cancel"}:
        return FeishuMessageResult(
            reply_text="已取消操作。",
            duplicate=False,
            reply_card=build_home_card(user),
        )
    if value.action == "show_free_machines":
        return FeishuMessageResult(
            reply_text="空闲机器",
            duplicate=False,
            reply_card=build_free_machines_card(session),
        )
    if value.action == "show_machines":
        return FeishuMessageResult(
            reply_text="机器列表",
            duplicate=False,
            reply_card=build_machines_card(session),
        )
    if value.action == "show_my_leases":
        return FeishuMessageResult(
            reply_text="我的租约",
            duplicate=False,
            reply_card=build_my_leases_card(session, user),
        )
    if value.action == "confirm_lease" and value.resource_code:
        text = (
            f"确认占用机器 **{value.resource_code}** {value.duration_minutes} 分钟？\n"
            f"用途：{value.purpose}"
        )
        return FeishuMessageResult(
            reply_text=f"请确认占用 {value.resource_code}。",
            duplicate=False,
            reply_card=build_confirmation_card(
                action="execute_lease",
                title="确认占用",
                content=text,
                confirm_label="确认占用",
                resource_code=value.resource_code,
                duration_minutes=value.duration_minutes,
                purpose=value.purpose,
            ),
        )
    if value.action == "confirm_extend" and value.lease_id:
        return FeishuMessageResult(
            reply_text=f"请确认延期租约 {value.lease_id}。",
            duplicate=False,
            reply_card=build_confirmation_card(
                action="execute_extend",
                title="确认延期",
                content=(
                    f"确认将租约 **{value.lease_id}** 延期 "
                    f"{value.duration_minutes} 分钟？"
                ),
                confirm_label="确认延期",
                lease_id=value.lease_id,
                duration_minutes=value.duration_minutes,
            ),
        )
    if value.action == "confirm_release" and value.lease_id:
        return FeishuMessageResult(
            reply_text=f"请确认释放租约 {value.lease_id}。",
            duplicate=False,
            reply_card=build_confirmation_card(
                action="execute_release",
                title="确认释放",
                content=f"释放租约 **{value.lease_id}** 后，机器将立即回到空闲状态。",
                confirm_label="确认释放",
                danger=True,
                lease_id=value.lease_id,
            ),
        )

    command = card_action_command(value)
    if command is None:
        return FeishuMessageResult(reply_text="卡片参数不完整，请重新打开卡片。", duplicate=False)
    inbound = FeishuInboundMessage(
        feishu_app_id=action.feishu_app_id,
        message_id="card-action",
        chat_id="card-action",
        sender_open_id=action.operator_open_id,
        message_type="interactive",
        text=command,
        raw_event=action.raw_event,
    )
    if value.action == "execute_lease":
        reply_text = lease_text(session, inbound, user)
    elif value.action == "execute_extend":
        reply_text = extend_text(session, command.split(), user)
    else:
        reply_text = release_text(session, command.split(), user)
    success = "成功" in reply_text
    return FeishuMessageResult(
        reply_text=reply_text,
        duplicate=False,
        reply_card=build_operation_result_card(
            "操作成功" if success else "操作失败",
            reply_text,
            success=success,
        ),
    )


def card_action_command(value: FeishuCardActionValue) -> str | None:
    if value.action == "execute_lease" and value.resource_code:
        return (
            f"/lease {value.resource_code} {value.duration_minutes} "
            f"{value.purpose}"
        )
    if value.action == "execute_extend" and value.lease_id:
        return f"/extend {value.lease_id} {value.duration_minutes}"
    if value.action == "execute_release" and value.lease_id:
        return f"/release {value.lease_id}"
    return None


def handle_feishu_inbound_message(
    session: Session,
    inbound: FeishuInboundMessage,
) -> FeishuMessageResult:
    app = session.get(FeishuApp, inbound.feishu_app_id)
    if app is None:
        raise FeishuMessageAppNotFoundError

    existing = session.scalar(
        select(FeishuMessageEvent).where(
            FeishuMessageEvent.feishu_app_id == inbound.feishu_app_id,
            FeishuMessageEvent.message_id == inbound.message_id,
        )
    )
    if existing is not None:
        return FeishuMessageResult(reply_text=None, duplicate=True)

    reply_text, reply_card = build_reply(session, inbound)
    event = FeishuMessageEvent(
        feishu_app_id=inbound.feishu_app_id,
        message_id=inbound.message_id,
        chat_id=inbound.chat_id,
        sender_open_id=inbound.sender_open_id,
        message_type=inbound.message_type,
        raw_event_json=json.dumps(inbound.raw_event, ensure_ascii=False),
        handled_status=FeishuMessageHandledStatus.REPLIED,
        reply_text=reply_text,
    )
    session.add(event)
    session.flush()
    return FeishuMessageResult(reply_text=reply_text, duplicate=False, reply_card=reply_card)


def build_reply(session: Session, inbound: FeishuInboundMessage) -> tuple[str, dict | None]:
    command = inbound.text.strip().split(maxsplit=1)[0].lower() if inbound.text.strip() else ""
    deterministic_commands = {
        "/help",
        "/whoami",
        "/bind",
        "/machines",
        "/lease",
        "/my-leases",
        "/release",
        "/extend",
    }
    if command in deterministic_commands:
        return build_reply_text(session, inbound), build_reply_card(session, inbound)

    user = bound_platform_user(session, inbound)
    if user is None:
        return (
            "请先绑定平台用户后再使用资源助手。可以先发送 /whoami 查看当前飞书 open_id。",
            None,
        )
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        return (
            "LLM 资源助手尚未配置，确定性快捷命令仍可正常使用。\n\n" + help_text(),
            build_home_card(user),
        )
    try:
        result = run_assistant_message(
            session=session,
            user=user,
            text=inbound.text.strip(),
            client=create_llm_client(settings),
        )
    except (AssistantError, LlmClientError):
        return "LLM 资源助手暂时不可用，请稍后重试；确定性快捷命令仍可正常使用。", None

    for tool_result in reversed(result.tool_results):
        if tool_result.name != "search_machines":
            continue
        machines = tool_result.data.get("machines")
        if not isinstance(machines, list):
            continue
        resource_codes = {
            str(machine.get("resource_code"))
            for machine in machines
            if isinstance(machine, dict) and machine.get("resource_code")
        }
        return (
            result.text,
            build_machines_card(
                session,
                resource_codes=resource_codes,
                title="智能匹配结果",
            ),
        )
    return result.text, None


def mark_message_event_error(session: Session, inbound: FeishuInboundMessage, error: str) -> None:
    event = session.scalar(
        select(FeishuMessageEvent).where(
            FeishuMessageEvent.feishu_app_id == inbound.feishu_app_id,
            FeishuMessageEvent.message_id == inbound.message_id,
        )
    )
    if event is None:
        return
    event.handled_status = FeishuMessageHandledStatus.ERROR
    event.reply_text = error
    session.flush()


def build_reply_text(session: Session, inbound: FeishuInboundMessage) -> str:
    text = inbound.text.strip()
    parts = text.split()
    command = text.split(maxsplit=1)[0].lower() if text else ""
    if command == "/help":
        return help_text()
    if command == "/whoami":
        return whoami_text(session, inbound)
    if command == "/bind":
        return bind_text(session, inbound, parts)
    if command in {"/machines", "/lease", "/my-leases", "/release", "/extend"}:
        user = bound_platform_user(session, inbound)
        if user is None:
            return "请先绑定平台用户后再操作资源。可以先发送 /whoami 查看当前飞书 open_id。"
        if command == "/machines":
            return machines_text(session, only_free=len(parts) > 1 and parts[1].lower() == "free")
        if command == "/lease":
            return lease_text(session, inbound, user)
        if command == "/my-leases":
            return my_leases_text(session, user)
        if command == "/release":
            return release_text(session, parts, user)
        if command == "/extend":
            return extend_text(session, parts, user)

    user = bound_platform_user(session, inbound)
    if user is None:
        return "请先绑定平台用户后再使用资源助手。可以先发送 /whoami 查看当前飞书 open_id。"
    return "无法识别该快捷命令。"


def build_reply_card(session: Session, inbound: FeishuInboundMessage) -> dict | None:
    parts = inbound.text.strip().split()
    command = parts[0].lower() if parts else ""
    user = bound_platform_user(session, inbound)
    if command == "/help":
        return build_home_card(user)
    if user is None:
        return None
    if command == "/machines":
        return build_machines_card(
            session,
            only_free=len(parts) > 1 and parts[1].lower() == "free",
        )
    if command == "/my-leases":
        return build_my_leases_card(session, user)
    return None


def help_text() -> str:
    return "\n".join(
        [
            "测试资源平台可用命令：",
            "/help - 查看帮助",
            "/whoami - 查看当前飞书身份和平台绑定状态",
            "/machines - 查看机器列表",
            "/machines free - 查看空闲机器",
            "/lease <resource_code> <minutes> <purpose> - 占用机器",
            "/my-leases - 查看我的租约",
            "/release <lease_id> - 释放租约",
            "/extend <lease_id> <minutes> - 延期租约",
        ]
    )


def whoami_text(session: Session, inbound: FeishuInboundMessage) -> str:
    binding = session.scalar(
        select(FeishuUserBinding).where(
            FeishuUserBinding.feishu_app_id == inbound.feishu_app_id,
            FeishuUserBinding.open_id == inbound.sender_open_id,
        )
    )
    lines = [
        "当前飞书身份：",
        f"open_id: {inbound.sender_open_id}",
    ]
    if binding is None:
        lines.append("平台绑定：未绑定")
        return "\n".join(lines)

    user = binding.platform_user
    lines.append(f"平台绑定：{user.username} ({user.role})")
    if binding.display_name:
        lines.append(f"飞书名称：{binding.display_name}")
    return "\n".join(lines)


def bound_platform_user(session: Session, inbound: FeishuInboundMessage):
    binding = session.scalar(
        select(FeishuUserBinding).where(
            FeishuUserBinding.feishu_app_id == inbound.feishu_app_id,
            FeishuUserBinding.open_id == inbound.sender_open_id,
        )
    )
    if binding is None:
        return None
    return binding.platform_user


def bind_text(session: Session, inbound: FeishuInboundMessage, parts: list[str]) -> str:
    if len(parts) != 2:
        return "格式错误：/bind <code>"
    code = parts[1].strip().upper()
    binding_code = session.scalar(
        select(FeishuBindingCode).where(
            FeishuBindingCode.code == code,
            FeishuBindingCode.consumed_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    if binding_code is None or is_expired(binding_code.expires_at, now):
        return "绑定失败：绑定码不存在、已使用或已过期。请在 Web 平台重新生成绑定码。"

    binding = session.scalar(
        select(FeishuUserBinding).where(
            FeishuUserBinding.feishu_app_id == inbound.feishu_app_id,
            FeishuUserBinding.open_id == inbound.sender_open_id,
        )
    )
    if binding is None:
        binding = FeishuUserBinding(
            feishu_app_id=inbound.feishu_app_id,
            platform_user_id=binding_code.platform_user_id,
            open_id=inbound.sender_open_id,
        )
        session.add(binding)
    else:
        binding.platform_user_id = binding_code.platform_user_id
    binding_code.consumed_at = now
    session.flush()
    return f"绑定成功：当前飞书身份已绑定到平台用户 {binding.platform_user.username}。"


def is_expired(expires_at: datetime, now: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= now


def machines_text(session: Session, only_free: bool) -> str:
    occupancy = list_active_machine_occupancy(session)
    rows = []
    for machine in list_machine_resources(session):
        pool = session.get(ResourcePool, machine.pool_id)
        is_available = (
            pool is not None
            and pool.is_active
            and machine.admin_status == ResourceAdminStatus.ACTIVE
            and machine.id not in occupancy
        )
        if only_free and not is_available:
            continue
        rows.append(format_machine_row(machine, occupancy, is_available))

    if not rows:
        return "暂无空闲机器。" if only_free else "暂无机器资源。"
    title = "空闲机器：" if only_free else "机器列表："
    return title + "\n" + "\n".join(rows[:20])


def format_machine_row(
    machine: MachineResource,
    occupancy: dict[int, tuple[str, str]],
    is_available: bool,
) -> str:
    if machine.id in occupancy:
        username, lease_id = occupancy[machine.id]
        status = f"已占用 by {username} ({lease_id})"
    elif is_available:
        status = "空闲"
    else:
        status = f"不可用 ({machine.admin_status})"
    return f"- {machine.resource_code} | {machine.name} | {machine.resource_type} | {status}"


def lease_text(session: Session, inbound: FeishuInboundMessage, user) -> str:
    parts = inbound.text.split(maxsplit=3)
    if len(parts) < 4:
        return "格式错误：/lease <resource_code> <minutes> <purpose>"
    resource_code = parts[1]
    try:
        duration_minutes = int(parts[2])
    except ValueError:
        return "格式错误：minutes 必须是数字。"
    purpose = parts[3].strip()
    try:
        lease = create_resource_lease(
            session,
            ResourceLeaseCreateRequest(
                resource_code=resource_code,
                duration_minutes=duration_minutes,
                purpose=purpose,
            ),
            user,
        )
    except MachineNotFoundError:
        return f"占用失败：机器 {resource_code} 不存在。"
    except ResourcePoolDisabledError:
        return f"占用失败：机器 {resource_code} 所属资源池已停用。"
    except MachineNotAvailableError:
        return f"占用失败：机器 {resource_code} 当前不可用。"
    except ResourceAlreadyLeasedError:
        return f"占用失败：机器 {resource_code} 已被占用。"
    return "\n".join(
        [
            "占用成功。",
            f"机器：{lease.machine.resource_code} {lease.machine.name}",
            f"租约：{lease.lease_id}",
            f"到期时间：{lease.expires_at}",
        ]
    )


def my_leases_text(session: Session, user) -> str:
    leases = list_user_leases(session, user)
    if not leases:
        return "你当前没有租约。"
    lines = ["我的租约："]
    for lease in leases[:20]:
        lines.append(format_lease_row(lease))
    return "\n".join(lines)


def format_lease_row(lease) -> str:
    return (
        f"- {lease.lease_id} | {lease.machine.resource_code} | "
        f"{lease.status} | 到期 {lease.expires_at}"
    )


def release_text(session: Session, parts: list[str], user) -> str:
    if len(parts) != 2:
        return "格式错误：/release <lease_id>"
    lease_id = parts[1]
    try:
        lease = release_resource_lease(session, lease_id, user)
    except LeaseNotFoundError:
        return f"释放失败：租约 {lease_id} 不存在。"
    except LeaseNotOwnedError:
        return f"释放失败：租约 {lease_id} 不属于你。"
    except LeaseNotActiveError:
        return f"释放失败：租约 {lease_id} 不是有效租约。"
    return f"释放成功：{lease.lease_id}，机器 {lease.machine.resource_code}。"


def extend_text(session: Session, parts: list[str], user) -> str:
    if len(parts) != 3:
        return "格式错误：/extend <lease_id> <minutes>"
    lease_id = parts[1]
    try:
        duration_minutes = int(parts[2])
    except ValueError:
        return "格式错误：minutes 必须是数字。"
    try:
        lease = extend_resource_lease(
            session,
            lease_id,
            user,
            ResourceLeaseExtendRequest(duration_minutes=duration_minutes),
        )
    except LeaseNotFoundError:
        return f"延期失败：租约 {lease_id} 不存在。"
    except LeaseNotOwnedError:
        return f"延期失败：租约 {lease_id} 不属于你。"
    except LeaseNotActiveError:
        return f"延期失败：租约 {lease_id} 不是有效租约。"
    return f"延期成功：{lease.lease_id}，新到期时间 {lease.expires_at}。"
