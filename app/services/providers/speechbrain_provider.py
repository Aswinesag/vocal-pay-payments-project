"""
SpeechBrain Speaker Verification Provider

Concrete implementation of the
SpeakerVerificationProvider protocol.

This module owns the lifecycle of the SpeechBrain
speaker verification model.

Model loading and inference are implemented in
later sections.
"""
from __future__ import annotations
import torch
from typing import TypeAlias
from dataclasses import dataclass, field
from typing import Final
from app.services.voice_service import (
    SpeakerVerificationProvider,
    SpeakerVerificationResult,
    VoiceProviderError,
    VoiceValidationError,
    _log_voice_failure,
    _log_voice_operation,
    _log_voice_step,
)
from pathlib import Path
from speechbrain.inference.speaker import EncoderClassifier


SpeechBrainAudio: TypeAlias = torch.Tensor
SpeechBrainEmbedding: TypeAlias = torch.Tensor

# ==========================================================
# Provider Configuration
# ==========================================================

DEFAULT_DEVICE: Final[str] = "cpu"
DEFAULT_MODEL_SOURCE: Final[str] = (
    "speechbrain/spkrec-ecapa-voxceleb"
)
DEFAULT_MODEL_CACHE: Final[Path] = (
    Path.home()
    / ".cache"
    / "vocalpay"
    / "speechbrain"
)
PROVIDER_NAME: Final[str] = "SpeechBrain"
PROVIDER_VERSION: Final[str] = "1.0"
MODEL_NOT_INITIALIZED_MESSAGE: Final[str] = (
    "SpeechBrain model has not been initialized."
)
DEFAULT_VERIFICATION_THRESHOLD: Final[float] = 0.75
MIN_SIMILARITY_SCORE: Final[float] = -1.0
MAX_SIMILARITY_SCORE: Final[float] = 1.0
# ==========================================================
# SpeechBrain Provider
# ==========================================================

