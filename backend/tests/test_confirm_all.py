import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.families import service as families
from app.modules.families.enums import AgeGroup
from app.modules.ledger import service as ledger
from app.modules.ledger.enums import EntryKind
from app.modules.ledger.models import LedgerEntry
from app.modules.tasks import service as tasks
from app.modules.tasks.enums import TaskIcon
from app.seed import PAPA_EMAIL, DemoFamily
from tests.api import adult_token, adult_tokens, bearer, warm_pool, with_key
from tests.factories import PAPA_PASSWORD

pytestmark = [pytest.mark.anyio, pytest.mark.us58]


async def marked_tasks(
    session: AsyncSession, demo: DemoFamily, plan: list[tuple[str, int]]
) -> list[str]:
    """Создаёт дела детям и отмечает их выполненными: Маше и Пете по очереди."""
    ids = []
    for n, (title, points) in enumerate(plan):
        child = demo.masha_id if n % 2 == 0 else demo.petya_id
        view = await tasks.create_task(
            session, demo.family_id, demo.mama_id, title, TaskIcon.BED, points, child
        )
        await tasks.mark(session, demo.family_id, view.id, child)
        ids.append(str(view.id))
    await session.commit()
    return ids


async def accruals(session: AsyncSession, task_id: str) -> int:
    return await session.scalar(
        select(func.count()).where(
            LedgerEntry.task_id == task_id, LedgerEntry.kind == EntryKind.ACCRUAL
        )
    )


async def test_all_marked_tasks_are_confirmed_in_one_request(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    ids = await marked_tasks(
        session, demo, [("Заправить кровать", 7), ("Почистить зубы", 3), ("Собрать рюкзак", 5)]
    )
    mama = await adult_token(client)
    response = await client.post(
        "/api/tasks/confirm-all", json={"task_ids": ids}, headers=bearer(mama)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert sorted(t["id"] for t in body["confirmed"]) == sorted(ids)
    assert {t["status"] for t in body["confirmed"]} == {"confirmed"}
    assert body["skipped"] == []

    assert (await ledger.get_balance(session, demo.masha_id)).balance == 35 + 7 + 5
    assert (await ledger.get_balance(session, demo.petya_id)).balance == 30 + 3
    assert [await accruals(session, i) for i in ids] == [1, 1, 1]
    pending = (await client.get("/api/tasks/pending", headers=bearer(mama))).json()
    assert not set(ids) & {t["id"] for t in pending}
    goal = (await client.get("/api/goal", headers=bearer(mama))).json()
    assert goal["progress"] == 260 + 15
    assert await ledger.find_mismatched_accounts(session) == []


async def test_already_confirmed_and_unmarked_tasks_are_skipped_not_failed(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    first, second = await marked_tasks(
        session, demo, [("Заправить кровать", 7), ("Убрать стол", 4)]
    )
    unmarked = await tasks.create_task(
        session, demo.family_id, demo.mama_id, "Почитать", TaskIcon.BED, 6, demo.masha_id
    )
    await session.commit()
    papa = (await adult_tokens(client, PAPA_EMAIL, PAPA_PASSWORD))["access_token"]
    await client.post(f"/api/tasks/{first}/confirm", headers=bearer(papa))

    mama = await adult_token(client)
    response = await client.post(
        "/api/tasks/confirm-all",
        json={"task_ids": [first, second, str(unmarked.id)]},
        headers=bearer(mama),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [t["id"] for t in body["confirmed"]] == [second]
    assert {s["task_id"]: s["reason"] for s in body["skipped"]} == {
        first: "Дело уже засчитано",
        str(unmarked.id): "Дело ещё не отмечено выполненным",
    }
    assert await accruals(session, first) == 1
    assert await accruals(session, second) == 1


async def test_task_of_other_family_fails_whole_batch_with_404(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    (mine,) = await marked_tasks(session, demo, [("Заправить кровать", 7)])
    other = await families.create_family(session, "Соседи", "Europe/Moscow")
    kid = await families.add_child(session, other, "Ваня", "panda", AgeGroup.AGE_6_7, True)
    stranger = await tasks.create_task(session, other, kid, "Чужое", TaskIcon.BED, 9, kid)
    await tasks.mark(session, other, stranger.id, kid)
    await session.commit()

    mama = await adult_token(client)
    response = await client.post(
        "/api/tasks/confirm-all",
        json={"task_ids": [mine, str(stranger.id)]},
        headers=bearer(mama),
    )
    assert response.status_code == 404
    assert await accruals(session, mine) == 0
    assert await accruals(session, str(stranger.id)) == 0


async def test_repeat_with_same_key_returns_saved_result(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    ids = await marked_tasks(session, demo, [("Заправить кровать", 7), ("Убрать стол", 4)])
    mama = await adult_token(client)
    headers = with_key(mama, "confirm-all-0001")
    first = await client.post("/api/tasks/confirm-all", json={"task_ids": ids}, headers=headers)
    again = await client.post(
        "/api/tasks/confirm-all", json={"task_ids": list(reversed(ids))}, headers=headers
    )
    assert first.status_code == again.status_code == 200
    assert first.json() == again.json()
    assert [await accruals(session, i) for i in ids] == [1, 1]


@pytest.mark.parametrize("task_ids", [[], ["не-идентификатор"]])
async def test_invalid_batch_is_rejected(client: AsyncClient, demo: DemoFamily, task_ids: list):
    mama = await adult_token(client)
    response = await client.post(
        "/api/tasks/confirm-all", json={"task_ids": task_ids}, headers=bearer(mama)
    )
    assert response.status_code == 422


async def test_batch_over_hundred_tasks_is_rejected(client: AsyncClient, demo: DemoFamily):
    mama = await adult_token(client)
    ids = [str(demo.family_id)] * 101
    response = await client.post(
        "/api/tasks/confirm-all", json={"task_ids": ids}, headers=bearer(mama)
    )
    assert response.status_code == 422


@pytest.mark.risk
async def test_two_adults_confirming_overlapping_batches_accrue_once(
    client: AsyncClient, session: AsyncSession, demo: DemoFamily
):
    ids = await marked_tasks(session, demo, [(f"Дело {n}", n + 1) for n in range(8)])
    mama = await adult_token(client)
    papa = (await adult_tokens(client, PAPA_EMAIL, PAPA_PASSWORD))["access_token"]
    await warm_pool(client, mama)
    # Мама берёт дела с начала списка, папа — с конца, середина у них общая;
    # разный порядок в запросе не должен приводить к взаимной блокировке
    batches = [(mama, ids[:6]), (papa, list(reversed(ids[2:]))), (mama, ids), (papa, ids)]
    responses = await asyncio.gather(
        *(
            client.post(
                "/api/tasks/confirm-all",
                json={"task_ids": batch},
                headers=with_key(token, f"confirm-race-{n:02d}"),
            )
            for n, (token, batch) in enumerate(batches)
        )
    )
    assert [r.status_code for r in responses] == [200, 200, 200, 200]
    confirmed = [t["id"] for r in responses for t in r.json()["confirmed"]]
    assert sorted(confirmed) == sorted(ids)
    assert [await accruals(session, i) for i in ids] == [1] * 8
    assert await ledger.find_mismatched_accounts(session) == []
