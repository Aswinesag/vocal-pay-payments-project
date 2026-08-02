"""
Voice Biometric Verification Service

Provider-independent foundation for in-memory speaker verification.

This module does not access persistence, manage users, make
authentication decisions, or perform transaction operations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sized
from dataclasses import dataclass
from typing import Final, Protocol, TypeAlias

from app.core.logger import EnterpriseLogger, get_logger


# ==========================================================
# Service Configuration
# ==========================================================

VOICE_COMPONENT: Final[str] = "VOICE"
VOICE_LOG_EVENT: Final[str] = "voice_verification"
UNKNOWN_PROVIDER: Final[str] = "-"

logger: Final[EnterpriseLogger] = get_logger(
    VOICE_COMPONENT
)


# ==========================================================
# Domain Exceptions
# ==========================================================

class VoiceServiceError(Exception):
    """Base exception for voice verification failures."""


class VoiceValidationError(VoiceServiceError):
    """Raised when voice verification input is invalid."""


class VoiceProviderError(VoiceServiceError):
    """Raised when a speaker verification provider fails."""


# ==========================================================
# Verification Result
# ==========================================================

@dataclass(frozen=True, slots=True)
class SpeakerVerificationResult:
    """Immutable result returned by a speaker verification provider."""

    verified: bool
    confidence: float
    replay_detected: bool
    provider: str
    metadata: Mapping[str, object]


# ==========================================================
# Provider Contract
# ==========================================================

class SpeakerVerificationProvider(Protocol):
    """Interface implemented by speaker verification backends."""

    @property
    def name(self) -> str:
        """Return the stable provider name used for observability."""
        ...

    async def verify_speaker(
        self,
        *,
        enrolled_embedding: object,
        live_embedding: object,
    ) -> SpeakerVerificationResult:
        """Verify a live embedding against an enrolled embedding."""
        ...


# ==========================================================
# Internal Logging Helpers
# ==========================================================

def _log_voice_step(
    step: str,
    *,
    outcome: str,
    provider: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> None:
    """Emit a structured log for a voice verification step."""

    logger.info(
        f"Voice verification step '{step}' completed with outcome "
        f"'{outcome}'.",
        event=VOICE_LOG_EVENT,
        step=step,
        outcome=outcome,
        provider=provider or UNKNOWN_PROVIDER,
        metadata=dict(metadata or {}),
    )


def _log_voice_failure(
    step: str,
    error: VoiceServiceError,
    *,
    provider: str | None = None,
) -> None:
    """Emit a structured warning for a voice-domain failure."""

    logger.warning(
        f"Voice verification step '{step}' failed: {error}",
        event=VOICE_LOG_EVENT,
        step=step,
        outcome="FAILED",
        provider=provider or UNKNOWN_PROVIDER,
        error_type=type(error).__name__,
    )


def _log_voice_operation(
    operation: str,
    *,
    provider: str | None = None,
) -> None:
    """Emit a standardized voice verification milestone log."""

    logger.info(
        f"Voice operation '{operation}' completed by provider "
        f"'{provider or UNKNOWN_PROVIDER}'.",
        event=VOICE_LOG_EVENT,
        operation=operation,
        outcome="COMPLETED",
        provider=provider or UNKNOWN_PROVIDER,
    )


# ==========================================================
# Section 2 - Embedding Validation and Preparation
# ==========================================================

VoiceEmbedding: TypeAlias = object


@dataclass(frozen=True, slots=True)
class VoiceEmbeddingPair:
    """Validated enrolled and live embeddings for provider use."""

    enrolled_embedding: VoiceEmbedding
    live_embedding: VoiceEmbedding


def _validate_embedding(
    embedding: VoiceEmbedding,
    *,
    role: str,
) -> VoiceEmbedding:
    """Validate an embedding without changing its representation."""

    if embedding is None:
        error = VoiceValidationError(
            f"{role} embedding cannot be None."
        )
        _log_voice_failure(
            "EMBEDDING_VALIDATION",
            error,
        )
        raise error

    if isinstance(embedding, (bool, int, float, str)):
        error = VoiceValidationError(
            f"{role} embedding has an unsupported primitive type."
        )
        _log_voice_failure(
            "EMBEDDING_VALIDATION",
            error,
        )
        raise error

    if isinstance(embedding, Sized):
        try:
            is_empty = len(embedding) == 0
        except TypeError:
            is_empty = False

        if is_empty:
            error = VoiceValidationError(
                f"{role} embedding cannot be empty."
            )
            _log_voice_failure(
                "EMBEDDING_VALIDATION",
                error,
            )
            raise error

    _log_voice_step(
        "EMBEDDING_VALIDATION",
        outcome="VALIDATED",
        metadata={
            "embedding_role": role,
            "embedding_type": type(embedding).__name__,
        },
    )

    return embedding


def _prepare_embedding_pair(
    enrolled_embedding: VoiceEmbedding,
    live_embedding: VoiceEmbedding,
) -> VoiceEmbeddingPair:
    """Validate and package enrolled and live voice embeddings."""

    validated_enrolled = _validate_embedding(
        enrolled_embedding,
        role="Enrolled",
    )
    validated_live = _validate_embedding(
        live_embedding,
        role="Live",
    )

    pair = VoiceEmbeddingPair(
        enrolled_embedding=validated_enrolled,
        live_embedding=validated_live,
    )

    _log_voice_step(
        "EMBEDDING_PAIR_PREPARATION",
        outcome="PREPARED",
        metadata={
            "enrolled_embedding_type": type(
                validated_enrolled
            ).__name__,
            "live_embedding_type": type(
                validated_live
            ).__name__,
        },
    )

    return pair


# ==========================================================
# Section 3 - Speaker Verification Engine
# ==========================================================

@dataclass(frozen=True, slots=True)
class _VerificationContext:
    """Provider and validated embeddings for one verification request."""

    provider: SpeakerVerificationProvider
    embeddings: VoiceEmbeddingPair


def _prepare_verification_context(
    provider: SpeakerVerificationProvider,
    enrolled_embedding: VoiceEmbedding,
    live_embedding: VoiceEmbedding,
) -> _VerificationContext:
    """Validate a provider and prepare a speaker verification request."""

    embeddings = _prepare_embedding_pair(
        enrolled_embedding,
        live_embedding,
    )

    if provider is None:
        error = VoiceValidationError(
            "Speaker verification provider cannot be None."
        )
        _log_voice_failure(
            "VERIFICATION_CONTEXT_PREPARATION",
            error,
        )
        raise error

    try:
        verify_speaker = getattr(
            provider,
            "verify_speaker",
            None,
        )
        provider_name = getattr(provider, "name", None)

    except Exception as exc:
        error = VoiceValidationError(
            "Speaker verification provider contract is invalid."
        )
        _log_voice_failure(
            "VERIFICATION_CONTEXT_PREPARATION",
            error,
        )
        raise error from exc

    if not callable(verify_speaker):
        error = VoiceValidationError(
            "Speaker verification provider must implement "
            "verify_speaker()."
        )
        _log_voice_failure(
            "VERIFICATION_CONTEXT_PREPARATION",
            error,
        )
        raise error

    if not isinstance(provider_name, str) or not provider_name.strip():
        error = VoiceValidationError(
            "Speaker verification provider must expose a name."
        )
        _log_voice_failure(
            "VERIFICATION_CONTEXT_PREPARATION",
            error,
        )
        raise error

    context = _VerificationContext(
        provider=provider,
        embeddings=embeddings,
    )

    _log_voice_step(
        "VERIFICATION_CONTEXT_PREPARATION",
        outcome="PREPARED",
        provider=provider_name,
        metadata={
            "enrolled_embedding_type": type(
                embeddings.enrolled_embedding
            ).__name__,
            "live_embedding_type": type(
                embeddings.live_embedding
            ).__name__,
        },
    )

    return context


async def _verify_speaker(
    context: _VerificationContext,
) -> SpeakerVerificationResult:
    """Delegate speaker verification to the configured provider."""

    provider = context.provider

    try:
        provider_name = provider.name

    except VoiceServiceError as exc:
        _log_voice_failure(
            "PROVIDER_INVOCATION",
            exc,
        )
        raise

    except Exception as exc:
        error = VoiceProviderError(
            "Speaker verification provider failed."
        )
        _log_voice_failure(
            "PROVIDER_INVOCATION",
            error,
        )
        raise error from exc

    _log_voice_operation(
        "VERIFICATION_STARTED",
        provider=provider_name,
    )
    _log_voice_step(
        "PROVIDER_INVOCATION",
        outcome="STARTED",
        provider=provider_name,
    )

    try:
        result = await provider.verify_speaker(
            enrolled_embedding=(
                context.embeddings.enrolled_embedding
            ),
            live_embedding=context.embeddings.live_embedding,
        )

    except VoiceServiceError as exc:
        _log_voice_failure(
            "PROVIDER_INVOCATION",
            exc,
            provider=provider_name,
        )
        raise

    except Exception as exc:
        error = VoiceProviderError(
            f"Speaker verification provider '{provider_name}' failed."
        )
        _log_voice_failure(
            "PROVIDER_INVOCATION",
            error,
            provider=provider_name,
        )
        raise error from exc

    _log_voice_step(
        "PROVIDER_INVOCATION",
        outcome="COMPLETED",
        provider=provider_name,
    )
    _log_voice_operation(
        "VERIFICATION_COMPLETED",
        provider=provider_name,
    )

    return result


__all__ = [
    "SpeakerVerificationProvider",
    "SpeakerVerificationResult",
    "VoiceEmbedding",
    "VoiceEmbeddingPair",
    "VoiceProviderError",
    "VoiceServiceError",
    "VoiceValidationError",
]
