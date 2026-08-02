"""
Tests for SpeechBrainProvider.

Validates provider foundation and model lifecycle.

Embedding extraction and speaker verification are
tested in later sections.
"""

from __future__ import annotations
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import torch
from app.services.providers.speechbrain_provider import (
    PROVIDER_NAME,
    PROVIDER_VERSION,
    SpeechBrainProvider,
)
from app.services.voice_service import (
    SpeakerVerificationProvider,
    SpeakerVerificationResult,
    VoiceProviderError,
    VoiceValidationError,
)

# ==========================================================
# Foundation
# ==========================================================

def test_provider_implements_protocol() -> None:
    provider = SpeechBrainProvider()

    assert isinstance(
        provider,
        SpeakerVerificationProvider,
    )


def test_provider_name() -> None:
    provider = SpeechBrainProvider()

    assert provider.name == PROVIDER_NAME


def test_provider_version() -> None:
    provider = SpeechBrainProvider()

    assert provider.version == PROVIDER_VERSION


def test_provider_initial_state() -> None:
    provider = SpeechBrainProvider()

    assert provider.initialized is False
    assert provider.model_loaded is False


# ==========================================================
# Lazy Model Loading
# ==========================================================

@pytest.mark.asyncio
async def test_model_loads_once() -> None:
    provider = SpeechBrainProvider()

    fake_model = MagicMock()

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ) as mocked_loader:

        await provider._ensure_model_loaded()
        await provider._ensure_model_loaded()

        mocked_loader.assert_called_once()

        assert provider.initialized
        assert provider.model_loaded


@pytest.mark.asyncio
async def test_model_loading_failure() -> None:
    provider = SpeechBrainProvider()

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        side_effect=RuntimeError("boom"),
    ):

        with pytest.raises(
            VoiceProviderError,
        ):
            await provider._ensure_model_loaded()


# ==========================================================
# Verification Input Validation
# ==========================================================

@pytest.mark.asyncio
async def test_verify_rejects_unsupported_embeddings() -> None:
    provider = SpeechBrainProvider()

    with pytest.raises(VoiceValidationError):
        await provider.verify_speaker(
            enrolled_embedding=object(),
            live_embedding=object(),
        )

    assert provider.initialized is False


@pytest.mark.asyncio
async def test_verify_does_not_load_model() -> None:
    provider = SpeechBrainProvider()

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
    ) as mocked_loader:
        for _ in range(3):
            await provider.verify_speaker(
                enrolled_embedding=torch.randn(1, 1, 192),
                live_embedding=torch.randn(1, 1, 192),
            )

        mocked_loader.assert_not_called()

@pytest.mark.asyncio
async def test_extract_embedding_none_audio() -> None:
    provider = SpeechBrainProvider()

    fake_model = MagicMock()

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ):
        with pytest.raises(
            VoiceValidationError,
        ):
            await provider.extract_embedding(None)

@pytest.mark.asyncio
async def test_extract_embedding_invalid_type() -> None:
    provider = SpeechBrainProvider()

    fake_model = MagicMock()

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ):
        with pytest.raises(
            VoiceValidationError,
        ):
            await provider.extract_embedding(
                "invalid",
            )

@pytest.mark.asyncio
async def test_extract_embedding_empty_tensor() -> None:
    provider = SpeechBrainProvider()

    fake_model = MagicMock()

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ):
        with pytest.raises(
            VoiceValidationError,
        ):
            await provider.extract_embedding(
                torch.empty(0),
            )

@pytest.mark.asyncio
async def test_extract_embedding_provider_failure() -> None:
    provider = SpeechBrainProvider()

    fake_model = MagicMock()

    fake_model.encode_batch.side_effect = RuntimeError(
        "Embedding failure",
    )

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ):
        audio = torch.randn(
            1,
            16000,
        )

        with pytest.raises(
            VoiceProviderError,
        ):
            await provider.extract_embedding(
                audio,
            )

@pytest.mark.asyncio
async def test_extract_embedding_success() -> None:
    provider = SpeechBrainProvider()

    fake_embedding = torch.randn(
        1,
        1,
        192,
    )

    fake_model = MagicMock()

    fake_model.encode_batch.return_value = (
        fake_embedding
    )

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ):
        audio = torch.randn(
            1,
            16000,
        )

        embedding = await provider.extract_embedding(
            audio,
        )

        fake_model.encode_batch.assert_called_once()

        assert torch.equal(
            embedding,
            fake_embedding,
        )