@dataclass(slots=True)
class SpeechBrainProvider(SpeakerVerificationProvider):
    """
    Concrete SpeechBrain implementation of the
    SpeakerVerificationProvider protocol.

    The provider owns model lifecycle only.

    Model loading and inference are introduced
    incrementally in later sections.
    """

    _model: object | None = field(
        default=None,
        init=False,
        repr=False,
    )

    _initialized: bool = field(
        default=False,
        init=False,
    )

    _version: str = field(
        default=PROVIDER_VERSION,
        init=False,
    )

    _device: str = field(
        default=DEFAULT_DEVICE,
    )

    _model_source: str = field(
        default=DEFAULT_MODEL_SOURCE,
    )

    _model_cache: Path = field(
        default=DEFAULT_MODEL_CACHE,
    )

    async def _ensure_model_loaded(self) -> None:
        """
        Lazily load the SpeechBrain model.

        The model is loaded only once during the provider
        lifetime.
        """

        if self._initialized:
            return

        try:
            self._model = EncoderClassifier.from_hparams(
                source=self._model_source,
                savedir=str(self._model_cache),
                run_opts={
                    "device": self._device,
                },
            )

        except Exception as exc:
            raise VoiceProviderError(
                "Unable to initialize SpeechBrain model."
            ) from exc

        self._initialized = True

    @property
    def name(self) -> str:
        """Stable provider name."""

        return PROVIDER_NAME

    @property
    def version(self) -> str:
        """Provider implementation version."""

        return self._version

    @property
    def initialized(self) -> bool:
        """Whether the provider has loaded a model."""
        return self._initialized
    
    @property
    def model_loaded(self) -> bool:
        """
        Whether the SpeechBrain model has been loaded.
        """
        return self._initialized

    async def verify_speaker(
        self,
        *,
        enrolled_embedding: object,
        live_embedding: object,
    ) -> SpeakerVerificationResult:
        """
        Verify a live embedding against an enrolled embedding.
        """

        if not isinstance(enrolled_embedding, torch.Tensor):
            raise VoiceValidationError(
                "Enrolled embedding must be a torch.Tensor."
            )

        if enrolled_embedding.numel() == 0:
            raise VoiceValidationError(
                "Enrolled embedding cannot be empty."
            )

        if not isinstance(live_embedding, torch.Tensor):
            raise VoiceValidationError(
                "Live embedding must be a torch.Tensor."
            )

        if live_embedding.numel() == 0:
            raise VoiceValidationError(
                "Live embedding cannot be empty."
            )

        _log_voice_operation(
            "VERIFICATION_STARTED",
            provider=self.name,
        )

        similarity = self._compute_similarity(
            enrolled_embedding,
            live_embedding,
        )

        result = SpeakerVerificationResult(
            verified=similarity >= DEFAULT_VERIFICATION_THRESHOLD,
            confidence=similarity,
            replay_detected=False,
            provider=self.name,
            metadata={
                "threshold": DEFAULT_VERIFICATION_THRESHOLD,
                "similarity": similarity,
            },
        )

        _log_voice_operation(
            "VERIFICATION_COMPLETED",
            provider=self.name,
        )

        return result

    def _validate_audio(
        self,
        audio: torch.Tensor,
    ) -> torch.Tensor:
        """
        Validate audio before embedding extraction.
        """

        if audio is None:
            raise VoiceValidationError(
                "Audio tensor cannot be None."
            )

        if not isinstance(audio, torch.Tensor):
            raise VoiceValidationError(
                "Audio must be a torch.Tensor."
            )

        if audio.numel() == 0:
            raise VoiceValidationError(
                "Audio tensor cannot be empty."
            )

        return audio

    async def extract_embedding(
        self,
        audio: torch.Tensor,
    ) -> torch.Tensor:
        """
        Generate a speaker embedding using SpeechBrain.

        This method is reusable for:

        - user registration
        - speaker verification
        - profile updates
        """

        await self._ensure_model_loaded()

        audio = self._validate_audio(audio)

        try:
            embedding = self._model.encode_batch(audio)

        except Exception as exc:
            raise VoiceProviderError(
                "SpeechBrain failed to generate "
                "speaker embedding."
            ) from exc

        return embedding

    def _validate_audio(
        self,
        audio: SpeechBrainAudio,
    ) -> SpeechBrainAudio:
        """
        Validate audio before embedding extraction.
        """

        if audio is None:
            error = VoiceValidationError(
                "Audio tensor cannot be None."
            )
            _log_voice_failure(
                "AUDIO_VALIDATION",
                error,
                provider=self.name,
            )
            raise error

        if not isinstance(audio, torch.Tensor):
            error = VoiceValidationError(
                "Audio must be a torch.Tensor."
            )
            _log_voice_failure(
                "AUDIO_VALIDATION",
                error,
                provider=self.name,
            )
            raise error

        if audio.numel() == 0:
            error = VoiceValidationError(
                "Audio tensor cannot be empty."
            )
            _log_voice_failure(
                "AUDIO_VALIDATION",
                error,
                provider=self.name,
            )
            raise error

        _log_voice_step(
            "AUDIO_VALIDATION",
            outcome="VALIDATED",
            provider=self.name,
            metadata={
                "shape": tuple(audio.shape),
                "dtype": str(audio.dtype),
            },
        )

        return audio

    async def extract_embedding(
        self,
        audio: SpeechBrainAudio,
    ) -> SpeechBrainEmbedding:
        """
        Generate a SpeechBrain speaker embedding.

        Used during:

        • user registration
        • authentication
        • biometric updates
        """

        await self._ensure_model_loaded()

        audio = self._validate_audio(audio)

        _log_voice_operation(
            "EMBEDDING_EXTRACTION_STARTED",
            provider=self.name,
        )

        try:
            embedding = self._model.encode_batch(audio)

        except Exception as exc:
            error = VoiceProviderError(
                "SpeechBrain embedding extraction failed."
            )
            _log_voice_failure(
                "EMBEDDING_EXTRACTION",
                error,
                provider=self.name,
            )
            raise error from exc

        _log_voice_step(
            "EMBEDDING_EXTRACTION",
            outcome="COMPLETED",
            provider=self.name,
            metadata={
                "embedding_shape": tuple(
                    embedding.shape
                ),
            },
        )

        _log_voice_operation(
            "EMBEDDING_EXTRACTION_COMPLETED",
            provider=self.name,
        )

        return embedding

    def _compute_similarity(
        self,
        enrolled_embedding: SpeechBrainEmbedding,
        live_embedding: SpeechBrainEmbedding,
    ) -> float:
        """
        Compute cosine similarity between two SpeechBrain embeddings.
        """

        try:
            similarity = torch.nn.functional.cosine_similarity(
                enrolled_embedding,
                live_embedding,
                dim=-1,
            )
            score = float(similarity.mean().item())

        except Exception as exc:
            raise VoiceProviderError(
                "Failed to compute speaker similarity."
            ) from exc

        return max(
            MIN_SIMILARITY_SCORE,
            min(
                MAX_SIMILARITY_SCORE,
                score,
            ),
        )
