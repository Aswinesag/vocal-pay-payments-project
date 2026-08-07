"""CUDA-optimized Faster-Whisper automatic speech recognition service."""

from __future__ import annotations

from threading import RLock
from time import perf_counter
from typing import ClassVar

import numpy as np
from faster_whisper import WhisperModel
from loguru import logger

from app.core.config import settings


class WhisperServiceError(RuntimeError):
    """Raised when Faster-Whisper initialization or decoding fails."""


class WhisperService:
    """Thread-safe CUDA Faster-Whisper transcription service."""

    _model: ClassVar[WhisperModel | None] = None
    _model_lock: ClassVar[RLock] = RLock()
    _inference_lock: ClassVar[RLock] = RLock()

    def __init__(self) -> None:
        self._model_instance = self._get_model()

    @classmethod
    def _get_model(cls) -> WhisperModel:
        """Load the process-wide CUDA model exactly once."""
        if cls._model is not None:
            return cls._model

        with cls._model_lock:
            if cls._model is not None:
                return cls._model

            started_at = perf_counter()
            logger.bind(
                model=settings.WHISPER_MODEL,
                device="cuda",
                compute_type="float16",
            ).info("Faster-Whisper model loading started.")
            try:
                cls._model = WhisperModel(
                    settings.WHISPER_MODEL,
                    device="cuda",
                    compute_type="float16",
                )
            except Exception as exc:
                logger.bind(error=str(exc)).exception(
                    "Faster-Whisper model loading failed."
                )
                raise WhisperServiceError(
                    "Faster-Whisper CUDA model could not be initialized."
                ) from exc

            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                model=settings.WHISPER_MODEL,
            ).info("Faster-Whisper model loaded successfully.")
            return cls._model

    def transcribe_audio(self, audio_waveform: np.ndarray) -> str:
        """Transcribe a normalized 16 kHz mono waveform into English text."""
        started_at = perf_counter()
        try:
            waveform = np.asarray(audio_waveform, dtype=np.float32)
            if waveform.ndim != 1 or waveform.size == 0:
                raise ValueError(
                    "Audio waveform must be a non-empty one-dimensional array."
                )
            if not np.isfinite(waveform).all():
                raise ValueError("Audio waveform contains non-finite samples.")

            vad_threshold = float(getattr(settings, "VAD_THRESHOLD", 0.5))
            if not 0.0 <= vad_threshold <= 1.0:
                raise ValueError("VAD threshold must be between 0.0 and 1.0.")

            with self._inference_lock:
                segments, _information = self._model_instance.transcribe(
                    np.ascontiguousarray(waveform),
                    beam_size=1,
                    language="en",
                    vad_filter=True,
                    vad_parameters={"threshold": vad_threshold},
                )
                transcription = " ".join(
                    segment.text.strip()
                    for segment in segments
                    if segment.text.strip()
                ).strip()

            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                characters=len(transcription),
                model=settings.WHISPER_MODEL,
                device="cuda",
            ).info("Faster-Whisper transcription completed.")
            return transcription
        except (ValueError, WhisperServiceError):
            raise
        except Exception as exc:
            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                error=str(exc),
            ).exception("Faster-Whisper transcription failed.")
            raise WhisperServiceError("Audio transcription failed.") from exc


__all__ = ("WhisperService", "WhisperServiceError")
