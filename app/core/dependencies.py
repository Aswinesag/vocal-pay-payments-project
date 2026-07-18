"""
app/core/dependencies.py

Dependency injection and lazy singleton resource manager.

Project:
A Secure Voice-based Financial Transaction System Using
Multimodal Biometrics and Agentic AI Fraud Detection

Responsibilities
----------------
- Central dependency injection
- Thread-safe singleton management
- Lazy model loading
- Resource sharing
- Hardware allocation management
"""
from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone

from threading import Lock
from typing import Any, Callable, Dict, Optional
from faster_whisper import WhisperModel
from speechbrain.inference.speaker import EncoderClassifier
from insightface.app import FaceAnalysis
from ollama import Client
from app.core.log_context import (RequestContext,get_context,)

from fastapi import Request

from app.core.config import settings, Settings
from app.core.logger import system_logger
from app.core.log_context import RequestContext


# ==========================================================
# Thread-Safe Model Registry
# ==========================================================

"""
Every AI model is stored exactly once during the application's
lifetime.

The actual models will be loaded lazily in Section 2.
"""

_model_registry: Dict[str, Optional[Any]] = {
    "whisper": None,
    "speaker": None,
    "face": None,
    "liveness": None,
    "ollama": None,
}


# ==========================================================
# Thread Locks
# ==========================================================

"""
Each model owns an independent lock.

This prevents multiple concurrent requests from loading the
same model into memory simultaneously.
"""

_model_locks: Dict[str, Lock] = {
    name: Lock()
    for name in _model_registry
}


# ==========================================================
# Basic Dependencies
# ==========================================================

def get_settings() -> Settings:
    """
    Returns the global application settings.
    """
    return settings


def get_logger():
    """
    Returns the default system logger.

    Individual services (ASR, Face, Fraud, etc.)
    should inject their own component logger when needed.
    """
    return system_logger


# ==========================================================
# Request Context Dependency
# ==========================================================

def get_request_context(request: Request) -> RequestContext:
    """
    Returns the RequestContext created by the logging middleware.

    Raises
    ------
    RuntimeError
        If the middleware has not populated request.state.context.
    """

    context = getattr(request.state, "context", None)

    if context is None:
        raise RuntimeError(
            "RequestContext not found. "
            "Ensure LoggingMiddleware is registered."
        )

    return context


# ==========================================================
# Registry Helpers
# ==========================================================

def get_model_registry() -> Dict[str, Optional[Any]]:
    """
    Returns the global model registry.

    Intended primarily for debugging and health endpoints.
    """
    return _model_registry


def get_model_locks() -> Dict[str, Lock]:
    """
    Returns the lock registry.

    Mainly used internally.
    """
    return _model_locks


def is_model_loaded(model_name: str) -> bool:
    """
    Checks whether a model has already been loaded.

    Parameters
    ----------
    model_name : str

    Returns
    -------
    bool
    """

    if model_name not in _model_registry:
        raise ValueError(f"Unknown model: {model_name}")

    return _model_registry[model_name] is not None

# ==========================================================
# Internal Singleton Helper
# ==========================================================

def _get_or_create_model(
    model_name: str,
    loader: Callable[[], Any],
) -> Any:
    """
    Thread-safe lazy singleton loader.

    Parameters
    ----------
    model_name : str
        Name of the model in the registry.

    loader : Callable
        Function responsible for constructing the model.

    Returns
    -------
    Any
        Loaded singleton model instance.
    """

    if model_name not in _model_registry:
        raise ValueError(f"Unknown model: {model_name}")

    # Fast path (already loaded)
    if _model_registry[model_name] is not None:
        return _model_registry[model_name]

    # Thread-safe initialization
    with _model_locks[model_name]:

        # Another thread may have loaded it
        if _model_registry[model_name] is None:
            system_logger.info(
                f"Loading '{model_name}' model..."
            )

            _model_registry[model_name] = loader()

            system_logger.info(
                f"'{model_name}' model loaded successfully."
            )

    return _model_registry[model_name]

