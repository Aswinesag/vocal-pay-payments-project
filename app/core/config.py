"""Centralized runtime configuration for the VocalPay backend."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Strict, environment-backed settings for VocalPay components."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        strict=False,  # Allow type coercion from env vars (strings → int)
        validate_default=True,
    )

    APP_NAME: str = Field(
        default="VocalPay Core Backend Engine",
        min_length=1,
    )
    LOG_LEVEL: str = Field(default="INFO", min_length=1)
    LOG_DIRECTORY: str = Field(default="logs", min_length=1)
    LOG_ROTATION: str = Field(default="10 MB", min_length=1)
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./vocalpay.db",
        pattern=r"^sqlite\+aiosqlite:///",
    )

    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        min_length=1,
    )
    OLLAMA_MODEL: str = Field(default="llama3.2:3b", min_length=1)

    WHISPER_MODEL: str = Field(default="small.en", min_length=1)
    WHISPER_DEVICE: str = Field(default="cuda", min_length=1)
    WHISPER_COMPUTE_TYPE: str = Field(default="float16", min_length=1)

    INSIGHTFACE_MODEL: str = Field(default="buffalo_l", min_length=1)
    INSIGHTFACE_DEVICE: str = Field(default="cuda", min_length=1)
    INSIGHTFACE_PROVIDER: str = Field(
        default="CUDAExecutionProvider",
        min_length=1,
    )

    SPEECHBRAIN_DEVICE: str = Field(default="cpu", min_length=1)

    ROLLOFF_THRESHOLD: float = Field(default=2500.0, gt=0.0)
    CENTROID_THRESHOLD: float = Field(default=1800.0, gt=0.0)
    SPEAKER_PASS_THRESHOLD: float = Field(default=0.75, ge=0.0, le=1.0)
    FACE_PASS_THRESHOLD: float = Field(default=0.80, ge=0.0, le=1.0)
    LIVENESS_CRITICAL_THRESHOLD: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
    )
    STEP_UP_TIMEOUT_SECONDS: int = Field(default=300, gt=0)

    # ------------------------------------------------------
    # Security & Authentication
    # ------------------------------------------------------

    JWT_SECRET_KEY: str = Field(
        default="CHANGE_THIS_TO_A_SECURE_RANDOM_SECRET_KEY_IN_PRODUCTION",
        min_length=32,
        description="Secret key for JWT token signing (HS256 algorithm)",
    )

    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm (HMAC SHA-256)",
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        gt=0,
        le=1440,
        description="JWT access token expiration time in minutes",
    )

    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        gt=0,
        le=30,
        description="JWT refresh token expiration time in days",
    )


settings = Settings()
