import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, InvalidInputError, NotFoundError
from app.modules.ledger.enums import BALANCE_KINDS, EARNING_KINDS, RESERVE_KINDS, EntryKind
from app.modules.ledger.models import Account, LedgerEntry


class AccountNotFoundError(NotFoundError):
    pass


class NotEnoughPointsError(ConflictError):
    pass


class ReserveMismatchError(ConflictError):
    pass


@dataclass(frozen=True)
class Balance:
    balance: int
    reserved: int

    @property
    def available(self) -> int:
        return self.balance - self.reserved


@dataclass(frozen=True)
class EarningView:
    member_id: uuid.UUID
    amount: int
    task_id: uuid.UUID | None
    note: str | None
    created_at: datetime


@dataclass(frozen=True)
class EntryView:
    kind: EntryKind
    amount: int
    task_id: uuid.UUID | None
    purchase_id: uuid.UUID | None
    note: str | None
    created_at: datetime


def _positive(amount: int) -> None:
    if amount <= 0:
        raise InvalidInputError("Число баллов должно быть положительным")


async def open_account(session: AsyncSession, family_id: uuid.UUID, member_id: uuid.UUID) -> None:
    """Заводит участнику пустой счёт баллов."""
    session.add(Account(family_id=family_id, member_id=member_id, balance=0, reserved=0))
    await session.flush()


async def _lock_account(session: AsyncSession, member_id: uuid.UUID) -> Account:
    account = await session.scalar(
        select(Account).where(Account.member_id == member_id).with_for_update()
    )
    if account is None:
        raise AccountNotFoundError("Счёт участника не найден")
    return account


async def accrue(
    session: AsyncSession,
    member_id: uuid.UUID,
    amount: int,
    task_id: uuid.UUID | None = None,
    note: str | None = None,
) -> bool:
    """Начисляет баллы под блокировкой счёта; повторное начисление за ту же задачу не проходит."""
    _positive(amount)
    account = await _lock_account(session, member_id)
    try:
        # Точка сохранения: нарушение уникальности откатывает только эту вставку,
        # а не всю транзакцию подтверждения
        async with session.begin_nested():
            session.add(
                LedgerEntry(
                    account_id=account.id,
                    kind=EntryKind.ACCRUAL,
                    amount=amount,
                    task_id=task_id,
                    note=note,
                )
            )
    except IntegrityError as error:
        if "uq_ledger_entries_accrual_task" not in str(error.orig):
            raise
        return False
    account.balance += amount
    await session.flush()
    return True


async def reserve(
    session: AsyncSession, member_id: uuid.UUID, amount: int, purchase_id: uuid.UUID | None
) -> None:
    """Откладывает баллы под покупку; проверка «хватает ли» идёт под блокировкой счёта."""
    _positive(amount)
    account = await _lock_account(session, member_id)
    available = account.balance - account.reserved
    if available < amount:
        missing = amount - available
        raise NotEnoughPointsError(f"Не хватает {missing}", extra={"missing": missing})
    session.add(
        LedgerEntry(
            account_id=account.id, kind=EntryKind.RESERVE, amount=amount, purchase_id=purchase_id
        )
    )
    account.reserved += amount
    await session.flush()


async def _take_from_reserve(
    session: AsyncSession,
    member_id: uuid.UUID,
    amount: int,
    purchase_id: uuid.UUID | None,
    kind: EntryKind,
) -> None:
    _positive(amount)
    account = await _lock_account(session, member_id)
    if account.reserved < amount:
        raise ReserveMismatchError("В резерве нет столько баллов")
    session.add(
        LedgerEntry(account_id=account.id, kind=kind, amount=-amount, purchase_id=purchase_id)
    )
    account.reserved -= amount
    if kind is EntryKind.SPEND:
        account.balance -= amount
    await session.flush()