@pytest.mark.asyncio
async def test_extract_embedding_lazy_loading() -> None:
    provider = SpeechBrainProvider()

    fake_embedding = torch.randn(
        1,
        1,
        192,
    )

    fake_model = MagicMock()

    fake_model.encode_batch.return_value = (
        fake_embedding
    )

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ) as mocked_loader:

        audio = torch.randn(
            1,
            16000,
        )

        await provider.extract_embedding(
            audio,
        )

        mocked_loader.assert_called_once()

        assert provider.initialized

@pytest.mark.asyncio
async def test_extract_embedding_multiple_calls_load_once() -> None:
    provider = SpeechBrainProvider()

    fake_embedding = torch.randn(
        1,
        1,
        192,
    )

    fake_model = MagicMock()

    fake_model.encode_batch.return_value = (
        fake_embedding
    )

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ) as mocked_loader:

        audio = torch.randn(
            1,
            16000,
        )

        for _ in range(3):
            await provider.extract_embedding(
                audio,
            )

        mocked_loader.assert_called_once()

        assert fake_model.encode_batch.call_count == 3

@pytest.mark.asyncio
async def test_verify_speaker_success() -> None:
    provider = SpeechBrainProvider()

    enrolled = torch.randn(1, 1, 192)
    live = torch.randn(1, 1, 192)

    with patch.object(
        provider,
        "_compute_similarity",
        return_value=0.93,
    ):
        result = await provider.verify_speaker(
            enrolled_embedding=enrolled,
            live_embedding=live,
        )

    assert isinstance(
        result,
        SpeakerVerificationResult,
    )
    assert result.verified is True
    assert result.confidence == 0.93
    assert result.provider == provider.name

@pytest.mark.asyncio
async def test_verify_speaker_failure() -> None:
    provider = SpeechBrainProvider()

    enrolled = torch.randn(1, 1, 192)
    live = torch.randn(1, 1, 192)

    with patch.object(
        provider,
        "_compute_similarity",
        return_value=0.42,
    ):
        result = await provider.verify_speaker(
            enrolled_embedding=enrolled,
            live_embedding=live,
        )

    assert result.verified is False
    assert result.confidence == 0.42

@pytest.mark.asyncio
async def test_verify_invalid_enrolled_embedding() -> None:
    provider = SpeechBrainProvider()

    with pytest.raises(
        VoiceValidationError,
    ):
        await provider.verify_speaker(
            enrolled_embedding=None,
            live_embedding=torch.randn(1, 1, 192),
        )

@pytest.mark.asyncio
async def test_verify_invalid_live_embedding() -> None:
    provider = SpeechBrainProvider()

    with pytest.raises(
        VoiceValidationError,
    ):
        await provider.verify_speaker(
            enrolled_embedding=torch.randn(1, 1, 192),
            live_embedding=None,
        )

@pytest.mark.asyncio
async def test_verify_similarity_failure() -> None:
    provider = SpeechBrainProvider()

    enrolled = torch.randn(1, 1, 192)
    live = torch.randn(1, 1, 192)

    with patch.object(
        provider,
        "_compute_similarity",
        side_effect=VoiceProviderError(
            "Similarity failed.",
        ),
    ):
        with pytest.raises(
            VoiceProviderError,
        ):
            await provider.verify_speaker(
                enrolled_embedding=enrolled,
                live_embedding=live,
            )

@pytest.mark.asyncio
async def test_verify_metadata() -> None:
    provider = SpeechBrainProvider()

    enrolled = torch.randn(1, 1, 192)
    live = torch.randn(1, 1, 192)

    with patch.object(
        provider,
        "_compute_similarity",
        return_value=0.88,
    ):
        result = await provider.verify_speaker(
            enrolled_embedding=enrolled,
            live_embedding=live,
        )

    assert result.metadata["similarity"] == 0.88
    assert "threshold" in result.metadata

