import asyncio
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.modules.tasks import service as tasks
from app.modules.tasks.enums import TaskIcon
from app.seed import PAPA_EMAIL, DemoFamily
from tests.api import adult_token, adult_tokens, bearer, child_token, warm_pool, with_key
from tests.factories import PAPA_PASSWORD

pytestmark = pytest.mark.anyio


async def task_id(client: AsyncClient, token: str, path: str, title: str) -> str:
    tasks = (await client.get(path, headers=bearer(token))).json()
    return next(t["id"] for t in tasks if t["title"] == title)


async def test_child_sees_only_own_tasks_and_family_board(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    my = (await client.get("/api/tasks/my", headers=bearer(masha))).json()
    assert [t["title"] for t in my] == ["Убрать игрушки", "Покормить кота", "Полить цветы"]
    assert {t["assignee_name"] for t in my} == {"Маша"}

    board = (await client.get("/api/tasks/board", headers=bearer(masha))).json()
    assert [(t["title"], t["created_by_name"]) for t in board] == [
        ("Вынести мусор", "Папа"),
        ("Разобрать посуду", "Мама"),
        ("Сложить носки", "Мама"),
    ]
    assert all(t["status"] == "open" and t["assignee_member_id"] is None for t in board)

    # У Пети нет назначенных дел, только засчитанные сегодня из истории семьи
    petya = await child_token(client, demo.petya_id)
    petya_tasks = (await client.get("/api/tasks/my", headers=bearer(petya))).json()
    assert {t["status"] for t in petya_tasks} == {"confirmed"}
    assert {t["assignee_name"] for t in petya_tasks} == {"Петя"}


async def test_mark_rules(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    petya = await child_token(client, demo.petya_id)
    toys = await task_id(client, masha, "/api/tasks/my", "Убрать игрушки")

    foreign = await client.post(f"/api/tasks/{toys}/mark", headers=bearer(petya))
    assert foreign.status_code == 404

    first = await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    assert first.status_code == 200
    assert first.json()["status"] == "marked"
    again = await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    assert again.status_code == 409
    assert again.json()["detail"] == "Дело уже отмечено и ждёт проверки"


async def test_repeated_mark_with_same_key_returns_same_answer(
    client: AsyncClient, demo: DemoFamily
):
    masha = await child_token(client, demo.masha_id)
    toys = await task_id(client, masha, "/api/tasks/my", "Убрать игрушки")
    cat = await task_id(client, masha, "/api/tasks/my", "Покормить кота")
    headers = with_key(masha, "mark-toys-0001")

    first = await client.post(f"/api/tasks/{toys}/mark", headers=headers)
    repeat = await client.post(f"/api/tasks/{toys}/mark", headers=headers)
    assert first.status_code == repeat.status_code == 200
    assert first.json() == repeat.json()

    other_request = await client.post(f"/api/tasks/{cat}/mark", headers=headers)
    assert other_request.status_code == 422


@pytest.mark.risk
async def test_parallel_repeats_with_same_key_run_once(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    trash = await task_id(client, masha, "/api/tasks/board", "Вынести мусор")
    headers = with_key(masha, "take-trash-0001")
    await warm_pool(client, masha)
    responses = await asyncio.gather(
        *(client.post(f"/api/tasks/{trash}/take", headers=headers) for _ in range(5))
    )
    assert {r.status_code for r in responses} == {200}
    assert all(r.json() == responses[0].json() for r in responses)


@pytest.mark.risk
async def test_two_children_take_same_task_only_one_wins(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    petya = await child_token(client, demo.petya_id)
    dishes = await task_id(client, masha, "/api/tasks/board", "Разобрать посуду")
    await warm_pool(client, masha)
    responses = await asyncio.gather(
        *(
            client.post(f"/api/tasks/{dishes}/take", headers=bearer(token))
            for token in [masha, petya] * 5
        )
    )
    assert sorted(r.status_code for r in responses) == [200] + [409] * 9
    winner = next(r for r in responses if r.status_code == 200).json()
    assert winner["status"] == "assigned"
    board = (await client.get("/api/tasks/board", headers=bearer(masha))).json()
    assert dishes not in [t["id"] for t in board]


async def test_taken_task_moves_to_my_list(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    socks = await task_id(client, masha, "/api/tasks/board", "Сложить носки")
    await client.post(f"/api/tasks/{socks}/take", headers=bearer(masha))
    my = (await client.get("/api/tasks/my", headers=bearer(masha))).json()
    assert socks in [t["id"] for t in my]


async def test_adult_task_counts_immediately(client: AsyncClient, demo: DemoFamily):
    papa = (await adult_tokens(client, PAPA_EMAIL, PAPA_PASSWORD))["access_token"]
    trash = await task_id(client, papa, "/api/tasks/board", "Вынести мусор")
    await client.post(f"/api/tasks/{trash}/take", headers=bearer(papa))
    marked = await client.post(f"/api/tasks/{trash}/mark", headers=bearer(papa))
    assert marked.json()["status"] == "confirmed"
    pending = (await client.get("/api/tasks/pending", headers=bearer(papa))).json()
    assert trash not in [t["id"] for t in pending]


async def test_reject_returns_task_with_reason(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    mama = await adult_token(client)
    toys = await task_id(client, masha, "/api/tasks/my", "Убрать игрушки")
    await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))

    pending = (await client.get("/api/tasks/pending", headers=bearer(mama))).json()
    assert [(t["title"], t["assignee_name"]) for t in pending] == [("Убрать игрушки", "Маша")]

    rejected = await client.post(
        f"/api/tasks/{toys}/reject", json={"reason": "Машинки под кроватью"}, headers=bearer(mama)
    )
    assert rejected.json()["status"] == "assigned"
    own = (await client.get(f"/api/tasks/{toys}", headers=bearer(masha))).json()
    assert own["reject_reason"] == "Машинки под кроватью"

    remarked = await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    assert remarked.json()["status"] == "marked"
    assert remarked.json()["reject_reason"] is None

    open_task = await task_id(client, masha, "/api/tasks/board", "Вынести мусор")
    wrong = await client.post(
        f"/api/tasks/{open_task}/reject", json={"reason": "нет"}, headers=bearer(mama)
    )
    assert wrong.status_code == 409


async def test_create_task_validation(client: AsyncClient, demo: DemoFamily):
    mama = await adult_token(client)
    created = await client.post(
        "/api/tasks",
        json={
            "title": "Заправить кровать",
            "icon": "bed",
            "points": 5,
            "assignee_id": str(demo.masha_id),
        },
        headers=bearer(mama),
    )
    assert created.status_code == 201
    assert created.json()["status"] == "assigned"
    to_board = await client.post(
        "/api/tasks",
        json={"title": "Помыть окна", "icon": "mop", "points": 15},
        headers=bearer(mama),
    )
    assert to_board.json()["status"] == "open"

    for bad in (
        {"title": "Дело", "icon": "rocket", "points": 5},
        {"title": "Дело", "icon": "bed", "points": 0},
        {"title": "", "icon": "bed", "points": 5},
    ):
        assert (await client.post("/api/tasks", json=bad, headers=bearer(mama))).status_code == 422


@pytest.mark.risk
async def test_child_cannot_create_reject_or_see_pending(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    toys = await task_id(client, masha, "/api/tasks/my", "Убрать игрушки")
    await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    create = await client.post(
        "/api/tasks", json={"title": "Себе", "icon": "bed", "points": 100}, headers=bearer(masha)
    )
    reject = await client.post(
        f"/api/tasks/{toys}/reject", json={"reason": "сам"}, headers=bearer(masha)
    )
    pending = await client.get("/api/tasks/pending", headers=bearer(masha))
    assert create.status_code == reject.status_code == pending.status_code == 403


async def test_family_tasks_are_the_same_for_child_and_adult(client: AsyncClient, demo: DemoFamily):
    masha = await child_token(client, demo.masha_id)
    toys = await task_id(client, masha, "/api/tasks/my", "Убрать игрушки")
    await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))

    as_child = (await client.get("/api/tasks/family", headers=bearer(masha))).json()
    as_adult = (
        await client.get("/api/tasks/family", headers=bearer(await adult_token(client)))
    ).json()
    assert as_child == as_adult
    statuses = {t["title"]: t["status"] for t in as_child}
    assert statuses["Убрать игрушки"] == "marked"
    assert statuses["Покормить кота"] == "assigned"
    assert statuses["Вынести мусор"] == "open"
    # Засчитанные сегодня дела истории тоже на доске, в колонке «Готово»
    assert statuses["Помыть посуду"] == "confirmed"


async def test_my_tasks_skip_confirmed_on_previous_days(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily, monkeypatch: pytest.MonkeyPatch
):
    masha = await child_token(client, demo.masha_id)
    before = (await client.get("/api/tasks/my", headers=bearer(masha))).json()
    start = now_utc()
    clock = {"now": start}
    monkeypatch.setattr("app.modules.tasks.service.now_utc", lambda: clock["now"])
    for day in range(1, 101):
        clock["now"] = start - timedelta(days=day)
        view = await tasks.create_task(
            session, demo.family_id, demo.mama_id, f"Старое {day}", TaskIcon.BED, 1, demo.masha_id
        )
        await tasks.mark(session, demo.family_id, view.id, demo.masha_id)
        await tasks.confirm(session, demo.family_id, view.id)
    await session.commit()
    clock["now"] = start

    toys = await task_id(client, masha, "/api/tasks/my", "Убрать игрушки")
    await client.post(f"/api/tasks/{toys}/mark", headers=bearer(masha))
    cat = await task_id(client, masha, "/api/tasks/my", "Покормить кота")
    await client.post(f"/api/tasks/{cat}/mark", headers=bearer(masha))
    confirmed = await client.post(
        f"/api/tasks/{cat}/confirm", headers=bearer(await adult_token(client))
    )
    assert confirmed.status_code == 200

    after = (await client.get("/api/tasks/my", headers=bearer(masha))).json()
    assert len(after) == len(before)
    assert not [t for t in after if t["title"].startswith("Старое")]
    assert [(t["title"], t["status"]) for t in after] == [
        ("Убрать игрушки", "marked"),
        ("Полить цветы", "assigned"),
        ("Покормить кота", "confirmed"),
    ]
