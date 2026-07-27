from app.services.user_service import (
    DEFAULT_LANGUAGE,
    MAX_FAILED_LOGIN_ATTEMPTS,
    _validate_full_name,
)

print("\n========== USER SERVICE ==========")

print(DEFAULT_LANGUAGE)
print(MAX_FAILED_LOGIN_ATTEMPTS)

print(_validate_full_name(" Aswin Kumar "))

try:
    _validate_full_name("A")
except Exception as exc:
    print(type(exc).__name__)
    print(exc)

import asyncio
from app.database import crud
from app.database.database import AsyncSessionLocal
from app.database.schemas import UserRegistrationRequest
from app.services.user_service import (
    _ensure_active_user,
    _get_user_by_email,
    _get_user_by_id,
    get_user_profile,
    get_user_profile_by_email,
    get_user_entity,
    ensure_user_can_transact,
    ensure_verified_user,
    register_user,
    UserAlreadyExistsError,
    UserNotFoundError,
    UserValidationError,
)
async def test_register_user():
    async with AsyncSessionLocal() as session:

        request = UserRegistrationRequest(
            user_id="USR_SERVICE_001",
            full_name="Aswin Kumar",
            email="aswin@example.com",
            phone_number="+919999999999",
            preferred_language="en",
            speaker_embedding=[0.1] * 192,
            face_embedding=[0.2] * 512,
        )

        user = await register_user(
            session,
            request,
        )

        print("\n========== REGISTER USER ==========")
        print(user.user_id)
        print(user.full_name)
        print(user.email)

        try:
            await register_user(
                session,
                request,
            )
        except UserAlreadyExistsError as exc:
            print(type(exc).__name__)
            print(exc)

        await session.rollback()


asyncio.run(test_register_user())

async def test_registration_audit():
    async with AsyncSessionLocal() as session:

        request = UserRegistrationRequest(
            user_id="USR_AUDIT_001",
            full_name="Audit User",
            email="audit@example.com",
            phone_number="+911234567890",
            preferred_language="en",
            speaker_embedding=[0.1] * 192,
            face_embedding=[0.2] * 512,
        )

        user = await register_user(
            session,
            request,
        )

        logs = await crud.get_audit_logs_by_user_id(
            session,
            user.user_id,
        )

        print("\n========== REGISTRATION AUDIT ==========")
        print(user.user_id)
        print(len(logs))

        if logs:
            print(logs[0].event_type)

        await session.rollback()


asyncio.run(test_registration_audit())

async def test_lookup_helpers():
    async with AsyncSessionLocal() as session:

        request = UserRegistrationRequest(
            user_id="USR_LOOKUP_001",
            full_name="Lookup User",
            email="lookup@example.com",
            phone_number="+911111111111",
            preferred_language="en",
            speaker_embedding=[0.1] * 192,
            face_embedding=[0.2] * 512,
        )

        created = await register_user(
            session,
            request,
        )

        user = await _get_user_by_id(
            session,
            created.user_id,
        )

        print("\n========== LOOKUP HELPERS ==========")
        print(user.user_id)

        user = await _get_user_by_email(
            session,
            "lookup@example.com",
        )

        print(user.email)

        await _ensure_active_user(
            session,
            user.user_id,
        )

        try:
            await _get_user_by_id(
                session,
                "INVALID_USER",
            )
        except UserNotFoundError as exc:
            print(type(exc).__name__)
            print(exc)

        await session.rollback()


asyncio.run(test_lookup_helpers())

async def test_profile_retrieval():
    async with AsyncSessionLocal() as session:

        request = UserRegistrationRequest(
            user_id="USR_PROFILE_001",
            full_name="Profile User",
            email="profile@example.com",
            phone_number="+919876543210",
            preferred_language="en",
            speaker_embedding=[0.1] * 192,
            face_embedding=[0.2] * 512,
        )

        created = await register_user(
            session,
            request,
        )

        print("\n========== PROFILE RETRIEVAL ==========")

        profile = await get_user_profile(
            session,
            created.user_id,
        )

        print(profile.user_id)
        print(profile.full_name)

        profile2 = await get_user_profile_by_email(
            session,
            "profile@example.com",
        )

        print(profile2.email)

        try:
            await get_user_profile(
                session,
                "INVALID_USER",
            )
        except UserNotFoundError as exc:
            print(type(exc).__name__)
            print(exc)

        await session.rollback()


asyncio.run(test_profile_retrieval())

async def test_profile_helpers():
    async with AsyncSessionLocal() as session:

        request = UserRegistrationRequest(
            user_id="USR_VALIDATION_001",
            full_name="Validation User",
            email="validation@example.com",
            phone_number="+919111111111",
            preferred_language="en",
            speaker_embedding=[0.1] * 192,
            face_embedding=[0.2] * 512,
        )

        created = await register_user(
            session,
            request,
        )

        user = await get_user_entity(
            session,
            created.user_id,
        )

        print("\n========== PROFILE HELPERS ==========")
        print(user.user_id)

        try:
            ensure_verified_user(user)
        except UserValidationError as exc:
            print(type(exc).__name__)
            print(exc)

        try:
            ensure_user_can_transact(user)
        except UserValidationError as exc:
            print(type(exc).__name__)
            print(exc)

        await session.rollback()


asyncio.run(test_profile_helpers())
