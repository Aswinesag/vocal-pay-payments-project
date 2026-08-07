import numpy as np
import pytest
from unittest.mock import MagicMock
from unittest.mock import patch
from app.services.face_service import FaceProviderError
from app.services.providers.insightface_provider import InsightFaceProvider

@pytest.mark.asyncio
async def test_extract_embedding_rejects_none_image() -> None:
    provider = InsightFaceProvider()

    with patch.object(
        provider,
        "_ensure_model_loaded",
    ):
        with pytest.raises(FaceProviderError):
            await provider.extract_embedding(
                image=None,
            )

def test_validate_detected_faces_rejects_empty() -> None:
    provider = InsightFaceProvider()

    with pytest.raises(FaceProviderError):
        provider._validate_detected_faces([])

def test_validate_detected_faces_rejects_multiple_faces() -> None:
    provider = InsightFaceProvider()

    faces = [
        MagicMock(),
        MagicMock(),
    ]

    with pytest.raises(FaceProviderError):
        provider._validate_detected_faces(
            faces,
        )

def test_validate_detected_faces_returns_single_face() -> None:
    provider = InsightFaceProvider()

    face = MagicMock()

    assert (
        provider._validate_detected_faces(
            [face],
        )
        is face
    )

@pytest.mark.asyncio
async def test_extract_embedding_returns_numpy_array() -> None:
    provider = InsightFaceProvider()

    embedding = np.random.rand(
        512,
    ).astype(np.float32)

    face = MagicMock()
    face.embedding = embedding

    app = MagicMock()
    app.get.return_value = [face]

    provider._app = app
    provider._initialized = True

    result = await provider.extract_embedding(
        image=np.zeros(
            (112, 112, 3),
            dtype=np.uint8,
        ),
    )

    assert isinstance(
        result,
        np.ndarray,
    )

    assert result.shape == (512,)

@pytest.mark.asyncio
async def test_extract_embedding_rejects_empty_embedding() -> None:
    provider = InsightFaceProvider()

    face = MagicMock()
    face.embedding = np.array(
        [],
        dtype=np.float32,
    )

    app = MagicMock()
    app.get.return_value = [face]

    provider._app = app
    provider._initialized = True

    with pytest.raises(FaceProviderError):
        await provider.extract_embedding(
            image=np.zeros(
                (10, 10, 3),
                dtype=np.uint8,
            ),
        )

@pytest.mark.asyncio
async def test_verify_face_accepts_identical_embeddings() -> None:
    provider = InsightFaceProvider()

    provider._initialized = True

    embedding = np.ones(
        512,
        dtype=np.float32,
    )

    result = await provider.verify_face(
        enrolled_embedding=embedding,
        live_embedding=embedding.copy(),
    )

    assert result.verified
    assert result.confidence > 0.99

@pytest.mark.asyncio
async def test_verify_face_rejects_dimension_mismatch() -> None:
    provider = InsightFaceProvider()

    provider._initialized = True

    with pytest.raises(FaceProviderError):
        await provider.verify_face(
            enrolled_embedding=np.ones(512),
            live_embedding=np.ones(256),
        )

@pytest.mark.asyncio
async def test_verify_face_returns_result_object() -> None:
    provider = InsightFaceProvider()

    provider._initialized = True

    enrolled = np.random.rand(
        512,
    ).astype(np.float32)

    live = enrolled.copy()

    result = await provider.verify_face(
        enrolled_embedding=enrolled,
        live_embedding=live,
    )

    assert result.provider == provider.name

    assert isinstance(
        result.confidence,
        float,
    )

    assert isinstance(
        result.metadata,
        dict,
    )

@pytest.mark.asyncio
async def test_verify_face_confidence_range() -> None:
    provider = InsightFaceProvider()

    provider._initialized = True

    a = np.random.rand(
        512,
    ).astype(np.float32)

    b = np.random.rand(
        512,
    ).astype(np.float32)

    result = await provider.verify_face(
        enrolled_embedding=a,
        live_embedding=b,
    )

    assert 0.0 <= result.confidence <= 1.0

@pytest.mark.asyncio
async def test_shutdown_resets_provider() -> None:
    provider = InsightFaceProvider()

    provider._initialized = True
    provider._app = MagicMock()

    await provider.shutdown()

    assert provider.initialized is False
    assert provider.model_loaded is False

@pytest.mark.asyncio
async def test_shutdown_is_idempotent() -> None:
    provider = InsightFaceProvider()

    await provider.shutdown()
    await provider.shutdown()

    assert provider.initialized is False

@pytest.mark.asyncio
async def test_provider_can_reload_after_shutdown() -> None:
    provider = InsightFaceProvider()

    provider._initialized = True
    provider._app = MagicMock()

    await provider.shutdown()

    assert provider.model_loaded is False

    fake_model = MagicMock()

    with patch(
        "app.services.providers.insightface_provider.FaceAnalysis"
    ) as mocked:

        mocked.return_value = fake_model

        await provider._ensure_model_loaded()

        assert provider.initialized