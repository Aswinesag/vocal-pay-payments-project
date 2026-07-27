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


__all__ = [
    "UserServiceError",
    "UserAlreadyExistsError",
    "UserNotFoundError",
    "UserInactiveError",
    "UserValidationError",
]
