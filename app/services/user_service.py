"""
User Service

Implements all business logic related to user lifecycle
management including:

- User registration
- User profile retrieval
- Profile updates
- Biometric embedding management
- Account verification
- Account activation/deactivation

This layer coordinates CRUD operations while ensuring
business rules remain separate from persistence.
"""

from __future__ import annotations
from typing import Final
from app.core.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import User
from app.database.schemas import (
    UserRegistrationRequest,
    UserResponse,
)
from app.database import crud

logger = get_logger(__name__)
DEFAULT_LANGUAGE: Final[str] = "en"
MAX_FAILED_LOGIN_ATTEMPTS: Final[int] = 5
MIN_NAME_LENGTH: Final[int] = 2

class UserServiceError(Exception):
    """
    Base exception for all user service errors.
    """


class UserAlreadyExistsError(UserServiceError):
    """
    Raised when attempting to register a user
    whose email or phone already exists.
    """


class UserNotFoundError(UserServiceError):
    """
    Raised when a requested user cannot be found.
    """


class UserInactiveError(UserServiceError):
    """
    Raised when an operation requires an active account.
    """


class UserValidationError(UserServiceError):
    """
    Raised when business validation fails.
    """

def _validate_full_name(full_name: str) -> str:
    """
    Validate and normalize a user's full name.
    """

    value = full_name.strip()

    if len(value) < MIN_NAME_LENGTH:
        raise UserValidationError(
            "Full name is too short."
        )

    return value

async def _ensure_user_does_not_exist(
    session: AsyncSession,
    user: UserRegistrationRequest,
) -> None:
    """
    Ensure that neither the email nor the phone number
    is already registered.
    """

    existing = await crud.get_user_by_email(
        session,
        user.email,
    )

    if existing is not None:
        raise UserAlreadyExistsError(
            f"Email '{user.email}' is already registered."
        )

    existing = await crud.get_user_by_phone(
        session,
        user.phone_number,
    )

    if existing is not None:
        raise UserAlreadyExistsError(
            f"Phone number '{user.phone_number}' is already registered."
        )

async def register_user(
    session: AsyncSession,
    user_data: UserRegistrationRequest,
) -> UserResponse:
    """
    Register a new VocalPay user.

    Workflow:
        1. Validate business rules.
        2. Ensure uniqueness.
        3. Build ORM object.
        4. Persist using CRUD.
        5. Return response schema.
    """

    await _ensure_user_does_not_exist(
        session,
        user_data,
    )

    full_name = _validate_full_name(
        user_data.full_name,
    )

    normalized_data = user_data.model_copy(
        update={
            "full_name": full_name,
            "preferred_language": (
                user_data.preferred_language
                or DEFAULT_LANGUAGE
            ),
        },
    )

    user = await crud.create_user(
        session,
        normalized_data,
    )

    await _log_user_registration(
        session,
        normalized_data,
    )

    logger.info(
        f"Registered new user '{user.user_id}'",
    )

    return UserResponse.model_validate(
        user,
        from_attributes=True,
    )

async def _log_user_registration(
    session: AsyncSession,
    user_data: UserRegistrationRequest,
) -> None:
    """
    Record a successful user registration
    in the audit log.
    """

    from app.database.models import AuditLog

    audit = AuditLog(
        user_id=user_data.user_id,
        transaction_id=user_data.user_id,
        endpoint="/users/register",
        method="SYSTEM",
        event_type="USER_REGISTERED",
        status="SUCCESS",
        message=(
            f"User '{user_data.user_id}' successfully registered."
        ),
    )

    await crud.create_audit_log(
        session,
        audit,
    )

async def _get_user_by_id(
    session: AsyncSession,
    user_id: str,
) -> User:
    """
    Retrieve a user by user ID.

    Raises:
        UserNotFoundError
    """

    user = await crud.get_user_by_user_id(
        session,
        user_id,
    )

    if user is None:
        raise UserNotFoundError(
            f"User '{user_id}' was not found."
        )

    return user

async def _get_user_by_email(
    session: AsyncSession,
    email: str,
) -> User:
    """
    Retrieve a user by email address.

    Raises:
        UserNotFoundError
    """

    user = await crud.get_user_by_email(
        session,
        email,
    )

    if user is None:
        raise UserNotFoundError(
            f"Email '{email}' is not registered."
        )

    return user

async def _ensure_active_user(
    session: AsyncSession,
    user_id: str,
) -> None:
    """
    Ensure the user account is active.
    """

    user = await _get_user_by_id(
        session,
        user_id,
    )

    if not user.is_active:
        raise UserInactiveError(
            f"User '{user.user_id}' is inactive."
        )

async def get_user_profile(
    session: AsyncSession,
    user_id: str,
) -> UserResponse:
    """
    Retrieve an active user's profile.

    Args:
        session: Active database session.
        user_id: User identifier.

    Returns:
        UserResponse

    Raises:
        UserNotFoundError
        UserInactiveError
    """

    user = await _get_user_by_id(
        session,
        user_id,
    )

    await _ensure_active_user(
        session,
        user.user_id,
    )

    logger.info(
        f"Retrieved profile for user '{user.user_id}'.",
    )

    return UserResponse.model_validate(
        user,
        from_attributes=True,
    )

async def get_user_profile_by_email(
    session: AsyncSession,
    email: str,
) -> UserResponse:
    """
    Retrieve an active user's profile using
    their email address.

    Args:
        session: Active database session.
        email: Registered email.

    Returns:
        UserResponse

    Raises:
        UserNotFoundError
        UserInactiveError
    """

    user = await _get_user_by_email(
        session,
        email,
    )

    await _ensure_active_user(
        session,
        user.user_id,
    )

    logger.info(
        f"Retrieved profile for email '{email}'.",
    )

    return UserResponse.model_validate(
        user,
        from_attributes=True,
    )

async def get_user_entity(
    session: AsyncSession,
    user_id: str,
) -> User:
    """
    Retrieve a validated User ORM object.

    This function is intended for internal service
    consumption where the ORM entity is required
    instead of a response schema.

    Raises:
        UserNotFoundError
        UserInactiveError
    """

    user = await _get_user_by_id(
        session,
        user_id,
    )

    await _ensure_active_user(
        session,
        user.user_id,
    )

    return user

def ensure_verified_user(
    user: User,
) -> None:
    """
    Ensure the user has completed
    biometric/account verification.
    """

    if not user.is_verified:
        raise UserValidationError(
            f"User '{user.user_id}' is not verified."
        )

def ensure_user_can_transact(
    user: User,
) -> None:
    """
    Ensure the user is eligible to
    perform financial transactions.
    """

    if not user.is_active:
        raise UserInactiveError(
            f"User '{user.user_id}' is inactive."
        )

    ensure_verified_user(user)

    if user.failed_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        raise UserValidationError(
            "Maximum authentication attempts exceeded."
        )

__all__ = [
    "UserServiceError",
    "UserAlreadyExistsError",
    "UserNotFoundError",
    "UserInactiveError",
    "UserValidationError",
]
