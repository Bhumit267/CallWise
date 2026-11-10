"""Self-cleaning teardown for E2E tests: deletes test businesses outside original seeds."""
import asyncio
from sqlalchemy import text
from callwise.db.session import AsyncSessionLocal

async def clean():
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "DELETE FROM businesses WHERE id NOT IN ("
                "'11111111-1111-1111-1111-111111111111', "
                "'22222222-2222-2222-2222-222222222222')"
            )
        )
        await session.commit()

if __name__ == "__main__":
    asyncio.run(clean())
