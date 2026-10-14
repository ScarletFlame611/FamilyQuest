import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_secret
from app.modules.families import service as families
from app.modules.families.models import Family
from app.modules.goals import service as goals
from app.modules.goals.models import Goal
from app.modules.ledger import service as ledger
from app.modules.ledger.enums import EntryKind
from app.modules.ledger.models import Account, LedgerEntry
from app.modules.users import service as users
from app.modules.users.models import User
from app.seed import DEMO_PIN, MAMA_EMAIL
from tests.factories import MAMA_PASSWORD, seed

pytestmark = pytest.mark.anyio


async def test_masha_starts_with_35_from_journal(session: AsyncSession):
    demo = await seed(session)
    balance = await ledger.get_balance(session, demo.masha_id)
    journal = await session.scalar(
        select(func.sum(LedgerEntry.amount))
        .join(Account, Account.id == LedgerEntry.account_id)
        .where(Account.member_id == demo.masha_id)
    )
    assert balance.balance == 35
    assert journal == 35
    assert await ledger.find_mismatched_accounts(session) == []


async def test_seed_recreates_family_from_scratch(session: AsyncSession):
    await seed(session)
    demo = await seed(session)
    assert await session.scalar(select(func.count()).select_from(Family)) == 1
    assert (await ledger.get_balance(session, demo.masha_id)).balance == 35


async def test_second_accrual_for_same_task_is_rejected(session: AsyncSession):
    await seed(session)
    first = await session.scalar(
        select(LedgerEntry).where(
            LedgerEntry.kind == EntryKind.ACCRUAL, LedgerEntry.task_id.is_not(None)
        )
    )
    assert first is not None
    session.add(
        LedgerEntry(
            account_id=first.account_id,
            kind=EntryKind.ACCRUAL,
            amount=first.amount,
            task_id=first.task_id,
        )
    )
    with pytest.raises(IntegrityError, match="uq_ledger_entries_accrual_task"):
        await session.flush()


async def test_second_active_goal_is_rejected(session: AsyncSession):
    demo = await seed(session)
    with pytest.raises(goals.ActiveGoalExistsError):
        await goals.create_goal(session, demo.family_id, "Ещё одна", "tent", 100)
    # База держит правило и в обход сервиса
    session.add(Goal(family_id=demo.family_id, title="В обход", icon="tent", target=1))
    with pytest.raises(IntegrityError, match="uq_goals_active_family"):
        await session.flush()


async def test_secrets_are_stored_only_as_argon2_hashes(session: AsyncSession):
    demo = await seed(session)
    hashes = list(await session.scalars(select(User.password_hash)))
    pin_hash = await session.scalar(select(Family.pin_hash).where(Family.id == demo.family_id))
    assert pin_hash is not None
    assert all(h.startswith("$argon2id$") for h in [*hashes, pin_hash])
    assert any(verify_secret(h, MAMA_PASSWORD) for h in hashes)
    assert verify_secret(pin_hash, DEMO_PIN)
    assert MAMA_PASSWORD not in hashes
    assert DEMO_PIN not in pin_hash


async def test_email_is_unique_regardless_of_case(session: AsyncSession):
    await seed(session)
    with pytest.raises(IntegrityError, match="uq_users_email_lower"):
        await users.create_user(session, MAMA_EMAIL.upper(), "another-password", "Двойник")


@pytest.mark.parametrize("pin", ["0000", "1111", "1234", "4321", "6789", "12a4", "123"])
async def test_weak_or_malformed_pin_is_rejected(session: AsyncSession, pin: str):
    demo = await seed(session)
    with pytest.raises(families.InvalidInputError):
        await families.set_pin(session, demo.family_id, pin)


async def test_seed_history_fills_goal_to_260(session: AsyncSession):
    demo = await seed(session)
    earned = {
        member: (await ledger.get_balance(session, member)).balance
        for member in (demo.mama_id, demo.papa_id, demo.masha_id, demo.petya_id)
    }
    assert list(earned.values()) == [110, 85, 35, 30]
    assert sum(earned.values()) == 260
