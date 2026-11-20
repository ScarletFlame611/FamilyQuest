import csv
import io
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.config import get_settings
from app.modules.families import service as families
from app.modules.users import service as users
from app.seed import DEMO_PIN, DemoFamily
from tests.api import adult_token, bearer, child_token
from tests.factories import seed

pytestmark = pytest.mark.anyio


async def first(client: AsyncClient, token: str, path: str, title: str) -> str:
    items = (await client.get(path, headers=bearer(token))).json()
    return next(i["id"] for i in items if i["title"] == title)


async def latest_session(client: AsyncClient, adult: str) -> str:
    sessions = (await client.get("/api/child-mode/sessions", headers=bearer(adult))).json()
    return sessions[0]["id"]


async def test_test_scenario_is_visible_in_export(
    client: AsyncClient, demo: DemoFamily, monkeypatch: pytest.MonkeyPatch
):
    masha = await child_token(client, demo.masha_id)
    start = now_utc()
    clock = {"now": start}
    monkeypatch.setattr("app.modules.child_mode.service.now_utc", lambda: clock["now"])

    toys = await first(client, masha, "/api/tasks/my", "Убрать игрушки")
    clock["now"] = start + timedelta(seconds=5)
    sent = await client.post(
        "/api/child-mode/events",
        json={
            "events": [
                {"type": "screen_opened", "detail": "/kid", "ago_ms": 4000},
                {"type": "task_opened", "detail": "Убрать игрушки", "ago_ms": 0},
            ]
        },
        headers=bearer(masha),
    )
    assert sent.status_code == 204

    clock["now"] = start + timedelta(seconds=47)
    await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    ice = await first(client, masha, "/api/rewards", "Мороженое")
    clock["now"] = start + timedelta(seconds=80)
    await client.post(f"/api/rewards/{ice}/buy", headers=bearer(masha))
    clock["now"] = start + timedelta(seconds=95)
    await client.post("/api/child-mode/exit", json={"pin": "9999"}, headers=bearer(masha))
    clock["now"] = start + timedelta(seconds=99)
    back = await client.post("/api/child-mode/exit", json={"pin": DEMO_PIN}, headers=bearer(masha))
    adult = back.json()["access_token"]

    session_id = await latest_session(client, adult)
    data = (
        await client.get(f"/api/child-mode/sessions/{session_id}/events", headers=bearer(adult))
    ).json()
    assert data["session"]["child_name"] == "Маша"
    assert data["session"]["ended_at"] is not None
    events = [(e["type"], e["detail"]) for e in data["events"]]
    assert events == [
        ("screen_opened", "/kid"),
        ("task_opened", "Убрать игрушки"),
        ("task_marked", "Убрать игрушки"),
        ("reward_bought", "Мороженое"),
        ("wrong_pin", None),
        ("pin_exit", None),
    ]
    seconds = {e["type"]: e["seconds_from_start"] for e in data["events"]}
    assert seconds["task_marked"] - seconds["task_opened"] == pytest.approx(42, abs=1)
    assert all(e["seconds_from_start"] >= 0 for e in data["events"])

    exported = await client.get(
        f"/api/child-mode/sessions/{session_id}/events.csv", headers=bearer(adult)
    )
    assert exported.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(exported.text.lstrip("﻿"))))
    assert rows[0] == ["seconds_from_start", "type", "detail", "occurred_at"]
    assert [row[1] for row in rows[1:]] == [e[0] for e in events]


async def test_client_cannot_forge_server_events(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    forged = await client.post(
        "/api/child-mode/events",
        json={"events": [{"type": "task_marked", "detail": "Всё", "ago_ms": 0}]},
        headers=bearer(masha),
    )
    assert forged.status_code == 422


@pytest.mark.us03
@pytest.mark.risk
async def test_events_are_only_for_own_family_adults(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    adult = await adult_token(client)
    session_id = await latest_session(client, adult)
    as_child = await client.get(
        f"/api/child-mode/sessions/{session_id}/events", headers=bearer(masha)
    )
    assert as_child.status_code == 403

    other = await families.create_family(session, "Соседи", "Europe/Moscow")
    user = await users.create_user(session, "sosed3@familyquest.local", "pass-sosed", "Сосед")
    await families.add_adult(session, other, user, "Сосед", "man")
    await session.commit()
    login = await client.post(
        "/api/auth/login", json={"email": "sosed3@familyquest.local", "password": "pass-sosed"}
    )
    stranger = bearer(login.json()["access_token"])
    foreign = await client.get(f"/api/child-mode/sessions/{session_id}/events", headers=stranger)
    assert foreign.status_code == 404
    assert (await client.get("/api/child-mode/sessions", headers=stranger)).json() == []


async def test_reseed_saves_child_journals_first(
    client: AsyncClient,
    session: AsyncSession,
    demo: DemoFamily,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(get_settings(), "exports_dir", str(tmp_path))
    masha = await child_token(client, demo.masha_id)
    await client.post(
        "/api/child-mode/events",
        json={"events": [{"type": "screen_opened", "detail": "/kid", "ago_ms": 0}]},
        headers=bearer(masha),
    )
    await seed(session)
    files = list(tmp_path.glob("*.csv"))
    assert len(files) == 1
    assert "Маша" in files[0].name
    assert "screen_opened" in files[0].read_text(encoding="utf-8")
