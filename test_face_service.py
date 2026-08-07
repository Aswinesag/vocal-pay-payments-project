"""
Unit tests for face_service.py Section 1.

These tests validate only the provider-independent foundation.

No real face model is loaded.
No images are processed.
No provider implementation is required.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock

import pytest

from app.services import face_service
from app.services.face_service import (
    FACE_COMPONENT,
    FaceEmbeddingPair,
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
        "FaceEmbedding",
        "FaceEmbeddingPair",
        "FaceVerificationProvider",
        "FaceVerificationResult",
        "FaceProviderError",
        "FaceServiceError",
        "FaceValidationError",
    }

    assert set(__all__) == expected


# ==========================================================
# Section 2 - Face Embedding Validation
# ==========================================================

@pytest.mark.parametrize(
    ("embedding", "role", "message"),
    [
        (None, "Enrolled", "Enrolled embedding cannot be None"),
        (True, "Live", "Live embedding has an unsupported primitive type"),
        (1, "Enrolled", "Enrolled embedding has an unsupported primitive type"),
        (1.5, "Live", "Live embedding has an unsupported primitive type"),
        ("embedding", "Enrolled", "unsupported primitive type"),
    ],
)
def test_validate_embedding_rejects_invalid_values(
    embedding: object,
    role: str,
    message: str,
) -> None:
    """None and unsupported primitive embeddings are rejected."""

    with pytest.raises(FaceValidationError, match=message):
        face_service._validate_embedding(
            embedding,
            role=role,
        )


@pytest.mark.parametrize(
    "embedding",
    [
        b"",
        bytearray(),
        memoryview(b""),
        [],
        (),
        {},
        set(),
    ],
)
def test_validate_embedding_rejects_empty_sized_values(
    embedding: object,
) -> None:
    """Every supported empty container representation is rejected."""

    with pytest.raises(FaceValidationError, match="cannot be empty"):
        face_service._validate_embedding(
            embedding,
            role="Live",
        )


@pytest.mark.parametrize(
    "embedding",
    [
        object(),
        b"encoded-embedding",
        [0.1, 0.2, 0.3],
        (0.1, 0.2),
        {"vector": [0.1]},
    ],
)
def test_validate_embedding_returns_value_unchanged(
    embedding: object,
) -> None:
    """Validation never converts or copies provider-owned embeddings."""

    result = face_service._validate_embedding(
        embedding,
        role="Enrolled",
    )

    assert result is embedding


class _LengthRaisesTypeError:
    """Sized provider object whose length is not available."""

    def __len__(self) -> int:
        raise TypeError("length unavailable")


def test_validate_embedding_accepts_sized_object_without_length() -> None:
    """Provider objects raising TypeError from len remain supported."""

    embedding = _LengthRaisesTypeError()

    assert (
        face_service._validate_embedding(
            embedding,
            role="Live",
        )
        is embedding
    )


def test_prepare_embedding_pair_preserves_embeddings() -> None:
    """Pair preparation validates and preserves both representations."""

    enrolled = [0.1, 0.2]
    live = b"live-embedding"

    pair = face_service._prepare_embedding_pair(
        enrolled,
        live,
    )

    assert isinstance(pair, FaceEmbeddingPair)
    assert pair.enrolled_embedding is enrolled
    assert pair.live_embedding is live


def test_prepare_embedding_pair_validates_enrolled_embedding_first() -> None:
    """An invalid enrolled embedding stops pair preparation immediately."""

    with pytest.raises(
        FaceValidationError,
        match="Enrolled embedding cannot be None",
    ):
        face_service._prepare_embedding_pair(
            None,
            object(),
        )


def test_prepare_embedding_pair_validates_live_embedding() -> None:
    """A valid enrolled value does not bypass live validation."""

    with pytest.raises(
        FaceValidationError,
        match="Live embedding cannot be empty",
    ):
        face_service._prepare_embedding_pair(
            object(),
            [],
        )


def test_embedding_pair_is_immutable() -> None:
    """Validated embedding pairs cannot be reassigned."""

    pair = FaceEmbeddingPair(
        enrolled_embedding=object(),
        live_embedding=object(),
    )

    with pytest.raises(FrozenInstanceError):
        pair.live_embedding = object()


# ==========================================================
# Section 2 - Explicit Validation Audit Cases
# ==========================================================

def test_validate_embedding_accepts_object() -> None:
    embedding = object()

    result = face_service._validate_embedding(
        embedding,
        role="Enrolled",
    )

    assert result is embedding


def test_validate_embedding_rejects_none() -> None:
    with pytest.raises(
        FaceValidationError,
        match="Enrolled embedding cannot be None",
    ):
        face_service._validate_embedding(
            None,
            role="Enrolled",
        )


def test_validate_embedding_rejects_empty_list() -> None:
    with pytest.raises(FaceValidationError, match="cannot be empty"):
        face_service._validate_embedding(
            [],
            role="Live",
        )


def test_validate_embedding_rejects_empty_tuple() -> None:
    with pytest.raises(FaceValidationError, match="cannot be empty"):
        face_service._validate_embedding(
            (),
            role="Live",
        )


@pytest.mark.parametrize(
    "embedding",
    [True, False, 0, 1, -1, 0.0, 1.5, "embedding"],
)
def test_validate_embedding_rejects_primitive_types(
    embedding: object,
) -> None:
    with pytest.raises(
        FaceValidationError,
        match="unsupported primitive type",
    ):
        face_service._validate_embedding(
            embedding,
            role="Enrolled",
        )


def test_prepare_embedding_pair_returns_pair() -> None:
    pair = face_service._prepare_embedding_pair(
        object(),
        object(),
    )

    assert isinstance(pair, FaceEmbeddingPair)


def test_prepare_embedding_pair_preserves_objects() -> None:
    enrolled = object()
    live = object()

    pair = face_service._prepare_embedding_pair(
        enrolled,
        live,
    )

    assert pair.enrolled_embedding is enrolled
    assert pair.live_embedding is live


# ==========================================================
# Section 3 - Face Verification Engine
# ==========================================================

class _FaceProvider:
    """Controllable provider used to validate engine delegation."""

    name = "TestFaceProvider"

    def __init__(self) -> None:
        self.verify_face = AsyncMock(
            return_value=FaceVerificationResult(
                verified=True,
                confidence=0.94,
                face_detected=True,
                liveness_checked=False,
                provider=self.name,
                metadata={"source": "unit-test"},
            )
        )


def test_prepare_verification_context_returns_context() -> None:
    provider = _FaceProvider()
    enrolled = object()
    live = object()

    context = face_service._prepare_verification_context(
        provider,
        enrolled,
        live,
    )

    assert isinstance(context, face_service._VerificationContext)
    assert context.provider is provider
    assert context.embeddings.enrolled_embedding is enrolled
    assert context.embeddings.live_embedding is live


def test_verification_context_is_immutable() -> None:
    context = face_service._prepare_verification_context(
        _FaceProvider(),
        object(),
        object(),
    )

    with pytest.raises(FrozenInstanceError):
        context.provider = _FaceProvider()


def test_prepare_verification_context_rejects_none_provider() -> None:
    with pytest.raises(
        FaceValidationError,
        match="provider cannot be None",
    ):
        face_service._prepare_verification_context(
            None,
            object(),
            object(),
        )


class _ProviderWithoutVerify:
    name = "IncompleteProvider"


def test_prepare_verification_context_requires_verify_face() -> None:
    with pytest.raises(
        FaceValidationError,
        match=r"must implement verify_face\(\)",
    ):
        face_service._prepare_verification_context(
            _ProviderWithoutVerify(),
            object(),
            object(),
        )


@pytest.mark.parametrize("provider_name", [None, "", "   ", 123])
def test_prepare_verification_context_requires_valid_provider_name(
    provider_name: object,
) -> None:
    provider = _FaceProvider()
    provider.name = provider_name

    with pytest.raises(
        FaceValidationError,
        match="must expose a name",
    ):
        face_service._prepare_verification_context(
            provider,
            object(),
            object(),
        )


class _ProviderWithBrokenContract:
    async def verify_face(
        self,
        *,
        enrolled_embedding: object,
        live_embedding: object,
    ) -> FaceVerificationResult:
        raise AssertionError("must not be called")

    @property
    def name(self) -> str:
        raise RuntimeError("property failed")


def test_prepare_verification_context_wraps_contract_access_failure() -> None:
    with pytest.raises(
        FaceValidationError,
        match="contract is invalid",
    ):
        face_service._prepare_verification_context(
            _ProviderWithBrokenContract(),
            object(),
            object(),
        )


@pytest.mark.parametrize(
    ("enrolled", "live", "message"),
    [
        (None, object(), "Enrolled embedding cannot be None"),
        (object(), None, "Live embedding cannot be None"),
        ([], object(), "Enrolled embedding cannot be empty"),
        (object(), (), "Live embedding cannot be empty"),
    ],
)
def test_prepare_verification_context_validates_embeddings(
    enrolled: object,
    live: object,
    message: str,
) -> None:
    with pytest.raises(FaceValidationError, match=message):
        face_service._prepare_verification_context(
            _FaceProvider(),
            enrolled,
            live,
        )


@pytest.mark.asyncio
async def test_verify_face_delegates_to_provider() -> None:
    provider = _FaceProvider()
    enrolled = object()
    live = object()
    context = face_service._prepare_verification_context(
        provider,
        enrolled,
        live,
    )

    result = await face_service._verify_face(context)

    provider.verify_face.assert_awaited_once_with(
        enrolled_embedding=enrolled,
        live_embedding=live,
    )
    assert result is provider.verify_face.return_value


@pytest.mark.asyncio
async def test_verify_face_propagates_domain_exception() -> None:
    provider = _FaceProvider()
    provider.verify_face.side_effect = FaceProviderError(
        "provider unavailable"
    )
    context = face_service._prepare_verification_context(
        provider,
        object(),
        object(),
    )

    with pytest.raises(FaceProviderError, match="provider unavailable"):
        await face_service._verify_face(context)


@pytest.mark.asyncio
async def test_verify_face_wraps_unexpected_provider_exception() -> None:
    provider = _FaceProvider()
    provider.verify_face.side_effect = RuntimeError("inference failed")
    context = face_service._prepare_verification_context(
        provider,
        object(),
        object(),
    )

    with pytest.raises(
        FaceProviderError,
        match="TestFaceProvider.*failed",
    ) as exc_info:
        await face_service._verify_face(context)

    assert isinstance(exc_info.value.__cause__, RuntimeError)


class _ProviderWithDomainNameFailure(_FaceProvider):
    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        raise FaceValidationError("provider name unavailable")


class _ProviderWithUnexpectedNameFailure(_FaceProvider):
    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        raise RuntimeError("provider name unavailable")


@pytest.mark.asyncio
async def test_verify_face_propagates_domain_name_failure() -> None:
    context = face_service._VerificationContext(
        provider=_ProviderWithDomainNameFailure(),
        embeddings=FaceEmbeddingPair(object(), object()),
    )

    with pytest.raises(
        FaceValidationError,
        match="provider name unavailable",
    ):
        await face_service._verify_face(context)


@pytest.mark.asyncio
async def test_verify_face_wraps_unexpected_name_failure() -> None:
    context = face_service._VerificationContext(
        provider=_ProviderWithUnexpectedNameFailure(),
        embeddings=FaceEmbeddingPair(object(), object()),
    )

    with pytest.raises(FaceProviderError) as exc_info:
        await face_service._verify_face(context)

    assert isinstance(exc_info.value.__cause__, RuntimeError)
