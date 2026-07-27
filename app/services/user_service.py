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
from uuid import uuid4
from app.core.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import User
from app.database.schemas import (
    UserRegistrationRequest,
    UserResponse,
    UserUpdateRequest,
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

def _normalize_optional_name(
    full_name: str | None,
) -> str | None:
    """
    Normalize an optional full name.

    Returns:
        Normalized name or None.
    """

    if full_name is None:
        return None

    return _validate_full_name(full_name)

def _normalize_language(
    language: str | None,
) -> str:
    """
    Normalize the preferred language.

    Falls back to the project default.
    """

    if language is None:
        return DEFAULT_LANGUAGE

    language = language.strip().lower()

    if not language:
        return DEFAULT_LANGUAGE

    return language

def _apply_profile_updates(
    user: User,
    update: UserUpdateRequest,
) -> None:
    """
    Apply validated profile updates to a User ORM object.
    """

    if update.full_name is not None:
        user.full_name = _normalize_optional_name(
            update.full_name
        )

    if update.preferred_language is not None:
        user.preferred_language = _normalize_language(
            update.preferred_language
        )

async def update_user_profile(
    session: AsyncSession,
    user_id: str,
    update: UserUpdateRequest,
) -> UserResponse:
    """
    Update a user's profile information.

    Workflow:
        1. Retrieve the user.
        2. Validate account state.
        3. Apply business updates.
        4. Persist changes.
        5. Record audit event.
        6. Return updated profile.
    """

    user = await get_user_entity(
        session,
        user_id,
    )

    user = await crud.update_user_profile(
        session,
        user,
        full_name=_normalize_optional_name(update.full_name),
        email=update.email,
        phone_number=update.phone_number,
        preferred_language=(
            _normalize_language(update.preferred_language)
            if update.preferred_language is not None
            else None
        ),
    )

    await _log_profile_update(
        session,
        user,
    )

    _log_profile_operation(
        "PROFILE_UPDATED",
        user.user_id,
    )

    return UserResponse.model_validate(
        user,
        from_attributes=True,
    )

async def _log_profile_update(
    session: AsyncSession,
    user: User,
) -> None:
    """
    Record a profile update event.
    """

    from app.database.models import AuditLog

    audit = AuditLog(
        user_id=user.user_id,
        transaction_id=f"PROFILE_{uuid4().hex}",
        endpoint="/users/profile",
        method="USER",
        event_type="PROFILE_UPDATED",
        status="SUCCESS",
        message=(
            f"Profile updated for '{user.user_id}'."
        ),
    )

    await crud.create_audit_log(
        session,
        audit,
    )

    logger.info(
        f"Profile update audit created for '{user.user_id}'.",
    )

async def _log_language_update(
    session: AsyncSession,
    user: User,
    previous_language: str,
) -> None:
    """
    Record a preferred language update.
    """

    from app.database.models import AuditLog

    audit = AuditLog(
        user_id=user.user_id,
        transaction_id=f"LANGUAGE_{uuid4().hex}",
        endpoint="/users/language",
        method="USER",
        event_type="LANGUAGE_UPDATED",
        status="SUCCESS",
        message=(
            f"Preferred language changed "
            f"from '{previous_language}' "
            f"to '{user.preferred_language}'."
        ),
    )

    await crud.create_audit_log(
        session,
        audit,
    )

    logger.info(
        f"Language updated for '{user.user_id}': "
        f"{previous_language} -> {user.preferred_language}",
    )

async def update_preferred_language(
    session: AsyncSession,
    user_id: str,
    language: str,
) -> UserResponse:
    """
    Update a user's preferred language.

    Workflow:
        1. Retrieve user.
        2. Validate account.
        3. Normalize language.
        4. Persist update.
        5. Record audit event.
        6. Return updated profile.
    """

    user = await get_user_entity(
        session,
        user_id,
    )

    previous_language = user.preferred_language

    normalized_language = _normalize_language(
        language,
    )

    if normalized_language == previous_language:
        logger.info(
            f"Preferred language unchanged for '{user.user_id}'.",
        )

        return UserResponse.model_validate(
            user,
            from_attributes=True,
        )

    user = await crud.update_user_profile(
        session,
        user,
        preferred_language=normalized_language,
    )

    await _log_language_update(
        session,
        user,
        previous_language,
    )

    _log_profile_operation(
        "LANGUAGE_UPDATED",
        user.user_id,
    )

    return UserResponse.model_validate(
        user,
        from_attributes=True,
    )

def _log_profile_operation(
    operation: str,
    user_id: str,
) -> None:
    """
    Emit a standardized profile operation log.

    This helper keeps logging consistent across all
    profile-related service methods.
    """

    logger.info(
        f"Profile operation '{operation}' completed "
        f"for user '{user_id}'.",
    )

__all__ = [
    "UserServiceError",
    "UserAlreadyExistsError",
    "UserNotFoundError",
    "UserInactiveError",
    "UserValidationError",
]
