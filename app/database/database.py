"""
app/database/database.py

Centralized database configuration.

Responsibilities
----------------
• SQLAlchemy engine creation
• Session factory
• Declarative Base
• SQLite configuration
"""

from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    sessionmaker,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from collections.abc import Generator
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logger import system_logger
from contextlib import contextmanager
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path

# ==========================================================
# Database URLs
# ==========================================================

DATABASE_URL = settings.DATABASE_URL

ASYNC_DATABASE_URL = DATABASE_URL.replace(
    "sqlite:///",
    "sqlite+aiosqlite:///",
)

# ==========================================================
# Declarative Base
# ==========================================================

class Base(DeclarativeBase):
    """
    Base class for all ORM models.
    """

    pass

# ==========================================================
# SQLAlchemy Engine
# ==========================================================

engine = create_engine(
    DATABASE_URL,
    echo=settings.SQL_ECHO,
    future=True,
)

# ==========================================================
# Async Engine
# ==========================================================

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# ==========================================================
# Session Factory
# ==========================================================

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

# ==========================================================
# Async Session Factory
# ==========================================================

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ==========================================================
# Database Dependency
# ==========================================================

def get_db() -> Generator[Session, None, None]:
    """
    Provides a database session.

    A new SQLAlchemy session is created for every request
    and is automatically closed afterwards.
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()

# ==========================================================
# Session Context Manager
# ==========================================================

@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provides a transactional database scope.
    """

    session = SessionLocal()

    try:
        yield session
        session.commit()

    except Exception:

        session.rollback()
        raise

    finally:

        session.close()

# ==========================================================
# Database Health
# ==========================================================

def check_database_connection() -> bool:
    """
    Returns True if the SQLite database
    is reachable.
    """

    try:

        with SessionLocal() as db:

            db.execute(
                text("SELECT 1")
            )

        return True

    except Exception as exc:

        system_logger.exception(
            f"Database connection failed: {exc}"
        )

        return False

# ==========================================================
# SQLite Connection Configuration
# ==========================================================

@event.listens_for(engine, "connect")
def configure_sqlite(dbapi_connection, connection_record) -> None:
    """
    Configure SQLite every time a new connection is opened.
    """

    cursor = dbapi_connection.cursor()

    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Better concurrent read/write performance
    cursor.execute("PRAGMA journal_mode = WAL;")

    # Improved durability/performance balance
    cursor.execute("PRAGMA synchronous = NORMAL;")

    cursor.close()

    system_logger.info(
        "SQLite PRAGMA configuration applied."
    )

# ==========================================================
# Database Initialization
# ==========================================================

def initialize_database() -> None:
    """
    Creates all database tables.

    This function should be called once during
    FastAPI startup.
    """

    try:

        system_logger.info(
            "Initializing SQLite database..."
        )

        Base.metadata.create_all(bind=engine)

        system_logger.info(
            "Database tables created successfully."
        )

    except SQLAlchemyError as exc:

        system_logger.exception(
            f"Database initialization failed: {exc}"
        )

        raise

def init_db() -> None:
    """
    Public database initialization entry point.
    """

    initialize_database()

# ==========================================================
# Database Validation
# ==========================================================

def validate_database() -> bool:
    """
    Validates that the database is ready for use.

    Checks:
    - SQLite connection
    - Database file existence
    - Basic SQL execution

    Returns
    -------
    bool
        True if validation succeeds.
    """

    try:

        # Validate connection
        with SessionLocal() as session:

            session.execute(
                text("SELECT 1")
            )

        # Validate SQLite file
        database_url = settings.DATABASE_URL

        if database_url.startswith("sqlite:///"):

            database_path = Path(
                database_url.replace("sqlite:///", "")
            )

            if not database_path.exists():

                system_logger.error(
                    f"Database file not found: {database_path}"
                )

                return False

        system_logger.info(
            "Database validation successful."
        )

        return True

    except Exception as exc:

        system_logger.exception(
            f"Database validation failed: {exc}"
        )

        return False

# ==========================================================
# Database Shutdown
# ==========================================================

def shutdown_database() -> None:
    """
    Gracefully shuts down the database engine.

    This function should be called during
    FastAPI shutdown.
    """

    system_logger.info(
        "Shutting down database engine..."
    )

    engine.dispose()

    system_logger.info(
        "Database engine shutdown complete."
    )

async def close_db() -> None:
    """
    Gracefully shuts down both database engines.
    """

    await async_engine.dispose()
    shutdown_database()

# ==========================================================
# Database Information
# ==========================================================

def get_database_information() -> dict[str, object]:
    """
    Returns lightweight database metadata.
    """

    return {
        "engine": engine.name,
        "database_url": settings.DATABASE_URL,
        "sqlite": engine.name == "sqlite",
        "connected": check_database_connection(),
    }

# ==========================================================
# Engine Access
# ==========================================================

def get_engine():
    """
    Returns the SQLAlchemy engine.
    """

    return engine

system_logger.info(
    "Database session utilities initialized."
)
