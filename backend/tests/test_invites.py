import asyncio
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.security import hash_refresh_token
from app.modules.families.models import Invite
from app.seed import DemoFamily
from tests.api import adult_token, bearer, child_token

pytestmark = [pytest.mark.anyio, pytest.mark.us11]

GRANDMA = {
    "email": "babushka@example.org",
    "password": "babushka-password",
    "name": "Бабушка",
    "avatar": "woman",
}


async def new_invite(client: AsyncClient) -> str:
    response = await client.post("/api/family/invites", headers=bearer(await adult_token(client)))
    assert response.status_code == 201, response.text
    return response.json()["token"]


async def test_invited_adult_joins_family_of_inviter(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    token = await new_invite(client)
    info = (await client.get(f"/api/auth/invites/{token}")).json()
    assert (info["family_name"], info["invited_by"]) == ("Демо-семья", "Мама")

    joined = await client.post(f"/api/auth/invites/{token}/accept", json=GRANDMA)
    assert joined.status_code == 201, joined.text
    grandma = joined.json()["access_token"]
    me = (await client.get("/api/me", headers=bearer(grandma))).json()
    assert (me["name"], me["role"], me["family"]["id"]) == ("Бабушка", "adult", str(demo.family_id))
    balance = (await client.get("/api/balance", headers=bearer(grandma))).json()
    assert balance == {"balance": 0, "reserved": 0, "available": 0}
    members = (await client.get("/api/family", headers=bearer(grandma))).json()["members"]
    assert "Бабушка" in {m["name"] for m in members}

    login = await client.post(
        "/api/auth/login", json={"email": GRANDMA["email"], "password": GRANDMA["password"]}
    )
    assert login.status_code == 200


async def test_only_hash_of_token_is_stored(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    token = await new_invite(client)
    stored = await session.scalar(select(Invite.token_hash))
    assert stored == hash_refresh_token(token)
    assert token not in stored


async def test_link_works_once(client: AsyncClient, demo: DemoFamily):
    token = await new_invite(client)
    await client.post(f"/api/auth/invites/{token}/accept", json=GRANDMA)
    again = await client.post(
        f"/api/auth/invites/{token}/accept", json={**GRANDMA, "email": "dedushka@example.org"}
    )
    assert again.status_code == 409
    assert again.json()["detail"] == "По этой ссылке уже присоединились. Попросите новую"
    assert (await client.get(f"/api/auth/invites/{token}")).status_code == 409


async def test_expired_link_is_refused(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    token = await new_invite(client)
    await session.execute(update(Invite).values(expires_at=now_utc() - timedelta(minutes=1)))
    await session.commit()
    response = await client.post(f"/api/auth/invites/{token}/accept", json=GRANDMA)
    assert response.status_code == 409
    assert response.json()["detail"] == "Ссылка устарела. Попросите прислать новую"


async def test_link_lives_48_hours(client: AsyncClient, session: AsyncSession, demo: DemoFamily):
    await new_invite(client)
    expires_at = await session.scalar(select(Invite.expires_at))
    assert timedelta(hours=47, minutes=59) < expires_at - now_utc() <= timedelta(hours=48)


async def test_unknown_link_is_404(client: AsyncClient, demo: DemoFamily):
    response = await client.get("/api/auth/invites/" + "x" * 43)
    assert response.status_code == 404


async def test_taken_email_does_not_spend_the_link(client: AsyncClient, demo: DemoFamily):
    token = await new_invite(client)
    taken = await client.post(
        f"/api/auth/invites/{token}/accept", json={**GRANDMA, "email": "papa@familyquest.local"}
    )
    assert taken.status_code == 409
    assert taken.json()["detail"] == "Эта почта уже зарегистрирована"
    assert (await client.post(f"/api/auth/invites/{token}/accept", json=GRANDMA)).status_code == 201


@pytest.mark.parametrize(
    "change",
    [{"avatar": "fox"}, {"password": "short"}, {"email": "не почта"}, {"name": ""}],
)
async def test_invalid_form_is_rejected(client: AsyncClient, demo: DemoFamily, change: dict):
    token = await new_invite(client)
    response = await client.post(f"/api/auth/invites/{token}/accept", json={**GRANDMA, **change})
    assert response.status_code == 422


async def test_child_cannot_create_invite(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    response = await client.post("/api/family/invites", headers=bearer(masha))
    assert response.status_code == 403


@pytest.mark.risk
async def test_one_link_cannot_be_used_twice_at_once(client: AsyncClient, demo: DemoFamily):
    token = await new_invite(client)
    responses = await asyncio.gather(
        *(
            client.post(
                f"/api/auth/invites/{token}/accept",
                json={**GRANDMA, "email": f"gost{n}@example.org"},
            )
            for n in range(4)
        )
    )
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409]
