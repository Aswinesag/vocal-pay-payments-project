"""Tests for authentication orchestration and dependency boundaries."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from app.services import authentication_service as service
from app.services.authentication_service import (
    AuthenticationDependencyError,
    AuthenticationValidationError,
    ChallengeAuthenticationResult,
    FaceAuthenticationResult,
)
from app.services.voice_service import (
    SpeakerVerificationResult,
    VoiceProviderError,
    VoiceValidationError,
)


class _VoiceProvider:
    name = "TestVoice"

    def __init__(self) -> None:
        self.extract_embedding = AsyncMock(return_value=object())
        self.verify_speaker = AsyncMock(
            return_value=SpeakerVerificationResult(
                verified=True,
                confidence=0.95,
                replay_detected=False,
                provider=self.name,
                metadata={"source": "test"},
            )
        )


class _FaceProvider:
    name = "TestFace"

    def __init__(self, *, verified: bool = True) -> None:
        self.verify_face = AsyncMock(
            return_value=FaceAuthenticationResult(
                verified=verified,
                confidence=0.9,
                provider=self.name,
                metadata={"source": "test"},
            )
        )


class _ChallengeProvider:
    def __init__(self) -> None:
        self.validate_response = AsyncMock(
            return_value=ChallengeAuthenticationResult(
                verified=True,
                provider="TestChallenge",
                metadata={},
            )
        )


def _context() -> service._ValidatedAuthenticationContext:
    user = SimpleNamespace(user_id="USR_AUTH_001")
    return service._ValidatedAuthenticationContext(
        user=cast(object, user),
        speaker_embedding=object(),
        face_embedding=object(),
        request_id="request-001",
    )


@pytest.mark.asyncio
async def test_voice_orchestration_uses_provider_factory() -> None:
    context = _context()
    provider = _VoiceProvider()
    payload = object()

    with patch.object(
        service,
        "get_speaker_verification_provider",
        return_value=provider,
    ) as provider_factory:
        result = await service._authenticate_voice(context, payload)

    provider_factory.assert_called_once_with()
    provider.extract_embedding.assert_awaited_once_with(payload)
    provider.verify_speaker.assert_awaited_once()
    assert result is provider.verify_speaker.return_value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [None, b"", bytearray(), memoryview(b""), "audio", 1, 1.0, True],
)
async def test_voice_payload_validation(payload: object) -> None:
    with pytest.raises(AuthenticationValidationError):
        await service._authenticate_voice(_context(), payload)


@pytest.mark.asyncio
async def test_voice_provider_validation_failure_is_preserved() -> None:
    provider = _VoiceProvider()
    provider.extract_embedding.side_effect = VoiceValidationError("bad audio")

    with patch.object(
        service,
        "get_speaker_verification_provider",
        return_value=provider,
    ):
        with pytest.raises(AuthenticationValidationError, match="bad audio"):
            await service._authenticate_voice(_context(), object())


@pytest.mark.asyncio
async def test_voice_provider_failure_is_translated() -> None:
    provider = _VoiceProvider()
    provider.verify_speaker.side_effect = VoiceProviderError("provider failed")

    with patch.object(
        service,
        "get_speaker_verification_provider",
        return_value=provider,
    ):
        with pytest.raises(AuthenticationDependencyError):
            await service._authenticate_voice(_context(), object())


@pytest.mark.asyncio
async def test_face_orchestration_delegates_unchanged() -> None:
    context = _context()
    provider = _FaceProvider()
    payload = object()

    result = await service._authenticate_face(context, payload, provider)

    provider.verify_face.assert_awaited_once_with(
        enrolled_embedding=context.face_embedding,
        live_payload=payload,
    )
    assert result is provider.verify_face.return_value


@pytest.mark.asyncio
async def test_face_provider_unavailable() -> None:
    with pytest.raises(AuthenticationDependencyError):
        await service._authenticate_face(_context(), object(), None)


@pytest.mark.asyncio
async def test_face_dependency_failure_is_translated() -> None:
    provider = _FaceProvider()
    provider.verify_face.side_effect = RuntimeError("provider failed")

    with pytest.raises(AuthenticationDependencyError):
        await service._authenticate_face(_context(), object(), provider)


def test_authentication_session_creation() -> None:
    session = service._create_authentication_session(
        "USR_AUTH_001",
        request_id="request-001",
        metadata={"channel": "mobile"},
    )

    assert session.request_id == "request-001"
    assert session.user_id == "USR_AUTH_001"
    assert session.started_at.tzinfo is not None
    assert session.metadata == {"channel": "mobile"}

    with pytest.raises(TypeError):
        session.metadata["channel"] = "web"

    with pytest.raises(FrozenInstanceError):
        session.user_id = "changed"


def test_authentication_session_generates_unique_identifiers() -> None:
    first = service._create_authentication_session("USR_AUTH_001")
    second = service._create_authentication_session("USR_AUTH_001")

    assert first.request_id != second.request_id


@pytest.mark.asyncio
async def test_multimodal_orchestration_success() -> None:
    context = _context()
    voice_result = SpeakerVerificationResult(
        verified=True,
        confidence=0.95,
        replay_detected=False,
        provider="TestVoice",
        metadata={},
    )
    face_result = FaceAuthenticationResult(
        verified=True,
        confidence=0.9,
        provider="TestFace",
        metadata={},
    )

    with (
        patch.object(
            service,
            "_prepare_authentication_context",
            AsyncMock(return_value=context),
        ),
        patch.object(
            service,
            "_authenticate_voice",
            AsyncMock(return_value=voice_result),
        ),
        patch.object(
            service,
            "_authenticate_face",
            AsyncMock(return_value=face_result),
        ),
    ):
        result = await service.authenticate_multimodal(
            cast(object, AsyncMock()),
            context.user.user_id,
            object(),
            object(),
            face_provider=_FaceProvider(),
            request_id="request-001",
        )

    assert result.authenticated is True
    assert result.voice_result is voice_result
    assert result.face_result is face_result
    assert result.request_id == "request-001"
    assert result.completed_at >= result.started_at


@pytest.mark.asyncio
async def test_multimodal_partial_failure_is_not_authenticated() -> None:
    context = _context()
    voice_result = SpeakerVerificationResult(
        verified=True,
        confidence=0.95,
        replay_detected=False,
        provider="TestVoice",
        metadata={},
    )
    face_result = FaceAuthenticationResult(
        verified=False,
        confidence=0.3,
        provider="TestFace",
        metadata={},
    )

    with (
        patch.object(
            service,
            "_prepare_authentication_context",
            AsyncMock(return_value=context),
        ),
        patch.object(
            service,
            "_authenticate_voice",
            AsyncMock(return_value=voice_result),
        ),
        patch.object(
            service,
            "_authenticate_face",
            AsyncMock(return_value=face_result),
        ),
    ):
        result = await service.authenticate_multimodal(
            cast(object, AsyncMock()),
            context.user.user_id,
            object(),
            object(),
            face_provider=_FaceProvider(verified=False),
        )

    assert result.authenticated is False


@pytest.mark.asyncio
async def test_challenge_orchestration() -> None:
    auth_session = service._create_authentication_session("USR_AUTH_001")
    provider = _ChallengeProvider()

    result = await service.authenticate_challenge(
        auth_session,
        "repeat phrase",
        "spoken response",
        provider=provider,
    )

    assert result is provider.validate_response.return_value
    provider.validate_response.assert_awaited_once_with(
        user_id=auth_session.user_id,
        challenge="repeat phrase",
        response="spoken response",
        request_id=auth_session.request_id,
    )


@pytest.mark.asyncio
async def test_challenge_provider_unavailable() -> None:
    auth_session = service._create_authentication_session("USR_AUTH_001")

    with pytest.raises(AuthenticationDependencyError):
        await service.authenticate_challenge(
            auth_session,
            "challenge",
            "response",
        )


def test_authentication_public_api_is_stable() -> None:
    assert service.__all__ == [
        "AUTHENTICATION_COMPONENT",
        "AuthenticationResult",
        "AuthenticationSession",
        "AuthenticationDependencyError",
        "AuthenticationServiceError",
        "AuthenticationValidationError",
        "ChallengeAuthenticationProvider",
        "ChallengeAuthenticationResult",
        "FaceAuthenticationProvider",
        "FaceAuthenticationResult",
        "authenticate_challenge",
        "authenticate_face",
        "authenticate_multimodal",
        "authenticate_voice",
    ]
