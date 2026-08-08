"""CUDA-optimized Faster-Whisper automatic speech recognition service."""

from __future__ import annotations

import ctypes
import gc
import sys
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
    _active_device: ClassVar[str] = "uninitialized"

    def __init__(self) -> None:
        self._model_instance = self._get_model()

    @classmethod
    def _get_model(cls) -> WhisperModel:
        """Load one process-wide model on CUDA or its safe CPU fallback."""
        if cls._model is not None:
            return cls._model

        with cls._model_lock:
            if cls._model is not None:
                return cls._model

            device = str(settings.WHISPER_DEVICE).casefold()
            compute_type = str(settings.WHISPER_COMPUTE_TYPE)
            if device == "cuda" and not cls._cuda_runtime_available():
                logger.warning(
                    "Faster-Whisper CUDA runtime libraries are unavailable; "
                    "loading the process-wide CPU model instead."
                )
                device = "cpu"
                compute_type = "int8"

            started_at = perf_counter()
            logger.bind(
                model=settings.WHISPER_MODEL,
                device=device,
                compute_type=compute_type,
            ).info("Faster-Whisper model loading started.")
            try:
                cls._model = WhisperModel(
                    settings.WHISPER_MODEL,
                    device=device,
                    compute_type=compute_type,
                )
                cls._active_device = device
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

    @staticmethod
    def _cuda_runtime_available() -> bool:
        """Return whether CTranslate2's required CUDA runtime is loadable."""
        if sys.platform != "win32":
            return True
        try:
            ctypes.WinDLL("cublas64_12.dll")
            ctypes.WinDLL("cudnn64_9.dll")
        except OSError:
            return False
        return True

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
                try:
                    transcription = self._transcribe(
                        self._model_instance,
                        waveform,
                        vad_threshold,
                    )
                except RuntimeError as exc:
                    if "cublas" not in str(exc).casefold() and "cudnn" not in str(exc).casefold():
                        raise
                    logger.bind(error=str(exc)).warning(
                        "Faster-Whisper CUDA runtime unavailable; retrying on CPU."
                    )
                    cpu_model = WhisperModel(
                        settings.WHISPER_MODEL,
                        device="cpu",
                        compute_type="int8",
                    )
                    type(self)._model = cpu_model
                    type(self)._active_device = "cpu"
                    self._model_instance = cpu_model
                    transcription = self._transcribe(
                        cpu_model,
                        waveform,
                        vad_threshold,
                    )

            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                characters=len(transcription),
                model=settings.WHISPER_MODEL,
                device=type(self)._active_device,
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

    def release_model(self) -> None:
        """Release the process-wide ASR model after a serialized transcription."""
        with self._model_lock:
            self._model_instance = None  # type: ignore[assignment]
            type(self)._model = None
            type(self)._active_device = "uninitialized"
        gc.collect()
        logger.info("Faster-Whisper model memory released.")

    @staticmethod
    def _transcribe(
        model: WhisperModel,
        waveform: np.ndarray,
        vad_threshold: float,
    ) -> str:
        """Decode one waveform with a prepared Faster-Whisper model."""
        segments, _information = model.transcribe(
            np.ascontiguousarray(waveform),
            beam_size=1,
            language="en",
            vad_filter=True,
            vad_parameters={"onset": vad_threshold},
        )
        return " ".join(
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ).strip()


__all__ = ("WhisperService", "WhisperServiceError")
