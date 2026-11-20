"""write_off

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "'accrual', 'reserve', 'release', 'spend', 'reversal'"


def upgrade() -> None:
    # Вид записи хранится строкой с CHECK, поэтому новое значение — это замена ограничения
    op.drop_constraint(op.f("ck_ledger_entries_entry_kind"), "ledger_entries", type_="check")
    op.create_check_constraint(
        op.f("ck_ledger_entries_entry_kind"),
        "ledger_entries",
        f"kind IN ({KINDS}, 'write_off')",
    )


def downgrade() -> None:
    # Откат возможен, пока в журнале нет ни одного списания минуса
    op.drop_constraint(op.f("ck_ledger_entries_entry_kind"), "ledger_entries", type_="check")
    op.create_check_constraint(
        op.f("ck_ledger_entries_entry_kind"), "ledger_entries", f"kind IN ({KINDS})"
    )
