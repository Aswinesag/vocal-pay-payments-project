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

def _validate_speaker_embedding(
    embedding: list[float],
) -> list[float]:
    """
    Validate a serialized speaker embedding.

    The service layer intentionally does not validate
    embedding dimensions because different biometric
    models may produce different vector sizes.
    """

    if not embedding:
        raise UserValidationError(
            "Speaker embedding cannot be empty."
        )

    return embedding

def _validate_face_embedding(
    embedding: list[float],
) -> list[float]:
    """
    Validate a serialized face embedding.
    """

    if not embedding:
        raise UserValidationError(
            "Face embedding cannot be empty."
        )

    return embedding

def has_complete_biometrics(
    user: User,
) -> bool:
    """
    Determine whether a user has completed
    biometric enrollment.

    Returns:
        True only if both speaker and face
        embeddings exist.
    """

    return (
        user.speaker_embedding is not None
        and user.face_embedding is not None
    )

async def _log_speaker_enrollment(
    session: AsyncSession,
    user: User,
) -> None:
    """
    Record successful speaker enrollment.
    """

    from app.database.models import AuditLog

    audit = AuditLog(
        user_id=user.user_id,
        transaction_id=f"SPEAKER_{uuid4().hex}",
        endpoint="/users/biometrics/speaker",
        method="SYSTEM",
        event_type="SPEAKER_ENROLLED",
        status="SUCCESS",
        message=(
            f"Speaker embedding enrolled for "
            f"user '{user.user_id}'."
        ),
    )

    await crud.create_audit_log(
        session,
        audit,
    )

    logger.info(
        f"Speaker enrollment audit created for '{user.user_id}'.",
    )

async def update_speaker_embedding(
    session: AsyncSession,
    user_id: str,
    embedding: list[float],
) -> UserResponse:
    """
    Store or replace a user's speaker embedding.

    This method manages biometric enrollment only.
    Speaker verification is handled by the
    Authentication Service.
    """

    user = await get_user_entity(
        session,
        user_id,
    )

    validated_embedding = _validate_speaker_embedding(
        embedding,
    )

    # Idempotent update
    if user.speaker_embedding == validated_embedding:
        logger.info(
            f"Speaker embedding unchanged for '{user.user_id}'.",
        )

        return UserResponse.model_validate(
            user,
            from_attributes=True,
        )

    user = await crud.update_biometric_embeddings(
        session,
        user,
        speaker_embedding=validated_embedding,
    )

    await _log_speaker_enrollment(
        session,
        user,
    )

    _log_biometric_operation(
        "SPEAKER_ENROLLED",
        user.user_id,
    )
    return UserResponse.model_validate(
        user,
        from_attributes=True,
    )

async def _log_face_enrollment(
    session: AsyncSession,
    user: User,
) -> None:
    """
    Record successful face enrollment.
    """

    from app.database.models import AuditLog

    audit = AuditLog(
        user_id=user.user_id,
        transaction_id=f"FACE_{uuid4().hex}",
        endpoint="/users/biometrics/face",
        method="SYSTEM",
        event_type="FACE_ENROLLED",
        status="SUCCESS",
        message=(
            f"Face embedding enrolled for "
            f"user '{user.user_id}'."
        ),
    )

    await crud.create_audit_log(
        session,
        audit,
    )

    logger.info(
        f"Face enrollment audit created for '{user.user_id}'.",
    )

async def update_face_embedding(
    session: AsyncSession,
    user_id: str,
    embedding: list[float],
) -> UserResponse:
    """
    Store or replace a user's face embedding.

    This method manages biometric enrollment only.
    Face verification is handled by the
    Authentication Service.
    """

    user = await get_user_entity(
        session,
        user_id,
    )

    validated_embedding = _validate_face_embedding(
        embedding,
    )

    # Idempotent update
    if user.face_embedding == validated_embedding:
        logger.info(
            f"Face embedding unchanged for '{user.user_id}'.",
        )

        return UserResponse.model_validate(
            user,
            from_attributes=True,
        )

    user = await crud.update_biometric_embeddings(
        session,
        user,
        face_embedding=validated_embedding,
    )

    await _log_face_enrollment(
        session,
        user,
    )

    _log_biometric_operation(
        "FACE_ENROLLED",
        user.user_id,
    )

    if has_complete_biometrics(user):
        _log_biometric_operation(
            "BIOMETRIC_ENROLLMENT_COMPLETED",
            user.user_id,
        )

    return UserResponse.model_validate(
        user,
        from_attributes=True,
    )

