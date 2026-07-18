"""
app/core/config.py

Central configuration management for the Secure Voice
Transaction System.

Loads all runtime configuration from the .env file.

Project:
A Secure Voice-based Financial Transaction System Using
Multimodal Biometrics and Agentic AI Fraud Detection
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ==========================================================
# Project Paths
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent

APP_DIR = BASE_DIR / "app"

DATABASE_DIR = BASE_DIR / "database"

LOG_DIR = BASE_DIR / "logs"

MODEL_DIR = BASE_DIR / "models"

UPLOAD_DIR = BASE_DIR / "uploads"


# ==========================================================
# Create Required Directories
# ==========================================================

DATABASE_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR.mkdir(parents=True, exist_ok=True)

MODEL_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# Application Settings
# ==========================================================

class Settings(BaseSettings):
    """
    Centralized application configuration.

    Values are automatically loaded from the .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------
    # Application
    # ------------------------------------------------------

    APP_NAME: str = Field(...)

    APP_VERSION: str = Field(...)

    ENVIRONMENT: str = Field(...)

    DEBUG: bool = Field(default=False)

    # ------------------------------------------------------
    # API Server
    # ------------------------------------------------------

    HOST: str = Field(...)

    PORT: int = Field(...)

    API_PREFIX: str = Field(...)

    # ------------------------------------------------------
    # Security
    # ------------------------------------------------------

    SECRET_KEY: str = Field(...)

    JWT_ALGORITHM: str = Field(...)

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(...)

    # ------------------------------------------------------
    # Project Directories
    # ------------------------------------------------------

    BASE_DIR: Path = BASE_DIR

    APP_DIR: Path = APP_DIR

    DATABASE_DIR: Path = DATABASE_DIR

    LOG_DIR: Path = LOG_DIR

    MODEL_DIR: Path = MODEL_DIR

    UPLOAD_DIR: Path = UPLOAD_DIR

        # ------------------------------------------------------
    # Database
    # ------------------------------------------------------

    DATABASE_URL: str = Field(...)
    SQL_ECHO: bool = Field(default=False)

    # ------------------------------------------------------
    # Logging
    # ------------------------------------------------------

    LOG_LEVEL: str = Field(...)

    LOG_DIRECTORY: str = Field(...)

    AUDIT_LOG_ENABLED: bool = Field(default=True)

    # ------------------------------------------------------
    # Upload Directories
    # ------------------------------------------------------

    UPLOAD_DIRECTORY: str = Field(...)

    MODEL_DIRECTORY: str = Field(...)

    # ------------------------------------------------------
    # Audio Configuration
    # ------------------------------------------------------

    MAX_AUDIO_DURATION: int = Field(...)

    MAX_AUDIO_SIZE_MB: int = Field(...)

    ALLOWED_AUDIO_FORMATS: str = Field(...)

    # ------------------------------------------------------
    # Image Configuration
    # ------------------------------------------------------

    MAX_IMAGE_SIZE_MB: int = Field(...)

    ALLOWED_IMAGE_FORMATS: str = Field(...)

    # ------------------------------------------------------
    # API / CORS
    # ------------------------------------------------------

    ALLOWED_ORIGINS: str = Field(...)

    # ------------------------------------------------------
    # Performance
    # ------------------------------------------------------

    MAX_WORKERS: int = Field(...)

    REQUEST_TIMEOUT_SECONDS: int = Field(...)

        # ------------------------------------------------------
    # Faster-Whisper Configuration
    # ------------------------------------------------------

    WHISPER_MODEL: str = Field(...)

    WHISPER_DEVICE: str = Field(...)

    WHISPER_COMPUTE_TYPE: str = Field(...)

    WHISPER_BEAM_SIZE: int = Field(...)

    WHISPER_LANGUAGE: str = Field(...)

    # ------------------------------------------------------
    # Speaker Verification
    # ------------------------------------------------------

    SPEAKER_DEVICE: str = Field(...)

    SPEAKER_SIMILARITY_THRESHOLD: float = Field(...)

    # ======================================================
    # SpeechBrain ECAPA-TDNN
    # ======================================================

    SPEAKER_MODEL: str = Field(...)

    # ------------------------------------------------------
    # Face Recognition
    # ------------------------------------------------------

    INSIGHTFACE_DEVICE: str = Field(...)

    FACE_SIMILARITY_THRESHOLD: float = Field(...)

    FACE_MODEL_NAME: str = Field(...)

    FACE_PROVIDER: str = Field(...)

    FACE_DET_WIDTH: int = Field(...)

    FACE_DET_HEIGHT: int = Field(...)

    # ------------------------------------------------------
    # Face Liveness Detection
    # ------------------------------------------------------

    LIVENESS_DEVICE: str = Field(...)

    LIVENESS_MODEL_PATH: str = Field(...)

    LIVENESS_THRESHOLD: float = Field(...)

    # ------------------------------------------------------
    # DSP Replay Gatekeeper
    # ------------------------------------------------------

    ENABLE_DSP_GATEKEEPER: bool = Field(...)

    SPECTRAL_ROLLOFF_THRESHOLD: float = Field(...)

    SPECTRAL_CENTROID_THRESHOLD: float = Field(...)

    # ------------------------------------------------------
    # Risk Engine
    # ------------------------------------------------------

    LOW_RISK_MAX: float = Field(...)

    MEDIUM_RISK_MAX: float = Field(...)

    HIGH_RISK_MAX: float = Field(...)

    OTP_LENGTH: int = Field(...)

    OTP_EXPIRY_MINUTES: int = Field(...)

    CHALLENGE_EXPIRY_MINUTES: int = Field(...)

    # ------------------------------------------------------
    # Ollama
    # ------------------------------------------------------

    OLLAMA_ENABLED: bool = Field(...)

    OLLAMA_HOST: str = Field(...)

    OLLAMA_MODEL: str = Field(...)

    OLLAMA_TIMEOUT_SECONDS: int = Field(...)

    # ------------------------------------------------------
    # Transaction Policy
    # ------------------------------------------------------

    DEFAULT_CURRENCY: str = Field(...)

    MAX_TRANSACTION_AMOUNT: float = Field(...)

    # ------------------------------------------------------
    # Convenience Properties
    # ------------------------------------------------------

    @property
    def allowed_audio_formats(self) -> List[str]:
        """
        Returns supported audio formats as a list.
        """
        return [
            fmt.strip().lower()
            for fmt in self.ALLOWED_AUDIO_FORMATS.split(",")
            if fmt.strip()
        ]

    @property
    def allowed_image_formats(self) -> List[str]:
        """
        Returns supported image formats as a list.
        """
        return [
            fmt.strip().lower()
            for fmt in self.ALLOWED_IMAGE_FORMATS.split(",")
            if fmt.strip()
        ]

    @property
    def allowed_origins(self) -> List[str]:
        """
        Returns allowed CORS origins.
        """
        return [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def database_path(self) -> Path:
        """
        Returns SQLite database file path.
        """
        return DATABASE_DIR / "vocalpay.db"

    @property
    def application_log_path(self) -> Path:
        """
        Returns application log path.
        """
        return LOG_DIR / "application.log"

    @property
    def audit_log_path(self) -> Path:
        """
        Returns audit log path.
        """
        return LOG_DIR / "audit.log"

    @property
    def upload_path(self) -> Path:
        """
        Upload directory.
        """
        return UPLOAD_DIR

    @property
    def model_path(self) -> Path:
        """
        AI model directory.
        """
        return MODEL_DIR

# ==========================================================
# Global Settings Instance
# ==========================================================

settings = Settings()