"""
app/core/constants.py

Application-wide immutable constants.

Project:
A Secure Voice-based Financial Transaction System
Using Multimodal Biometrics and Agentic AI Fraud Detection

Guidelines
----------
Only values that are constant across all environments
should be placed here.

Do NOT place:

- Secrets
- API Keys
- Thresholds
- Database URLs
- Model names

Those belong inside config.py/.env.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path


# ==========================================================
# API
# ==========================================================

API_VERSION: str = "v1"

API_PREFIX: str = "/api/v1"

PROJECT_NAME: str = (
    "Secure Voice Transaction System"
)


# ==========================================================
# Directories
# ==========================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

APP_DIR = ROOT_DIR / "app"

LOG_DIR = ROOT_DIR / "logs"

MODEL_DIR = ROOT_DIR / "models"

TEST_DIR = ROOT_DIR / "tests"


# ==========================================================
# Audio
# ==========================================================

SUPPORTED_AUDIO_EXTENSIONS = frozenset({
    ".wav",
    ".mp3",
    ".m4a",
    ".flac"
})

SUPPORTED_MIME_TYPES = frozenset({
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/flac",
    "audio/x-flac",
    "audio/mp4",
    "audio/m4a",
})

PCM_BIT_DEPTH = 16

MONO_CHANNEL = 1


# ==========================================================
# Languages
# ==========================================================

SUPPORTED_LANGUAGES = frozenset({
    "en"
})


# ==========================================================
# Transaction Intents
# ==========================================================

class TransactionIntent(str, Enum):

    TRANSFER = "TRANSFER"

    BALANCE = "BALANCE"

    MINI_STATEMENT = "MINI_STATEMENT"

    BENEFICIARY = "BENEFICIARY"

    CANCEL = "CANCEL"

    UNKNOWN = "UNKNOWN"


# ==========================================================
# Risk Levels
# ==========================================================

class RiskLevel(str, Enum):

    LOW = "LOW"

    MEDIUM = "MEDIUM"

    HIGH = "HIGH"

    CRITICAL = "CRITICAL"


# ==========================================================
# Verification Methods
# ==========================================================

class VerificationMethod(str, Enum):

    OTP = "OTP"

    FACE_LIVENESS = "FACE_LIVENESS"

    DYNAMIC_CHALLENGE = "DYNAMIC_CHALLENGE"


# ==========================================================
# Fraud Decision
# ==========================================================

class FraudDecision(str, Enum):

    ALLOW = "ALLOW"

    VERIFY = "VERIFY"

    BLOCK = "BLOCK"


# ==========================================================
# Speaker Verification
# ==========================================================

class SpeakerStatus(str, Enum):

    VERIFIED = "VERIFIED"

    REJECTED = "REJECTED"

    UNKNOWN = "UNKNOWN"


# ==========================================================
# Face Verification
# ==========================================================

class FaceStatus(str, Enum):

    VERIFIED = "VERIFIED"

    SPOOF = "SPOOF"

    UNKNOWN = "UNKNOWN"


# ==========================================================
# Liveness
# ==========================================================

class LivenessStatus(str, Enum):

    LIVE = "LIVE"

    SPOOF = "SPOOF"

    FAILED = "FAILED"


# ==========================================================
# Processing Status
# ==========================================================

class ProcessingStatus(str, Enum):

    SUCCESS = "SUCCESS"

    FAILED = "FAILED"

    PENDING = "PENDING"


# ==========================================================
# Error Codes
# ==========================================================

class ErrorCode(str, Enum):

    INVALID_AUDIO = "INVALID_AUDIO"

    AUDIO_TOO_SHORT = "AUDIO_TOO_SHORT"

    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"

    NO_SPEECH = "NO_SPEECH"

    LOW_AUDIO_QUALITY = "LOW_AUDIO_QUALITY"

    ASR_FAILED = "ASR_FAILED"

    SPEAKER_FAILED = "SPEAKER_FAILED"

    FACE_FAILED = "FACE_FAILED"

    LIVENESS_FAILED = "LIVENESS_FAILED"

    NLP_FAILED = "NLP_FAILED"

    FRAUD_ENGINE_FAILED = "FRAUD_ENGINE_FAILED"

    AGENT_FAILED = "AGENT_FAILED"

    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


# ==========================================================
# Logging
# ==========================================================

LOGGER_NAME = "voice_transaction_system"

DEFAULT_REQUEST_ID = "-"

DEFAULT_USER_ID = "-"

DEFAULT_TRANSACTION_ID = "-"

DEFAULT_SESSION_ID = "-"

SYSTEM_MODULE = "SYSTEM"


# ==========================================================
# HTTP
# ==========================================================

HTTP_SUCCESS = 200

HTTP_CREATED = 201

HTTP_BAD_REQUEST = 400

HTTP_UNAUTHORIZED = 401

HTTP_FORBIDDEN = 403

HTTP_NOT_FOUND = 404

HTTP_UNPROCESSABLE = 422

HTTP_INTERNAL_ERROR = 500


# ==========================================================
# AI Models
# ==========================================================

class AIModel(str, Enum):

    FASTER_WHISPER = "FASTER_WHISPER"

    ECAPA_TDNN = "ECAPA_TDNN"

    INSIGHTFACE = "INSIGHTFACE"

    MINI_LM = "MINI_LM"

    XGBOOST = "XGBOOST"

    AGENTIC_AI = "AGENTIC_AI"