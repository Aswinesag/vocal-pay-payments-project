from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, TypeVar
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logger import system_logger
from app.database.database import AsyncSessionLocal
from app.database.models import (
    AuditLog,
    FraudEvent,
    PendingTransaction,
    Transaction,
    User,
)

# ==========================================================
# Type Aliases
# ==========================================================

ModelType = TypeVar(
    "ModelType",
    User,
    PendingTransaction,
    Transaction,
    FraudEvent,
    AuditLog,
)

DBSession = AsyncSession

# ==========================================================
# Atomic Session Manager
# ==========================================================

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[DBSession, None]:
    """
    Provides an atomic async database session.

    Automatically:
    - commits on success
    - rolls back on failure
    - closes the session
    """

    session = AsyncSessionLocal()

    try:
        yield session
        await session.commit()

    except Exception:
        await session.rollback()
        raise

    finally:
        await session.close()

# ==========================================================
# Utility Helpers
# ==========================================================

def utc_now() -> datetime:
    """
    Returns timezone-aware UTC datetime.
    """

    return datetime.now(timezone.utc)

async def get_by_id(
    db: DBSession,
    model: type[ModelType],
    object_id: int,
) -> ModelType | None:
    """
    Generic helper to fetch a model by primary key.
    """
    result = await db.execute(select(model).where(model.id == object_id))
    return result.scalar_one_or_none()

async def get_by_transaction_id(
    db: DBSession,
    model: type[ModelType],
    transaction_id: str,
) -> ModelType | None:
    """
    Fetches a model by transaction_id.
    """

    result = await db.execute(
        select(model).where(
            model.transaction_id == transaction_id
        )
    )

    return result.scalar_one_or_none()

# ==========================================================
# Database Safety Helpers
# ==========================================================

async def safe_flush(db: DBSession) -> None:
    """
    Flushes pending changes and converts database
    integrity errors into application-safe exceptions.
    """

    try:
        await db.flush()

    except IntegrityError as exc:
        system_logger.error(
            "Database integrity violation during flush.",
            extra={
                "error": str(exc),
            },
        )

        raise

    except SQLAlchemyError as exc:
        system_logger.error(
            "Database operation failed during flush.",
            extra={
                "error": str(exc),
            },
        )

        raise