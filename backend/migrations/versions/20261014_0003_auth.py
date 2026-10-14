"""auth

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "adult",
                "child",
                name="token_role",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("child_session_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["child_session_id"],
            ["child_sessions.id"],
            name=op.f("fk_refresh_tokens_child_session_id_child_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name=op.f("fk_refresh_tokens_family_id_families"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_refresh_tokens_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_refresh_tokens_child_session_id"),
        "refresh_tokens",
        ["child_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_tokens_member_id"), "refresh_tokens", ["member_id"], unique=False
    )
    op.add_column(
        "users", sa.Column("failed_logins", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "users", sa.Column("login_locked_until", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "login_locked_until")
    op.drop_column("users", "failed_logins")
    op.drop_index(op.f("ix_refresh_tokens_member_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_child_session_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
