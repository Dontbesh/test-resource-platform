"""widen feishu setup device code

Revision ID: 20260711_0008
Revises: 20260710_0007
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260711_0008"
down_revision: str | None = "20260710_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "feishu_setup_sessions",
            "device_code",
            existing_type=sa.String(length=256),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "feishu_setup_sessions",
            "device_code",
            existing_type=sa.Text(),
            type_=sa.String(length=256),
            existing_nullable=False,
        )