async def get_speaker_embedding(
    session: AsyncSession,
    user_id: str,
) -> list[float]:
    """
    Retrieve a user's stored speaker embedding.

    Intended for internal service use only.
    """

    user = await get_user_entity(
        session,
        user_id,
    )

    if user.speaker_embedding is None:
        raise UserValidationError(
            "Speaker embedding has not been enrolled."
        )

    return user.speaker_embedding

async def get_face_embedding(
    session: AsyncSession,
    user_id: str,
) -> list[float]:
    """
    Retrieve a user's stored face embedding.

    Intended for internal service use only.
    """

    user = await get_user_entity(
        session,
        user_id,
    )

    if user.face_embedding is None:
        raise UserValidationError(
            "Face embedding has not been enrolled."
        )

    return user.face_embedding

async def get_biometric_profile(
    session: AsyncSession,
    user_id: str,
) -> tuple[list[float], list[float]]:
    """
    Retrieve both enrolled biometric embeddings.

    Intended for Authentication Service only.
    """

    user = await get_user_entity(
        session,
        user_id,
    )

    if not has_complete_biometrics(user):
        raise UserValidationError(
            "User has not completed biometric enrollment."
        )

    return (
        user.speaker_embedding,
        user.face_embedding,
    )

async def get_biometric_status(
    session: AsyncSession,
    user_id: str,
) -> dict[str, bool]:
    """
    Retrieve biometric enrollment status.

    This method intentionally exposes only
    enrollment state—not biometric data.
    """

    user = await get_user_entity(
        session,
        user_id,
    )

    return {
        "speaker_enrolled": (
            user.speaker_embedding is not None
        ),
        "face_enrolled": (
            user.face_embedding is not None
        ),
        "biometric_complete": (
            has_complete_biometrics(user)
        ),
    }

def _log_biometric_operation(
    operation: str,
    user_id: str,
) -> None:
    """
    Emit a standardized biometric operation log.

    This helper centralizes logging for all
    biometric-related service methods.
    """

    logger.info(
        f"Biometric operation '{operation}' completed "
        f"for user '{user_id}'.",
    )

async def _log_account_activation(
    session: AsyncSession,
    user: User,
) -> None:
    """
    Record successful account activation.
    """

    from app.database.models import AuditLog

    audit = AuditLog(
        user_id=user.user_id,
        transaction_id=f"ACTIVATE_{uuid4().hex}",
        endpoint="/users/activate",
        method="SYSTEM",
        event_type="ACCOUNT_ACTIVATED",
        status="SUCCESS",
        message=(
            f"Account '{user.user_id}' activated."
        ),
    )

    await crud.create_audit_log(
        session,
        audit,
    )

    logger.info(
        f"Account activation audit created for '{user.user_id}'.",
    )

async def _log_account_deactivation(
    session: AsyncSession,
    user: User,
) -> None:
    """
    Record successful account deactivation.
    """

    from app.database.models import AuditLog

    audit = AuditLog(
        user_id=user.user_id,
        transaction_id=f"DEACTIVATE_{uuid4().hex}",
        endpoint="/users/deactivate",
        method="SYSTEM",
        event_type="ACCOUNT_DEACTIVATED",
        status="SUCCESS",
        message=(
            f"Account '{user.user_id}' deactivated."
        ),
    )

    await crud.create_audit_log(
        session,
        audit,
    )

    logger.info(
        f"Account deactivation audit created for '{user.user_id}'.",
    )

