from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.identity.models import User


class FeishuPlatformType(StrEnum):
    FEISHU = "FEISHU"
    LARK = "LARK"


class FeishuSetupStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"


class FeishuAppStatus(StrEnum):
    CONFIGURED = "CONFIGURED"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class FeishuMessageHandledStatus(StrEnum):
    REPLIED = "REPLIED"
    IGNORED = "IGNORED"
    ERROR = "ERROR"


class FeishuSetupSession(Base):
    __tablename__ = "feishu_setup_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_code: Mapped[str] = mapped_column(Text, unique=True, index=True, nullable=False)
    qr_url: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[FeishuSetupStatus] = mapped_column(
        Enum(FeishuSetupStatus),
        nullable=False,
        default=FeishuSetupStatus.PENDING,
    )
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    created_by: Mapped[User] = relationship()


class FeishuApp(Base):
    __tablename__ = "feishu_apps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    platform_type: Mapped[FeishuPlatformType] = mapped_column(
        Enum(FeishuPlatformType),
        nullable=False,
    )
    app_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    encrypted_app_secret: Mapped[str] = mapped_column(Text, nullable=False)
    owner_open_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tenant_brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bot_open_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[FeishuAppStatus] = mapped_column(
        Enum(FeishuAppStatus),
        nullable=False,
        default=FeishuAppStatus.CONFIGURED,
    )
    last_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    created_by: Mapped[User] = relationship()


class FeishuUserBinding(Base):
    __tablename__ = "feishu_user_bindings"
    __table_args__ = (
        UniqueConstraint("feishu_app_id", "open_id", name="uq_feishu_user_bindings_app_open_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feishu_app_id: Mapped[int] = mapped_column(
        ForeignKey("feishu_apps.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    platform_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    open_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    feishu_app: Mapped[FeishuApp] = relationship()
    platform_user: Mapped[User] = relationship()


class FeishuBindingCode(Base):
    __tablename__ = "feishu_binding_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    platform_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC) + timedelta(minutes=10),
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    platform_user: Mapped[User] = relationship()


class FeishuMessageEvent(Base):
    __tablename__ = "feishu_message_events"
    __table_args__ = (
        UniqueConstraint(
            "feishu_app_id",
            "message_id",
            name="uq_feishu_message_events_app_message",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feishu_app_id: Mapped[int] = mapped_column(
        ForeignKey("feishu_apps.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    sender_open_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    message_type: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_event_json: Mapped[str] = mapped_column(Text, nullable=False)
    handled_status: Mapped[FeishuMessageHandledStatus] = mapped_column(
        Enum(FeishuMessageHandledStatus),
        nullable=False,
    )
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    feishu_app: Mapped[FeishuApp] = relationship()


class FeishuCardActionEvent(Base):
    __tablename__ = "feishu_card_action_events"
    __table_args__ = (
        UniqueConstraint(
            "feishu_app_id",
            "action_event_id",
            name="uq_feishu_card_action_events_app_event",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feishu_app_id: Mapped[int] = mapped_column(
        ForeignKey("feishu_apps.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    operator_open_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    action_name: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_event_json: Mapped[str] = mapped_column(Text, nullable=False)
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_card_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    feishu_app: Mapped[FeishuApp] = relationship()
