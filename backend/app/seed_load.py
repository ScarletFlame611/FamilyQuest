import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import session_factory
from app.modules.families import service as families
from app.modules.goals import service as goals
from app.modules.goals.enums import GoalIcon
from app.modules.tasks import service as tasks
from app.modules.tasks.enums import TaskIcon
from app.modules.users import service as users
from app.seed import DEMO_PIN


def load_email(n: int) -> str:
    return f"load-{n:04d}@familyquest.local"


async def remove_load_families(session: AsyncSession, limit: int) -> None:
    user_ids = []
    for n in range(1, limit + 1):
        user_id = await users.find_user_id_by_email(session, load_email(n))
        if user_id is None:
            continue
        user_ids.append(user_id)
        family_id = await families.find_family_id_by_user(session, user_id)
        if family_id:
            await families.delete_family(session, family_id)
    await users.delete_users(session, user_ids)


async def create_load_family(session: AsyncSession, n: int, password: str, tasks_per_child: int):
    family_id = await families.create_family(session, f"Нагрузка {n:04d}", "Europe/Moscow")
    await families.set_pin(session, family_id, DEMO_PIN)
    user_id = await users.create_user(session, load_email(n), password, "Мама")
    adult = await families.add_adult(session, family_id, user_id, "Мама", "woman")
    child = await families.add_child(session, family_id, "Маша", "fox")
    await goals.create_goal(session, family_id, "Поход", GoalIcon.TENT, 300)
    await tasks.create_assigned_tasks(
        session,
        family_id,
        adult,
        child,
        [(f"Дело {i}", TaskIcon.TOYS, 5) for i in range(tasks_per_child)],
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Готовит семьи для нагрузочного теста")
    parser.add_argument("families", type=int)
    # Столько же активных дел, сколько у ребёнка на экране; взамен засчитанного
    # дела нагрузочный сценарий сам создаёт новое
    parser.add_argument("--tasks", type=int, default=5)
    args = parser.parse_args()
    password = get_settings().load_password
    if password is None:
        sys.exit("Задайте LOAD_PASSWORD в .env")
    async with session_factory() as session:
        # Прошлые нагрузочные семьи удаляются с запасом, даже если их было больше
        await remove_load_families(session, max(args.families, 1000))
        await session.commit()
        for n in range(1, args.families + 1):
            await create_load_family(session, n, password.get_secret_value(), args.tasks)
            if n % 50 == 0:
                await session.commit()
        await session.commit()
    print(f"Готово семей: {args.families}, дел у каждого ребёнка: {args.tasks}")


if __name__ == "__main__":
    asyncio.run(main())