# ==========================================================
# Whisper Loader
# ==========================================================

def _load_whisper_model() -> WhisperModel:
    """
    Loads the Faster-Whisper model.

    Hardware Allocation
    -------------------
    Device : CUDA
    Precision : float16
    """

    system_logger.info(
        "Initializing Faster-Whisper model..."
    )

    model = WhisperModel(
        model_size_or_path=settings.WHISPER_MODEL,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )

    system_logger.info(
        "Faster-Whisper model initialized."
    )

    return model

def get_whisper_model() -> WhisperModel:
    """
    Returns the singleton Faster-Whisper model.
    """

    return _get_or_create_model(
        "whisper",
        _load_whisper_model,
    )

# ==========================================================
# SpeechBrain ECAPA Loader
# ==========================================================

def _load_speaker_model() -> EncoderClassifier:
    """
    Loads the SpeechBrain ECAPA-TDNN speaker verification model.

    Hardware Allocation
    -------------------
    Device : CPU
    """

    system_logger.info(
        "Initializing SpeechBrain ECAPA-TDNN..."
    )

    model = EncoderClassifier.from_hparams(
        source=settings.SPEAKER_MODEL,
        run_opts={
            "device": settings.SPEAKER_DEVICE,
        },
    )
    system_logger.info(
        "SpeechBrain ECAPA initialized."
    )

    return model

def get_speaker_model() -> EncoderClassifier:
    """
    Returns the singleton ECAPA speaker model.
    """

    return _get_or_create_model(
        "speaker",
        _load_speaker_model,
    )

# ==========================================================
# InsightFace Loader
# ==========================================================

def _load_face_model() -> FaceAnalysis:
    """
    Loads the InsightFace FaceAnalysis model.

    Hardware Allocation
    -------------------
    Device : CUDA
    Execution : Single image only
    """

    system_logger.info(
        "Initializing InsightFace..."
    )

    model = FaceAnalysis(
        name=settings.FACE_MODEL_NAME,
        providers=[
            settings.FACE_PROVIDER
        ],
    )

    model.prepare(
        ctx_id=0,
        det_size=(
            settings.FACE_DET_WIDTH,
            settings.FACE_DET_HEIGHT,
        ),
    )

    system_logger.info(
        "InsightFace initialized."
    )

    return model

def get_face_model() -> FaceAnalysis:
    """
    Returns the singleton InsightFace model.
    """

    return _get_or_create_model(
        "face",
        _load_face_model,
    )

# ==========================================================
# Ollama Client Loader
# ==========================================================

def _load_ollama_client() -> Client:
    """
    Creates the singleton Ollama client.

    The actual LLM runs inside the Ollama server.
    This client simply communicates with it.
    """

    system_logger.info(
        "Initializing Ollama client..."
    )

    client = Client(
        host=settings.OLLAMA_HOST,
    )

    system_logger.info(
        "Ollama client initialized."
    )

    return client

def get_ollama_client() -> Client:
    """
    Returns the singleton Ollama client.
    """

    return _get_or_create_model(
        "ollama",
        _load_ollama_client,
    )

# ==========================================================
# Temporary Liveness Dependency
# ==========================================================

class LivenessDetector:
    """
    Temporary placeholder implementation.

    This will be replaced by
    app.services.liveness.detector.LivenessDetector
    once the liveness module is completed.
    """

    def predict(self, image):
        raise NotImplementedError(
            "Liveness detector is not implemented yet."
        )


_liveness_detector: LivenessDetector | None = None


def get_liveness_detector() -> LivenessDetector:
    """
    Returns the singleton temporary liveness detector.
    """

    global _liveness_detector

    if _liveness_detector is None:
        system_logger.info(
            "Initializing temporary liveness detector..."
        )
        _liveness_detector = LivenessDetector()

    return _liveness_detector

