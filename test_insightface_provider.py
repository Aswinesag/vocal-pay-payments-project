"""Unit tests for the lazy InsightFace provider implementation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.face_service import FaceProviderError
from app.services.providers.insightface_provider import InsightFaceProvider


@pytest.fixture(autouse=True)
def reset_shared_model() -> None:
    InsightFaceProvider._model = None
    yield
    InsightFaceProvider._model = None


def _face(embedding: np.ndarray, bbox: tuple[float, float, float, float]) -> object:
    return SimpleNamespace(normed_embedding=embedding, bbox=np.asarray(bbox))


def test_constructor_is_lazy() -> None:
    with patch("app.services.providers.insightface_provider.FaceAnalysis") as model:
        provider = InsightFaceProvider()
    model.assert_not_called()
    assert provider.initialized is False


def test_extract_embedding_rejects_invalid_image() -> None:
    provider = InsightFaceProvider()
    with pytest.raises(ValueError, match="BGR image matrix"):
        provider.extract_embedding(image=None)


def test_extract_embedding_rejects_no_face() -> None:
    provider = InsightFaceProvider()
    provider._app = MagicMock()
    provider._app.get.return_value = []
    with pytest.raises(ValueError, match="No face detected"):
        provider.extract_embedding(image=np.zeros((64, 64, 3), dtype=np.uint8))


def test_extract_embedding_selects_largest_centered_face() -> None:
    provider = InsightFaceProvider()
    primary = np.linspace(0.0, 1.0, 512, dtype=np.float32)
    secondary = np.ones(512, dtype=np.float32)
    provider._app = MagicMock()
    provider._app.get.return_value = [
        _face(secondary, (0, 0, 10, 10)),
        _face(primary, (20, 20, 60, 60)),
    ]

    result = provider.extract_embedding(
        image=np.zeros((80, 80, 3), dtype=np.uint8)
    )

    assert isinstance(result, list)
    assert len(result) == 512
    assert result == pytest.approx(primary.tolist())


def test_extract_embedding_rejects_empty_embedding() -> None:
    provider = InsightFaceProvider()
    provider._app = MagicMock()
    provider._app.get.return_value = [_face(np.array([], dtype=np.float32), (0, 0, 5, 5))]
    with pytest.raises(FaceProviderError, match="invalid embedding"):
        provider.extract_embedding(image=np.zeros((10, 10, 3), dtype=np.uint8))


@pytest.mark.asyncio
async def test_verify_face_accepts_identical_embeddings() -> None:
    provider = InsightFaceProvider()
    embedding = np.ones(512, dtype=np.float32)
    result = await provider.verify_face(
        enrolled_embedding=embedding,
        live_embedding=embedding.copy(),
    )
    assert result.verified
    assert result.confidence == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_verify_face_rejects_dimension_mismatch() -> None:
    provider = InsightFaceProvider()
    with pytest.raises(FaceProviderError):
        await provider.verify_face(
            enrolled_embedding=np.ones(512),
            live_embedding=np.ones(256),
        )


@pytest.mark.asyncio
async def test_verify_face_confidence_range() -> None:
    provider = InsightFaceProvider()
    result = await provider.verify_face(
        enrolled_embedding=np.random.default_rng(1).random(512),
        live_embedding=np.random.default_rng(2).random(512),
    )
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_shutdown_is_idempotent_and_allows_reload() -> None:
    provider = InsightFaceProvider()
    provider._app = MagicMock()
    InsightFaceProvider._model = provider._app
    await provider.shutdown()
    await provider.shutdown()
    assert provider.initialized is False
    assert provider.model_loaded is False

    fake_model = MagicMock()
    with patch(
        "app.services.providers.insightface_provider.FaceAnalysis",
        return_value=fake_model,
    ):
        provider._ensure_model_loaded()
    assert provider.initialized is True
