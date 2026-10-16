import re
import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.modules.child_mode.models import ChildSession
from app.modules.families import service as families
from app.modules.families.enums import AgeGroup, MemberRole
from app.modules.rewards import service as rewards
from app.modules.tasks import service as tasks
from app.modules.tasks.enums import TaskIcon
from app.modules.users import service as users
from app.seed import MAMA_EMAIL, DemoFamily
from tests.factories import MAMA_PASSWORD

pytestmark = pytest.mark.anyio


async def login(client: AsyncClient, email: str = MAMA_EMAIL, password: str = MAMA_PASSWORD):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.us02
async def test_adult_logs_in_and_sees_herself(client: AsyncClient, demo: DemoFamily):
    response = await login(client, MAMA_EMAIL.upper())
    assert response.status_code == 200
    me = await client.get("/api/me", headers=bearer(response.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["name"] == "Мама"
    assert me.json()["role"] == "adult"
    assert me.json()["family"]["id"] == str(demo.family_id)


async def test_family_lists_all_members(client: AsyncClient, demo: DemoFamily):
    token = (await login(client)).json()["access_token"]
    response = await client.get("/api/family", headers=bearer(token))
    assert [m["name"] for m in response.json()["members"]] == ["Мама", "Папа", "Маша", "Петя"]


@pytest.mark.us02
async def test_wrong_password_and_unknown_email_look_the_same(
    client: AsyncClient, demo: DemoFamily
):
    wrong = await login(client, password="not-the-password")
    unknown = await login(client, email="nobody@familyquest.local")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


@pytest.mark.us02
async def test_ten_failures_lock_login_for_15_minutes(
    client: AsyncClient, demo: DemoFamily, monkeypatch: pytest.MonkeyPatch
):
    for _ in range(10):
        assert (await login(client, password="wrong")).status_code == 401
    assert (await login(client)).status_code == 429
    later = now_utc() + timedelta(minutes=16)
    monkeypatch.setattr("app.modules.users.service.now_utc", lambda: later)
    assert (await login(client)).status_code == 200


@pytest.mark.us02
@pytest.mark.us02
async def test_validation_error_does_not_echo_password(client: AsyncClient, demo: DemoFamily):
    too_long = "секрет-" * 40
    response = await login(client, password=too_long)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "password"]
    assert "секрет" not in response.text


async def test_success_resets_failure_counter(client: AsyncClient, demo: DemoFamily):
    for _ in range(9):
        await login(client, password="wrong")
    assert (await login(client)).status_code == 200
    for _ in range(9):
        await login(client, password="wrong")
    assert (await login(client)).status_code == 200


async def test_refresh_rotates_and_logout_revokes(client: AsyncClient, demo: DemoFamily):
    first = (await login(client)).json()["refresh_token"]
    rotated = await client.post("/api/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    reused = await client.post("/api/auth/refresh", json={"refresh_token": first})
    assert reused.status_code == 401

    current = rotated.json()["refresh_token"]
    assert (
        await client.post("/api/auth/logout", json={"refresh_token": current})
    ).status_code == 204
    after = await client.post("/api/auth/refresh", json={"refresh_token": current})
    assert after.status_code == 401


async def test_requests_without_valid_token_are_rejected(client: AsyncClient, demo: DemoFamily):
    assert (await client.get("/api/me")).status_code == 401
    assert (await client.get("/api/me", headers=bearer("garbage"))).status_code == 401


@pytest.mark.us03
@pytest.mark.risk
async def test_other_family_objects_are_not_found(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    other_family = await families.create_family(session, "Соседи", "Europe/Moscow")
    other_user = await users.create_user(session, "sosed@familyquest.local", "secret-pass", "Сосед")
    other_adult = await families.add_adult(session, other_family, other_user, "Сосед", "man")
    other_child = await families.add_child(
        session, other_family, "Ваня", "panda", AgeGroup.AGE_6_7, True
    )
    other_task_view = await tasks.create_task(
        session, other_family, other_adult, "Чужое дело", TaskIcon.TOYS, 5, other_child
    )
    other_reward = await rewards.create_reward(session, other_family, "Чужая награда", "park", 10)
    await session.commit()

    token = (await login(client)).json()["access_token"]
    for path in (
        f"/api/tasks/{other_task_view.id}",
        f"/api/family/members/{other_child}",
        f"/api/rewards/{other_reward}",
        f"/api/tasks/{uuid.uuid4()}",  # noqa: TID251 — случайный несуществующий id
    ):
        assert (await client.get(path, headers=bearer(token))).status_code == 404, path
    own = await client.get(f"/api/family/members/{demo.masha_id}", headers=bearer(token))
    assert own.status_code == 200


@pytest.mark.us03
async def test_no_endpoint_accepts_family_id(client: AsyncClient):
    spec = (await client.get("/api/openapi.json")).json()
    for path, operations in spec["paths"].items():
        assert not [p for p in re.findall(r"{(\w+)}", path) if "family" in p], path
        for operation in operations.values():
            names = [p["name"] for p in operation.get("parameters", [])]
            assert not [n for n in names if "family" in n], path
    for name, schema in spec["components"]["schemas"].items():
        if name.endswith("In"):
            # Название новой семьи при регистрации допустимо, идентификатор — нет
            fields = [f for f in schema.get("properties", {}) if "family" in f]
            assert fields in ([], ["family_name"]), name
            if fields:
                assert schema["properties"]["family_name"].get("format") != "uuid", name


@pytest.mark.risk
async def test_child_token_stops_working_when_session_ends(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    child_session = ChildSession(child_member_id=demo.masha_id, started_by_member_id=demo.mama_id)
    session.add(child_session)
    await session.flush()
    tokens = await users.issue_tokens(
        session, demo.masha_id, demo.family_id, MemberRole.CHILD, child_session.id
    )
    await session.commit()
    me = await client.get("/api/me", headers=bearer(tokens.access_token))
    assert me.json()["name"] == "Маша"

    await session.execute(
        update(ChildSession).where(ChildSession.id == child_session.id).values(ended_at=now_utc())
    )
    await session.commit()
    assert (await client.get("/api/me", headers=bearer(tokens.access_token))).status_code == 401


async def test_adult_token_of_deleted_family_is_rejected(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    token = (await login(client)).json()["access_token"]
    await families.delete_family(session, demo.family_id)
    await session.commit()
    assert (await client.get("/api/family", headers=bearer(token))).status_code == 401