# ==========================================================
# Request Context Dependency
# ==========================================================

def get_request_context() -> RequestContext:
    """
    Returns the current request context.

    Always returns a valid RequestContext instance,
    even outside an active HTTP request.
    """

    context = get_context()

    if context is None:
        return RequestContext()

    return context

def get_request_id() -> str:
    """
    Returns the active request ID.
    """

    return get_context().request_id

def get_transaction_id() -> str:
    """
    Returns the active transaction ID.
    """

    return get_context().transaction_id

# ==========================================================
# Application Health
# ==========================================================

def get_application_health() -> dict[str, object]:
    """
    Returns the current application health.
    """

    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }

# ==========================================================
# Readiness Check
# ==========================================================

def is_application_ready() -> bool:
    """
    Returns True when the application
    is ready to serve requests.

    Since all AI models are lazy-loaded,
    startup readiness simply means the
    configuration has been loaded.
    """

    return True

# ==========================================================
# Loaded Model Status
# ==========================================================

def get_loaded_models() -> dict[str, bool]:
    """
    Returns which singleton models
    have already been initialized.
    """

    return {
        name: model is not None
        for name, model in _model_registry.items()
    }

# ==========================================================
# Runtime Information
# ==========================================================

def get_runtime_information() -> dict[str, str]:
    """
    Returns lightweight runtime information.
    """

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }

# ==========================================================
# Cleanup Utilities
# ==========================================================

def cleanup_models() -> None:
    """
    Releases all loaded singleton models.

    This function is intended to be called during
    FastAPI shutdown to free memory and allow the
    Python process to exit cleanly.
    """

    global _model_registry

    released = 0

    for model_name in list(_model_registry.keys()):
        if _model_registry[model_name] is not None:
            system_logger.info(
                f"Releasing '{model_name}' model."
            )

            _model_registry[model_name] = None
            released += 1

    system_logger.info(
        f"Released {released} loaded model(s)."
    )

def reset_model_registry() -> None:
    """
    Resets the model registry.

    Intended for testing only.
    """

    cleanup_models()

    system_logger.info(
        "Model registry reset."
    )

def has_loaded_models() -> bool:
    """
    Returns True if at least one model
    has been initialized.
    """

    return any(
        model is not None
        for model in _model_registry.values()
    )

# ==========================================================
# Application Startup
# ==========================================================

def initialize_dependencies() -> None:
    """
    Initializes application dependencies.

    Heavy AI models are NOT loaded here.
    They remain lazy-loaded and will be
    initialized on first use.
    """

    system_logger.info(
        "=" * 60
    )
    system_logger.info(
        "Initializing VocalPay dependencies..."
    )

    system_logger.info(
        f"Application : {settings.APP_NAME}"
    )

    system_logger.info(
        f"Version     : {settings.APP_VERSION}"
    )

    system_logger.info(
        "Dependency injection initialized."
    )

    system_logger.info(
        "AI models configured for lazy loading."
    )

    system_logger.info(
        "=" * 60
    )

# ==========================================================
# Optional Warm-up
# ==========================================================

def warmup_dependencies() -> None:
    """
    Performs lightweight dependency warm-up.

    No GPU models are loaded.
    """

    system_logger.info(
        "Starting dependency warm-up..."
    )

    try:
        get_ollama_client()

        system_logger.info(
            "Ollama client ready."
        )

    except Exception as exc:
        system_logger.warning(
            f"Ollama warm-up skipped: {exc}"
        )

    system_logger.info(
        "Dependency warm-up complete."
    )

# ==========================================================
# Application Shutdown
# ==========================================================

def shutdown_dependencies() -> None:
    """
    Releases application resources.
    """

    system_logger.info(
        "Shutting down dependency injection..."
    )

    cleanup_models()

    system_logger.info(
        "Dependency shutdown complete."
    )