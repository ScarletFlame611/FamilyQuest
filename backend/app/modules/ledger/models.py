import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import now_utc
from app.core.db import Base, str_enum
from app.core.ids import new_id
from app.modules.ledger.enums import EntryKind


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("reserved >= 0", name="reserved_not_negative"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), unique=True
    )
    # Кэш суммы журнала; меняется только в одной транзакции с новой записью.
    # Баланс может уйти в минус после отмены подтверждения уже потраченных баллов.
    balance: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="amount_not_zero"),
        # Одно начисление на одно выполнение задачи: последняя линия защиты от двойного
        # начисления, если повторный запрос прошёл мимо ключа идемпотентности
        Index(
            "uq_ledger_entries_accrual_task",
            "task_id",
            unique=True,
            postgresql_where=text(f"kind = '{EntryKind.ACCRUAL}'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[EntryKind] = mapped_column(str_enum(EntryKind, "entry_kind"))
    amount: Mapped[int] = mapped_column(Integer)
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reward_purchases.id", ondelete="CASCADE"), index=True
    )
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )
