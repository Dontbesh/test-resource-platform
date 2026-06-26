"""create resource leases

Revision ID: 20260626_0004
Revises: 20260626_0003
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0004"
down_revision: str | None = "20260626_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resource_leases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lease_id", sa.String(length=64), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "RELEASED", "EXPIRED", name="leasestatus"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machine_resources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_resource_leases_lease_id"),
        "resource_leases",
        ["lease_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_resource_leases_machine_id"),
        "resource_leases",
        ["machine_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_leases_status"),
        "resource_leases",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_leases_user_id"),
        "resource_leases",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "uq_resource_leases_active_machine",
        "resource_leases",
        ["machine_id"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE'"),
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_resource_leases_active_machine", table_name="resource_leases")
    op.drop_index(op.f("ix_resource_leases_user_id"), table_name="resource_leases")
    op.drop_index(op.f("ix_resource_leases_status"), table_name="resource_leases")
    op.drop_index(op.f("ix_resource_leases_machine_id"), table_name="resource_leases")
    op.drop_index(op.f("ix_resource_leases_lease_id"), table_name="resource_leases")
    op.drop_table("resource_leases")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS leasestatus")
