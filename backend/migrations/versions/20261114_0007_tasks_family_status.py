"""tasks_family_status

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_tasks_family_id_status", "tasks", ["family_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tasks_family_id_status", table_name="tasks")
