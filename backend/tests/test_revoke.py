import asyncio
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.modules.families.models import Family
from app.modules.ledger import service as ledger
from app.modules.ledger.enums import EntryKind
from app.modules.ledger.models import LedgerEntry
from app.modules.rewards import service as rewards
from app.modules.rewards.enums import RewardIcon
from app.modules.rewards.models import RewardPurchase
from app.modules.tasks import service as tasks
from app.modules.tasks.enums import TaskIcon
from app.modules.tasks.models import Task
from app.seed import DemoFamily
from tests.api import adult_token, bearer, child_token, warm_pool, with_key

pytestmark = [pytest.mark.anyio, pytest.mark.us26]

REASON = "Посуда не помыта"


async def confirmed_toys(client: AsyncClient, demo: DemoFamily) -> tuple[str, str, str]:
    """Маша отмечает «Убрать игрушки» (10), мама подтверждает: у Маши 45."""
    masha = await child_token(client, demo.masha_id)
    my = (await client.get("/api/tasks/my", headers=bearer(masha))).json()
    toys = next(t["id"] for t in my if t["title"] == "Убрать игрушки")
    await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    mama = await adult_token(client)
    confirmed = await client.post(f"/api/tasks/{toys}/confirm", headers=bearer(mama))
    assert confirmed.json()["status"] == "confirmed"
    return toys, mama, masha


async def revoke(client: AsyncClient, token: str, task_id: str, reason: str = REASON):
    return await client.post(
        f"/api/tasks/{task_id}/revoke", json={"reason": reason}, headers=bearer(token)
    )


async def entries(session: AsyncSession, task_id: str, kind: EntryKind) -> list[LedgerEntry]:
    return list(
        await session.scalars(
            select(LedgerEntry).where(LedgerEntry.task_id == task_id, LedgerEntry.kind == kind)
        )
    )


async def reward_id(client: AsyncClient, token: str, title: str) -> str:
    offers = (await client.get("/api/rewards", headers=bearer(token))).json()
    return next(r["id"] for r in offers if r["title"] == title)