async def release(
    session: AsyncSession, member_id: uuid.UUID, amount: int, purchase_id: uuid.UUID | None
) -> None:
    """Снимает резерв: баллы снова можно тратить."""
    await _take_from_reserve(session, member_id, amount, purchase_id, EntryKind.RELEASE)


async def spend(
    session: AsyncSession, member_id: uuid.UUID, amount: int, purchase_id: uuid.UUID | None
) -> None:
    """Превращает резерв в окончательное списание с баланса."""
    await _take_from_reserve(session, member_id, amount, purchase_id, EntryKind.SPEND)


async def get_balance(session: AsyncSession, member_id: uuid.UUID) -> Balance:
    """Возвращает баланс и резерв участника из сохранённого кэша."""
    account = await session.scalar(select(Account).where(Account.member_id == member_id))
    if account is None:
        raise AccountNotFoundError("Счёт участника не найден")
    return Balance(balance=account.balance, reserved=account.reserved)


async def find_mismatched_accounts(session: AsyncSession) -> list[uuid.UUID]:
    """Сверяет сохранённые баланс и резерв каждого счёта с суммой журнала."""
    journal = (
        select(
            LedgerEntry.account_id,
            func.sum(
                case((LedgerEntry.kind.in_(BALANCE_KINDS), LedgerEntry.amount), else_=0)
            ).label("balance"),
            func.sum(
                case((LedgerEntry.kind.in_(RESERVE_KINDS), LedgerEntry.amount), else_=0)
            ).label("reserved"),
        )
        .group_by(LedgerEntry.account_id)
        .subquery()
    )
    rows = await session.execute(
        select(Account.id)
        .outerjoin(journal, journal.c.account_id == Account.id)
        .where(
            (Account.balance != func.coalesce(journal.c.balance, 0))
            | (Account.reserved != func.coalesce(journal.c.reserved, 0))
        )
    )
    return list(rows.scalars())


async def list_entries(
    session: AsyncSession, member_id: uuid.UUID, limit: int = 50
) -> list[EntryView]:
    """Возвращает последние операции участника, новые сверху."""
    entries = await session.scalars(
        select(LedgerEntry)
        .join(Account, Account.id == LedgerEntry.account_id)
        .where(Account.member_id == member_id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(limit)
    )
    return [
        EntryView(
            kind=entry.kind,
            amount=entry.amount,
            task_id=entry.task_id,
            purchase_id=entry.purchase_id,
            note=entry.note,
            created_at=entry.created_at,
        )
        for entry in entries
    ]


async def family_earnings_since(
    session: AsyncSession, family_id: uuid.UUID, since: datetime
) -> dict[uuid.UUID, int]:
    """Сколько баллов заработал каждый участник семьи с указанного момента."""
    rows = await session.execute(
        select(Account.member_id, func.sum(LedgerEntry.amount))
        .join(LedgerEntry, LedgerEntry.account_id == Account.id)
        .where(
            Account.family_id == family_id,
            LedgerEntry.kind.in_(EARNING_KINDS),
            LedgerEntry.created_at >= since,
        )
        .group_by(Account.member_id)
    )
    return {member_id: int(total) for member_id, total in rows.tuples()}


async def recent_family_earnings(
    session: AsyncSession, family_id: uuid.UUID, since: datetime, limit: int = 10
) -> list[EarningView]:
    """Возвращает последние начисления и их отмены в семье с указанного момента."""
    rows = await session.execute(
        select(Account.member_id, LedgerEntry)
        .join(LedgerEntry, LedgerEntry.account_id == Account.id)
        .where(
            Account.family_id == family_id,
            LedgerEntry.kind.in_(EARNING_KINDS),
            LedgerEntry.created_at >= since,
        )
        .order_by(LedgerEntry.created_at.desc())
        .limit(limit)
    )
    return [
        EarningView(
            member_id=member_id,
            amount=entry.amount,
            task_id=entry.task_id,
            note=entry.note,
            created_at=entry.created_at,
        )
        for member_id, entry in rows.tuples()
    ]
