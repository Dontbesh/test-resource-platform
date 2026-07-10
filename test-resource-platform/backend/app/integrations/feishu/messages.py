import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.feishu.models import (
    FeishuApp,
    FeishuMessageEvent,
    FeishuMessageHandledStatus,
    FeishuUserBinding,
)


class FeishuMessageAppNotFoundError(Exception):
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
class FeishuMessageResult:
    reply_text: str | None
    duplicate: bool


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
    return FeishuMessageResult(reply_text=reply_text, duplicate=False)


def build_reply_text(session: Session, inbound: FeishuInboundMessage) -> str:
    text = inbound.text.strip()
    command = text.split(maxsplit=1)[0].lower() if text else ""
    if command == "/help":
        return help_text()
    if command == "/whoami":
        return whoami_text(session, inbound)
    return "暂时只支持确定性快捷命令。\n\n" + help_text()


def help_text() -> str:
    return "\n".join(
        [
            "测试资源平台可用命令：",
            "/help - 查看帮助",
            "/whoami - 查看当前飞书身份和平台绑定状态",
            "/machines - 查看机器列表（开发中）",
            "/machines free - 查看空闲机器（开发中）",
            "/lease <resource_code> <minutes> <purpose> - 占用机器（开发中）",
            "/my-leases - 查看我的租约（开发中）",
            "/release <lease_id> - 释放租约（开发中）",
            "/extend <lease_id> <minutes> - 延期租约（开发中）",
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
