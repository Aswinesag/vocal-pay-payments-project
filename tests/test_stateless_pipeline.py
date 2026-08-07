"""Deterministic integration tests for the stateless VocalPay pipeline."""

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
from loguru import logger
from sqlalchemy import delete

from app.database import crud
from app.database.database import AsyncSessionLocal, initialize_database
from app.database.models import AuditLog, FraudEvent, PendingTransaction, Transaction, User
from app.main import app


TEST_USER_ID = "integration_test_01"


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


@pytest_asyncio.fixture(scope="function", autouse=True)
async def isolated_pipeline_state() -> AsyncIterator[None]:
    """Initialize tables and isolate records owned by this test module."""
    await initialize_database()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(AuditLog).where(AuditLog.user_id == TEST_USER_ID))
        await session.execute(delete(FraudEvent).where(FraudEvent.user_id == TEST_USER_ID))
        await session.execute(
            delete(PendingTransaction).where(PendingTransaction.user_id == TEST_USER_ID)
        )
        await session.execute(delete(Transaction).where(Transaction.user_id == TEST_USER_ID))
        await session.execute(delete(User).where(User.user_id == TEST_USER_ID))
        await session.commit()

    yield

    async with AsyncSessionLocal() as session:
        await session.execute(delete(AuditLog).where(AuditLog.user_id == TEST_USER_ID))
        await session.execute(delete(FraudEvent).where(FraudEvent.user_id == TEST_USER_ID))
        await session.execute(
            delete(PendingTransaction).where(PendingTransaction.user_id == TEST_USER_ID)
        )
        await session.execute(delete(Transaction).where(Transaction.user_id == TEST_USER_ID))
        await session.execute(delete(User).where(User.user_id == TEST_USER_ID))
        await session.commit()


@pytest_asyncio.fixture
async def async_client() -> AsyncIterator[httpx.AsyncClient]:
    """Yield a reusable in-process asynchronous API client."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_user_enrollment_pipeline(async_client: httpx.AsyncClient) -> None:
    """Enroll deterministic biometric templates without loading neural models."""
    logger.info("Starting deterministic user enrollment integration stage.")
    face_proxy = SimpleNamespace(
        extract_embedding=AsyncMock(return_value=[0.02] * 512),
    )
    voice_proxy = SimpleNamespace(
        extract_embedding=AsyncMock(return_value=[0.04] * 192),
    )

    with (
        patch(
            "app.services.providers.provider_factory.get_face_verification_provider",
            return_value=face_proxy,
        ),
        patch(
            "app.services.providers.provider_factory.get_speaker_verification_provider",
            return_value=voice_proxy,
        ),
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
            data={
                "user_id": TEST_USER_ID,
                "full_name": "Test Automation",
                "email": "integration_test@vocalpay.com",
                "phone_number": "+1999888888",
            },
            files={
                "audio_file": ("voice.wav", io.BytesIO(_wav_bytes()), "audio/wav"),
                "photo_file": ("face.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg"),
            },
        )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["user_id"] == TEST_USER_ID
    assert payload["speaker_embedding_dimensions"] == 192
    assert payload["face_embedding_dimensions"] == 512
    logger.success("User enrollment integration stage completed.")


@pytest.mark.asyncio
async def test_conditional_transaction_step_up_loop(
    async_client: httpx.AsyncClient,
) -> None:
    """Freeze, rehydrate, consume, and replay-check one step-up transaction."""
    logger.info("Starting deterministic transaction step-up integration stage.")
    async with AsyncSessionLocal() as session:
        session.add(
            User(
                user_id=TEST_USER_ID,
                full_name="Test Automation",
                email="auto@vocalpay.test",
                phone_number="+19998888",
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
        verify_speaker=AsyncMock(
            return_value=SimpleNamespace(confidence=0.82, verified=True)
        ),
    )

    with (
        patch(
            "app.services.providers.provider_factory.get_speaker_verification_provider",
            return_value=voice_proxy,
        ),
        patch(
            "app.api.v1.endpoints.transaction.get_speaker_verification_provider",
            return_value=voice_proxy,
        ),
        patch(
            "app.api.v1.endpoints.transaction.detect_replay_attack",
            return_value=False,
        ),
        patch.object(
            __import__(
                "app.api.v1.endpoints.transaction",
                fromlist=["ollama_service"],
            ).ollama_service,
            "evaluate_transaction_context",
            new=AsyncMock(
                return_value={
                    "risk_tier": "HIGH",
                    "explainable_ai_rationale": "Deterministic step-up required.",
                }
            ),
        ),
    ):
        initiate_response = await async_client.post(
            "/api/v1/transactions/initiate",
            data={"user_id": TEST_USER_ID, "amount": "650.00"},
            files={
                "audio_file": ("verify.wav", io.BytesIO(_wav_bytes()), "audio/wav")
            },
        )

    assert initiate_response.status_code == 403, initiate_response.text
    initiate_payload = initiate_response.json()["detail"]
    transaction_id = initiate_payload["transaction_id"]
    assert initiate_payload["risk_tier"] == "HIGH"

    async with AsyncSessionLocal() as session:
        frozen = await crud.get_pending_transaction_by_transaction_id(
            session,
            transaction_id,
        )
        assert frozen is not None
        verification_secret = frozen.verification_secret
        assert frozen.is_active is True

    verify_response = await async_client.post(
        "/api/v1/transactions/verify",
        data={
            "transaction_id": transaction_id,
            "otp_code": verification_secret,
        },
    )
    assert verify_response.status_code == 200, verify_response.text
    verify_payload = verify_response.json()
    assert verify_payload["success"] is True
    assert verify_payload["status"] == "SUCCESS"
    assert verify_payload["transaction_id"] == transaction_id

    async with AsyncSessionLocal() as session:
        consumed = await crud.get_pending_transaction_by_transaction_id(
            session,
            transaction_id,
        )
        assert consumed is not None
        assert consumed.is_active is False

    replay_response = await async_client.post(
        "/api/v1/transactions/verify",
        data={
            "transaction_id": transaction_id,
            "otp_code": verification_secret,
        },
    )
    assert replay_response.status_code == 401
    logger.success("Transaction step-up integration stage completed.")