@pytest.mark.asyncio
async def test_verify_confidence_range() -> None:
    provider = SpeechBrainProvider()

    enrolled = torch.randn(1, 1, 192)
    live = torch.randn(1, 1, 192)

    with patch.object(
        provider,
        "_compute_similarity",
        return_value=0.76,
    ):
        result = await provider.verify_speaker(
            enrolled_embedding=enrolled,
            live_embedding=live,
        )

    assert -1.0 <= result.confidence <= 1.0

@pytest.mark.asyncio
async def test_verify_provider_name() -> None:
    provider = SpeechBrainProvider()

    enrolled = torch.randn(1, 1, 192)
    live = torch.randn(1, 1, 192)

    with patch.object(
        provider,
        "_compute_similarity",
        return_value=0.91,
    ):
        result = await provider.verify_speaker(
            enrolled_embedding=enrolled,
            live_embedding=live,
        )

    assert result.provider == provider.name

@pytest.mark.asyncio
async def test_verify_replay_default() -> None:
    provider = SpeechBrainProvider()

    enrolled = torch.randn(1, 1, 192)
    live = torch.randn(1, 1, 192)

    with patch.object(
        provider,
        "_compute_similarity",
        return_value=0.90,
    ):
        result = await provider.verify_speaker(
            enrolled_embedding=enrolled,
            live_embedding=live,
        )

    assert result.replay_detected is False

def test_similarity_clamped() -> None:
    provider = SpeechBrainProvider()

    enrolled = torch.randn(1, 1, 192)
    live = torch.randn(1, 1, 192)

    similarity = provider._compute_similarity(
        enrolled,
        live,
    )

    assert -1.0 <= similarity <= 1.0


# ==========================================================
# Production Provider Hardening
# ==========================================================

@pytest.mark.asyncio
async def test_concurrent_model_initialization_loads_once() -> None:
    provider = SpeechBrainProvider()
    fake_model = MagicMock()

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ) as mocked_loader:
        await asyncio.gather(
            *(provider._ensure_model_loaded() for _ in range(20))
        )

    mocked_loader.assert_called_once()
    assert provider.initialized is True
    assert provider._model is fake_model


@pytest.mark.asyncio
async def test_failed_initialization_can_be_retried() -> None:
    provider = SpeechBrainProvider()
    fake_model = MagicMock()

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        side_effect=[RuntimeError("unavailable"), fake_model],
    ) as mocked_loader:
        with pytest.raises(VoiceProviderError):
            await provider._ensure_model_loaded()

        assert provider.initialized is False
        assert provider._model is None

        await provider._ensure_model_loaded()

    assert mocked_loader.call_count == 2
    assert provider.initialized is True


@pytest.mark.asyncio
async def test_model_loader_receives_provider_configuration() -> None:
    cache_directory = Path.cwd()
    provider = SpeechBrainProvider(
        _model_source="test/model",
        _model_cache=cache_directory,
        _device="cpu",
    )

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=MagicMock(),
    ) as mocked_loader:
        await provider._ensure_model_loaded()

    mocked_loader.assert_called_once_with(
        source="test/model",
        savedir=str(cache_directory),
        run_opts={"device": "cpu"},
    )


@pytest.mark.parametrize(
    "configuration",
    [
        {"_model_source": ""},
        {"_model_source": "   "},
        {"_device": ""},
        {"_device": "meta"},
        {"_verification_threshold": True},
        {"_verification_threshold": "0.75"},
        {"_verification_threshold": float("nan")},
        {"_verification_threshold": -1.01},
        {"_verification_threshold": 1.01},
    ],
)
def test_invalid_provider_configuration_rejected(
    configuration: dict[str, object],
) -> None:
    with pytest.raises(VoiceValidationError):
        SpeechBrainProvider(**configuration)


def test_non_directory_model_cache_rejected() -> None:
    with pytest.raises(VoiceValidationError):
        SpeechBrainProvider(_model_cache=Path(__file__))


def test_unavailable_cuda_configuration_rejected() -> None:
    with patch.object(torch.cuda, "is_available", return_value=False):
        with pytest.raises(VoiceValidationError, match="CUDA"):
            SpeechBrainProvider(_device="cuda")


