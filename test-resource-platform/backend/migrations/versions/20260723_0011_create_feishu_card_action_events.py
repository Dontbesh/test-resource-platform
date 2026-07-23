"""create feishu card action events

Revision ID: 20260723_0011
Revises: 20260712_0010
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0011"
down_revision: str | None = "20260712_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feishu_card_action_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feishu_app_id", sa.Integer(), nullable=False),
        sa.Column("action_event_id", sa.String(length=128), nullable=False),
        sa.Column("operator_open_id", sa.String(length=128), nullable=False),
        sa.Column("action_name", sa.String(length=64), nullable=False),
        sa.Column("raw_event_json", sa.Text(), nullable=False),
        sa.Column("reply_text", sa.Text(), nullable=True),
        sa.Column("reply_card_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feishu_app_id"], ["feishu_apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "feishu_app_id",
            "action_event_id",
            name="uq_feishu_card_action_events_app_event",
        ),
    )
    op.create_index(
        op.f("ix_feishu_card_action_events_feishu_app_id"),
        "feishu_card_action_events",
        ["feishu_app_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feishu_card_action_events_operator_open_id"),
        "feishu_card_action_events",
        ["operator_open_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_feishu_card_action_events_operator_open_id"),
        table_name="feishu_card_action_events",
    )
    op.drop_index(
        op.f("ix_feishu_card_action_events_feishu_app_id"),
        table_name="feishu_card_action_events",
    )
    op.drop_table("feishu_card_action_events")
