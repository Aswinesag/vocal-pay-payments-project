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

# ==========================================================
# User Model
# ==========================================================

class User(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    Registered VocalPay user.
    """

    __tablename__ = "users"

    # ------------------------------------------------------
    # Identity
    # ------------------------------------------------------

    user_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    # ------------------------------------------------------
    # Biometrics
    # ------------------------------------------------------

    speaker_embedding: Mapped[list[float]] = mapped_column(
        JSON,
        nullable=False,
    )

    face_embedding: Mapped[list[float]] = mapped_column(
        JSON,
        nullable=False,
    )

    # ------------------------------------------------------
    # Account Status
    # ------------------------------------------------------

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    failed_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # ------------------------------------------------------
    # Optional Profile
    # ------------------------------------------------------

    preferred_language: Mapped[str] = mapped_column(
        String(20),
        default="en",
        nullable=False,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

# ==========================================================
# Pending Transaction Model
# ==========================================================

class PendingTransaction(
    Base,
    PrimaryKeyMixin,
    TransactionIDMixin,
    TimestampMixin,
):
    """
    Stores temporary transactions awaiting
    OTP or challenge verification.
    """

    __tablename__ = "pending_transactions"

    # ------------------------------------------------------
    # User Information
    # ------------------------------------------------------

    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )

    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # ------------------------------------------------------
    # Risk Evaluation
    # ------------------------------------------------------

    risk_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    # ------------------------------------------------------
    # Verification
    # ------------------------------------------------------

    verification_secret: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # ------------------------------------------------------
    # AI Decision
    # ------------------------------------------------------

    speaker_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    face_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    fraud_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    replay_attack: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

# ==========================================================
# Transaction Model
# ==========================================================

class Transaction(
    Base,
    PrimaryKeyMixin,
    TransactionIDMixin,
    TimestampMixin,
):
    """
    Permanent transaction ledger.
    """

    __tablename__ = "transactions"

    # ------------------------------------------------------
    # User Information
    # ------------------------------------------------------

    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )

    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # ------------------------------------------------------
    # Transaction Result
    # ------------------------------------------------------

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    risk_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    # ------------------------------------------------------
    # Biometric Scores
    # ------------------------------------------------------

    speaker_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    face_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    fraud_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # ------------------------------------------------------
    # Explainable AI
    # ------------------------------------------------------

    xai_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # ------------------------------------------------------
    # Processing Metadata
    # ------------------------------------------------------

    processing_time_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    replay_attack: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

# ==========================================================
# Fraud Event Model
# ==========================================================

class FraudEvent(
    Base,
    PrimaryKeyMixin,
    TransactionIDMixin,
    TimestampMixin,
):
    """
    Stores security and fraud-related events.
    """

    __tablename__ = "fraud_events"

    # ------------------------------------------------------
    # User Information
    # ------------------------------------------------------

    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------
    # Fraud Details
    # ------------------------------------------------------

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    risk_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    blocked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # ------------------------------------------------------
    # Detection Scores
    # ------------------------------------------------------

    speaker_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    face_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    fraud_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # ------------------------------------------------------
    # Investigation
    # ------------------------------------------------------

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    replay_attack: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )