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
    register_user,
    UserAlreadyExistsError,
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