async def test_revoke_while_points_are_on_balance(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    toys, mama, masha = await confirmed_toys(client, demo)
    response = await revoke(client, mama, toys)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["task"]["status"] == "assigned"
    assert body["task"]["reject_reason"] == REASON
    assert body["task"]["confirmed_at"] is None
    assert body["cancelled_purchases"] == []

    assert (await ledger.get_balance(session, demo.masha_id)).balance == 35
    (accrual,) = await entries(session, toys, EntryKind.ACCRUAL)
    (reversal,) = await entries(session, toys, EntryKind.REVERSAL)
    assert reversal.amount == -accrual.amount == -10
    assert reversal.reverses_entry_id == accrual.id
    assert reversal.created_by_member_id == demo.mama_id
    assert reversal.note == REASON
    assert await ledger.find_mismatched_accounts(session) == []

    goal = (await client.get("/api/goal", headers=bearer(masha))).json()
    assert goal["progress"] == 260
    mine = (await client.get("/api/tasks/my", headers=bearer(masha))).json()
    assert next(t for t in mine if t["id"] == toys)["reject_reason"] == REASON


async def test_task_can_be_done_again_and_earns_new_accrual(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    toys, mama, masha = await confirmed_toys(client, demo)
    await revoke(client, mama, toys)
    again = await revoke(client, mama, toys)
    assert again.status_code == 409
    assert again.json()["detail"] == "Отменить можно только засчитанное дело"

    await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    confirmed = await client.post(f"/api/tasks/{toys}/confirm", headers=bearer(mama))
    assert confirmed.status_code == 200
    assert confirmed.json()["reject_reason"] is None
    assert len(await entries(session, toys, EntryKind.ACCRUAL)) == 2
    assert len(await entries(session, toys, EntryKind.REVERSAL)) == 1
    assert (await ledger.get_balance(session, demo.masha_id)).balance == 45


async def test_reserved_purchases_are_cancelled_from_newest_when_points_run_short(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    await rewards.create_reward(session, demo.family_id, "Наклейки", RewardIcon.MARKERS, 20)
    await session.commit()
    toys, mama, masha = await confirmed_toys(client, demo)
    older = await client.post(
        f"/api/rewards/{await reward_id(client, masha, 'Мороженое')}/buy", headers=bearer(masha)
    )
    newer = await client.post(
        f"/api/rewards/{await reward_id(client, masha, 'Наклейки')}/buy", headers=bearer(masha)
    )
    assert older.status_code == newer.status_code == 200

    body = (await revoke(client, mama, toys)).json()
    assert body["cancelled_purchases"] == ["Наклейки"]
    pending = (await client.get("/api/purchases/pending", headers=bearer(mama))).json()
    assert [p["id"] for p in pending] == [older.json()["id"]]
    balance = await ledger.get_balance(session, demo.masha_id)
    assert (balance.balance, balance.reserved) == (35, 20)
    cancelled = await rewards.cancel_unaffordable_purchases(
        session, demo.family_id, demo.masha_id, "не нужно"
    )
    assert cancelled == []
    assert await ledger.find_mismatched_accounts(session) == []


async def test_cancelled_purchase_tells_why(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    toys, mama, masha = await confirmed_toys(client, demo)
    bought = await client.post(
        f"/api/rewards/{await reward_id(client, masha, 'Фломастеры')}/buy", headers=bearer(masha)
    )
    await revoke(client, mama, toys)
    purchase = await session.get(RewardPurchase, bought.json()["id"])
    assert purchase is not None
    assert purchase.status == "cancelled"
    assert purchase.cancel_reason == "Покупка отменена, потому что отменено дело «Убрать игрушки»"


async def test_revoke_after_reward_given_leaves_balance_negative(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    toys, mama, masha = await confirmed_toys(client, demo)
    bought = await client.post(
        f"/api/rewards/{await reward_id(client, masha, 'Фломастеры')}/buy", headers=bearer(masha)
    )
    await client.post(f"/api/purchases/{bought.json()['id']}/give", headers=bearer(mama))
    assert (await revoke(client, mama, toys)).status_code == 200
    balance = await ledger.get_balance(session, demo.masha_id)
    assert (balance.balance, balance.reserved) == (-5, 0)
    stale = await client.post(
        f"/api/rewards/{await reward_id(client, masha, 'Мороженое')}/buy", headers=bearer(masha)
    )
    assert stale.status_code == 409
    assert stale.json()["missing"] == 25
    assert await ledger.find_mismatched_accounts(session) == []


async def test_revoke_window_is_family_setting(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    toys, mama, _ = await confirmed_toys(client, demo)
    await session.execute(
        update(Task).where(Task.id == toys).values(confirmed_at=now_utc() - timedelta(days=8))
    )
    await session.commit()
    late = await revoke(client, mama, toys)
    assert late.status_code == 409
    assert late.json()["detail"] == "Подтверждение можно отменить только в течение 7 дней"

    await session.execute(
        update(Family).where(Family.id == demo.family_id).values(revoke_window_days=10)
    )
    await session.commit()
    assert (await revoke(client, mama, toys)).status_code == 200


async def test_revoke_after_goal_reached_keeps_goal_reached(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    await ledger.accrue(session, demo.petya_id, 30, note="Помог на даче")
    await session.commit()
    toys, mama, masha = await confirmed_toys(client, demo)
    reached = (await client.get("/api/goal", headers=bearer(masha))).json()
    assert reached["reached"] is True
    await revoke(client, mama, toys)
    after = (await client.get("/api/goal", headers=bearer(masha))).json()
    assert after["reached"] is True
    assert after["progress"] == reached["progress"] == 300
    assert after["feed"][0]["points"] == -10


@pytest.mark.parametrize("reason", ["", "   ", "x" * 201])
async def test_reason_is_required_and_short(client: AsyncClient, demo: DemoFamily, reason: str):
    toys, mama, _ = await confirmed_toys(client, demo)
    assert (await revoke(client, mama, toys, reason)).status_code == 422


async def test_repeat_with_same_key_reverses_once(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    toys, mama, _ = await confirmed_toys(client, demo)
    headers = with_key(mama, "revoke-0001")
    url = f"/api/tasks/{toys}/revoke"
    first = await client.post(url, json={"reason": REASON}, headers=headers)
    again = await client.post(url, json={"reason": REASON}, headers=headers)
    assert first.status_code == again.status_code == 200
    assert first.json() == again.json()
    assert len(await entries(session, toys, EntryKind.REVERSAL)) == 1


@pytest.mark.risk
async def test_revoke_racing_purchase_keeps_balance_consistent(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    mama = await adult_token(client)
    masha = await child_token(client, demo.masha_id)
    markers = await reward_id(client, masha, "Фломастеры")
    await warm_pool(client, mama)
    for n in range(10):
        task = await tasks.create_task(
            session, demo.family_id, demo.mama_id, f"Дело {n}", TaskIcon.BED, 10, demo.masha_id
        )
        await tasks.mark(session, demo.family_id, task.id, demo.masha_id)
        await tasks.confirm(session, demo.family_id, task.id)
        await session.commit()
        revoked, bought = await asyncio.gather(
            revoke(client, mama, str(task.id)),
            client.post(f"/api/rewards/{markers}/buy", headers=bearer(masha)),
        )
        assert revoked.status_code == 200
        assert bought.status_code in (200, 409)
        session.expire_all()
        balance = await ledger.get_balance(session, demo.masha_id)
        assert balance.reserved == 0 or balance.reserved <= balance.balance
        assert await ledger.find_mismatched_accounts(session) == []
    reversals = await session.scalar(
        select(func.count()).where(LedgerEntry.kind == EntryKind.REVERSAL)
    )
    assert reversals == 10
