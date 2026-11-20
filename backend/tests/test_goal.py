import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.families import service as families
from app.modules.families.enums import AgeGroup
from app.modules.goals import service as goals
from app.modules.goals.enums import GoalIcon
from app.modules.goals.models import Goal
from app.modules.ledger import service as ledger
from app.modules.ledger.enums import EntryKind
from app.modules.ledger.models import Account, LedgerEntry
from app.modules.users import service as users
from app.seed import DemoFamily
from tests.api import adult_token, bearer, child_token

pytestmark = pytest.mark.anyio


async def goal(client: AsyncClient, token: str) -> dict:
    response = await client.get("/api/goal", headers=bearer(token))
    assert response.status_code == 200
    return response.json()


async def test_progress_after_seed_equals_family_accruals_since_goal(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    data = await goal(client, masha)
    created_at = await session.scalar(
        select(Goal.created_at).where(Goal.family_id == demo.family_id)
    )
    accruals = await session.scalar(
        select(func.sum(LedgerEntry.amount))
        .join(Account, Account.id == LedgerEntry.account_id)
        .where(
            Account.family_id == demo.family_id,
            LedgerEntry.kind == EntryKind.ACCRUAL,
            LedgerEntry.created_at >= created_at,
        )
    )
    assert data["progress"] == accruals == 260
    assert data["target"] == 300
    assert data["reached"] is False
    assert [(c["name"], c["points"]) for c in data["contributions"]] == [
        ("Мама", 110),
        ("Папа", 85),
        ("Маша", 35),
        ("Петя", 30),
    ]
    assert sum(c["points"] for c in data["contributions"]) == data["progress"]
    assert [(f["name"], f["title"], f["points"]) for f in data["feed"][:3]] == [
        ("Папа", "Помыть посуду", 15),
        ("Мама", "Приготовить ужин", 20),
        ("Петя", "Пропылесосить", 10),
    ]


@pytest.mark.us09
async def test_confirmed_task_raises_balance_and_goal_equally(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    my = (await client.get("/api/tasks/my", headers=bearer(masha))).json()
    toys = next(t["id"] for t in my if t["title"] == "Убрать игрушки")
    await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    await client.post(f"/api/tasks/{toys}/confirm", headers=bearer(await adult_token(client)))

    data = await goal(client, masha)
    assert data["progress"] == 270
    assert next(c for c in data["contributions"] if c["name"] == "Маша")["points"] == 45
    assert (await ledger.get_balance(session, demo.masha_id)).balance == 45
    assert data["feed"][0]["title"] == "Убрать игрушки"


async def test_buying_reward_does_not_change_goal(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    offers = (await client.get("/api/rewards", headers=bearer(masha))).json()
    ice = next(r["id"] for r in offers if r["title"] == "Мороженое")
    purchase = (await client.post(f"/api/rewards/{ice}/buy", headers=bearer(masha))).json()
    await client.post(
        f"/api/purchases/{purchase['id']}/give", headers=bearer(await adult_token(client))
    )
    data = await goal(client, masha)
    assert data["progress"] == 260
    assert next(c for c in data["contributions"] if c["name"] == "Маша")["points"] == 35


async def test_reversal_entry_reduces_progress(session: AsyncSession, demo: DemoFamily):
    account_id = await session.scalar(select(Account.id).where(Account.member_id == demo.papa_id))
    # Отмены подтверждения в PoC нет; запись вставляется напрямую,
    # чтобы проверить, что расчёт цели её учтёт
    session.add(LedgerEntry(account_id=account_id, kind=EntryKind.REVERSAL, amount=-15))
    await session.commit()
    view = await goals.get_active_goal(session, demo.family_id)
    assert view.progress == 245
    assert next(c for c in view.contributions if c.name == "Папа").points == 70


async def test_points_earned_before_goal_do_not_count(session: AsyncSession, demo: DemoFamily):
    family = await families.create_family(session, "Новая", "Europe/Moscow")
    child = await families.add_child(session, family, "Лиза", "fox", AgeGroup.AGE_6_7, True)
    await ledger.accrue(session, child, 50, note="До цели")
    await goals.create_goal(session, family, "Велосипед", GoalIcon.TENT, 100)
    await ledger.accrue(session, child, 7, note="После цели")
    view = await goals.get_active_goal(session, family)
    assert view.progress == 7
    assert [f.title for f in view.feed] == ["После цели"]


async def test_no_goal_is_404(client: AsyncClient, session: AsyncSession, demo: DemoFamily):
    await session.execute(Goal.__table__.update().values(is_active=False))
    await session.commit()
    masha = await child_token(client, demo.masha_id)
    assert (await client.get("/api/goal", headers=bearer(masha))).status_code == 404


async def test_contributions_add_up_to_progress(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    mama = await adult_token(client)
    toys = next(
        t["id"]
        for t in (await client.get("/api/tasks/my", headers=bearer(masha))).json()
        if t["title"] == "Убрать игрушки"
    )
    await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    await client.post(f"/api/tasks/{toys}/confirm", headers=bearer(mama))
    data = await goal(client, masha)
    assert sum(c["points"] for c in data["contributions"]) == data["progress"] == 270
    assert {c["member_id"] for c in data["contributions"]} == {
        str(m) for m in (demo.mama_id, demo.papa_id, demo.masha_id, demo.petya_id)
    }


async def test_other_family_does_not_see_goal(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    other = await families.create_family(session, "Соседи", "Europe/Moscow")
    user = await users.create_user(session, "goal-sosed@example.org", "sosed-password", "Сосед")
    await families.add_adult(session, other, user, "Сосед", "man")
    child = await families.add_child(session, other, "Ваня", "panda", AgeGroup.AGE_6_7, True)
    await families.set_pin(session, other, "3917")
    await session.commit()
    login = await client.post(
        "/api/auth/login", json={"email": "goal-sosed@example.org", "password": "sosed-password"}
    )
    adult = login.json()["access_token"]
    started = await client.post(
        "/api/child-mode/start", json={"child_id": str(child)}, headers=bearer(adult)
    )
    for token in (adult, started.json()["access_token"]):
        response = await client.get("/api/goal", headers=bearer(token))
        assert response.status_code == 404
        assert "Поход" not in response.text
