"""add resource pool active flag

Revision ID: 20260626_0003
Revises: 20260626_0002
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0003"
down_revision: str | None = "20260626_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "resource_pools",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("resource_pools", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("resource_pools", "is_active")
