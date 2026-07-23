import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant.llm import LlmClientError, create_llm_client
from app.assistant.service import AssistantError, handle_assistant_message
from app.core.config import get_settings
from app.credentials.crypto import CredentialCipher, CredentialDecryptionError
from app.integrations.feishu.cards import build_free_machines_card
from app.integrations.feishu.client import (
    FeishuClientError,
    send_feishu_card_reply,
    send_feishu_text_reply,
)
from app.integrations.feishu.models import (
    FeishuApp,
    FeishuBindingCode,
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
    action_name = str(action.action_value.get("action") or "")
    if action_name != "lease":
        return FeishuMessageResult(reply_text="暂不支持该卡片操作。", duplicate=False)

    resource_code = str(action.action_value.get("resource_code") or "")
    duration_minutes = int(action.action_value.get("duration_minutes") or 60)
    purpose = str(action.action_value.get("purpose") or "feishu-card")
    inbound = FeishuInboundMessage(
        feishu_app_id=action.feishu_app_id,
        message_id="card-action",
        chat_id="card-action",
        sender_open_id=action.operator_open_id,
        message_type="interactive",
        text=f"/lease {resource_code} {duration_minutes} {purpose}",
        raw_event=action.raw_event,
    )
    user = bound_platform_user(session, inbound)
    if user is None:
        return FeishuMessageResult(
            reply_text="请先绑定平台用户后再操作资源。可以先发送 /whoami 查看当前飞书 open_id。",
            duplicate=False,
        )
    return FeishuMessageResult(reply_text=lease_text(session, inbound, user), duplicate=False)


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

    reply_text = build_reply_text(session, inbound)
    reply_card = build_reply_card(session, inbound)
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
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        return "LLM 资源助手尚未配置，确定性快捷命令仍可正常使用。\n\n" + help_text()
    try:
        return handle_assistant_message(
            session=session,
            user=user,
            text=text,
            client=create_llm_client(settings),
        )
    except (AssistantError, LlmClientError):
        return "LLM 资源助手暂时不可用，请稍后重试；确定性快捷命令仍可正常使用。"


def build_reply_card(session: Session, inbound: FeishuInboundMessage) -> dict | None:
    parts = inbound.text.strip().split()
    if len(parts) > 1 and parts[0].lower() == "/machines" and parts[1].lower() == "free":
        if bound_platform_user(session, inbound) is None:
            return None
        return build_free_machines_card(session)
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
