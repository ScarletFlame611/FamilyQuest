import re

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient

from app.deps import require_child
from app.main import app
from app.seed import DemoFamily
from tests.api import adult_token, bearer, child_tokens

pytestmark = [pytest.mark.anyio, pytest.mark.us03, pytest.mark.risk]

BODIES = {
    "/api/tasks/{task_id}/reject": {"reason": "чужое"},
    "/api/purchases/{purchase_id}/cancel": {"reason": "чужое"},
}


def _calls(dependant) -> set:
    found = set()
    for dep in dependant.dependencies:
        found.add(dep.call)
        found |= _calls(dep)
    return found


def routes_with_ids() -> list[tuple[str, str, bool]]:
    return sorted(
        (method, route.path, require_child in _calls(route.dependant))
        for route in app.routes
        if isinstance(route, APIRoute) and "{" in route.path
        for method in route.methods
    )


async def stranger_tokens(client: AsyncClient) -> tuple[str, str]:
    registered = await client.post(
        "/api/auth/register",
        json={
            "email": "stranger@example.org",
            "password": "stranger-password",
            "name": "Сосед",
            "avatar": "man",
            "family_name": "Соседи",
        },
    )
    adult = registered.json()["access_token"]
    child = await client.post(
        "/api/family/children",
        json={"name": "Ваня", "avatar": "panda", "age_group": "6-7", "parent_consent": True},
        headers=bearer(adult),
    )
    await client.put(
        "/api/family/pin",
        json={"current_password": "stranger-password", "pin": "3917"},
        headers=bearer(adult),
    )
    started = await client.post(
        "/api/child-mode/start", json={"child_id": child.json()["id"]}, headers=bearer(adult)
    )
    assert started.status_code == 200, started.text
    adult = (
        await client.post(
            "/api/auth/login",
            json={"email": "stranger@example.org", "password": "stranger-password"},
        )
    ).json()["access_token"]
    return adult, started.json()["access_token"]


async def test_every_endpoint_with_id_hides_other_family(client: AsyncClient, demo: DemoFamily):
    masha = (await child_tokens(client, demo.masha_id))["access_token"]
    my = (await client.get("/api/tasks/my", headers=bearer(masha))).json()
    rewards = (await client.get("/api/rewards", headers=bearer(masha))).json()
    ice_cream = next(r["id"] for r in rewards if r["title"] == "Мороженое")
    purchase = await client.post(f"/api/rewards/{ice_cream}/buy", headers=bearer(masha))
    mama = await adult_token(client)
    sessions = (await client.get("/api/child-mode/sessions", headers=bearer(mama))).json()
    ids = {
        "task_id": my[0]["id"],
        "reward_id": ice_cream,
        "purchase_id": purchase.json()["id"],
        "session_id": sessions[0]["id"],
        "member_id": str(demo.masha_id),
    }

    adult, child = await stranger_tokens(client)
    checked = []
    for method, path, child_only in routes_with_ids():
        names = re.findall(r"{(\w+)}", path)
        assert set(names) <= set(ids), f"{path}: нет чужого объекта для {names}"
        response = await client.request(
            method,
            path.format(**ids),
            json=BODIES.get(path),
            headers=bearer(child if child_only else adult),
        )
        assert response.status_code == 404, f"{method} {path}: {response.status_code}"
        checked.append(f"{method} {path}")
    assert len(checked) >= 12

    # Попытки соседа ничего не изменили в демо-семье
    pending = (await client.get("/api/purchases/pending", headers=bearer(mama))).json()
    assert [p["id"] for p in pending] == [ids["purchase_id"]]
    task = (await client.get(f"/api/tasks/{ids['task_id']}", headers=bearer(mama))).json()
    assert task["status"] == "assigned"
