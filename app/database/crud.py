from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from datetime import timedelta
from typing import AsyncGenerator, TypeVar
from sqlalchemy import select
from sqlalchemy import delete
from sqlalchemy import func
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
from app.database.schemas import UserRegistrationRequest

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

async def create_user(
    session: AsyncSession,
    user_data: UserRegistrationRequest,
) -> User:
    """
    Create a new user record.

    Raises:
        ValueError:
            If the user_id, email, or phone number already exists.

        SQLAlchemyError:
            If the database operation fails.
    """

    # --------------------------------------------------
    # Duplicate User ID
    # --------------------------------------------------

    existing = await session.scalar(
        select(User).where(User.user_id == user_data.user_id)
    )

    if existing is not None:
        raise ValueError(
            f"User ID '{user_data.user_id}' already exists."
        )

    # --------------------------------------------------
    # Duplicate Email
    # --------------------------------------------------

    existing = await session.scalar(
        select(User).where(User.email == user_data.email)
    )

    if existing is not None:
        raise ValueError(
            f"Email '{user_data.email}' already exists."
        )

    # --------------------------------------------------
    # Duplicate Phone
    # --------------------------------------------------

    existing = await session.scalar(
        select(User).where(
            User.phone_number == user_data.phone_number
        )
    )

    if existing is not None:
        raise ValueError(
            f"Phone number '{user_data.phone_number}' already exists."
        )

    # --------------------------------------------------
    # Create ORM Object
    # --------------------------------------------------

    user = User(
        user_id=user_data.user_id,
        full_name=user_data.full_name,
        email=user_data.email,
        phone_number=user_data.phone_number,
        preferred_language=user_data.preferred_language,
        speaker_embedding=user_data.speaker_embedding,
        face_embedding=user_data.face_embedding,
        is_active=True,
        is_verified=False,
        failed_attempts=0,
    )

    session.add(user)

    try:
        await safe_flush(session)

    except IntegrityError as exc:
        raise ValueError(
            "A user with the same unique information already exists."
        ) from exc

    return user

async def get_user_by_user_id(
    session: AsyncSession,
    user_id: str,
) -> User | None:
    """
    Retrieve a user by their unique user ID.

    Returns:
        User if found, otherwise None.
    """

    return await session.scalar(
        select(User).where(
            User.user_id == user_id
        )
    )

async def get_user_by_email(
    session: AsyncSession,
    email: str,
) -> User | None:
    """
    Retrieve a user by email address.

    Returns:
        User if found, otherwise None.
    """

    return await session.scalar(
        select(User).where(
            User.email == email
        )
    )

async def get_user_by_phone(
    session: AsyncSession,
    phone_number: str,
) -> User | None:
    """
    Retrieve a user by phone number.

    Returns:
        User if found, otherwise None.
    """

    return await session.scalar(
        select(User).where(
            User.phone_number == phone_number
        )
    )

async def update_user_profile(
    session: AsyncSession,
    user: User,
    *,
    full_name: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
    preferred_language: str | None = None,
) -> User:
    """
    Update mutable user profile fields.

    Only fields explicitly provided are updated.

    Returns:
        Updated ORM User object.
    """

    if full_name is not None:
        user.full_name = full_name

    if email is not None:
        user.email = email

    if phone_number is not None:
        user.phone_number = phone_number

    if preferred_language is not None:
        user.preferred_language = preferred_language

    await safe_flush(session)

    return user

async def update_biometric_embeddings(
    session: AsyncSession,
    user: User,
    *,
    speaker_embedding: list[float] | None = None,
    face_embedding: list[float] | None = None,
) -> User:
    """
    Update biometric embeddings after successful enrollment
    or biometric re-registration.

    Returns:
        Updated ORM User object.
    """

    if speaker_embedding is not None:
        user.speaker_embedding = speaker_embedding

    if face_embedding is not None:
        user.face_embedding = face_embedding

    await safe_flush(session)

    return user

async def increment_failed_attempts(
    session: AsyncSession,
    user: User,
) -> User:
    """
    Increment the user's failed authentication counter.

    Returns:
        Updated ORM User object.
    """

    user.failed_attempts += 1

    await safe_flush(session)

    return user

async def reset_failed_attempts(
    session: AsyncSession,
    user: User,
) -> User:
    """
    Reset the failed authentication counter after
    a successful authentication.
    """

    user.failed_attempts = 0

    await safe_flush(session)

    return user

async def deactivate_user(
    session: AsyncSession,
    user: User,
) -> User:
    """
    Deactivate a user account.

    The account remains in the database but
    cannot authenticate.
    """

    user.is_active = False

    await safe_flush(session)

    return user

async def activate_user(
    session: AsyncSession,
    user: User,
) -> User:
    """
    Reactivate a previously deactivated user account.
    """

    user.is_active = True

    await safe_flush(session)

    return user

async def update_last_login(
    session: AsyncSession,
    user: User,
) -> User:
    """
    Update the user's last successful login timestamp.
    """

    user.last_login_at = utc_now()

    await safe_flush(session)

    return user

