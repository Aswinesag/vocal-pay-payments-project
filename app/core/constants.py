"""
app/core/constants.py

Application-wide immutable constants and enumerations.

Project:
A Secure Voice-based Financial Transaction System Using
Multimodal Biometrics and Agentic AI Fraud Detection
"""

from __future__ import annotations

from enum import Enum


# ==========================================================
# API Response Codes
# ==========================================================

class APIResponseCode(str, Enum):
    """
    Standard API response codes returned to the client.
    """

    SUCCESS = "SUCCESS"

    PENDING_OTP = "PENDING_OTP"

    PENDING_CHALLENGE = "PENDING_CHALLENGE"

    FAILED = "FAILED"

    FAILED_FRAUD = "FAILED_FRAUD"


# ==========================================================
# Transaction Status
# ==========================================================

class TransactionStatus(str, Enum):
    """
    Transaction lifecycle states.
    """

    INITIATED = "INITIATED"

    PENDING_OTP = "PENDING_OTP"

    PENDING_CHALLENGE = "PENDING_CHALLENGE"

    VERIFIED = "VERIFIED"

    APPROVED = "APPROVED"

    REJECTED = "REJECTED"

    BLOCKED = "BLOCKED"

    EXPIRED = "EXPIRED"

    COMPLETED = "COMPLETED"


# ==========================================================
# Risk Levels
# ==========================================================

class RiskLevel(str, Enum):
    """
    Four-tier risk matrix used by the Risk Engine.
    """

    LOW = "LOW"

    MEDIUM = "MEDIUM"

    HIGH = "HIGH"

    CRITICAL = "CRITICAL"


# ==========================================================
# Fraud Decisions
# ==========================================================

class FraudDecision(str, Enum):
    """
    Final fraud decision returned by the Risk Engine.
    """

    APPROVE = "APPROVE"

    REQUIRE_OTP = "REQUIRE_OTP"

    REQUIRE_VOICE_CHALLENGE = "REQUIRE_VOICE_CHALLENGE"

    BLOCK = "BLOCK"

# ==========================================================
# Transaction Intent
# ==========================================================

class TransactionIntent(str, Enum):
    """
    Supported financial transaction intents.
    """

    TRANSFER = "TRANSFER"

    BALANCE_INQUIRY = "BALANCE_INQUIRY"

    MINI_STATEMENT = "MINI_STATEMENT"

    BENEFICIARY_PAYMENT = "BENEFICIARY_PAYMENT"

    BILL_PAYMENT = "BILL_PAYMENT"

    RECHARGE = "RECHARGE"

    UNKNOWN = "UNKNOWN"


# ==========================================================
# Verification Type
# ==========================================================

class VerificationType(str, Enum):
    """
    Verification mechanism selected by the Risk Engine.
    """

    NONE = "NONE"

    OTP = "OTP"

    VOICE_CHALLENGE = "VOICE_CHALLENGE"


# ==========================================================
# AI Components
# ==========================================================

class ModelComponent(str, Enum):
    """
    AI modules used throughout the pipeline.
    """

    DSP = "DSP"

    WHISPER = "WHISPER"

    SPEAKER = "SPEAKER"

    FACE = "FACE"

    LIVENESS = "LIVENESS"

    RISK_ENGINE = "RISK_ENGINE"

    OLLAMA = "OLLAMA"

    ORCHESTRATOR = "ORCHESTRATOR"


# ==========================================================
# Logging Components
# ==========================================================

class LogComponent(str, Enum):
    """
    Logical components used in structured logging.
    """

    SYSTEM = "SYSTEM"

    API = "API"

    DATABASE = "DATABASE"

    AUTH = "AUTH"

    SECURITY = "SECURITY"

    DSP = "DSP"

    ASR = "ASR"

    SPEAKER = "SPEAKER"

    FACE = "FACE"

    LIVENESS = "LIVENESS"

    FRAUD = "FRAUD"

    OLLAMA = "OLLAMA"

    TRANSACTION = "TRANSACTION"

    ORCHESTRATOR = "ORCHESTRATOR"


# ==========================================================
# Device Types
# ==========================================================

