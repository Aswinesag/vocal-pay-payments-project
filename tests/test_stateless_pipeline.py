"""Deterministic integration tests for the current VocalPay API lifecycle."""

from __future__ import annotations

import io
import wave
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import cv2
import httpx
import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.core.config import settings
from app.database import crud
from app.database.database import AsyncSessionLocal, initialize_database
from app.database.models import AuditLog, FraudEvent, PendingTransaction, Transaction, User
from app.main import app


TEST_USER_ID = "integration-test-user"
TEST_EMAIL = "integration_test@vocalpay.com"


def _jpeg_bytes() -> bytes:
    image = np.full((320, 320, 3), 127, dtype=np.uint8)
    cv2.circle(image, (160, 160), 90, (180, 160, 140), thickness=-1)
    encoded, payload = cv2.imencode(".jpg", image)
    assert encoded
    return payload.tobytes()


def _wav_bytes() -> bytes:
    sample_rate = 16_000
    time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
    waveform = 0.15 * np.sin(2.0 * np.pi * 220.0 * time_axis)
    pcm = np.clip(waveform * 32767.0, -32768, 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm.tobytes())
    return buffer.getvalue()


@pytest_asyncio.fixture(autouse=True)
async def isolated_pipeline_state() -> AsyncIterator[None]:
    """Remove deterministic integration records before and after every test."""
    await initialize_database()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(AuditLog).where(AuditLog.user_id == TEST_USER_ID))
        await session.execute(delete(FraudEvent).where(FraudEvent.user_id == TEST_USER_ID))
        await session.execute(
            delete(PendingTransaction).where(PendingTransaction.user_id == TEST_USER_ID)
        )
        await session.execute(delete(Transaction).where(Transaction.user_id == TEST_USER_ID))
        await session.execute(
            delete(User).where((User.user_id == TEST_USER_ID) | (User.email == TEST_EMAIL))
        )
        await session.commit()
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(delete(AuditLog).where(AuditLog.user_id == TEST_USER_ID))
        await session.execute(delete(FraudEvent).where(FraudEvent.user_id == TEST_USER_ID))
        await session.execute(
            delete(PendingTransaction).where(PendingTransaction.user_id == TEST_USER_ID)
        )
        await session.execute(delete(Transaction).where(Transaction.user_id == TEST_USER_ID))
        await session.execute(
            delete(User).where((User.user_id == TEST_USER_ID) | (User.email == TEST_EMAIL))
        )
        await session.commit()


@pytest_asyncio.fixture
async def async_client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _create_authenticated_user(client: httpx.AsyncClient) -> str:
    original_cookie_secure = settings.COOKIE_SECURE
    settings.COOKIE_SECURE = False
    try:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={
                "full_name": "Test Automation",
                "email": TEST_EMAIL,
                "phone_number": "+1999888888",
                "password": "IntegrationPassword123!",
            },
        )
        assert signup.status_code == 201, signup.text
        user_id = signup.json()["user"]["user_id"]
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": TEST_EMAIL, "password": "IntegrationPassword123!"},
        )
        assert login.status_code == 200, login.text
        return str(user_id)
    finally:
        settings.COOKIE_SECURE = original_cookie_secure


@pytest.mark.asyncio
async def test_user_enrollment_pipeline(async_client: httpx.AsyncClient) -> None:
    user_id = await _create_authenticated_user(async_client)
    face_proxy = SimpleNamespace(
        extract_embedding=AsyncMock(return_value=[0.02] * 512),
    )
    voice_proxy = SimpleNamespace(
        extract_embedding=AsyncMock(return_value=[0.04] * 192),
    )
    with (
        patch(
            "app.api.v1.endpoints.user.get_face_verification_provider",
            return_value=face_proxy,
        ),
        patch(
            "app.api.v1.endpoints.user.get_speaker_verification_provider",
            return_value=voice_proxy,
        ),
    ):
        response = await async_client.post(
            "/api/v1/users/enroll",
            files={
                "audio_file": ("voice.wav", io.BytesIO(_wav_bytes()), "audio/wav"),
                "photo_file": ("face.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg"),
            },
        )

    assert response.status_code == 201, response.text
    assert response.json() == {
        "status": "SUCCESS",
        "user_id": user_id,
        "message": "Biometric card identity generated.",
    }


@pytest.mark.asyncio
async def test_conditional_transaction_step_up_loop(
    async_client: httpx.AsyncClient,
) -> None:
    from app.core.security import hash_password

    async with AsyncSessionLocal() as session:
        session.add(
            User(
                user_id=TEST_USER_ID,
                full_name="Test Automation",
                email=TEST_EMAIL,
                phone_number="+1999888888",
                hashed_password=hash_password("IntegrationPassword123!"),
                speaker_embedding=[0.04] * 192,
                face_embedding=[0.02] * 512,
                is_active=True,
                is_verified=True,
                failed_attempts=0,
                preferred_language="en",
            )
        )
        await session.commit()

    voice_proxy = SimpleNamespace(
        extract_embedding=AsyncMock(return_value=[0.04] * 192),
    )
    with (
        patch(
            "app.api.v1.endpoints.transaction.get_speaker_verification_provider",
            return_value=voice_proxy,
        ),
        patch(
            "app.api.v1.endpoints.transaction.search_voiceprint",
            new=AsyncMock(return_value=(TEST_USER_ID, 0.92)),
        ),
        patch(
            "app.api.v1.endpoints.transaction.detect_replay_attack",
            return_value=False,
        ),
        patch(
            "app.api.v1.endpoints.transaction.whisper_provider",
            new=SimpleNamespace(
                transcribe=AsyncMock(
                    return_value="Authorize transaction for 650 dollars"
                )
            ),
        ),
    ):
        initiate_response = await async_client.post(
            "/api/v1/transactions/initiate",
            headers={"X-User-ID": TEST_USER_ID},
            files={"audio_file": ("verify.wav", io.BytesIO(_wav_bytes()), "audio/wav")},
        )

    assert initiate_response.status_code == 403, initiate_response.text
    detail = initiate_response.json()["detail"]
    transaction_id = detail["transaction_id"]
    assert detail["status"] == "PENDING_CHALLENGE"
    assert detail["risk_tier"] == "HIGH"

    async with AsyncSessionLocal() as session:
        frozen = await crud.get_pending_transaction_by_transaction_id(
            session, transaction_id
        )
        assert frozen is not None
        challenge_phrase = frozen.verification_secret
        assert frozen.risk_level == "HIGH"
        assert frozen.speaker_score == pytest.approx(0.92)

    with patch(
        "app.api.v1.endpoints.transaction.whisper_provider",
        new=SimpleNamespace(transcribe=AsyncMock(return_value=challenge_phrase)),
    ):
        verify_response = await async_client.post(
            "/api/v1/transactions/verify",
            headers={"X-User-ID": TEST_USER_ID},
            data={"transaction_id": transaction_id},
            files={"audio_file": ("challenge.wav", io.BytesIO(_wav_bytes()), "audio/wav")},
        )

    assert verify_response.status_code == 200, verify_response.text
    async with AsyncSessionLocal() as session:
        assert (
            await crud.get_pending_transaction_by_transaction_id(session, transaction_id)
            is None
        )
        completed = await crud.get_transaction_by_transaction_id(session, transaction_id)
        assert completed is not None
        assert completed.status == "COMPLETED"
        assert completed.risk_level == "HIGH"

    replay_response = await async_client.post(
        "/api/v1/transactions/verify",
        headers={"X-User-ID": TEST_USER_ID},
        data={"transaction_id": transaction_id, "otp_code": "000000"},
    )
    assert replay_response.status_code == 404
