import asyncio

from app.database.crud import (
    DBSession,
    get_db_session,
    utc_now,
)

print("\n========== CRUD FOUNDATION ==========")

print(DBSession)

print("\n========== UTC NOW ==========")

print(utc_now())


async def test_session():
    async with get_db_session() as db:
        print("\n========== SESSION ==========")
        print(type(db).__name__)


asyncio.run(test_session())