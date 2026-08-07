"""
Face Biometric Verification Service

Provider-independent foundation for in-memory face verification.

This module does not access persistence, manage users,
make authentication decisions, or perform transaction operations.
"""

from __future__ import annotations
from collections.abc import Mapping, Sized
from dataclasses import dataclass
from typing import Final, Protocol, TypeAlias

from app.core.logger import EnterpriseLogger, get_logger

FACE_COMPONENT: Final[str] = "FACE"
FACE_LOG_EVENT: Final[str] = "face_verification"
UNKNOWN_PROVIDER: Final[str] = "-"

logger: Final[EnterpriseLogger] = get_logger(
    FACE_COMPONENT
)


def _log_face_step(
    step: str,
    *,
    outcome: str,
    provider: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> None:
    """Emit a structured face-verification workflow log."""

    logger.info(
        f"Face verification step '{step}' completed with outcome "
        f"'{outcome}'.",
        event=FACE_LOG_EVENT,
        step=step,
        outcome=outcome,
        provider=provider or UNKNOWN_PROVIDER,
        metadata=dict(metadata or {}),
    )


def _log_face_failure(
    step: str,
    error: FaceServiceError,
    *,
    provider: str | None = None,
) -> None:
    """Emit a structured face-verification failure log."""

    logger.warning(
        f"Face verification step '{step}' failed: {error}",
        event=FACE_LOG_EVENT,
        step=step,
        outcome="FAILED",
        provider=provider or UNKNOWN_PROVIDER,
        error_type=type(error).__name__,
    )


def _log_face_operation(
    operation: str,
    *,
    provider: str | None = None,
) -> None:
    """Emit a structured face-verification operation log."""

    logger.info(
        f"Face operation '{operation}' completed by provider "
        f"'{provider or UNKNOWN_PROVIDER}'.",
        event=FACE_LOG_EVENT,
        operation=operation,
        outcome="COMPLETED",
        provider=provider or UNKNOWN_PROVIDER,
    )

class FaceServiceError(Exception):
    """Base exception for face verification failures."""


class FaceValidationError(FaceServiceError):
    """Raised when face verification input is invalid."""


class FaceProviderError(FaceServiceError):
    """Raised when a face verification provider fails."""

@dataclass(frozen=True, slots=True)
class FaceVerificationResult:
    """Immutable result returned by a face verification provider."""

    verified: bool
    confidence: float
    face_detected: bool
    liveness_checked: bool
    provider: str
    metadata: Mapping[str, object]

class FaceVerificationProvider(Protocol):
    """Interface implemented by face verification backends."""

    @property
    def name(self) -> str:
        ...

    async def extract_embedding(
        self,
        *,
        image: object,
    ) -> object:
        ...

    async def verify_face(
        self,
        *,
        enrolled_embedding: object,
        live_embedding: object,
    ) -> FaceVerificationResult:
        ...

# ==========================================================
# Section 2 - Face Embedding Validation
# ==========================================================

FaceEmbedding: TypeAlias = object
FaceImage: TypeAlias = object


@dataclass(frozen=True, slots=True)
class FaceEmbeddingPair:
    """Validated enrolled and live face embeddings for provider use."""

    enrolled_embedding: FaceEmbedding
    live_embedding: FaceEmbedding


def _validate_embedding(
    embedding: FaceEmbedding,
    *,
    role: str,
) -> FaceEmbedding:
    """Validate a face embedding without changing its representation."""

    if embedding is None:
        error = FaceValidationError(
            f"{role} embedding cannot be None."
        )
        _log_face_failure(
            "EMBEDDING_VALIDATION",
            error,
        )
        raise error

    if isinstance(
        embedding,
        (
            bool,
            int,
            float,
            str,
        ),
    ):
        error = FaceValidationError(
            f"{role} embedding has an unsupported primitive type."
        )
        _log_face_failure(
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
            error = FaceValidationError(
                f"{role} embedding cannot be empty."
            )
            _log_face_failure(
                "EMBEDDING_VALIDATION",
                error,
            )
            raise error

    _log_face_step(
        "EMBEDDING_VALIDATION",
        outcome="VALIDATED",
        metadata={
            "embedding_role": role,
            "embedding_type": type(
                embedding
            ).__name__,
        },
    )

    return embedding

def _prepare_embedding_pair(
    enrolled_embedding: FaceEmbedding,
    live_embedding: FaceEmbedding,
) -> FaceEmbeddingPair:
    """Validate and package enrolled and live face embeddings."""

    validated_enrolled = _validate_embedding(
        enrolled_embedding,
        role="Enrolled",
    )

    validated_live = _validate_embedding(
        live_embedding,
        role="Live",
    )

    pair = FaceEmbeddingPair(
        enrolled_embedding=validated_enrolled,
        live_embedding=validated_live,
    )

    _log_face_step(
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
# Section 3 - Face Verification Engine
# ==========================================================

@dataclass(frozen=True, slots=True)
class _VerificationContext:
    """Provider and validated embeddings for one verification request."""

    provider: FaceVerificationProvider
    embeddings: FaceEmbeddingPair

def _prepare_verification_context(
    provider: FaceVerificationProvider,
    enrolled_embedding: FaceEmbedding,
    live_embedding: FaceEmbedding,
) -> _VerificationContext:
    """Validate a provider and prepare a face verification request."""

    embeddings = _prepare_embedding_pair(
        enrolled_embedding,
        live_embedding,
    )

    if provider is None:
        error = FaceValidationError(
            "Face verification provider cannot be None."
        )
        _log_face_failure(
            "VERIFICATION_CONTEXT_PREPARATION",
            error,
        )
        raise error

    try:
        verify_face = getattr(
            provider,
            "verify_face",
            None,
        )

        provider_name = getattr(
            provider,
            "name",
            None,
        )

    except Exception as exc:
        error = FaceValidationError(
            "Face verification provider contract is invalid."
        )

        _log_face_failure(
            "VERIFICATION_CONTEXT_PREPARATION",
            error,
        )

        raise error from exc

    if not callable(verify_face):
        error = FaceValidationError(
            "Face verification provider must implement "
            "verify_face()."
        )

        _log_face_failure(
            "VERIFICATION_CONTEXT_PREPARATION",
            error,
        )

        raise error

    if (
        not isinstance(provider_name, str)
        or not provider_name.strip()
    ):
        error = FaceValidationError(
            "Face verification provider must expose a name."
        )

        _log_face_failure(
            "VERIFICATION_CONTEXT_PREPARATION",
            error,
        )

        raise error

    context = _VerificationContext(
        provider=provider,
        embeddings=embeddings,
    )

    _log_face_step(
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

async def _verify_face(
    context: _VerificationContext,
) -> FaceVerificationResult:
    """Delegate face verification to the configured provider."""

    provider = context.provider

    try:
        provider_name = provider.name

    except FaceServiceError as exc:
        _log_face_failure(
            "PROVIDER_INVOCATION",
            exc,
        )
        raise

    except Exception as exc:
        error = FaceProviderError(
            "Face verification provider failed."
        )

        _log_face_failure(
            "PROVIDER_INVOCATION",
            error,
        )

        raise error from exc

    _log_face_operation(
        "VERIFICATION_STARTED",
        provider=provider_name,
    )

    _log_face_step(
        "PROVIDER_INVOCATION",
        outcome="STARTED",
        provider=provider_name,
    )

    try:
        result = await provider.verify_face(
            enrolled_embedding=(
                context.embeddings.enrolled_embedding
            ),
            live_embedding=(
                context.embeddings.live_embedding
            ),
        )

    except FaceServiceError as exc:
        _log_face_failure(
            "PROVIDER_INVOCATION",
            exc,
            provider=provider_name,
        )

        raise

    except Exception as exc:
        error = FaceProviderError(
            f"Face verification provider "
            f"'{provider_name}' failed."
        )

        _log_face_failure(
            "PROVIDER_INVOCATION",
            error,
            provider=provider_name,
        )

        raise error from exc

    _log_face_step(
        "PROVIDER_INVOCATION",
        outcome="COMPLETED",
        provider=provider_name,
    )

    _log_face_operation(
        "VERIFICATION_COMPLETED",
        provider=provider_name,
    )

    return result

__all__ = [
    "FaceEmbedding",
    "FaceEmbeddingPair",
    "FaceVerificationProvider",
    "FaceVerificationResult",
    "FaceProviderError",
    "FaceServiceError",
    "FaceValidationError",
]