async def _log_failed_authentication(
    session: AsyncSession,
    user: User,
) -> None:
    """
    Record a failed authentication attempt.
    """

    from app.database.models import AuditLog

    audit = AuditLog(
        user_id=user.user_id,
        transaction_id=f"FAILED_AUTH_{uuid4().hex}",
        endpoint="/users/authentication",
        method="SYSTEM",
        event_type="FAILED_AUTHENTICATION",
        status="FAILED",
        message=(
            f"Failed authentication attempt "
            f"({user.failed_attempts}) "
            f"for user '{user.user_id}'."
        ),
    )

    await crud.create_audit_log(
        session,
        audit,
    )

    logger.info(
        f"Failed authentication audit created for '{user.user_id}'.",
    )

async def increment_failed_attempts(
    session: AsyncSession,
    user_id: str,
    max_attempts: int = 5,
) -> UserResponse:
    """
    Increment the failed authentication counter.

    Automatically deactivates the account when the
    configured threshold is reached.
    """

    if max_attempts < 1:
        raise ValueError(
            "max_attempts must be at least 1."
        )

    user = await _get_user_by_id(
        session,
        user_id,
    )

    was_active = user.is_active

    user = await crud.increment_failed_attempts(
        session,
        user,
    )

    if user.failed_attempts >= max_attempts and user.is_active:
        user = await crud.deactivate_user(
            session,
            user,
        )

    await _log_failed_authentication(
        session,
        user,
    )

    if was_active and not user.is_active:
        await _log_account_deactivation(
            session,
            user,
        )

        _log_account_operation(
            "ACCOUNT_LOCKED",
            user.user_id,
        )

    return UserResponse.model_validate(
        user,
        from_attributes=True,
    )

async def reset_failed_attempts(
    session: AsyncSession,
    user_id: str,
) -> UserResponse:
    """
    Reset the failed authentication counter.

    Intended to be called after a successful
    authentication.
    """

    user = await _get_user_by_id(
        session,
        user_id,
    )

    if user.failed_attempts == 0:
        return UserResponse.model_validate(
            user,
            from_attributes=True,
        )

    user = await crud.reset_failed_attempts(
        session,
        user,
    )

    logger.info(
        f"Failed authentication counter reset for '{user.user_id}'.",
    )

    return UserResponse.model_validate(
        user,
        from_attributes=True,
    )

def _log_account_operation(
    operation: str,
    user_id: str,
) -> None:
    """
    Emit a standardized account-management log.

    Centralizes logging for account lifecycle
    and security operations.
    """

    logger.info(
        f"Account operation '{operation}' completed "
        f"for user '{user_id}'.",
    )

async def activate_user_account(
    session: AsyncSession,
    user_id: str,
) -> UserResponse:
    """
    Activate a user's account.

    This operation only changes the account
    activation state.
    """

    user = await _get_user_by_id(
        session,
        user_id,
    )

    if user.is_active:
        return UserResponse.model_validate(
            user,
            from_attributes=True,
        )

    user = await crud.activate_user(
        session,
        user,
    )

    await _log_account_activation(
        session,
        user,
    )

    _log_account_operation(
        "ACCOUNT_ACTIVATED",
        user.user_id,
    )

    return UserResponse.model_validate(
        user,
        from_attributes=True,
    )

async def deactivate_user_account(
    session: AsyncSession,
    user_id: str,
) -> UserResponse:
    """
    Deactivate a user's account.

    This operation prevents future service
    interactions until the account is
    reactivated.
    """

    user = await _get_user_by_id(
        session,
        user_id,
    )

    # Idempotent operation
    if not user.is_active:
        return UserResponse.model_validate(
            user,
            from_attributes=True,
        )

    user = await crud.deactivate_user(
        session,
        user,
    )

    await _log_account_deactivation(
        session,
        user,
    )

    _log_account_operation(
        "ACCOUNT_DEACTIVATED",
        user.user_id,
    )

    return UserResponse.model_validate(
        user,
        from_attributes=True,
    )

__all__ = [
    "UserServiceError",
    "UserAlreadyExistsError",
    "UserNotFoundError",
    "UserInactiveError",
    "UserValidationError",
]
