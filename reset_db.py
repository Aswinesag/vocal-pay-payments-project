"""Destructively reset and reinitialize the VocalPay database schema."""

from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy import text

from app.database.database import async_engine, initialize_database
from app.database.models import Base


async def purge_and_reinitialize_database() -> None:
    """Drop every mapped table and recreate a clean database schema."""
    logger.warning("Database reset started; all existing records will be deleted.")

    async with async_engine.connect() as conn:
        try:
            logger.info("Disabling SQLite foreign-key enforcement.")
            await conn.execute(text("PRAGMA foreign_keys = OFF;"))
            await conn.commit()

            logger.info("Dropping all mapped database tables.")
            await conn.run_sync(Base.metadata.drop_all)
            await conn.commit()
            logger.success("All mapped database tables were dropped.")
        except Exception as exc:
            await conn.rollback()
            logger.bind(error=str(exc)).exception("Database purge failed.")
            raise
        finally:
            logger.info("Restoring SQLite foreign-key enforcement.")
            await conn.execute(text("PRAGMA foreign_keys = ON;"))
            await conn.commit()

    logger.info("Reinitializing the VocalPay database schema.")
    await initialize_database()
    logger.success("Database reset and schema reinitialization completed.")


if __name__ == "__main__":
    asyncio.run(purge_and_reinitialize_database())
