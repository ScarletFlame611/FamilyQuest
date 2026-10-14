import asyncio
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import session_factory
from app.modules.families import service as families
from app.modules.goals import service as goals
from app.modules.ledger import service as ledger
from app.modules.rewards import service as rewards
from app.modules.tasks import service as tasks
from app.modules.users import service as users

MAMA_EMAIL = "mama@familyquest.local"
PAPA_EMAIL = "papa@familyquest.local"
DEMO_PIN = "2580"


@dataclass(frozen=True)
class DemoFamily:
    family_id: uuid.UUID
    mama_id: uuid.UUID
    papa_id: uuid.UUID
    masha_id: uuid.UUID
    petya_id: uuid.UUID


async def remove_demo_family(session: AsyncSession) -> None:
    user_ids = [
        user_id
        for email in (MAMA_EMAIL, PAPA_EMAIL)
        if (user_id := await users.find_user_id_by_email(session, email))
    ]
    for user_id in user_ids:
        family_id = await families.find_family_id_by_user(session, user_id)
        if family_id:
            await families.delete_family(session, family_id)
    await users.delete_users(session, user_ids)


async def seed_demo_family(
    session: AsyncSession, mama_password: str, papa_password: str
) -> DemoFamily:
    await remove_demo_family(session)

    family_id = await families.create_family(session, "Демо-семья", "Europe/Moscow")
    await families.set_pin(session, family_id, DEMO_PIN)
    mama_user = await users.create_user(session, MAMA_EMAIL, mama_password, "Мама")
    papa_user = await users.create_user(session, PAPA_EMAIL, papa_password, "Папа")
    mama = await families.add_adult(session, family_id, mama_user, "Мама", "woman")
    papa = await families.add_adult(session, family_id, papa_user, "Папа", "man")
    masha = await families.add_child(session, family_id, "Маша", "fox")
    petya = await families.add_child(session, family_id, "Петя", "panda")

    # Цель создаётся раньше начислений, иначе они не попадут в её прогресс
    await goals.create_goal(session, family_id, "Поход с палатками всей семьёй", "tent", 300)

    await ledger.accrue(session, masha, 35, note="Стартовые баллы")
    history = [
        (petya, mama, "Пропылесосить", "vacuum", 10),
        (mama, mama, "Приготовить ужин", "cooking", 20),
        (papa, papa, "Помыть посуду", "dishes", 15),
    ]
    for assignee, author, title, icon, points in history:
        await tasks.record_completed_task(session, family_id, author, assignee, title, icon, points)

    for title, icon, points in [
        ("Убрать игрушки", "toys", 10),
        ("Покормить кота", "cat", 5),
        ("Полить цветы", "plant", 5),
    ]:
        await tasks.create_task(session, family_id, mama, title, icon, points, masha)
    for author, title, icon, points in [
        (papa, "Вынести мусор", "trash", 10),
        (mama, "Разобрать посуду", "dishes", 10),
        (mama, "Сложить носки", "socks", 5),
    ]:
        await tasks.create_task(session, family_id, author, title, icon, points, None)

    for title, icon, price in [
        ("Мороженое", "ice_cream", 20),
        ("Мультфильм перед сном", "cartoon", 30),
        ("Фломастеры", "markers", 40),
        ("Новый пазл", "puzzle", 60),
        ("Поход в парк", "park", 80),
        ("Конструктор", "construction_set", 150),
    ]:
        await rewards.create_reward(session, family_id, title, icon, price)

    return DemoFamily(family_id, mama, papa, masha, petya)


async def main() -> None:
    settings = get_settings()
    if not settings.demo_mama_password or not settings.demo_papa_password:
        sys.exit("Задайте DEMO_MAMA_PASSWORD и DEMO_PAPA_PASSWORD в .env")
    async with session_factory() as session:
        await seed_demo_family(
            session,
            settings.demo_mama_password.get_secret_value(),
            settings.demo_papa_password.get_secret_value(),
        )
        await session.commit()
    print(f"Демо-семья создана. Вход: {MAMA_EMAIL}, {PAPA_EMAIL}")


if __name__ == "__main__":
    asyncio.run(main())
