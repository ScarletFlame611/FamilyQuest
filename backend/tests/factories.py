from sqlalchemy.ext.asyncio import AsyncSession

from app.seed import DemoFamily, seed_demo_family

MAMA_PASSWORD = "mama-test-password"
PAPA_PASSWORD = "papa-test-password"


async def seed(session: AsyncSession) -> DemoFamily:
    demo = await seed_demo_family(session, MAMA_PASSWORD, PAPA_PASSWORD)
    await session.commit()
    return demo
