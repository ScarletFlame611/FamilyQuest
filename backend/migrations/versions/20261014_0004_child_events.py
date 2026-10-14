"""child_events

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "child_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_session_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "screen_opened",
                "task_opened",
                "button_pressed",
                "task_taken",
                "task_marked",
                "reward_bought",
                "wrong_pin",
                "pin_locked",
                "pin_exit",
                "password_exit",
                name="child_event_type",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("detail", sa.String(length=200), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["child_session_id"],
            ["child_sessions.id"],
            name=op.f("fk_child_events_child_session_id_child_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_child_events")),
    )
    op.create_index(
        op.f("ix_child_events_child_session_id"), "child_events", ["child_session_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_child_events_child_session_id"), table_name="child_events")
    op.drop_table("child_events")
