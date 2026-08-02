"""
Tests for SpeechBrainProvider.

Validates provider foundation and model lifecycle.

Embedding extraction and speaker verification are
tested in later sections.
"""

from __future__ import annotations
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
# Verification Stub
# ==========================================================

@pytest.mark.asyncio
async def test_verify_triggers_lazy_loading() -> None:
    provider = SpeechBrainProvider()

    fake_model = MagicMock()

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ):

        with pytest.raises(
            NotImplementedError,
        ):
            await provider.verify_speaker(
                enrolled_embedding=object(),
                live_embedding=object(),
            )

        assert provider.initialized


@pytest.mark.asyncio
async def test_verify_does_not_reload_model() -> None:
    provider = SpeechBrainProvider()

    fake_model = MagicMock()

    with patch(
        "app.services.providers.speechbrain_provider."
        "EncoderClassifier.from_hparams",
        return_value=fake_model,
    ) as mocked_loader:

        for _ in range(3):
            with pytest.raises(
                NotImplementedError,
            ):
                await provider.verify_speaker(
                    enrolled_embedding=object(),
                    live_embedding=object(),
                )

        mocked_loader.assert_called_once()

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