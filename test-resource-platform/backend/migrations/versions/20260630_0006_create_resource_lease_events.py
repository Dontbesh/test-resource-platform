"""create resource lease events

Revision ID: 20260630_0006
Revises: 20260630_0005
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260630_0006"
down_revision: str | None = "20260630_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resource_lease_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lease_id", sa.String(length=64), nullable=False),
        sa.Column("resource_lease_id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "CREATED",
                "EXTENDED",
                "RELEASED",
                "EXPIRED",
                "FORCE_RELEASED",
                name="leaseeventtype",
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["machine_id"], ["machine_resources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resource_lease_id"], ["resource_leases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_resource_lease_events_actor_user_id"),
        "resource_lease_events",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_lease_events_event_type"),
        "resource_lease_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_lease_events_lease_id"),
        "resource_lease_events",
        ["lease_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_lease_events_machine_id"),
        "resource_lease_events",
        ["machine_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_lease_events_resource_lease_id"),
        "resource_lease_events",
        ["resource_lease_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_lease_events_target_user_id"),
        "resource_lease_events",
        ["target_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_resource_lease_events_target_user_id"),
        table_name="resource_lease_events",
    )
    op.drop_index(
        op.f("ix_resource_lease_events_resource_lease_id"),
        table_name="resource_lease_events",
    )
    op.drop_index(op.f("ix_resource_lease_events_machine_id"), table_name="resource_lease_events")
    op.drop_index(op.f("ix_resource_lease_events_lease_id"), table_name="resource_lease_events")
    op.drop_index(op.f("ix_resource_lease_events_event_type"), table_name="resource_lease_events")
    op.drop_index(
        op.f("ix_resource_lease_events_actor_user_id"),
        table_name="resource_lease_events",
    )
    op.drop_table("resource_lease_events")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS leaseeventtype")
