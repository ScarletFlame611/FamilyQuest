import io
import zipfile
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.clock import now_utc
from app.core.ids import new_id
from app.modules.exports import service as exports
from app.modules.jobs import service as jobs
from app.seed import DemoFamily
from app.worker import process_one
from tests.api import adult_token, bearer, child_token, with_key

pytestmark = [pytest.mark.anyio, pytest.mark.us48]

LEASE = timedelta(seconds=60)


async def requested(client: AsyncClient, token: str) -> dict:
    response = await client.post("/api/family/exports", headers=with_key(token, str(new_id())))
    assert response.status_code == 202, response.text
    return response.json()


async def test_export_is_queued_once_and_built_by_worker(
    client: AsyncClient, demo: DemoFamily, engine: AsyncEngine
):
    mama = await adult_token(client)
    first = await requested(client, mama)
    assert first["status"] == "pending"
    assert first["job_status"] == "queued"
    # Повторное нажатие, пока архив готовится, не ставит второе задание
    assert (await requested(client, mama))["id"] == first["id"]

    assert await process_one(async_sessionmaker(engine, expire_on_commit=False), LEASE)
    [ready] = (await client.get("/api/family/exports", headers=bearer(mama))).json()
    assert ready["status"] == "ready"
    assert ready["job_status"] == "done"

    response = await client.get(f"/api/family/exports/{ready['id']}/file", headers=bearer(mama))
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert set(archive.namelist()) == {
        "прочитай меня.txt",
        "участники.csv",
        "дела.csv",
        "история баллов.csv",
        "награды.csv",
        "покупки.csv",
        "цели.csv",
        "детский режим.csv",
    }
    history = archive.read("история баллов.csv").decode("utf-8-sig")
    assert "Маша;" in history and "Стартовые баллы" in history
    everything = b"".join(archive.read(name) for name in archive.namelist()).lower()
    assert b"argon2" not in everything
    assert b"token" not in everything


async def test_only_adults_of_the_family_get_the_export(client: AsyncClient, demo: DemoFamily):
    mama = await adult_token(client)
    export = await requested(client, mama)
    masha = await child_token(client, demo.masha_id)
    assert (await client.get("/api/family/exports", headers=bearer(masha))).status_code == 403
    assert (await client.post("/api/family/exports", headers=bearer(masha))).status_code == 403

    stranger = await client.post(
        "/api/auth/register",
        json={
            "email": "stranger@example.com",
            "password": "stranger-password",
            "name": "Чужой",
            "avatar": "man",
            "family_name": "Чужая семья",
        },
    )
    other = stranger.json()["access_token"]
    file = await client.get(f"/api/family/exports/{export['id']}/file", headers=bearer(other))
    assert file.status_code == 404
    assert (await client.get("/api/family/exports", headers=bearer(other))).json() == []


async def test_job_of_crashed_worker_is_finished_by_next_worker(
    client: AsyncClient, demo: DemoFamily, engine: AsyncEngine, session: AsyncSession
):
    mama = await adult_token(client)
    export = await requested(client, mama)
    # Первый воркер забрал задание и упал: аренда истекает сразу, а результата нет
    crashed = await jobs.claim(session, now_utc(), timedelta(0))
    await session.commit()
    assert crashed is not None and str(crashed.id) == export["job_id"]

    assert await process_one(async_sessionmaker(engine, expire_on_commit=False), LEASE)
    state = await jobs.get_job(session, crashed.id)
    assert state.attempts == 2
    assert state.process_count == 1
    [ready] = (await client.get("/api/family/exports", headers=bearer(mama))).json()
    assert ready["id"] == export["id"] and ready["status"] == "ready"


async def test_late_worker_does_not_overwrite_result(
    client: AsyncClient, demo: DemoFamily, engine: AsyncEngine, session: AsyncSession
):
    mama = await adult_token(client)
    await requested(client, mama)
    late = await jobs.claim(session, now_utc(), timedelta(0))
    await session.commit()
    assert late is not None
    assert await process_one(async_sessionmaker(engine, expire_on_commit=False), LEASE)
    [done] = (await client.get("/api/family/exports", headers=bearer(mama))).json()

    # Опоздавший воркер дособрал архив и пытается его сохранить
    moment = now_utc()
    with pytest.raises(jobs.StaleOwnerError):
        await exports.run_export_job(
            session, late.payload, moment, lambda: jobs.complete(session, late, moment)
        )
    await session.rollback()
    [after] = (await client.get("/api/family/exports", headers=bearer(mama))).json()
    assert after["ready_at"] == done["ready_at"]
    assert (await jobs.get_job(session, late.id)).process_count == 1
