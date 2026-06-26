"""create resource inventory

Revision ID: 20260626_0002
Revises: 20260625_0001
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0002"
down_revision: str | None = "20260625_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resource_pools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.Column("network_zone", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resource_pools_name"), "resource_pools", ["name"], unique=True)

    op.create_table(
        "machine_resources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("resource_code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "resource_type",
            sa.Enum("PHYSICAL", "VIRTUAL", name="resourcetype"),
            nullable=False,
        ),
        sa.Column("pool_id", sa.Integer(), nullable=False),
        sa.Column("host_machine_id", sa.Integer(), nullable=True),
        sa.Column(
            "admin_status",
            sa.Enum("ACTIVE", "MAINTENANCE", "DISABLED", name="resourceadminstatus"),
            nullable=False,
        ),
        sa.Column(
            "connectivity_status",
            sa.Enum("UNKNOWN", "REACHABLE", "UNREACHABLE", name="connectivitystatus"),
            nullable=False,
        ),
        sa.Column("is_critical", sa.Boolean(), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=True),
        sa.Column("architecture", sa.String(length=64), nullable=True),
        sa.Column("os_name", sa.String(length=128), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("mac_address", sa.String(length=64), nullable=True),
        sa.Column("bmc_address", sa.String(length=128), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["host_machine_id"], ["machine_resources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pool_id"], ["resource_pools.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_machine_resources_resource_code"),
        "machine_resources",
        ["resource_code"],
        unique=True,
    )
    op.create_index(op.f("ix_machine_resources_name"), "machine_resources", ["name"], unique=False)
    op.create_index(
        op.f("ix_machine_resources_pool_id"),
        "machine_resources",
        ["pool_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_machine_resources_pool_id"), table_name="machine_resources")
    op.drop_index(op.f("ix_machine_resources_name"), table_name="machine_resources")
    op.drop_index(op.f("ix_machine_resources_resource_code"), table_name="machine_resources")
    op.drop_table("machine_resources")
    op.drop_index(op.f("ix_resource_pools_name"), table_name="resource_pools")
    op.drop_table("resource_pools")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS connectivitystatus")
        op.execute("DROP TYPE IF EXISTS resourceadminstatus")
        op.execute("DROP TYPE IF EXISTS resourcetype")
