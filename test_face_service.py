"""
Unit tests for face_service.py Section 1.

These tests validate only the provider-independent foundation.

No real face model is loaded.
No images are processed.
No provider implementation is required.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.services.face_service import (
    FACE_COMPONENT,
    FaceProviderError,
    FaceServiceError,
    FaceValidationError,
    FaceVerificationProvider,
    FaceVerificationResult,
    logger,
)


# ==========================================================
# Provider Contract
# ==========================================================

def test_provider_protocol_exists() -> None:
    """Face provider protocol exposes the required interface."""

    assert hasattr(
        FaceVerificationProvider,
        "extract_embedding",
    )

    assert hasattr(
        FaceVerificationProvider,
        "verify_face",
    )

    assert hasattr(
        FaceVerificationProvider,
        "name",
    )


# ==========================================================
# Result Dataclass
# ==========================================================

def test_result_dataclass_fields() -> None:
    """Verification result stores the expected values."""

    result = FaceVerificationResult(
        verified=True,
        confidence=0.98,
        face_detected=True,
        liveness_checked=False,
        provider="InsightFace",
        metadata={"model": "buffalo_l"},
    )

    assert result.verified is True
    assert result.confidence == 0.98
    assert result.face_detected is True
    assert result.liveness_checked is False
    assert result.provider == "InsightFace"
    assert result.metadata["model"] == "buffalo_l"


def test_result_is_immutable() -> None:
    """Verification result must be immutable."""

    result = FaceVerificationResult(
        verified=True,
        confidence=0.91,
        face_detected=True,
        liveness_checked=False,
        provider="InsightFace",
        metadata={},
    )

    with pytest.raises(FrozenInstanceError):
        result.confidence = 0.50


# ==========================================================
# Exception Hierarchy
# ==========================================================

def test_exception_hierarchy() -> None:
    """All domain exceptions inherit correctly."""

    assert issubclass(
        FaceValidationError,
        FaceServiceError,
    )

    assert issubclass(
        FaceProviderError,
        FaceServiceError,
    )


# ==========================================================
# Logger
# ==========================================================

def test_logger_component() -> None:
    """Logger is initialized."""

    assert logger is not None
    assert FACE_COMPONENT == "FACE"


# ==========================================================
# Public API
# ==========================================================

def test_public_api_exports() -> None:
    """Public API exports remain stable."""

    from app.services.face_service import __all__

    expected = {
        "FaceVerificationProvider",
        "FaceVerificationResult",
        "FaceProviderError",
        "FaceServiceError",
        "FaceValidationError",
    }

    assert set(__all__) == expected