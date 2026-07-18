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

from app.core.config import settings
from app.core.logger import system_logger

# ==========================================================
# SQLAlchemy Engine
# ==========================================================

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    future=True,
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
# Declarative Base
# ==========================================================

class Base(DeclarativeBase):
    """
    Base class for all ORM models.
    """

    pass

system_logger.info(
    "Database engine initialized."
)