async def create_pending_transaction(
    session: AsyncSession,
    pending: PendingTransaction,
) -> PendingTransaction:
    """
    Persist a pending transaction.

    The PendingTransaction ORM object must already be fully
    populated by the service layer.
    """

    session.add(pending)

    await safe_flush(session)

    return pending

async def get_pending_transaction_by_transaction_id(
    session: AsyncSession,
    transaction_id: str,
) -> PendingTransaction | None:
    """
    Retrieve a pending transaction using its transaction ID.

    Returns:
        PendingTransaction if found, otherwise None.
    """

    return await session.scalar(
        select(PendingTransaction).where(
            PendingTransaction.transaction_id == transaction_id
        )
    )

async def get_pending_transaction_by_verification_secret(
    session: AsyncSession,
    verification_secret: str,
) -> PendingTransaction | None:
    """
    Retrieve a pending transaction using its verification secret.

    The verification secret may represent:
    - an OTP
    - a challenge identifier
    - another verification token

    Returns:
        PendingTransaction if found, otherwise None.
    """

    return await session.scalar(
        select(PendingTransaction).where(
            PendingTransaction.verification_secret == verification_secret
        )
    )

async def update_pending_status(
    session: AsyncSession,
    pending: PendingTransaction,
    status: str,
) -> PendingTransaction:
    """
    Update the status of a pending transaction.

    This function performs only the persistence operation.
    Status transition validation belongs to the service layer.

    Returns:
        Updated PendingTransaction ORM object.
    """

    pending.status = status

    await safe_flush(session)

    return pending

async def extend_pending_expiry(
    session: AsyncSession,
    pending: PendingTransaction,
    extension: timedelta,
) -> PendingTransaction:
    """
    Extend the expiration time of a pending transaction.

    The service layer decides whether an extension
    is allowed.

    Returns:
        Updated PendingTransaction ORM object.
    """

    pending.expires_at += extension

    await safe_flush(session)

    return pending

async def delete_pending_transaction(
    session: AsyncSession,
    pending: PendingTransaction,
) -> None:
    """
    Delete a pending transaction.

    This is typically called after:
    - successful verification
    - permanent rejection
    - manual cancellation
    """

    await session.delete(pending)

    await safe_flush(session)

async def delete_expired_pending_transactions(
    session: AsyncSession,
    *,
    reference_time: datetime | None = None,
) -> int:
    """
    Delete all expired pending transactions.

    Args:
        reference_time:
            Optional timestamp for comparison.
            Defaults to utc_now().

    Returns:
        Number of deleted rows.
    """

    reference_time = reference_time or utc_now()

    result = await session.execute(
        delete(PendingTransaction).where(
            PendingTransaction.expires_at < reference_time
        )
    )

    await safe_flush(session)

    return result.rowcount or 0

async def create_transaction(
    session: AsyncSession,
    transaction: Transaction,
) -> Transaction:
    """
    Persist a completed transaction.

    The Transaction ORM object must already be fully
    constructed by the service layer.

    Returns:
        Persisted Transaction ORM object.
    """

    session.add(transaction)

    await safe_flush(session)

    return transaction

async def get_transaction_by_transaction_id(
    session: AsyncSession,
    transaction_id: str,
) -> Transaction | None:
    """
    Retrieve a completed transaction by its unique
    transaction ID.

    Returns:
        Transaction if found, otherwise None.
    """

    return await session.scalar(
        select(Transaction).where(
            Transaction.transaction_id == transaction_id
        )
    )

