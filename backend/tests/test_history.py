import csv
import io

import pytest
from httpx import AsyncClient

from app.seed import DemoFamily
from tests.api import adult_token, bearer, child_token

pytestmark = [pytest.mark.anyio, pytest.mark.us28]


async def busy_day(client: AsyncClient, demo: DemoFamily) -> tuple[str, str]:
    """Маше засчитали игрушки (45), выдали мороженое (25), отложила второе (5), дело отменили."""
    masha = await child_token(client, demo.masha_id)
    mama = await adult_token(client)
    toys = next(
        t["id"]
        for t in (await client.get("/api/tasks/my", headers=bearer(masha))).json()
        if t["title"] == "Убрать игрушки"
    )
    await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    await client.post(f"/api/tasks/{toys}/confirm", headers=bearer(mama))
    offers = {
        r["title"]: r["id"]
        for r in (await client.get("/api/rewards", headers=bearer(masha))).json()
    }
    ice = await client.post(f"/api/rewards/{offers['Мороженое']}/buy", headers=bearer(masha))
    await client.post(f"/api/purchases/{ice.json()['id']}/give", headers=bearer(mama))
    await client.post(f"/api/rewards/{offers['Мороженое']}/buy", headers=bearer(masha))
    await client.post(
        f"/api/tasks/{toys}/revoke", json={"reason": "Игрушки снова на полу"}, headers=bearer(mama)
    )
    return masha, mama


async def test_history_adds_up_to_available_balance(client: AsyncClient, demo: DemoFamily):
    masha, _ = await busy_day(client, demo)
    history = (await client.get("/api/ledger", headers=bearer(masha))).json()
    balance = (await client.get("/api/balance", headers=bearer(masha))).json()
    assert sum(e["available_delta"] for e in history) == balance["available"]
    shown = [(e["kind"], e["available_delta"], e["label"]) for e in history]
    # Сторно и снятие резерва пишутся одной транзакцией, их взаимный порядок не важен
    assert set(shown[:2]) == {
        ("release", 20, "Мороженое"),
        ("reversal", -10, "Убрать игрушки"),
    }
    assert ("spend", 0, "Мороженое") in shown
    assert ("reserve", -20, "Мороженое") in shown


async def test_adult_sees_history_of_each_member(client: AsyncClient, demo: DemoFamily):
    masha, mama = await busy_day(client, demo)
    own = (await client.get("/api/ledger", headers=bearer(masha))).json()
    seen = await client.get(f"/api/members/{demo.masha_id}/ledger", headers=bearer(mama))
    assert seen.status_code == 200
    assert seen.json() == own
    papa = (await client.get(f"/api/members/{demo.papa_id}/ledger", headers=bearer(mama))).json()
    assert {e["label"] for e in papa} >= {"Починить кран", "Помыть посуду"}


async def test_history_csv_opens_in_excel(client: AsyncClient, demo: DemoFamily):
    _, mama = await busy_day(client, demo)
    response = await client.get(f"/api/members/{demo.masha_id}/ledger.csv", headers=bearer(mama))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(response.text.lstrip("﻿")), delimiter=";"))
    assert rows[0] == ["Дата и время", "Что произошло", "Дело или награда", "Баллы", "Причина"]
    entries = (
        await client.get(f"/api/members/{demo.masha_id}/ledger", headers=bearer(mama))
    ).json()
    assert len(rows) - 1 == len(entries)
    assert rows[1][1:4] == ["Начисление за дело", "Стартовые баллы", "35"]
    revoke = next(r for r in rows if r[1] == "Отмена подтверждения")
    assert revoke[2:] == ["Убрать игрушки", "-10", "Игрушки снова на полу"]
    assert sum(int(r[3]) for r in rows[1:]) == 35 + 10 - 20 - 20 - 10 + 20
