import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.families import service as families
from app.modules.users import service as users
from app.seed import DEMO_PIN, MAMA_EMAIL, DemoFamily
from tests.api import warm_pool
from tests.factories import MAMA_PASSWORD, PAPA_PASSWORD

pytestmark = pytest.mark.anyio


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def adult_tokens(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/auth/login", json={"email": MAMA_EMAIL, "password": MAMA_PASSWORD}
    )
    return response.json()


async def start_child_mode(client: AsyncClient, demo: DemoFamily) -> dict[str, str]:
    adult = await adult_tokens(client)
    response = await client.post(
        "/api/child-mode/start",
        json={"child_id": str(demo.masha_id), "adult_refresh_token": adult["refresh_token"]},
        headers=bearer(adult["access_token"]),
    )
    assert response.status_code == 200
    return response.json()


async def exit_pin(client: AsyncClient, child: dict[str, str], pin: str):
    return await client.post(
        "/api/child-mode/exit", json={"pin": pin}, headers=bearer(child["access_token"])
    )


@pytest.mark.us05
@pytest.mark.parametrize("pin", ["1234", "0000", "1111", "4321"])
async def test_simple_pins_are_rejected(client: AsyncClient, demo: DemoFamily, pin: str):
    adult = await adult_tokens(client)
    response = await client.put(
        "/api/family/pin",
        json={"current_password": MAMA_PASSWORD, "pin": pin},
        headers=bearer(adult["access_token"]),
    )
    assert response.status_code == 422
    assert "легко угадать" in response.json()["detail"]


@pytest.mark.us05
async def test_pin_is_set_only_with_current_password(client: AsyncClient, demo: DemoFamily):
    adult = await adult_tokens(client)
    headers = bearer(adult["access_token"])
    wrong = await client.put(
        "/api/family/pin", json={"current_password": "nope", "pin": "2580"}, headers=headers
    )
    assert wrong.status_code == 422
    ok = await client.put(
        "/api/family/pin", json={"current_password": MAMA_PASSWORD, "pin": "2580"}, headers=headers
    )
    assert ok.status_code == 204


async def test_child_mode_needs_a_pin_and_a_child(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    adult = await adult_tokens(client)
    headers = bearer(adult["access_token"])
    as_adult = await client.post(
        "/api/child-mode/start", json={"child_id": str(demo.papa_id)}, headers=headers
    )
    assert as_adult.status_code == 422

    family_id = await families.create_family(session, "Без PIN", "Europe/Moscow")
    user_id = await users.create_user(session, "nopin@familyquest.local", "pass-nopin", "Оля")
    await families.add_adult(session, family_id, user_id, "Оля", "woman")
    child_id = await families.add_child(session, family_id, "Коля", "fox")
    await session.commit()
    login = await client.post(
        "/api/auth/login", json={"email": "nopin@familyquest.local", "password": "pass-nopin"}
    )
    no_pin = await client.post(
        "/api/child-mode/start",
        json={"child_id": str(child_id)},
        headers=bearer(login.json()["access_token"]),
    )
    assert no_pin.status_code == 409

    foreign = await client.post(
        "/api/child-mode/start", json={"child_id": str(child_id)}, headers=headers
    )
    assert foreign.status_code == 404


@pytest.mark.us07
@pytest.mark.risk
async def test_child_token_cannot_do_adult_actions(client: AsyncClient, demo: DemoFamily):
    child = await start_child_mode(client, demo)
    headers = bearer(child["access_token"])
    me = await client.get("/api/me", headers=headers)
    assert me.json()["name"] == "Маша"
    set_pin = await client.put(
        "/api/family/pin", json={"current_password": MAMA_PASSWORD, "pin": "2580"}, headers=headers
    )
    assert set_pin.status_code == 403
    restart = await client.post(
        "/api/child-mode/start", json={"child_id": str(demo.masha_id)}, headers=headers
    )
    assert restart.status_code == 403


async def test_starting_child_mode_revokes_adult_refresh_token(
    client: AsyncClient, demo: DemoFamily
):
    adult = await adult_tokens(client)
    await client.post(
        "/api/child-mode/start",
        json={"child_id": str(demo.masha_id), "adult_refresh_token": adult["refresh_token"]},
        headers=bearer(adult["access_token"]),
    )
    reuse = await client.post("/api/auth/refresh", json={"refresh_token": adult["refresh_token"]})
    assert reuse.status_code == 401


@pytest.mark.us93
@pytest.mark.risk
async def test_correct_pin_returns_adult_and_kills_child_tokens(
    client: AsyncClient, demo: DemoFamily
):
    child = await start_child_mode(client, demo)
    response = await exit_pin(client, child, DEMO_PIN)
    assert response.status_code == 200
    me = await client.get("/api/me", headers=bearer(response.json()["access_token"]))
    assert me.json()["name"] == "Мама"
    assert me.json()["role"] == "adult"

    assert (await client.get("/api/me", headers=bearer(child["access_token"]))).status_code == 401
    refresh = await client.post("/api/auth/refresh", json={"refresh_token": child["refresh_token"]})
    assert refresh.status_code == 401


@pytest.mark.us07
@pytest.mark.risk
async def test_child_refresh_never_yields_adult_rights(client: AsyncClient, demo: DemoFamily):
    child = await start_child_mode(client, demo)
    refreshed = await client.post(
        "/api/auth/refresh", json={"refresh_token": child["refresh_token"]}
    )
    assert refreshed.status_code == 200
    headers = bearer(refreshed.json()["access_token"])
    me = await client.get("/api/me", headers=headers)
    assert me.json()["role"] == "child"
    pin = await client.put(
        "/api/family/pin", json={"current_password": MAMA_PASSWORD, "pin": "2580"}, headers=headers
    )
    assert pin.status_code == 403


@pytest.mark.us93
@pytest.mark.risk
async def test_five_wrong_pins_lock_until_password(client: AsyncClient, demo: DemoFamily):
    child = await start_child_mode(client, demo)
    for left in (4, 3, 2, 1):
        response = await exit_pin(client, child, "9999")
        assert response.status_code == 401
        assert response.json()["attempts_left"] == left
    fifth = await exit_pin(client, child, "9999")
    assert fifth.status_code == 429
    assert (await exit_pin(client, child, DEMO_PIN)).status_code == 429

    headers = bearer(child["access_token"])
    papa = await client.post(
        "/api/child-mode/exit-with-password", json={"password": PAPA_PASSWORD}, headers=headers
    )
    assert papa.status_code == 422
    mama = await client.post(
        "/api/child-mode/exit-with-password", json={"password": MAMA_PASSWORD}, headers=headers
    )
    assert mama.status_code == 200

    # Блокировка снята: следующий детский сеанс снова выходит по PIN
    again = await start_child_mode(client, demo)
    assert (await exit_pin(client, again, DEMO_PIN)).status_code == 200


@pytest.mark.us93
@pytest.mark.risk
async def test_parallel_guessing_cannot_exceed_five_attempts(client: AsyncClient, demo: DemoFamily):
    child = await start_child_mode(client, demo)
    guesses = [f"{n:04d}" for n in range(1000, 1012) if f"{n:04d}" != DEMO_PIN]
    await warm_pool(client, child["access_token"])
    responses = await asyncio.gather(*(exit_pin(client, child, pin) for pin in guesses))
    codes = sorted(r.status_code for r in responses)
    assert codes.count(401) == 4
    assert codes.count(429) == len(guesses) - 4
    assert (await exit_pin(client, child, DEMO_PIN)).status_code == 429
