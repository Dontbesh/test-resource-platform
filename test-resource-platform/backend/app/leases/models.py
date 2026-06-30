from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.identity.models import User
from app.resources.models import MachineResource


class LeaseStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class LeaseEventType(StrEnum):
    CREATED = "CREATED"
    EXTENDED = "EXTENDED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"
    FORCE_RELEASED = "FORCE_RELEASED"


class ResourceLease(Base):
    __tablename__ = "resource_leases"
    __table_args__ = (
        Index(
            "uq_resource_leases_active_machine",
            "machine_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lease_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machine_resources.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeaseStatus] = mapped_column(
        Enum(LeaseStatus),
        nullable=False,
        default=LeaseStatus.ACTIVE,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    machine: Mapped[MachineResource] = relationship(MachineResource)
    user: Mapped[User] = relationship(User)


class ResourceLeaseEvent(Base):
    __tablename__ = "resource_lease_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lease_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_lease_id: Mapped[int] = mapped_column(
        ForeignKey("resource_leases.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machine_resources.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    target_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    event_type: Mapped[LeaseEventType] = mapped_column(
        Enum(LeaseEventType),
        nullable=False,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    new_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    resource_lease: Mapped[ResourceLease] = relationship(ResourceLease)
    machine: Mapped[MachineResource] = relationship(MachineResource)
    actor_user: Mapped[User] = relationship(User, foreign_keys=[actor_user_id])
    target_user: Mapped[User] = relationship(User, foreign_keys=[target_user_id])
