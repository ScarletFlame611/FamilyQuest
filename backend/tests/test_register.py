import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_secret
from app.modules.users.models import User
from tests.api import bearer

pytestmark = [pytest.mark.anyio, pytest.mark.us01]

NEW_ADULT = {
    "email": "Olga@Example.org",
    "password": "olga-strong-password",
    "name": "Ольга",
    "avatar": "woman",
    "family_name": "Семья Ольги",
}


async def test_registration_creates_family_and_lets_in(client: AsyncClient):
    response = await client.post("/api/auth/register", json=NEW_ADULT)
    assert response.status_code == 201
    me = await client.get("/api/me", headers=bearer(response.json()["access_token"]))
    assert me.json()["name"] == "Ольга"
    assert me.json()["role"] == "adult"
    assert me.json()["family"]["name"] == "Семья Ольги"

    login = await client.post(
        "/api/auth/login",
        json={"email": "olga@example.org", "password": NEW_ADULT["password"]},
    )
    assert login.status_code == 200


async def test_password_is_stored_only_as_argon2_hash(client: AsyncClient, session: AsyncSession):
    await client.post("/api/auth/register", json=NEW_ADULT)
    stored = await session.scalar(select(User.password_hash))
    assert stored is not None
    assert stored.startswith("$argon2id$")
    assert NEW_ADULT["password"] not in stored
    assert await verify_secret(stored, NEW_ADULT["password"])


async def test_same_email_in_other_case_is_taken(client: AsyncClient):
    assert (await client.post("/api/auth/register", json=NEW_ADULT)).status_code == 201
    again = await client.post("/api/auth/register", json={**NEW_ADULT, "email": "OLGA@example.org"})
    assert again.status_code == 409
    assert again.json()["detail"] == "Эта почта уже зарегистрирована"


@pytest.mark.parametrize(
    "bad",
    [
        {"email": "not-an-email"},
        {"password": "short7!"},
        {"name": ""},
        {"family_name": ""},
    ],
)
async def test_invalid_registration_is_rejected(client: AsyncClient, bad: dict[str, str]):
    response = await client.post("/api/auth/register", json={**NEW_ADULT, **bad})
    assert response.status_code == 422
    # Ответ об ошибке не повторяет присланные значения, в том числе пароль
    assert all(value not in response.text for value in bad.values() if value)
