import uuid
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInputError, NotFoundError
from app.modules.ledger.enums import BALANCE_KINDS, RESERVE_KINDS, EntryKind
from app.modules.ledger.models import Account, LedgerEntry


class AccountNotFoundError(NotFoundError):
    pass


@dataclass(frozen=True)
class Balance:
    balance: int
    reserved: int

    @property
    def available(self) -> int:
        return self.balance - self.reserved


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
) -> None:
    """Начисляет баллы участнику под блокировкой его счёта."""
    if amount <= 0:
        raise InvalidInputError("Начислить можно только положительное число баллов")
    account = await _lock_account(session, member_id)
    session.add(
        LedgerEntry(
            account_id=account.id,
            kind=EntryKind.ACCRUAL,
            amount=amount,
            task_id=task_id,
            note=note,
        )
    )
    account.balance += amount
    await session.flush()


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
