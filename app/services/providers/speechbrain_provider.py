"""CPU-isolated SpeechBrain speaker verification provider."""

from __future__ import annotations

from threading import RLock
from time import perf_counter
from typing import ClassVar

import numpy as np
import torch
from loguru import logger
from speechbrain.inference.speaker import EncoderClassifier

from app.core.config import settings
from app.services.voice_service import (
    SpeakerVerificationProvider,
    SpeakerVerificationResult,
    VoiceProviderError,
    VoiceValidationError,
)


class SpeechBrainProvider(SpeakerVerificationProvider):
    """Thread-safe CPU-only ECAPA-TDNN speaker verification provider."""

    _model_source: ClassVar[str] = "speechbrain/spkrec-ecapa-voxceleb"
    _model: ClassVar[EncoderClassifier | None] = None
    _model_lock: ClassVar[RLock] = RLock()

    def __init__(self, _device: str = "cpu") -> None:
        if _device.strip().casefold() != "cpu":
            raise VoiceValidationError("SpeechBrain must execute on the CPU.")

        self._device = "cpu"
        self._classifier: EncoderClassifier | None = None

    def _ensure_model_loaded(self) -> None:
        """Load the shared checkpoint inside the inference coordinator."""
        if self._classifier is None:
            self._classifier = self._get_classifier()

    @classmethod
    def _get_classifier(cls) -> EncoderClassifier:
        """Load the process-wide checkpoint once and return its singleton."""
        if cls._model is not None:
            return cls._model

        with cls._model_lock:
            if cls._model is not None:
                return cls._model

            started_at = perf_counter()
            logger.info("SpeechBrain CPU checkpoint loading started.")
            try:
                cls._model = EncoderClassifier.from_hparams(
                    source=cls._model_source,
                    run_opts={"device": "cpu"},
                )
            except Exception as exc:
                logger.bind(error=str(exc)).exception(
                    "SpeechBrain CPU checkpoint loading failed."
                )
                raise VoiceProviderError(
                    "SpeechBrain checkpoint could not be initialized."
                ) from exc

            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2)
            ).info("SpeechBrain CPU checkpoint loaded.")
            return cls._model

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "SpeechBrain"

    @property
    def version(self) -> str:
        """Return the provider implementation version."""
        return "1.0"

    @property
    def initialized(self) -> bool:
        """Return whether the shared model is loaded."""
        return type(self)._model is not None

    def extract_embedding(self, waveform: np.ndarray) -> list[float]:
        """Extract one 192-dimensional CPU speaker embedding."""
        started_at = perf_counter()
        try:
            samples = np.asarray(waveform, dtype=np.float32)
            if samples.ndim != 1 or samples.size == 0:
                raise VoiceValidationError(
                    "Waveform must be a non-empty one-dimensional array."
                )
            if not np.isfinite(samples).all():
                raise VoiceValidationError(
                    "Waveform contains non-finite sample values."
                )

            self._ensure_model_loaded()
            if self._classifier is None:
                raise VoiceProviderError("SpeechBrain classifier is unavailable.")
            tensor = torch.from_numpy(np.ascontiguousarray(samples)).unsqueeze(0)
            with torch.inference_mode():
                encoded = self._classifier.encode_batch(tensor.to("cpu"))

            embedding = encoded.squeeze().detach().cpu().float().numpy().reshape(-1)
            if embedding.size != 192:
                raise VoiceProviderError(
                    f"SpeechBrain returned {embedding.size} values; expected 192."
                )

            result = [float(value) for value in embedding]
            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                dimensions=len(result),
                device="cpu",
            ).info("SpeechBrain embedding extraction completed.")
            return result
        except (VoiceValidationError, VoiceProviderError):
            raise
        except Exception as exc:
            logger.bind(error=str(exc)).exception(
                "SpeechBrain embedding extraction failed."
            )
            raise VoiceProviderError(
                "Speaker embedding extraction failed."
            ) from exc

    def calculate_similarity(
        self,
        embedding_a: list[float],
        embedding_b: list[float],
    ) -> float:
        """Calculate normalized cosine similarity on the inclusive 0–1 scale."""
        started_at = perf_counter()
        try:
            vector_a = np.asarray(embedding_a, dtype=np.float32).reshape(-1)
            vector_b = np.asarray(embedding_b, dtype=np.float32).reshape(-1)
            if vector_a.size != 192 or vector_b.size != 192:
                raise VoiceValidationError(
                    "Speaker embeddings must each contain exactly 192 values."
                )
            if not np.isfinite(vector_a).all() or not np.isfinite(vector_b).all():
                raise VoiceValidationError(
                    "Speaker embeddings contain non-finite values."
                )

            denominator = float(np.linalg.norm(vector_a) * np.linalg.norm(vector_b))
            if denominator == 0.0:
                raise VoiceValidationError("Speaker embeddings cannot have zero norm.")

            cosine = float(np.dot(vector_a, vector_b) / denominator)
            similarity = float(np.clip((cosine + 1.0) / 2.0, 0.0, 1.0))
            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                similarity=round(similarity, 6),
            ).info("Speaker cosine similarity calculated.")
            return similarity
        except (VoiceValidationError, VoiceProviderError):
            raise
        except Exception as exc:
            logger.bind(error=str(exc)).exception(
                "Speaker cosine similarity calculation failed."
            )
            raise VoiceProviderError(
                "Speaker similarity calculation failed."
            ) from exc

    async def verify_speaker(
        self,
        *,
        enrolled_embedding: object,
        live_embedding: object,
    ) -> SpeakerVerificationResult:
        """Verify two speaker embeddings using normalized cosine similarity."""
        try:
            enrolled = np.asarray(enrolled_embedding, dtype=np.float32).reshape(-1).tolist()
            live = np.asarray(live_embedding, dtype=np.float32).reshape(-1).tolist()
            confidence = self.calculate_similarity(enrolled, live)
            return SpeakerVerificationResult(
                verified=confidence >= settings.SPEAKER_PASS_THRESHOLD,
                confidence=confidence,
                replay_detected=False,
                provider=self.name,
                metadata={"device": "cpu", "dimensions": 192},
            )
        except (VoiceValidationError, VoiceProviderError):
            raise
        except Exception as exc:
            raise VoiceProviderError("Speaker verification failed.") from exc

    async def shutdown(self) -> None:
        """Release the shared classifier so it can be initialized again."""
        cls = type(self)
        with cls._model_lock:
            self._classifier = None
            cls._model = None
        logger.info("SpeechBrain model reference released.")
