import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.goals.models import Goal
from app.modules.ledger import service as ledger
from app.modules.ledger.enums import EntryKind
from app.modules.ledger.models import Account, LedgerEntry
from app.seed import DemoFamily
from tests.api import adult_token, bearer, child_token, warm_pool, with_key

pytestmark = pytest.mark.anyio

BICYCLE = {"title": "Велосипед для Пети", "icon": "bicycle", "target": 50}


async def goal(client: AsyncClient, token: str) -> dict:
    response = await client.get("/api/goal", headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()


async def reach_demo_goal(session: AsyncSession, demo: DemoFamily) -> None:
    # После сида семья накопила 260 из 300
    await ledger.accrue(session, demo.masha_id, 40, note="Генеральная уборка")
    await session.commit()


@pytest.mark.us16
async def test_new_goal_is_rejected_while_current_is_not_reached(
    client: AsyncClient, demo: DemoFamily
):
    mama = await adult_token(client)
    response = await client.post("/api/goal", json=BICYCLE, headers=bearer(mama))
    assert response.status_code == 409
    assert response.json()["detail"] == "Сначала семья должна накопить на текущую цель"


@pytest.mark.us33
async def test_reached_goal_keeps_its_progress_after_later_entries(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    await reach_demo_goal(session, demo)
    masha = await child_token(client, demo.masha_id)
    reached = await goal(client, masha)
    assert reached["reached"] is True
    assert reached["reached_at"] is not None
    assert reached["progress"] == 300

    await ledger.accrue(session, demo.petya_id, 10, note="Уже после цели")
    papa_account = await session.scalar(select(Account.id).where(Account.member_id == demo.papa_id))
    # Отмена подтверждения после достижения: цель не переоткрывается
    session.add(LedgerEntry(account_id=papa_account, kind=EntryKind.REVERSAL, amount=-15))
    await session.commit()

    later = await goal(client, masha)
    assert later["reached"] is True
    assert later["reached_at"] == reached["reached_at"]
    assert later["progress"] == 300
    assert sum(c["points"] for c in later["contributions"]) == 300
    assert [f["points"] for f in later["feed"][:2]] == [-15, 10]


@pytest.mark.us33
async def test_reversal_before_reaching_still_reduces_progress(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    papa_account = await session.scalar(select(Account.id).where(Account.member_id == demo.papa_id))
    session.add(LedgerEntry(account_id=papa_account, kind=EntryKind.REVERSAL, amount=-15))
    await ledger.accrue(session, demo.masha_id, 40, note="Не хватит до цели")
    await session.commit()
    data = await goal(client, await adult_token(client))
    assert data["progress"] == 285
    assert data["reached"] is False
    assert data["reached_at"] is None


@pytest.mark.us16
async def test_new_goal_after_reached_one_starts_from_zero(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    await reach_demo_goal(session, demo)
    mama = await adult_token(client)
    created = await client.post("/api/goal", json=BICYCLE, headers=bearer(mama))
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["title"], body["icon"], body["target"]) == ("Велосипед для Пети", "bicycle", 50)
    assert body["progress"] == 0
    assert body["reached"] is False

    active = await session.scalars(
        select(Goal.title).where(Goal.family_id == demo.family_id, Goal.is_active)
    )
    assert list(active) == ["Велосипед для Пети"]

    masha = await child_token(client, demo.masha_id)
    assert (await goal(client, masha))["title"] == "Велосипед для Пети"


@pytest.mark.us16
async def test_repeat_with_same_key_returns_same_goal(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    await reach_demo_goal(session, demo)
    mama = await adult_token(client)
    first = await client.post("/api/goal", json=BICYCLE, headers=with_key(mama, "goal-0001"))
    again = await client.post("/api/goal", json=BICYCLE, headers=with_key(mama, "goal-0001"))
    assert first.status_code == again.status_code == 201
    assert first.json()["id"] == again.json()["id"]


@pytest.mark.us16
@pytest.mark.parametrize(
    "body",
    [
        {**BICYCLE, "target": 0},
        {**BICYCLE, "target": -5},
        {**BICYCLE, "target": 2.5},
        {**BICYCLE, "target": 100001},
        {**BICYCLE, "title": "  "},
        {**BICYCLE, "icon": "yacht"},
    ],
)
async def test_invalid_goal_is_rejected(client: AsyncClient, demo: DemoFamily, body: dict):
    mama = await adult_token(client)
    response = await client.post("/api/goal", json=body, headers=bearer(mama))
    assert response.status_code == 422


@pytest.mark.us16
@pytest.mark.risk
async def test_two_adults_creating_first_goal_at_once_get_one_goal(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    await session.execute(Goal.__table__.update().values(is_active=False))
    await session.commit()
    mama = await adult_token(client)
    await warm_pool(client, mama)
    responses = await asyncio.gather(
        *(
            client.post(
                "/api/goal",
                json={**BICYCLE, "title": f"Цель {n}"},
                headers=with_key(mama, f"goal-race-{n:02d}"),
            )
            for n in range(4)
        )
    )
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409]
    active = await session.scalars(
        select(Goal.id).where(Goal.family_id == demo.family_id, Goal.is_active)
    )
    assert len(list(active)) == 1
