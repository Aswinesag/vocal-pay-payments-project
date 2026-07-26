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

__all__ = [
    "UserServiceError",
    "UserAlreadyExistsError",
    "UserNotFoundError",
    "UserInactiveError",
    "UserValidationError",
]
