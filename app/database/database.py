"""Asynchronous SQLAlchemy runtime configuration for VocalPay."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


DATABASE_URL: str = settings.DATABASE_URL


class Base(DeclarativeBase):
    """Declarative base shared by all VocalPay ORM models."""


async_engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield one asynchronous database session per API request."""
    session = AsyncSessionLocal()
    logger.debug("Opened asynchronous database session.")

    try:
        yield session
    except Exception:
        logger.exception("Database session failed; rolling back transaction.")
        await session.rollback()
        raise
    finally:
        await session.close()
        logger.debug("Closed asynchronous database session.")


async def initialize_database() -> None:
    """Import ORM mappings and create missing database tables asynchronously."""
    from app.database.models import Base

    logger.info("Initializing asynchronous SQLite database.")

    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except SQLAlchemyError:
        logger.exception("SQLAlchemy failed to initialize the database schema.")
        raise
    except Exception:
        logger.exception("Unexpected database initialization failure.")
        raise

    logger.info("Asynchronous SQLite database initialized successfully.")


async def close_database() -> None:
    """Dispose of the process-wide asynchronous database engine."""
    logger.info("Disposing asynchronous database engine.")
    await async_engine.dispose()
    logger.info("Asynchronous database engine disposed successfully.")


__all__ = (
    "DATABASE_URL",
    "Base",
    "async_engine",
    "AsyncSessionLocal",
    "get_async_db",
    "initialize_database",
    "close_database",
)