async def get_transactions_by_user_id(
    session: AsyncSession,
    user_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[Transaction]:
    """
    Retrieve a paginated list of transactions
    belonging to a user.

    Results are ordered from newest to oldest.
    """

    result = await session.scalars(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(result)

async def get_recent_transactions(
    session: AsyncSession,
    *,
    limit: int = 10,
) -> list[Transaction]:
    """
    Retrieve the most recent completed transactions
    across all users.

    Primarily intended for:
    - admin dashboards
    - monitoring
    - system analytics
    """

    result = await session.scalars(
        select(Transaction)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    )

    return list(result)

async def get_transaction_count(
    session: AsyncSession,
    *,
    user_id: str | None = None,
) -> int:
    """
    Count completed transactions.

    If user_id is provided, returns the count
    for that specific user.
    Otherwise returns the global count.
    """

    stmt = select(func.count(Transaction.id))

    if user_id is not None:
        stmt = stmt.where(Transaction.user_id == user_id)

    result = await session.scalar(stmt)

    return int(result or 0)

async def get_total_transaction_amount(
    session: AsyncSession,
    *,
    user_id: str | None = None,
) -> float:
    """
    Calculate the total amount of completed transactions.

    If user_id is provided, only that user's transactions
    are included.
    """

    stmt = select(func.sum(Transaction.amount))

    if user_id is not None:
        stmt = stmt.where(Transaction.user_id == user_id)

    result = await session.scalar(stmt)

    return float(result or 0.0)

async def get_successful_transaction_count(
    session: AsyncSession,
    *,
    user_id: str | None = None,
) -> int:
    """
    Count successful transactions.
    """

    stmt = select(func.count(Transaction.id)).where(
        Transaction.status == "SUCCESS"
    )

    if user_id is not None:
        stmt = stmt.where(
            Transaction.user_id == user_id
        )

    result = await session.scalar(stmt)

    return int(result or 0)

async def get_failed_transaction_count(
    session: AsyncSession,
    *,
    user_id: str | None = None,
) -> int:
    """
    Count failed transactions.
    """

    stmt = select(func.count(Transaction.id)).where(
        Transaction.status == "FAILED"
    )

    if user_id is not None:
        stmt = stmt.where(
            Transaction.user_id == user_id
        )

    result = await session.scalar(stmt)

    return int(result or 0)

async def get_average_transaction_amount(
    session: AsyncSession,
    *,
    user_id: str | None = None,
) -> float:
    """
    Calculate the average transaction amount.

    Returns 0.0 when no matching transactions exist.
    """

    stmt = select(func.avg(Transaction.amount))

    if user_id is not None:
        stmt = stmt.where(
            Transaction.user_id == user_id
        )

    result = await session.scalar(stmt)

    return float(result or 0.0)

async def create_fraud_event(
    session: AsyncSession,
    fraud_event: FraudEvent,
) -> FraudEvent:
    """
    Persist a fraud detection event.

    The FraudEvent ORM object must already be fully
    populated by the service layer.

    Returns:
        Persisted FraudEvent ORM object.
    """

    session.add(fraud_event)

    await safe_flush(session)

    return fraud_event

async def get_fraud_event_by_transaction_id(
    session: AsyncSession,
    transaction_id: str,
) -> FraudEvent | None:
    """
    Retrieve the fraud event associated with a transaction.

    Returns:
        FraudEvent if found, otherwise None.
    """

    return await session.scalar(
        select(FraudEvent).where(
            FraudEvent.transaction_id == transaction_id
        )
    )

async def get_fraud_events_by_user_id(
    session: AsyncSession,
    user_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[FraudEvent]:
    """
    Retrieve fraud events belonging to a user.

    Results are ordered from newest to oldest.
    """

    result = await session.scalars(
        select(FraudEvent)
        .where(FraudEvent.user_id == user_id)
        .order_by(FraudEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(result)

async def get_high_risk_events(
    session: AsyncSession,
    *,
    limit: int = 50,
    threshold: float = 0.90,
) -> list[FraudEvent]:
    """
    Retrieve fraud events whose fraud score is
    greater than or equal to the given threshold.

    Results are ordered from highest fraud score
    to lowest.
    """

    result = await session.scalars(
        select(FraudEvent)
        .where(FraudEvent.fraud_score >= threshold)
        .order_by(
            FraudEvent.fraud_score.desc(),
            FraudEvent.created_at.desc(),
        )
        .limit(limit)
    )

    return list(result)

async def get_fraud_event_count(
    session: AsyncSession,
    *,
    user_id: str | None = None,
) -> int:
    """
    Count fraud events.

    If user_id is supplied, only events for that
    user are counted.
    """

    stmt = select(func.count(FraudEvent.id))

    if user_id is not None:
        stmt = stmt.where(
            FraudEvent.user_id == user_id
        )

    result = await session.scalar(stmt)

    return int(result or 0)

async def get_fraud_detection_rate(
    session: AsyncSession,
) -> float:
    """
    Calculate the percentage of fraud events
    where fraud was detected.

    Returns:
        Percentage between 0.0 and 100.0
    """

    total = await session.scalar(
        select(func.count(FraudEvent.id))
    )

    if not total:
        return 0.0

    detected = await session.scalar(
        select(func.count(FraudEvent.id))
        .where(FraudEvent.blocked.is_(True))
    )

    return (float(detected or 0) / float(total)) * 100.0

async def get_replay_attack_events(
    session: AsyncSession,
    *,
    limit: int = 50,
) -> list[FraudEvent]:
    """
    Retrieve fraud events where a replay attack
    was detected.

    Results are ordered from newest to oldest.
    """

    result = await session.scalars(
        select(FraudEvent)
        .where(
            FraudEvent.replay_attack.is_(True)
        )
        .order_by(
            FraudEvent.created_at.desc()
        )
        .limit(limit)
    )

    return list(result)

async def get_blocked_events(
    session: AsyncSession,
    *,
    limit: int = 50,
) -> list[FraudEvent]:
    """
    Retrieve fraud events that resulted in
    an AI decision to block the transaction.

    Results are ordered from newest to oldest.
    """

    result = await session.scalars(
        select(FraudEvent)
        .where(
            FraudEvent.blocked.is_(True)
        )
        .order_by(
            FraudEvent.created_at.desc()
        )
        .limit(limit)
    )

    return list(result)

async def get_recent_fraud_events(
    session: AsyncSession,
    *,
    limit: int = 20,
) -> list[FraudEvent]:
    """
    Retrieve the most recent fraud events.

    Intended for:
    - Admin dashboard
    - Security monitoring
    - Live incident review
    """

    result = await session.scalars(
        select(FraudEvent)
        .order_by(
            FraudEvent.created_at.desc()
        )
        .limit(limit)
    )

    return list(result)
