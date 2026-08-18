"""Asynchronous SQLAlchemy runtime configuration for VocalPay."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
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
    except SQLAlchemyError:
        logger.exception("Database session failed; rolling back transaction.")
        await session.rollback()
        raise
    except Exception as exc:
        logger.bind(exception_type=type(exc).__name__).debug(
            "Request exited through the database dependency; rolling back open work."
        )
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
        async with async_engine.connect() as conn:
            await conn.execute(text("PRAGMA foreign_keys = OFF"))
            await conn.commit()
            await conn.run_sync(Base.metadata.create_all)
            await conn.commit()
            await _ensure_pending_attempt_columns(conn)
            await _ensure_nullable_fraud_user(conn)
            await conn.execute(text("PRAGMA foreign_keys = ON"))
            await conn.commit()
    except SQLAlchemyError:
        logger.exception("SQLAlchemy failed to initialize the database schema.")
        raise
    except Exception:
        logger.exception("Unexpected database initialization failure.")
        raise

    logger.info("Asynchronous SQLite database initialized successfully.")


async def _ensure_nullable_fraud_user(conn: AsyncConnection) -> None:
    """Preserve fraud records while relaxing the legacy user constraint."""
    if conn.dialect.name != "sqlite":
        return

    columns = (await conn.execute(text("PRAGMA table_info(fraud_events)"))).all()
    user_column = next((column for column in columns if column[1] == "user_id"), None)
    if user_column is None or not bool(user_column[3]):
        return

    logger.info("Migrating fraud_events.user_id to nullable storage.")
    await conn.execute(text("DROP TABLE IF EXISTS fraud_events_new"))
    await conn.execute(
        text(
            "CREATE TABLE fraud_events_new ("
            "user_id VARCHAR(64), event_type VARCHAR(50) NOT NULL, "
            "risk_level VARCHAR(20) NOT NULL, blocked BOOLEAN NOT NULL, "
            "speaker_score FLOAT, face_score FLOAT, fraud_score FLOAT, "
            "reason TEXT NOT NULL, replay_attack BOOLEAN NOT NULL, "
            "id INTEGER NOT NULL PRIMARY KEY, transaction_id VARCHAR(64) NOT NULL, "
            "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, "
            "FOREIGN KEY(user_id) REFERENCES users (user_id))"
        )
    )
    column_names = (
        "user_id,event_type,risk_level,blocked,speaker_score,face_score,"
        "fraud_score,reason,replay_attack,id,transaction_id,created_at,updated_at"
    )
    await conn.execute(
        text(
            f"INSERT INTO fraud_events_new ({column_names}) "
            f"SELECT {column_names} FROM fraud_events"
        )
    )
    await conn.execute(text("DROP TABLE fraud_events"))
    await conn.execute(text("ALTER TABLE fraud_events_new RENAME TO fraud_events"))
    await conn.execute(text("CREATE INDEX idx_fraud_event ON fraud_events (event_type)"))
    await conn.execute(text("CREATE INDEX idx_fraud_risk ON fraud_events (risk_level)"))
    await conn.execute(text("CREATE INDEX ix_fraud_events_user_id ON fraud_events (user_id)"))
    await conn.execute(
        text(
            "CREATE UNIQUE INDEX ix_fraud_events_transaction_id "
            "ON fraud_events (transaction_id)"
        )
    )
    await conn.commit()
    logger.info("fraud_events.user_id migration completed.")


async def _ensure_pending_attempt_columns(conn: AsyncConnection) -> None:
    """Add bounded verification-attempt state to existing SQLite databases."""
    if conn.dialect.name != "sqlite":
        return

    columns = {
        column[1]
        for column in (
            await conn.execute(text("PRAGMA table_info(pending_transactions)"))
        ).all()
    }
    if "verification_attempts" not in columns:
        await conn.execute(
            text(
                "ALTER TABLE pending_transactions ADD COLUMN "
                "verification_attempts INTEGER NOT NULL DEFAULT 0"
            )
        )
    if "max_verification_attempts" not in columns:
        await conn.execute(
            text(
                "ALTER TABLE pending_transactions ADD COLUMN "
                "max_verification_attempts INTEGER NOT NULL DEFAULT 5"
            )
        )
    await conn.commit()


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
