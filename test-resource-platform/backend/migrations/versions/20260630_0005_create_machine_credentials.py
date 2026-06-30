"""create machine credentials

Revision ID: 20260630_0005
Revises: 20260626_0004
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260630_0005"
down_revision: str | None = "20260626_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "machine_credentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("ssh_username", sa.String(length=128), nullable=True),
        sa.Column("encrypted_ssh_password", sa.Text(), nullable=True),
        sa.Column("bmc_username", sa.String(length=128), nullable=True),
        sa.Column("encrypted_bmc_password", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machine_resources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_machine_credentials_machine_id"),
        "machine_credentials",
        ["machine_id"],
        unique=True,
    )

    op.create_table(
        "credential_access_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machine_resources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_credential_access_events_machine_id"),
        "credential_access_events",
        ["machine_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_credential_access_events_user_id"),
        "credential_access_events",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_credential_access_events_user_id"),
        table_name="credential_access_events",
    )
    op.drop_index(
        op.f("ix_credential_access_events_machine_id"),
        table_name="credential_access_events",
    )
    op.drop_table("credential_access_events")
    op.drop_index(op.f("ix_machine_credentials_machine_id"), table_name="machine_credentials")
    op.drop_table("machine_credentials")
