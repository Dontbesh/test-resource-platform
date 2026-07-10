from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
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
