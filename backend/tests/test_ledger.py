import asyncio
import random
import re
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ledger import service as ledger
from app.modules.ledger.enums import EntryKind
from app.modules.ledger.models import Account, LedgerEntry
from app.seed import DEMO_PIN, DemoFamily
from tests.api import adult_token, bearer, child_tokens, warm_pool, with_key

pytestmark = pytest.mark.anyio


async def masha_marks_toys(client: AsyncClient, demo: DemoFamily) -> tuple[str, dict[str, str]]:
    child = await child_tokens(client, demo.masha_id)
    my = (await client.get("/api/tasks/my", headers=bearer(child["access_token"]))).json()
    toys = next(t["id"] for t in my if t["title"] == "Убрать игрушки")
    marked = await client.post(f"/api/tasks/{toys}/mark", headers=bearer(child["access_token"]))
    assert marked.status_code == 200
    return toys, child


async def test_critical_path_through_api(client: AsyncClient, demo: DemoFamily):
    mama = await adult_token(client)
    created = await client.post(
        "/api/tasks",
        json={
            "title": "Заправить кровать",
            "icon": "bed",
            "points": 7,
            "assignee_id": str(demo.masha_id),
        },
        headers=bearer(mama),
    )
    task = created.json()["id"]

    child = await child_tokens(client, demo.masha_id)
    child_headers = bearer(child["access_token"])
    before = (await client.get("/api/balance", headers=child_headers)).json()
    assert (await client.post(f"/api/tasks/{task}/mark", headers=child_headers)).status_code == 200

    back = await client.post("/api/child-mode/exit", json={"pin": DEMO_PIN}, headers=child_headers)
    adult = back.json()["access_token"]
    confirmed = await client.post(
        f"/api/tasks/{task}/confirm", headers=with_key(adult, "confirm-bed-1")
    )
    assert confirmed.json()["status"] == "confirmed"

    again = await child_tokens(client, demo.masha_id)
    after = (await client.get("/api/balance", headers=bearer(again["access_token"]))).json()
    assert after["balance"] == before["balance"] + 7
    assert after["available"] == before["available"] + 7

    history = (await client.get("/api/ledger", headers=bearer(again["access_token"]))).json()
    assert (history[0]["label"], history[0]["amount"]) == ("Заправить кровать", 7)


@pytest.mark.risk
async def test_fifty_parallel_confirms_accrue_once(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    toys, _ = await masha_marks_toys(client, demo)
    mama = await adult_token(client)
    await warm_pool(client, mama, 20)
    responses = await asyncio.gather(
        *(
            client.post(f"/api/tasks/{toys}/confirm", headers=with_key(mama, f"confirm-{n:04d}"))
            for n in range(50)
        )
    )
    codes = [r.status_code for r in responses]
    assert set(codes) <= {200, 409}
    assert codes.count(200) == 1
    accruals = await session.scalar(
        select(func.count()).where(
            LedgerEntry.task_id == toys, LedgerEntry.kind == EntryKind.ACCRUAL
        )
    )
    assert accruals == 1
    assert (await ledger.get_balance(session, demo.masha_id)).balance == 35 + 10
    assert await ledger.find_mismatched_accounts(session) == []


@pytest.mark.risk
async def test_second_accrual_for_task_is_absorbed_not_500(session: AsyncSession, demo: DemoFamily):
    entry, member = (
        await session.execute(
            select(LedgerEntry, Account.member_id)
            .join(Account, Account.id == LedgerEntry.account_id)
            .where(LedgerEntry.kind == EntryKind.ACCRUAL, LedgerEntry.task_id.is_not(None))
            .limit(1)
        )
    ).one()
    before = (await ledger.get_balance(session, member)).balance
    assert await ledger.accrue(session, member, entry.amount, task_id=entry.task_id) is False
    await session.commit()
    assert (await ledger.get_balance(session, member)).balance == before
    assert await ledger.find_mismatched_accounts(session) == []


@pytest.mark.risk
async def test_random_operations_keep_cache_equal_to_journal(
    session: AsyncSession, demo: DemoFamily
):
    rng = random.Random(20261017)
    members = [demo.masha_id, demo.petya_id, demo.mama_id]
    reserved: dict = {m: [] for m in members}
    for _ in range(300):
        member = rng.choice(members)
        operation = rng.choice(["accrue", "reserve", "release", "spend"])
        amount = rng.randint(1, 30)
        if operation == "accrue":
            await ledger.accrue(session, member, amount, note="тест")
        elif operation == "reserve":
            try:
                await ledger.reserve(session, member, amount, None)
                reserved[member].append(amount)
            except ledger.NotEnoughPointsError:
                pass
        elif reserved[member]:
            held = reserved[member].pop(rng.randrange(len(reserved[member])))
            if operation == "release":
                await ledger.release(session, member, held, None)
            else:
                await ledger.spend(session, member, held, None)
    await session.commit()
    assert await ledger.find_mismatched_accounts(session) == []
    for member in members:
        current = await ledger.get_balance(session, member)
        assert current.reserved == sum(reserved[member])
        assert current.available >= 0


@pytest.mark.risk
async def test_child_cannot_confirm(client: AsyncClient, session: AsyncSession, demo: DemoFamily):
    toys, child = await masha_marks_toys(client, demo)
    response = await client.post(
        f"/api/tasks/{toys}/confirm", headers=bearer(child["access_token"])
    )
    assert response.status_code == 403
    assert (await ledger.get_balance(session, demo.masha_id)).balance == 35


def test_only_ledger_module_touches_point_tables():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if "modules/ledger" in path.as_posix():
            continue
        text = path.read_text()
        # Модели журнала или имена его таблиц в SQL; вызовы ledger.service разрешены
        if re.search(
            r"ledger\.models|\bAccount\b|\bLedgerEntry\b|[\"'](accounts|ledger_entries)[\"']", text
        ):
            offenders.append(path.relative_to(app_dir).as_posix())
    assert offenders == []
