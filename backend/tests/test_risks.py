import uuid

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient

from app.deps import require_adult
from app.main import app
from app.seed import DemoFamily
from tests.api import bearer, child_token

pytestmark = [pytest.mark.anyio, pytest.mark.risk]

# Действия, которые ребёнок не должен выполнять ни через интерфейс, ни прямым запросом
ADULT_ONLY = {
    ("POST", "/api/tasks"),
    ("POST", "/api/tasks/{task_id}/confirm"),
    ("POST", "/api/tasks/{task_id}/reject"),
    ("GET", "/api/tasks/pending"),
    ("POST", "/api/purchases/{purchase_id}/give"),
    ("POST", "/api/purchases/{purchase_id}/cancel"),
    ("GET", "/api/purchases/pending"),
    ("PUT", "/api/family/pin"),
    ("POST", "/api/child-mode/start"),
    ("GET", "/api/child-mode/sessions"),
    ("GET", "/api/child-mode/sessions/{session_id}/events"),
    ("GET", "/api/child-mode/sessions/{session_id}/events.csv"),
}

BODIES = {
    "/api/tasks": {"title": "Себе", "icon": "bed", "points": 100},
    "/api/tasks/{task_id}/reject": {"reason": "сам"},
    "/api/purchases/{purchase_id}/cancel": {"reason": "сам"},
    "/api/family/pin": {"current_password": "x", "pin": "2580"},
    "/api/child-mode/start": {"child_id": str(uuid.uuid4())},  # noqa: TID251
}


def _calls(dependant) -> set:
    found = set()
    for dep in dependant.dependencies:
        found.add(dep.call)
        found |= _calls(dep)
    return found


def adult_routes() -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute) and require_adult in _calls(route.dependant)
        for method in route.methods
    }


def test_t1_adult_actions_are_guarded_on_the_server():
    assert adult_routes() == ADULT_ONLY


async def test_t1_t4_child_token_gets_403_on_every_adult_action(
    client: AsyncClient, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    some_id = str(uuid.uuid4())  # noqa: TID251 — право проверяется раньше, чем объект
    for method, path in sorted(ADULT_ONLY):
        url = path.format(task_id=some_id, purchase_id=some_id, session_id=some_id)
        response = await client.request(method, url, json=BODIES.get(path), headers=bearer(masha))
        assert response.status_code == 403, f"{method} {path}: {response.status_code}"
