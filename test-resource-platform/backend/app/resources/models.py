from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResourceType(StrEnum):
    PHYSICAL = "PHYSICAL"
    VIRTUAL = "VIRTUAL"


class ResourceAdminStatus(StrEnum):
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    DISABLED = "DISABLED"


class ConnectivityStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    REACHABLE = "REACHABLE"
    UNREACHABLE = "UNREACHABLE"


class ResourcePool(Base):
    __tablename__ = "resource_pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    network_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
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


class MachineResource(Base):
    __tablename__ = "machine_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_code: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    resource_type: Mapped[ResourceType] = mapped_column(Enum(ResourceType), nullable=False)
    pool_id: Mapped[int] = mapped_column(
        ForeignKey("resource_pools.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    host_machine_id: Mapped[int | None] = mapped_column(
        ForeignKey("machine_resources.id", ondelete="SET NULL"),
        nullable=True,
    )
    admin_status: Mapped[ResourceAdminStatus] = mapped_column(
        Enum(ResourceAdminStatus),
        nullable=False,
        default=ResourceAdminStatus.ACTIVE,
    )
    connectivity_status: Mapped[ConnectivityStatus] = mapped_column(
        Enum(ConnectivityStatus),
        nullable=False,
        default=ConnectivityStatus.UNKNOWN,
    )
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    architecture: Mapped[str | None] = mapped_column(String(64), nullable=True)
    os_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bmc_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
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
