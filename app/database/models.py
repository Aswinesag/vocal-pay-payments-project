"""
app/database/models.py

SQLAlchemy ORM models for VocalPay.

This module defines all database entities used by the
application.
"""

from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from app.database.database import Base
from app.core.constants import (
    RiskLevel,
    TransactionStatus,
)

# ==========================================================
# Timestamp Mixin
# ==========================================================

class TimestampMixin:
    """
    Automatically tracks creation and update timestamps.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

# ==========================================================
# Primary Key Mixin
# ==========================================================

class PrimaryKeyMixin:
    """
    Provides an auto-incrementing primary key.
    """

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

# ==========================================================
# Transaction ID Mixin
# ==========================================================

class TransactionIDMixin:
    """
    Shared transaction identifier.
    """

    transaction_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )