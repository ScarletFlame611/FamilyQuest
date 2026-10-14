from collections.abc import AsyncIterator

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_session, make_engine
from app.main import app


async def test_health_ok(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_unavailable_without_database(client: AsyncClient):
    # Порт 1 на localhost закрыт: так база «остановлена» без управления контейнерами
    dead = make_engine("postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none")
    factory = async_sessionmaker(dead)

    async def dead_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = dead_session
    response = await client.get("/api/health")
    await dead.dispose()
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
