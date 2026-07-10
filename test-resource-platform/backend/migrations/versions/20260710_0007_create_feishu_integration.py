"""create feishu integration tables

Revision ID: 20260710_0007
Revises: 20260630_0006
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_0007"
down_revision: str | None = "20260630_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feishu_setup_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_code", sa.String(length=256), nullable=False),
        sa.Column("qr_url", sa.Text(), nullable=False),
        sa.Column("base_url", sa.String(length=256), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "COMPLETED", "DENIED", "EXPIRED", "ERROR", name="feishusetupstatus"),
            nullable=False,
        ),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_feishu_setup_sessions_created_by_user_id"),
        "feishu_setup_sessions",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feishu_setup_sessions_device_code"),
        "feishu_setup_sessions",
        ["device_code"],
        unique=True,
    )

    op.create_table(
        "feishu_apps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "platform_type",
            sa.Enum("FEISHU", "LARK", name="feishuplatformtype"),
            nullable=False,
        ),
        sa.Column("app_id", sa.String(length=128), nullable=False),
        sa.Column("encrypted_app_secret", sa.Text(), nullable=False),
        sa.Column("owner_open_id", sa.String(length=128), nullable=True),
        sa.Column("tenant_brand", sa.String(length=64), nullable=True),
        sa.Column("bot_open_id", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "CONFIGURED",
                "CONNECTED",
                "DISCONNECTED",
                "ERROR",
                name="feishuappstatus",
            ),
            nullable=False,
        ),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_feishu_apps_app_id"),
        "feishu_apps",
        ["app_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_feishu_apps_created_by_user_id"),
        "feishu_apps",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_feishu_apps_created_by_user_id"), table_name="feishu_apps")
    op.drop_index(op.f("ix_feishu_apps_app_id"), table_name="feishu_apps")
    op.drop_table("feishu_apps")
    op.drop_index(
        op.f("ix_feishu_setup_sessions_device_code"),
        table_name="feishu_setup_sessions",
    )
    op.drop_index(
        op.f("ix_feishu_setup_sessions_created_by_user_id"),
        table_name="feishu_setup_sessions",
    )
    op.drop_table("feishu_setup_sessions")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS feishuappstatus")
        op.execute("DROP TYPE IF EXISTS feishuplatformtype")
        op.execute("DROP TYPE IF EXISTS feishusetupstatus")
