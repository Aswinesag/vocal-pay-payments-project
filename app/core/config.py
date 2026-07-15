"""
Application Configuration Module

This module centralizes all application configuration using
Pydantic Settings. Every configurable value in the project
must originate from this file.

Project:
A Secure Voice-based Financial Transaction System Using
Multimodal Biometrics and Agentic AI Fraud Detection.

Author: Aswin Kumar
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Global application settings.

    Values are automatically loaded from the .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # ==========================================================
    # Application
    # ==========================================================

    APP_NAME: str
    APP_VERSION: str

    ENVIRONMENT: Literal[
        "development",
        "testing",
        "production"
    ]

    DEBUG: bool

    # ==========================================================
    # Server
    # ==========================================================

    HOST: str
    PORT: int

    API_V1_PREFIX: str

    # ==========================================================
    # Logging
    # ==========================================================

    LOG_LEVEL: str

    LOG_DIRECTORY: Path

    LOG_RETENTION: str

    LOG_ROTATION: str

    # ==========================================================
    # Audio
    # ==========================================================

    SUPPORTED_AUDIO_FORMATS: str

    TARGET_SAMPLE_RATE: int

    TARGET_CHANNELS: int

    MIN_AUDIO_DURATION: int

    MAX_AUDIO_DURATION: int

    MAX_AUDIO_SIZE_MB: int

    # ==========================================================
    # Whisper
    # ==========================================================

    WHISPER_MODEL: str

    WHISPER_DEVICE: str

    WHISPER_COMPUTE_TYPE: str

    # ==========================================================
    # Voice Activity Detection
    # ==========================================================

    VAD_THRESHOLD: float

    MIN_SPEECH_DURATION_MS: int

    # ==========================================================
    # Speaker Verification
    # ==========================================================

    SPEAKER_THRESHOLD: float

    # ==========================================================
    # Face Recognition
    # ==========================================================

    FACE_MATCH_THRESHOLD: float

    # ==========================================================
    # Liveness
    # ==========================================================

    LIVENESS_THRESHOLD: float

    # ==========================================================
    # Fraud Detection
    # ==========================================================

    LOW_RISK_THRESHOLD: float

    MEDIUM_RISK_THRESHOLD: float

    HIGH_RISK_THRESHOLD: float

    # ==========================================================
    # Security
    # ==========================================================

    JWT_SECRET_KEY: str

    JWT_ALGORITHM: str

    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int

    # ==========================================================
    # Database
    # ==========================================================

    DATABASE_URL: str

    # ==========================================================
    # Models
    # ==========================================================

    MODEL_DIRECTORY: Path

    # ==========================================================
    # Validators
    # ==========================================================

    @field_validator("PORT")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not (1024 <= value <= 65535):
            raise ValueError(
                "PORT must be between 1024 and 65535."
            )
        return value

    @field_validator("MAX_AUDIO_DURATION")
    @classmethod
    def validate_audio_duration(cls, value: int) -> int:
        if value <= 0:
            raise ValueError(
                "MAX_AUDIO_DURATION must be greater than zero."
            )
        return value

    @field_validator("TARGET_SAMPLE_RATE")
    @classmethod
    def validate_sample_rate(cls, value: int) -> int:
        supported = [
            8000,
            16000,
            22050,
            44100,
            48000
        ]

        if value not in supported:
            raise ValueError(
                f"Unsupported sample rate: {value}"
            )

        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:

        allowed = {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL"
        }

        upper = value.upper()

        if upper not in allowed:
            raise ValueError(
                f"Invalid LOG_LEVEL: {value}"
            )

        return upper

    @field_validator("WHISPER_DEVICE")
    @classmethod
    def validate_device(cls, value: str) -> str:

        allowed = {
            "cpu",
            "cuda",
            "auto"
        }

        lower = value.lower()

        if lower not in allowed:
            raise ValueError(
                "WHISPER_DEVICE must be cpu, cuda or auto."
            )

        return lower

    @property
    def audio_formats(self) -> list[str]:
        """
        Returns supported audio extensions.

        Example:
            ['.wav', '.mp3', '.m4a']
        """
        return [
            ext.strip().lower()
            for ext in self.SUPPORTED_AUDIO_FORMATS.split(",")
        ]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns a singleton Settings instance.

    Prevents repeatedly reading the .env file.
    """
    settings = Settings()

    settings.LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    settings.MODEL_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    return settings


settings = get_settings()