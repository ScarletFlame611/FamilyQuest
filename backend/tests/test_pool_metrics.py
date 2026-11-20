import pytest
from httpx import AsyncClient

from app.core.config import get_settings

pytestmark = pytest.mark.anyio


async def test_pool_metrics_are_hidden_when_disabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(get_settings(), "pool_metrics_enabled", False)
    assert (await client.get("/api/health/pool")).status_code == 404


async def test_pool_metrics_show_usage_when_enabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(get_settings(), "pool_metrics_enabled", True)
    response = await client.get("/api/health/pool")
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 15
    assert 0 <= body["checked_out"] <= body["limit"]
