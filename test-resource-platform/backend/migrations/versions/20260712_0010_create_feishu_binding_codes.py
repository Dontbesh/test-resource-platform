"""create feishu binding codes

Revision ID: 20260712_0010
Revises: 20260711_0009
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260712_0010"
down_revision: str | None = "20260711_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feishu_binding_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("platform_user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["platform_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_feishu_binding_codes_code"),
        "feishu_binding_codes",
        ["code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_feishu_binding_codes_platform_user_id"),
        "feishu_binding_codes",
        ["platform_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_feishu_binding_codes_platform_user_id"),
        table_name="feishu_binding_codes",
    )
    op.drop_index(op.f("ix_feishu_binding_codes_code"), table_name="feishu_binding_codes")
    op.drop_table("feishu_binding_codes")
