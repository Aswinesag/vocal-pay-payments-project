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

from app.database.crud import create_user
from app.database.database import AsyncSessionLocal
from app.database.schemas import UserRegistrationRequest


async def test_create_user():
    async with AsyncSessionLocal() as session:

        user = await create_user(
            session,
            UserRegistrationRequest(
                user_id="USR0001",
                full_name="Test User",
                email="test@example.com",
                phone_number="9876543210",
                preferred_language="en",
                speaker_embedding=[0.1] * 192,
                face_embedding=[0.2] * 512,
            ),
        )

        print("\n========== CREATE USER ==========")
        print(user.user_id)
        print(user.email)

        await session.rollback()


asyncio.run(test_create_user())