"""Seed a deterministic VocalPay user profile for local integration testing."""

from __future__ import annotations

import asyncio
import math

from loguru import logger
from sqlalchemy import select

from app.core.config import settings
from app.database.database import AsyncSessionLocal, initialize_database
from app.database.models import User


async def seed_test_profiles() -> None:
    """Create the canonical test user when it is not already present."""
    await initialize_database()

    speaker_values = [
        math.sin((index + 1) * 0.173) + math.cos((index + 1) * 0.071)
        for index in range(192)
    ]
    speaker_norm = math.sqrt(sum(value * value for value in speaker_values))
    speaker_embedding = [float(value / speaker_norm) for value in speaker_values]

    face_values = [
        math.sin((index + 1) * 0.113) - math.cos((index + 1) * 0.047)
        for index in range(512)
    ]
    face_norm = math.sqrt(sum(value * value for value in face_values))
    face_embedding = [float(value / face_norm) for value in face_values]

    async with AsyncSessionLocal() as session:
        try:
            existing_user = await session.scalar(
                select(User).where(User.user_id == "test_user_01")
            )
            if existing_user is not None:
                logger.bind(
                    user_id="test_user_01",
                    database=settings.DATABASE_URL,
                ).info("Test user already exists; seed insert skipped.")
                return

            session.add(
                User(
                    user_id="test_user_01",
                    full_name="Jane Doe",
                    email="janedoe@vocalpay.local",
                    phone_number="+15550199",
                    speaker_embedding=speaker_embedding,
                    face_embedding=face_embedding,
                    is_active=True,
                    is_verified=True,
                    failed_attempts=0,
                    preferred_language="en",
                )
            )
            await session.commit()
            logger.bind(
                user_id="test_user_01",
                speaker_dimensions=len(speaker_embedding),
                face_dimensions=len(face_embedding),
            ).success("Test user seeded successfully.")
        except Exception as exc:
            await session.rollback()
            logger.bind(user_id="test_user_01", error=str(exc)).exception(
                "Test user seeding failed."
            )
            raise


if __name__ == "__main__":
    asyncio.run(seed_test_profiles())
