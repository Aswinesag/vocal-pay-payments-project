"""
Voice Biometric Verification Service

Provider-independent foundation for in-memory speaker verification.

This module does not access persistence, manage users, make
authentication decisions, or perform transaction operations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

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


__all__ = [
    "SpeakerVerificationProvider",
    "SpeakerVerificationResult",
    "VoiceProviderError",
    "VoiceServiceError",
    "VoiceValidationError",
]
