"""
Face Biometric Verification Service

Provider-independent foundation for in-memory face verification.

This module does not access persistence, manage users,
make authentication decisions, or perform transaction operations.
"""

from __future__ import annotations
from typing import Final
from typing_extensions import Protocol
from typing import Mapping
from app.core.config import settings
from dataclasses import dataclass
from app.core.logger import EnterpriseLogger, get_logger
TypeAlias = type

FACE_COMPONENT: Final[str] = "FACE"
FACE_LOG_EVENT: Final[str] = "face_verification"
UNKNOWN_PROVIDER: Final[str] = "-"

logger: Final[EnterpriseLogger] = get_logger(
    FACE_COMPONENT
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

__all__ = [
    "FaceVerificationProvider",
    "FaceVerificationResult",
    "FaceProviderError",
    "FaceServiceError",
    "FaceValidationError",
]