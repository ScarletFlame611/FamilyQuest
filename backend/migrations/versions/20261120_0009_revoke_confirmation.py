"""revoke_confirmation

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "families",
        sa.Column("revoke_window_days", sa.Integer(), server_default="7", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_families_revoke_window_positive"), "families", "revoke_window_days > 0"
    )

    op.add_column("tasks", sa.Column("attempt", sa.Integer(), server_default="0", nullable=False))

    op.add_column("ledger_entries", sa.Column("task_attempt", sa.Integer(), nullable=True))
    op.add_column("ledger_entries", sa.Column("reverses_entry_id", sa.Uuid(), nullable=True))
    op.add_column("ledger_entries", sa.Column("created_by_member_id", sa.Uuid(), nullable=True))
    # Все прежние записи по задачам относятся к первому выполнению; без этого
    # проверка ниже не применится, а уникальность начисления перестанет работать
    op.execute("UPDATE ledger_entries SET task_attempt = 0 WHERE task_id IS NOT NULL")
    op.create_check_constraint(
        op.f("ck_ledger_entries_task_attempt_with_task"),
        "ledger_entries",
        "(task_id IS NULL) = (task_attempt IS NULL)",
    )
    op.drop_index("uq_ledger_entries_accrual_task", table_name="ledger_entries")
    op.create_index(
        "uq_ledger_entries_accrual_task",
        "ledger_entries",
        ["task_id", "task_attempt"],
        unique=True,
        postgresql_where=sa.text("kind = 'accrual'"),
    )
    op.create_index(
        "uq_ledger_entries_reverses",
        "ledger_entries",
        ["reverses_entry_id"],
        unique=True,
        postgresql_where=sa.text("reverses_entry_id IS NOT NULL"),
    )
    op.create_foreign_key(
        op.f("fk_ledger_entries_reverses_entry_id_ledger_entries"),
        "ledger_entries",
        "ledger_entries",
        ["reverses_entry_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_ledger_entries_created_by_member_id_members"),
        "ledger_entries",
        "members",
        ["created_by_member_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Откат возможен, пока ни одно подтверждение не отменено: прежний индекс
    # допускает только одно начисление на задачу, и база откажет, если их два
    op.drop_constraint(
        op.f("fk_ledger_entries_created_by_member_id_members"), "ledger_entries", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_ledger_entries_reverses_entry_id_ledger_entries"),
        "ledger_entries",
        type_="foreignkey",
    )
    op.drop_index("uq_ledger_entries_reverses", table_name="ledger_entries")
    op.drop_index("uq_ledger_entries_accrual_task", table_name="ledger_entries")
    op.create_index(
        "uq_ledger_entries_accrual_task",
        "ledger_entries",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'accrual'"),
    )
    op.drop_constraint(
        op.f("ck_ledger_entries_task_attempt_with_task"), "ledger_entries", type_="check"
    )
    op.drop_column("ledger_entries", "created_by_member_id")
    op.drop_column("ledger_entries", "reverses_entry_id")
    op.drop_column("ledger_entries", "task_attempt")
    op.drop_column("tasks", "attempt")
    op.drop_constraint(op.f("ck_families_revoke_window_positive"), "families", type_="check")
    op.drop_column("families", "revoke_window_days")
