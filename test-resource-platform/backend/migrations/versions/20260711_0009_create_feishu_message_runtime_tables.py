"""create feishu message runtime tables

Revision ID: 20260711_0009
Revises: 20260711_0008
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260711_0009"
down_revision: str | None = "20260711_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feishu_user_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feishu_app_id", sa.Integer(), nullable=False),
        sa.Column("platform_user_id", sa.Integer(), nullable=False),
        sa.Column("open_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feishu_app_id"], ["feishu_apps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["platform_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "feishu_app_id",
            "open_id",
            name="uq_feishu_user_bindings_app_open_id",
        ),
    )
    op.create_index(
        op.f("ix_feishu_user_bindings_feishu_app_id"),
        "feishu_user_bindings",
        ["feishu_app_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feishu_user_bindings_open_id"),
        "feishu_user_bindings",
        ["open_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feishu_user_bindings_platform_user_id"),
        "feishu_user_bindings",
        ["platform_user_id"],
        unique=False,
    )

    op.create_table(
        "feishu_message_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feishu_app_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("chat_id", sa.String(length=128), nullable=False),
        sa.Column("sender_open_id", sa.String(length=128), nullable=False),
        sa.Column("message_type", sa.String(length=64), nullable=False),
        sa.Column("raw_event_json", sa.Text(), nullable=False),
        sa.Column(
            "handled_status",
            sa.Enum("REPLIED", "IGNORED", "ERROR", name="feishumessagehandledstatus"),
            nullable=False,
        ),
        sa.Column("reply_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feishu_app_id"], ["feishu_apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "feishu_app_id",
            "message_id",
            name="uq_feishu_message_events_app_message",
        ),
    )
    op.create_index(
        op.f("ix_feishu_message_events_chat_id"),
        "feishu_message_events",
        ["chat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feishu_message_events_feishu_app_id"),
        "feishu_message_events",
        ["feishu_app_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feishu_message_events_sender_open_id"),
        "feishu_message_events",
        ["sender_open_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_feishu_message_events_sender_open_id"),
        table_name="feishu_message_events",
    )
    op.drop_index(
        op.f("ix_feishu_message_events_feishu_app_id"),
        table_name="feishu_message_events",
    )
    op.drop_index(op.f("ix_feishu_message_events_chat_id"), table_name="feishu_message_events")
    op.drop_table("feishu_message_events")
    op.drop_index(
        op.f("ix_feishu_user_bindings_platform_user_id"),
        table_name="feishu_user_bindings",
    )
    op.drop_index(op.f("ix_feishu_user_bindings_open_id"), table_name="feishu_user_bindings")
    op.drop_index(
        op.f("ix_feishu_user_bindings_feishu_app_id"),
        table_name="feishu_user_bindings",
    )
    op.drop_table("feishu_user_bindings")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS feishumessagehandledstatus")
