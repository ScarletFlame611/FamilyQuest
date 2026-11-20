import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ledger import service as ledger
from app.seed import DemoFamily
from tests.api import adult_token, bearer, child_token, with_key

pytestmark = [pytest.mark.anyio, pytest.mark.us15]


async def offers(client: AsyncClient, token: str) -> dict[str, dict]:
    return {r["title"]: r for r in (await client.get("/api/rewards", headers=bearer(token))).json()}


async def managed(client: AsyncClient, token: str) -> dict[str, dict]:
    response = await client.get("/api/rewards/manage", headers=bearer(token))
    assert response.status_code == 200, response.text
    return {r["title"]: r for r in response.json()}


async def test_created_reward_appears_in_child_catalog(client: AsyncClient, demo: DemoFamily):
    mama = await adult_token(client)
    created = await client.post(
        "/api/rewards",
        json={"title": "  Поход в кино  ", "icon": "cartoon", "price": 40},
        headers=bearer(mama),
    )
    assert created.status_code == 201, created.text
    assert created.json()["title"] == "Поход в кино"
    assert created.json()["hidden"] is False

    masha = await child_token(client, demo.masha_id)
    cinema = (await offers(client, masha))["Поход в кино"]
    assert cinema["price"] == 40
    assert cinema["affordable"] is False
    assert cinema["missing"] == 5


async def test_repeated_create_with_same_key_makes_one_reward(
    client: AsyncClient, demo: DemoFamily
):
    mama = await adult_token(client)
    body = {"title": "Пицца", "icon": "park", "price": 60}
    first = await client.post("/api/rewards", json=body, headers=with_key(mama, "reward-0001"))
    again = await client.post("/api/rewards", json=body, headers=with_key(mama, "reward-0001"))
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()
    assert [t for t in await managed(client, mama) if t == "Пицца"] == ["Пицца"]


@pytest.mark.parametrize(
    "body",
    [
        {"title": "Кино", "icon": "cartoon", "price": 0},
        {"title": "Кино", "icon": "cartoon", "price": -5},
        {"title": "Кино", "icon": "cartoon", "price": 2.5},
        {"title": "Кино", "icon": "cartoon", "price": "много"},
        {"title": "Кино", "icon": "cartoon", "price": 10001},
        {"title": "   ", "icon": "cartoon", "price": 10},
        {"title": "Кино", "icon": "car", "price": 10},
    ],
)
async def test_invalid_reward_is_rejected(client: AsyncClient, demo: DemoFamily, body: dict):
    mama = await adult_token(client)
    response = await client.post("/api/rewards", json=body, headers=bearer(mama))
    assert response.status_code == 422


async def test_new_price_does_not_change_existing_purchase(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    ice_cream = (await offers(client, masha))["Мороженое"]
    bought = await client.post(f"/api/rewards/{ice_cream['id']}/buy", headers=bearer(masha))
    assert bought.status_code == 200

    mama = await adult_token(client)
    changed = await client.patch(
        f"/api/rewards/{ice_cream['id']}", json={"price": 50}, headers=bearer(mama)
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["price"] == 50

    given = await client.post(f"/api/purchases/{bought.json()['id']}/give", headers=bearer(mama))
    assert given.json()["price"] == ice_cream["price"]
    balance = (await client.get("/api/balance", headers=bearer(masha))).json()
    assert balance["balance"] == 35 - ice_cream["price"]
    assert balance["reserved"] == 0
    assert await ledger.find_mismatched_accounts(session) == []


async def test_hidden_reward_leaves_catalog_but_pending_purchase_can_be_given(
    client: AsyncClient, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    catalog = await offers(client, masha)
    ice_cream, cartoon = catalog["Мороженое"]["id"], catalog["Мультфильм перед сном"]["id"]
    bought = await client.post(f"/api/rewards/{ice_cream}/buy", headers=bearer(masha))

    mama = await adult_token(client)
    for rid in (ice_cream, cartoon):
        hidden = await client.patch(
            f"/api/rewards/{rid}", json={"hidden": True}, headers=bearer(mama)
        )
        assert hidden.json()["hidden"] is True
    assert {"Мороженое", "Мультфильм перед сном"}.isdisjoint(await offers(client, masha))
    assert (await managed(client, mama))["Мороженое"]["hidden"] is True

    stale = await client.post(f"/api/rewards/{cartoon}/buy", headers=bearer(masha))
    assert stale.status_code == 409
    assert stale.json()["detail"] == "Этой награды больше нет в списке"

    given = await client.post(f"/api/purchases/{bought.json()['id']}/give", headers=bearer(mama))
    assert given.status_code == 200
    assert given.json()["title"] == "Мороженое"

    shown = await client.patch(
        f"/api/rewards/{cartoon}", json={"hidden": False}, headers=bearer(mama)
    )
    assert shown.json()["hidden"] is False
    assert "Мультфильм перед сном" in await offers(client, masha)


async def test_title_can_be_renamed_but_not_blanked(client: AsyncClient, demo: DemoFamily):
    mama = await adult_token(client)
    rid = (await managed(client, mama))["Мороженое"]["id"]
    renamed = await client.patch(
        f"/api/rewards/{rid}", json={"title": "Мороженое в кафе"}, headers=bearer(mama)
    )
    assert renamed.json()["title"] == "Мороженое в кафе"
    blank = await client.patch(f"/api/rewards/{rid}", json={"title": " "}, headers=bearer(mama))
    assert blank.status_code == 422
