from __future__ import annotations
from datetime import datetime, timedelta
from typing import TypeVar
from uuid import uuid4

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import (
    AuditLog,
    FraudEvent,
    PendingTransaction,
    Transaction,
    User,
    utc_now_naive,
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

TransactionModelType = TypeVar(
    "TransactionModelType",
    PendingTransaction,
    Transaction,
    FraudEvent,
    AuditLog,
)

DBSession = AsyncSession

# ==========================================================
# Utility Helpers
# ==========================================================

def utc_now() -> datetime:
    """
    Return the centralized UTC-naive persistence timestamp.
    """

    return utc_now_naive()

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
    model: type[TransactionModelType],
    transaction_id: str,
) -> TransactionModelType | None:
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
        await db.rollback()
        logger.bind(error=str(exc)).error(
            "Database integrity violation during flush."
        )

        raise

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.bind(error=str(exc)).error(
            "Database operation failed during flush."
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


async def freeze_transaction(
    db: AsyncSession,
    user_id: str,
    amount: float,
    status: str,
    verification_secret: str,
    *,
    risk_level: str = "PENDING",
    speaker_score: float = 0.0,
    face_score: float = 0.0,
    fraud_score: float = 0.0,
    replay_attack: bool = False,
) -> PendingTransaction:
    """Persist an active step-up transaction with a strict five-minute TTL."""
    now = utc_now_naive()
    pending = PendingTransaction(
        transaction_id=f"TXN-{uuid4().hex.upper()}",
        user_id=user_id,
        amount=amount,
        status=status,
        verification_secret=verification_secret,
        expires_at=now + timedelta(minutes=5),
        is_active=True,
        verification_attempts=0,
        max_verification_attempts=5,
        risk_level=risk_level,
        speaker_score=speaker_score,
        face_score=face_score,
        fraud_score=fraud_score,
        replay_attack=replay_attack,
    )

    try:
        db.add(pending)
        await db.flush()
        logger.bind(
            transaction_id=pending.transaction_id,
            user_id=user_id,
            expires_at=pending.expires_at.isoformat(),
        ).info("Step-up transaction frozen.")
        return pending
    except Exception as exc:
        await db.rollback()
        logger.bind(user_id=user_id, error=str(exc)).exception(
            "Failed to freeze step-up transaction."
        )
        raise


async def get_active_transaction(
    db: AsyncSession,
    verification_secret: str,
) -> PendingTransaction | None:
    """Return an unexpired active step-up transaction for a secret."""
    try:
        pending = await db.scalar(
            select(PendingTransaction).where(
                PendingTransaction.verification_secret == verification_secret,
                PendingTransaction.is_active.is_(True),
            )
        )

        if pending is None:
            logger.debug("No active step-up transaction found.")
            return None

        if pending.expires_at <= utc_now_naive():
            await db.delete(pending)
            await db.flush()
            logger.bind(transaction_id=pending.transaction_id).warning(
                "Expired step-up transaction deleted."
            )
            return None

        logger.bind(transaction_id=pending.transaction_id).debug(
            "Active step-up transaction retrieved."
        )
        return pending
    except Exception as exc:
        await db.rollback()
        logger.bind(error=str(exc)).exception(
            "Failed to retrieve active step-up transaction."
        )
        raise


async def invalidate_transaction(
    db: AsyncSession,
    transaction: PendingTransaction,
) -> None:
    """Permanently deactivate a consumed step-up verification token."""
    try:
        transaction.is_active = False
        await db.flush()
        logger.bind(transaction_id=transaction.transaction_id).info(
            "Step-up transaction invalidated."
        )
    except Exception as exc:
        await db.rollback()
        logger.bind(
            transaction_id=transaction.transaction_id,
            error=str(exc),
        ).exception("Failed to invalidate step-up transaction.")
        raise

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

async def create_audit_log(
    session: AsyncSession,
    audit_log: AuditLog,
) -> AuditLog:
    """
    Persist an immutable audit log entry.

    The AuditLog ORM object must already be fully
    populated by the service layer.

    Returns:
        Persisted AuditLog ORM object.
    """

    session.add(audit_log)

    await safe_flush(session)

    return audit_log

async def get_audit_logs_by_transaction_id(
    session: AsyncSession,
    transaction_id: str,
) -> list[AuditLog]:
    """
    Retrieve all audit logs associated with
    a transaction.

    Results are ordered chronologically.
    """

    result = await session.scalars(
        select(AuditLog)
        .where(
            AuditLog.transaction_id == transaction_id
        )
        .order_by(
            AuditLog.created_at.asc()
        )
    )

    return list(result)

async def get_audit_logs_by_user_id(
    session: AsyncSession,
    user_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """
    Retrieve audit logs for a user.

    Results are ordered from newest to oldest.
    """

    result = await session.scalars(
        select(AuditLog)
        .where(
            AuditLog.user_id == user_id
        )
        .order_by(
            AuditLog.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
    )

    return list(result)

async def get_recent_audit_logs(
    session: AsyncSession,
    *,
    limit: int = 100,
) -> list[AuditLog]:
    """
    Retrieve the most recent audit log entries.

    Intended for:
    - Admin dashboard
    - Live monitoring
    - Security operations
    """

    result = await session.scalars(
        select(AuditLog)
        .order_by(
            AuditLog.created_at.desc()
        )
        .limit(limit)
    )

    return list(result)

async def get_audit_log_count(
    session: AsyncSession,
    *,
    user_id: str | None = None,
) -> int:
    """
    Count audit log entries.

    If user_id is supplied,
    only that user's logs are counted.
    """

    stmt = select(func.count(AuditLog.id))

    if user_id is not None:
        stmt = stmt.where(
            AuditLog.user_id == user_id
        )

    result = await session.scalar(stmt)

    return int(result or 0)

async def get_logs_by_action(
    session: AsyncSession,
    action: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """
    Retrieve audit logs matching a specific action.

    Results are ordered from newest to oldest.
    """

    result = await session.scalars(
        select(AuditLog)
        .where(
            AuditLog.event_type == action
        )
        .order_by(
            AuditLog.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
    )

    return list(result)

async def get_logs_by_actor(
    session: AsyncSession,
    actor: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """
    Retrieve audit logs generated by a specific actor.

    Results are ordered from newest to oldest.
    """

    result = await session.scalars(
        select(AuditLog)
        .where(
            AuditLog.method == actor
        )
        .order_by(
            AuditLog.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
    )

    return list(result)

async def get_logs_by_time_range(
    session: AsyncSession,
    start_time: datetime,
    end_time: datetime,
    *,
    limit: int = 500,
) -> list[AuditLog]:
    """
    Retrieve audit logs within a time range.

    Results are ordered chronologically.
    """

    result = await session.scalars(
        select(AuditLog)
        .where(
            AuditLog.created_at >= start_time,
            AuditLog.created_at <= end_time,
        )
        .order_by(
            AuditLog.created_at.asc()
        )
        .limit(limit)
    )

    return list(result)