class DeviceType(str, Enum):
    """
    Runtime execution devices.
    """

    CPU = "cpu"

    CUDA = "cuda"

# ==========================================================
# Supported File Extensions
# ==========================================================

SUPPORTED_AUDIO_EXTENSIONS = (
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
)

SUPPORTED_IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
)


# ==========================================================
# MIME Types
# ==========================================================

SUPPORTED_AUDIO_MIME_TYPES = (
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/flac",
    "audio/x-flac",
    "audio/mp4",
)

SUPPORTED_IMAGE_MIME_TYPES = (
    "image/jpeg",
    "image/png",
)


# ==========================================================
# Database Tables
# ==========================================================

USER_TABLE = "users"

TRANSACTION_TABLE = "transactions"

PENDING_TRANSACTION_TABLE = "pending_transactions"

AUDIT_LOG_TABLE = "audit_logs"


# ==========================================================
# Embedding Types
# ==========================================================

VOICE_EMBEDDING = "voice_embedding"

FACE_EMBEDDING = "face_embedding"


# ==========================================================
# Challenge Phrase
# ==========================================================

CHALLENGE_PREFIX = "Transfer"

CHALLENGE_WORDS = (
    "green",
    "orange",
    "blue",
    "silver",
    "purple",
    "yellow",
    "crimson",
    "gold",
    "white",
    "black",
)


# ==========================================================
# OTP
# ==========================================================

OTP_DIGITS = "0123456789"


# ==========================================================
# Request Headers
# ==========================================================

HEADER_REQUEST_ID = "X-Request-ID"

HEADER_PROCESSING_TIME = "X-Processing-Time"

HEADER_USER_ID = "X-User-ID"


# ==========================================================
# Content Types
# ==========================================================

CONTENT_TYPE_JSON = "application/json"

CONTENT_TYPE_MULTIPART = "multipart/form-data"


# ==========================================================
# Default Encoding
# ==========================================================

DEFAULT_ENCODING = "utf-8"


# ==========================================================
# SQLite
# ==========================================================

SQLITE_PRAGMA_FOREIGN_KEYS = "PRAGMA foreign_keys=ON;"

# ==========================================================
# API Response Messages
# ==========================================================

SUCCESS_MESSAGE = "Transaction completed successfully."

OTP_REQUIRED_MESSAGE = (
    "Additional verification required. Please verify using the OTP."
)

VOICE_CHALLENGE_REQUIRED_MESSAGE = (
    "Voice verification challenge required."
)

TRANSACTION_BLOCKED_MESSAGE = (
    "Transaction blocked due to security policy."
)

FRAUD_DETECTED_MESSAGE = (
    "Potential fraud detected."
)

REPLAY_ATTACK_MESSAGE = (
    "Possible replay attack detected."
)

LIVENESS_FAILED_MESSAGE = (
    "Face liveness verification failed."
)

INVALID_OTP_MESSAGE = (
    "Invalid or expired OTP."
)

INVALID_CHALLENGE_MESSAGE = (
    "Voice challenge verification failed."
)

TRANSACTION_EXPIRED_MESSAGE = (
    "Pending transaction has expired."
)


# ==========================================================
# AI Model Display Names
# ==========================================================

MODEL_DSP = "DSP Replay Detector"

MODEL_WHISPER = "Faster-Whisper Small.en"

MODEL_ECAPA = "SpeechBrain ECAPA-TDNN"

MODEL_INSIGHTFACE = "InsightFace"

MODEL_MINIFASNET = "MiniFASNet"

MODEL_OLLAMA = "Llama-3.2-3B"


# ==========================================================
# Risk Reason Identifiers
# ==========================================================

RISK_REASON_REPLAY_ATTACK = "Replay Attack"

RISK_REASON_LIVENESS_FAILURE = "Liveness Failure"

RISK_REASON_LOW_SPEAKER_SCORE = "Low Speaker Similarity"

RISK_REASON_LOW_FACE_SCORE = "Low Face Similarity"

RISK_REASON_HIGH_AMOUNT = "High Transaction Amount"

RISK_REASON_VOICE_MISMATCH = "Voice Verification Failed"

