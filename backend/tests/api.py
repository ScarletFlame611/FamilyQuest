import asyncio
import uuid

from httpx import AsyncClient

from app.seed import MAMA_EMAIL
from tests.factories import MAMA_PASSWORD


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def with_key(token: str, key: str) -> dict[str, str]:
    return {**bearer(token), "Idempotency-Key": key}


async def adult_tokens(
    client: AsyncClient, email: str = MAMA_EMAIL, password: str = MAMA_PASSWORD
) -> dict[str, str]:
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


async def adult_token(client: AsyncClient) -> str:
    return (await adult_tokens(client))["access_token"]


async def child_tokens(client: AsyncClient, child_id: uuid.UUID) -> dict[str, str]:
    response = await client.post(
        "/api/child-mode/start",
        json={"child_id": str(child_id)},
        headers=bearer(await adult_token(client)),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def child_token(client: AsyncClient, child_id: uuid.UUID) -> str:
    return (await child_tokens(client, child_id))["access_token"]


async def warm_pool(client: AsyncClient, token: str, n: int = 12) -> None:
    # Без прогрева первый запрос идёт по готовому соединению, а остальные сначала
    # подключаются к базе, и гонка в тесте не воспроизводится
    await asyncio.gather(*(client.get("/api/me", headers=bearer(token)) for _ in range(n)))