@pytest.mark.asyncio
async def test_embedding_extraction_uses_inference_mode() -> None:
    provider = SpeechBrainProvider()
    fake_model = MagicMock()
    inference_states: list[bool] = []

    def encode_batch(audio: torch.Tensor) -> torch.Tensor:
        inference_states.append(torch.is_inference_mode_enabled())
        assert audio.device.type == "cpu"
        return torch.randn(1, 1, 192)

    fake_model.encode_batch.side_effect = encode_batch

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ):
        await provider.extract_embedding(torch.randn(1, 16000))

    assert inference_states == [True]


@pytest.mark.asyncio
async def test_audio_device_transfer_failure_is_wrapped() -> None:
    provider = SpeechBrainProvider()
    audio = torch.randn(1, 16000)

    with (
        patch(
            "app.services.providers.speechbrain_provider."
            "EncoderClassifier.from_hparams",
            return_value=MagicMock(),
        ),
        patch.object(
            torch.Tensor,
            "to",
            side_effect=RuntimeError("transfer failed"),
        ),
    ):
        with pytest.raises(
            VoiceProviderError,
            match="transfer audio",
        ):
            await provider.extract_embedding(audio)


def test_embedding_normalization_produces_unit_norm() -> None:
    provider = SpeechBrainProvider()
    embedding = torch.tensor([[[3.0, 4.0]]])

    normalized = provider._normalize_embedding(embedding)

    norm = torch.linalg.vector_norm(normalized, dim=-1)
    assert torch.allclose(norm, torch.ones_like(norm))
    assert torch.equal(embedding, torch.tensor([[[3.0, 4.0]]]))


def test_similarity_uses_normalized_embeddings() -> None:
    provider = SpeechBrainProvider()
    enrolled = torch.tensor([[[10.0, 0.0]]])
    same_direction = torch.tensor([[[2.0, 0.0]]])
    opposite_direction = torch.tensor([[[-3.0, 0.0]]])

    assert provider._compute_similarity(enrolled, same_direction) == pytest.approx(1.0)
    assert provider._compute_similarity(enrolled, opposite_direction) == pytest.approx(-1.0)


@pytest.mark.asyncio
async def test_verification_uses_configured_threshold() -> None:
    provider = SpeechBrainProvider(_verification_threshold=0.9)
    embedding = torch.randn(1, 1, 192)

    with patch.object(provider, "_compute_similarity", return_value=0.85):
        result = await provider.verify_speaker(
            enrolled_embedding=embedding,
            live_embedding=embedding,
        )

    assert result.verified is False
    assert result.metadata["threshold"] == 0.9


@pytest.mark.asyncio
async def test_verification_operational_metadata() -> None:
    provider = SpeechBrainProvider()
    model = MagicMock()
    model.version = "model-2026.1"
    provider._model = model
    provider._initialized = True
    embedding = torch.randn(1, 1, 192)

    with patch.object(provider, "_compute_similarity", return_value=0.95):
        result = await provider.verify_speaker(
            enrolled_embedding=embedding,
            live_embedding=embedding,
        )

    assert result.metadata == {
        "threshold": 0.75,
        "similarity": 0.95,
        "provider_version": PROVIDER_VERSION,
        "device": "cpu",
        "model_source": "speechbrain/spkrec-ecapa-voxceleb",
        "model_version": "model-2026.1",
    }


@pytest.mark.asyncio
async def test_shutdown_is_idempotent_and_allows_reinitialization() -> None:
    provider = SpeechBrainProvider()
    first_model = MagicMock()
    second_model = MagicMock()

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        side_effect=[first_model, second_model],
    ) as mocked_loader:
        await provider._ensure_model_loaded()
        await provider.shutdown()
        await provider.shutdown()

        assert provider.initialized is False
        assert provider.model_loaded is False
        assert provider._model is None

        await provider._ensure_model_loaded()

    assert mocked_loader.call_count == 2
    assert provider.initialized is True
    assert provider._model is second_model


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enrolled", "live"),
    [
        (torch.empty(0), torch.randn(1, 1, 192)),
        (torch.randn(1, 1, 192), torch.empty(0)),
    ],
)
async def test_verification_rejects_empty_embeddings(
    enrolled: torch.Tensor,
    live: torch.Tensor,
) -> None:
    provider = SpeechBrainProvider()

    with pytest.raises(VoiceValidationError, match="empty"):
        await provider.verify_speaker(
            enrolled_embedding=enrolled,
            live_embedding=live,
        )
