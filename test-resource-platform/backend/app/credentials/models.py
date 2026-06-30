from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.identity.models import User
from app.resources.models import MachineResource


class MachineCredential(Base):
    __tablename__ = "machine_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(
        ForeignKey("machine_resources.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
        nullable=False,
    )
    ssh_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    encrypted_ssh_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    bmc_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    encrypted_bmc_password: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class CredentialAccessEvent(Base):
    __tablename__ = "credential_access_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    access_type: Mapped[str] = mapped_column(String(32), nullable=False, default="VIEW")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    machine: Mapped[MachineResource] = relationship(MachineResource)
    user: Mapped[User] = relationship(User)
