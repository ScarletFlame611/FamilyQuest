import asyncio
import sys

from app.core.db import session_factory
from app.modules.ledger import service as ledger


async def main() -> None:
    async with session_factory() as session:
        mismatched = await ledger.find_mismatched_accounts(session)
    if mismatched:
        sys.exit(f"Баланс расходится с журналом у счетов: {len(mismatched)}")
    print("Сверка: баланс всех счетов равен сумме журнала")


if __name__ == "__main__":
    asyncio.run(main())
