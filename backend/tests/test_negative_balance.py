import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ledger import service as ledger
from app.modules.ledger.enums import EntryKind
from app.modules.ledger.models import LedgerEntry
from app.seed import DemoFamily
from tests.api import adult_token, bearer, child_token, with_key

pytestmark = [pytest.mark.anyio, pytest.mark.us94]


async def masha_in_minus(client: AsyncClient, demo: DemoFamily) -> tuple[str, str, str]:
    """Маша получает 10 за игрушки, тратит 40 на фломастеры, потом подтверждение отменяют."""
    masha = await child_token(client, demo.masha_id)
    mama = await adult_token(client)
    toys = next(
        t["id"]
        for t in (await client.get("/api/tasks/my", headers=bearer(masha))).json()
        if t["title"] == "Убрать игрушки"
    )
    await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    await client.post(f"/api/tasks/{toys}/confirm", headers=bearer(mama))
    offers = (await client.get("/api/rewards", headers=bearer(masha))).json()
    markers = next(r["id"] for r in offers if r["title"] == "Фломастеры")
    bought = await client.post(f"/api/rewards/{markers}/buy", headers=bearer(masha))
    await client.post(f"/api/purchases/{bought.json()['id']}/give", headers=bearer(mama))
    revoked = await client.post(
        f"/api/tasks/{toys}/revoke", json={"reason": "Игрушки снова на полу"}, headers=bearer(mama)
    )
    assert revoked.status_code == 200
    return toys, mama, masha


async def test_child_sees_minus_and_next_points_close_it(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    _, _, masha = await masha_in_minus(client, demo)
    balance = (await client.get("/api/balance", headers=bearer(masha))).json()
    assert balance == {"balance": -5, "reserved": 0, "available": -5}

    await ledger.accrue(session, demo.masha_id, 7, note="Полила цветы")
    await session.commit()
    balance = (await client.get("/api/balance", headers=bearer(masha))).json()
    assert balance["balance"] == 2
    assert await ledger.find_mismatched_accounts(session) == []


async def test_adult_writes_off_minus_with_reason(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    _, mama, masha = await masha_in_minus(client, demo)
    goal_before = (await client.get("/api/goal", headers=bearer(mama))).json()["progress"]
    response = await client.post(
        f"/api/members/{demo.masha_id}/write-off",
        json={"reason": "Договорились начать с чистого листа"},
        headers=bearer(mama),
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"balance": 0, "reserved": 0, "available": 0}

    entry = await session.scalar(select(LedgerEntry).where(LedgerEntry.kind == EntryKind.WRITE_OFF))
    assert entry is not None
    assert (entry.amount, entry.note) == (5, "Договорились начать с чистого листа")
    assert entry.created_by_member_id == demo.mama_id
    # Прощённый минус не заработан, поэтому в общую цель не идёт
    assert (await client.get("/api/goal", headers=bearer(mama))).json()["progress"] == goal_before
    history = (await client.get("/api/ledger", headers=bearer(masha))).json()
    assert (history[0]["kind"], history[0]["amount"]) == ("write_off", 5)
    assert await ledger.find_mismatched_accounts(session) == []


async def test_write_off_without_minus_is_rejected(client: AsyncClient, demo: DemoFamily):
    mama = await adult_token(client)
    response = await client.post(
        f"/api/members/{demo.masha_id}/write-off",
        json={"reason": "просто так"},
        headers=bearer(mama),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Списывать нечего: баланс не в минусе"


@pytest.mark.parametrize("reason", ["", "  ", "x" * 201])
async def test_write_off_needs_reason(client: AsyncClient, demo: DemoFamily, reason: str):
    mama = await adult_token(client)
    response = await client.post(
        f"/api/members/{demo.masha_id}/write-off", json={"reason": reason}, headers=bearer(mama)
    )
    assert response.status_code == 422


async def test_repeat_with_same_key_writes_off_once(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    _, mama, _ = await masha_in_minus(client, demo)
    url = f"/api/members/{demo.masha_id}/write-off"
    headers = with_key(mama, "write-off-0001")
    first = await client.post(url, json={"reason": "Прощаем"}, headers=headers)
    again = await client.post(url, json={"reason": "Прощаем"}, headers=headers)
    assert first.status_code == again.status_code == 200
    entries = await session.scalars(
        select(LedgerEntry).where(LedgerEntry.kind == EntryKind.WRITE_OFF)
    )
    assert len(list(entries)) == 1


async def test_adult_sees_balances_of_whole_family(client: AsyncClient, demo: DemoFamily):
    await masha_in_minus(client, demo)
    mama = await adult_token(client)
    balances = {
        b["member_id"]: b for b in (await client.get("/api/balances", headers=bearer(mama))).json()
    }
    assert set(balances) == {
        str(m) for m in (demo.mama_id, demo.papa_id, demo.masha_id, demo.petya_id)
    }
    assert balances[str(demo.masha_id)]["balance"] == -5
    assert balances[str(demo.petya_id)]["available"] == 30
