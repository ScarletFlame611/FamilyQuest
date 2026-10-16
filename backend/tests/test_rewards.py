import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.families import service as families
from app.modules.ledger import service as ledger
from app.modules.rewards import service as rewards
from app.modules.users import service as users
from app.seed import PAPA_EMAIL, DemoFamily
from tests.api import adult_token, adult_tokens, bearer, child_token, warm_pool, with_key
from tests.factories import PAPA_PASSWORD

pytestmark = pytest.mark.anyio


async def reward_id(client: AsyncClient, token: str, title: str) -> str:
    offers = (await client.get("/api/rewards", headers=bearer(token))).json()
    return next(r["id"] for r in offers if r["title"] == title)


async def buy(client: AsyncClient, token: str, title: str, key: str | None = None):
    rid = await reward_id(client, token, title)
    headers = with_key(token, key) if key else bearer(token)
    return await client.post(f"/api/rewards/{rid}/buy", headers=headers)


async def available(client: AsyncClient, token: str) -> int:
    return (await client.get("/api/balance", headers=bearer(token))).json()["available"]


async def test_offers_show_what_is_affordable(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    offers = {
        r["title"]: r for r in (await client.get("/api/rewards", headers=bearer(masha))).json()
    }
    assert offers["Мороженое"]["affordable"] is True
    assert offers["Мороженое"]["missing"] == 0
    assert offers["Конструктор"]["affordable"] is False
    assert offers["Конструктор"]["missing"] == 115


async def test_buy_ice_cream_then_lego_is_short_by_135(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    bought = await buy(client, masha, "Мороженое")
    assert bought.status_code == 200
    assert bought.json()["status"] == "pending"
    assert await available(client, masha) == 15

    lego = await buy(client, masha, "Конструктор")
    assert lego.status_code == 409
    assert lego.json() == {"detail": "Не хватает 135", "missing": 135}

    offers = {
        r["title"]: r for r in (await client.get("/api/rewards", headers=bearer(masha))).json()
    }
    assert offers["Мороженое"]["waiting"] is True
    assert offers["Конструктор"]["missing"] == 135
    assert await ledger.find_mismatched_accounts(session) == []


@pytest.mark.risk
async def test_two_parallel_purchases_cannot_spend_same_points(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    await rewards.create_reward(session, demo.family_id, "Наклейки", "markers", 30)
    await session.commit()
    masha = await child_token(client, demo.masha_id)
    cartoon = await reward_id(client, masha, "Мультфильм перед сном")
    stickers = await reward_id(client, masha, "Наклейки")
    await warm_pool(client, masha)
    responses = await asyncio.gather(
        *(
            client.post(f"/api/rewards/{rid}/buy", headers=with_key(masha, f"buy-{n:04d}"))
            for n, rid in enumerate([cartoon, stickers] * 4)
        )
    )
    assert sorted(r.status_code for r in responses) == [200] + [409] * 7
    assert await available(client, masha) == 5
    assert len(await rewards.list_pending_purchases(session, demo.family_id)) == 1
    assert await ledger.find_mismatched_accounts(session) == []


async def test_give_turns_reserve_into_spend(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    purchase = (await buy(client, masha, "Мороженое")).json()

    # Покупку видят все взрослые, а не только тот, кто включил детский режим
    papa = (await adult_tokens(client, PAPA_EMAIL, PAPA_PASSWORD))["access_token"]
    pending = (await client.get("/api/purchases/pending", headers=bearer(papa))).json()
    assert [(p["title"], p["child_name"]) for p in pending] == [("Мороженое", "Маша")]

    given = await client.post(f"/api/purchases/{purchase['id']}/give", headers=bearer(papa))
    assert given.json()["status"] == "given"
    balance = await ledger.get_balance(session, demo.masha_id)
    assert (balance.balance, balance.reserved, balance.available) == (15, 0, 15)

    again = await client.post(f"/api/purchases/{purchase['id']}/give", headers=bearer(papa))
    assert again.status_code == 409
    cancel_after = await client.post(
        f"/api/purchases/{purchase['id']}/cancel",
        json={"reason": "передумали"},
        headers=bearer(papa),
    )
    assert cancel_after.status_code == 409

    history = (await client.get("/api/ledger", headers=bearer(masha))).json()
    assert [(e["kind"], e["amount"], e["label"]) for e in history[:2]] == [
        ("spend", -20, "Мороженое"),
        ("reserve", 20, "Мороженое"),
    ]
    assert await ledger.find_mismatched_accounts(session) == []


async def test_cancel_releases_reserve(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    purchase = (await buy(client, masha, "Мороженое")).json()
    mama = await adult_token(client)
    cancelled = await client.post(
        f"/api/purchases/{purchase['id']}/cancel",
        json={"reason": "Сегодня уже было сладкое"},
        headers=bearer(mama),
    )
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancel_reason"] == "Сегодня уже было сладкое"
    balance = await ledger.get_balance(session, demo.masha_id)
    assert (balance.balance, balance.reserved, balance.available) == (35, 0, 35)
    assert await ledger.find_mismatched_accounts(session) == []


@pytest.mark.risk
async def test_child_cannot_give_or_cancel_and_adult_cannot_buy(
    client: AsyncClient, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    purchase = (await buy(client, masha, "Мороженое")).json()
    give = await client.post(f"/api/purchases/{purchase['id']}/give", headers=bearer(masha))
    cancel = await client.post(
        f"/api/purchases/{purchase['id']}/cancel", json={"reason": "сам"}, headers=bearer(masha)
    )
    pending = await client.get("/api/purchases/pending", headers=bearer(masha))
    assert give.status_code == cancel.status_code == pending.status_code == 403

    mama = await adult_token(client)
    assert (await buy(client, mama, "Мороженое")).status_code == 403


@pytest.mark.us03
@pytest.mark.risk
async def test_other_family_purchase_is_not_found(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    purchase = (await buy(client, masha, "Мороженое")).json()
    other = await families.create_family(session, "Соседи", "Europe/Moscow")
    user = await users.create_user(session, "sosed2@familyquest.local", "pass-sosed", "Сосед")
    await families.add_adult(session, other, user, "Сосед", "man")
    await session.commit()
    login = await client.post(
        "/api/auth/login", json={"email": "sosed2@familyquest.local", "password": "pass-sosed"}
    )
    stranger = login.json()["access_token"]
    response = await client.post(f"/api/purchases/{purchase['id']}/give", headers=bearer(stranger))
    assert response.status_code == 404


@pytest.mark.risk
async def test_parallel_give_spends_once(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    purchase = (await buy(client, masha, "Мороженое")).json()
    mama = await adult_token(client)
    await warm_pool(client, mama)
    responses = await asyncio.gather(
        *(
            client.post(
                f"/api/purchases/{purchase['id']}/give", headers=with_key(mama, f"give-{n:04d}")
            )
            for n in range(8)
        )
    )
    assert sorted(r.status_code for r in responses) == [200] + [409] * 7
    assert (await ledger.get_balance(session, demo.masha_id)).balance == 15
    assert await ledger.find_mismatched_accounts(session) == []
