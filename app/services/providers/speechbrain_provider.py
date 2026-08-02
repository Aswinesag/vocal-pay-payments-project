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
import asyncio
import math
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

    _verification_threshold: float = field(
        default=DEFAULT_VERIFICATION_THRESHOLD,
    )

    _initialization_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        init=False,
        repr=False,
    )

    _inference_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Validate provider configuration."""

        if not isinstance(self._model_source, str) or not self._model_source.strip():
            raise VoiceValidationError("Model source cannot be empty.")

        if not isinstance(self._model_cache, Path):
            raise VoiceValidationError("Model cache must be a pathlib.Path.")

        try:
            if self._model_cache.exists() and not self._model_cache.is_dir():
                raise VoiceValidationError("Model cache must be a directory.")
        except OSError as exc:
            raise VoiceValidationError(
                "Model cache path cannot be accessed."
            ) from exc

        if not isinstance(self._device, str) or not self._device.strip():
            raise VoiceValidationError("Inference device cannot be empty.")

        try:
            device = torch.device(self._device)
        except (RuntimeError, TypeError) as exc:
            raise VoiceValidationError("Invalid inference device.") from exc

        if device.type not in {"cpu", "cuda"}:
            raise VoiceValidationError(
                "Inference device must use CPU or CUDA."
            )

        if device.type == "cuda" and not torch.cuda.is_available():
            raise VoiceValidationError("CUDA is not available.")

        if isinstance(self._verification_threshold, bool) or not isinstance(
            self._verification_threshold,
            (int, float),
        ):
            raise VoiceValidationError(
                "Similarity threshold must be numeric."
            )

        if not math.isfinite(self._verification_threshold) or not (
            MIN_SIMILARITY_SCORE
            <= self._verification_threshold
            <= MAX_SIMILARITY_SCORE
        ):
            raise VoiceValidationError(
                "Similarity threshold must be between -1.0 and 1.0."
            )

    async def _ensure_model_loaded(self) -> None:
        """
        Lazily load the SpeechBrain model.

        The model is loaded only once during the provider
        lifetime.
        """

        if self._initialized:
            _log_voice_step(
                "MODEL_INITIALIZATION",
                outcome="SKIPPED",
                provider=self.name,
            )
            return

        async with self._initialization_lock:
            if self._initialized:
                _log_voice_step(
                    "MODEL_INITIALIZATION",
                    outcome="SKIPPED",
                    provider=self.name,
                )
                return

            _log_voice_operation(
                "MODEL_INITIALIZATION_STARTED",
                provider=self.name,
            )

            try:
                self._model = EncoderClassifier.from_hparams(
                    source=self._model_source,
                    savedir=str(self._model_cache),
                    run_opts={
                        "device": self._device,
                    },
                )

            except Exception as exc:
                error = VoiceProviderError(
                    "Unable to initialize SpeechBrain model."
                )
                _log_voice_failure(
                    "MODEL_INITIALIZATION",
                    error,
                    provider=self.name,
                )
                raise error from exc

            self._initialized = True
            _log_voice_operation(
                "MODEL_INITIALIZATION_COMPLETED",
                provider=self.name,
            )

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
            verified=similarity >= self._verification_threshold,
            confidence=similarity,
            replay_detected=False,
            provider=self.name,
            metadata={
                "threshold": self._verification_threshold,
                "similarity": similarity,
                "provider_version": self.version,
                "device": self._device,
                "model_source": self._model_source,
                "model_version": self._model_version,
            },
        )

        _log_voice_operation(
            "VERIFICATION_COMPLETED",
            provider=self.name,
        )

        return result

    @property
    def _model_version(self) -> str | None:
        """Return provider-supplied model version metadata when available."""

        version = getattr(self._model, "version", None)
        return version if isinstance(version, str) else None

    async def shutdown(self) -> None:
        """Release provider resources safely and idempotently."""

        async with self._inference_lock:
            async with self._initialization_lock:
                self._model = None
                self._initialized = False

        if self._device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.empty_cache()

        _log_voice_operation(
            "PROVIDER_SHUTDOWN",
            provider=self.name,
        )

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

        audio = self._validate_audio(audio)

        async with self._inference_lock:
            await self._ensure_model_loaded()

            try:
                device_audio = audio.to(self._device)
            except Exception as exc:
                error = VoiceProviderError(
                    "Unable to transfer audio to the inference device."
                )
                _log_voice_failure(
                    "AUDIO_DEVICE_TRANSFER",
                    error,
                    provider=self.name,
                )
                raise error from exc

            _log_voice_step(
                "AUDIO_DEVICE_TRANSFER",
                outcome="COMPLETED",
                provider=self.name,
                metadata={"device": self._device},
            )

            _log_voice_operation(
                "EMBEDDING_EXTRACTION_STARTED",
                provider=self.name,
            )

            try:
                with torch.inference_mode():
                    embedding = self._model.encode_batch(device_audio)

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

    def _normalize_embedding(
        self,
        embedding: SpeechBrainEmbedding,
    ) -> SpeechBrainEmbedding:
        """Normalize an embedding without changing the public representation."""

        try:
            device_embedding = embedding.to(self._device)
            with torch.inference_mode():
                normalized = torch.nn.functional.normalize(
                    device_embedding,
                    p=2.0,
                    dim=-1,
                )
        except Exception as exc:
            raise VoiceProviderError(
                "Failed to normalize speaker embedding."
            ) from exc

        _log_voice_step(
            "EMBEDDING_DEVICE_TRANSFER",
            outcome="COMPLETED",
            provider=self.name,
            metadata={"device": self._device},
        )
        _log_voice_step(
            "EMBEDDING_NORMALIZATION",
            outcome="COMPLETED",
            provider=self.name,
            metadata={"device": self._device},
        )
        return normalized

    def _compute_similarity(
        self,
        enrolled_embedding: SpeechBrainEmbedding,
        live_embedding: SpeechBrainEmbedding,
    ) -> float:
        """
        Compute cosine similarity between two SpeechBrain embeddings.
        """

        try:
            normalized_enrolled = self._normalize_embedding(
                enrolled_embedding
            )
            normalized_live = self._normalize_embedding(live_embedding)

            with torch.inference_mode():
                similarity = torch.nn.functional.cosine_similarity(
                    normalized_enrolled,
                    normalized_live,
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