RISK_REASON_OTP_REQUIRED = "OTP Verification Required"

RISK_REASON_CHALLENGE_REQUIRED = "Voice Challenge Required"


# ==========================================================
# Transaction Defaults
# ==========================================================

DEFAULT_TRANSACTION_CURRENCY = "INR"

DEFAULT_OTP_LENGTH = 6

DEFAULT_CHALLENGE_PREFIX = "Transfer"


# ==========================================================
# Timestamp Format
# ==========================================================

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


# ==========================================================
# Version Information
# ==========================================================

PROJECT_NAME = (
    "Secure Voice-based Financial Transaction System"
)

PROJECT_SHORT_NAME = "VocalPay"

PROJECT_VERSION = "1.0.0"


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    # Core Enums
    "APIResponseCode",
    "TransactionStatus",
    "RiskLevel",
    "FraudDecision",
    "TransactionIntent",
    "VerificationType",
    "ModelComponent",
    "LogComponent",
    "DeviceType",

    # File Support
    "SUPPORTED_AUDIO_EXTENSIONS",
    "SUPPORTED_IMAGE_EXTENSIONS",
    "SUPPORTED_AUDIO_MIME_TYPES",
    "SUPPORTED_IMAGE_MIME_TYPES",

    # Database
    "USER_TABLE",
    "TRANSACTION_TABLE",
    "PENDING_TRANSACTION_TABLE",
    "AUDIT_LOG_TABLE",

    # Embeddings
    "VOICE_EMBEDDING",
    "FACE_EMBEDDING",

    # Headers
    "HEADER_REQUEST_ID",
    "HEADER_PROCESSING_TIME",
    "HEADER_USER_ID",

    # Messages
    "SUCCESS_MESSAGE",
    "OTP_REQUIRED_MESSAGE",
    "VOICE_CHALLENGE_REQUIRED_MESSAGE",
    "TRANSACTION_BLOCKED_MESSAGE",
    "FRAUD_DETECTED_MESSAGE",
    "REPLAY_ATTACK_MESSAGE",
    "LIVENESS_FAILED_MESSAGE",

    # AI Models
    "MODEL_DSP",
    "MODEL_WHISPER",
    "MODEL_ECAPA",
    "MODEL_INSIGHTFACE",
    "MODEL_MINIFASNET",
    "MODEL_OLLAMA",

    "DEFAULT_REQUEST_ID",
    "DEFAULT_TRANSACTION_ID",
    "DEFAULT_SESSION_ID",
    "DEFAULT_USER_ID",
    "DEFAULT_CLIENT_IP",
    "DEFAULT_USER_AGENT",
    "DEFAULT_ENDPOINT",
    "DEFAULT_HTTP_METHOD",

    "LOGGER_NAME",
    "APPLICATION_LOG_FILENAME",
    "AUDIT_LOG_FILENAME",
    "LOG_ROTATION",
    "LOG_RETENTION",
    "LOG_COMPRESSION",
    "LOG_FORMAT",
    "DEFAULT_LOG_COMPONENT",

    "get_liveness_detector",
    "LivenessDetector",
]

# ==========================================================
# Default Request Context Values
# ==========================================================

DEFAULT_REQUEST_ID = "-"

DEFAULT_TRANSACTION_ID = "-"

DEFAULT_SESSION_ID = "-"

DEFAULT_USER_ID = "anonymous"

DEFAULT_CLIENT_IP = "unknown"

DEFAULT_USER_AGENT = "unknown"

DEFAULT_ENDPOINT = "-"

DEFAULT_HTTP_METHOD = "-"

# ==========================================================
# Logger Constants
# ==========================================================

LOGGER_NAME = "VocalPay"

APPLICATION_LOG_FILENAME = "application.log"

AUDIT_LOG_FILENAME = "audit.log"

LOG_ROTATION = "10 MB"

LOG_RETENTION = "30 days"

LOG_COMPRESSION = "zip"

LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss,SSS} | "
    "{level:<8} | "
    "{extra[request_id]} | "
    "{extra[component]} | "
    "{message}"
)

DEFAULT_LOG_COMPONENT = "SYSTEM"