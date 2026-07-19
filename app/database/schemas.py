from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)
from pydantic import field_validator


# ==========================================================
# Base Schema
# ==========================================================

class BaseSchema(BaseModel):
    """
    Base Pydantic schema for all API models.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        validate_assignment=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

# ==========================================================
# Common Response Models
# ==========================================================

class APIResponse(BaseSchema):
    """
    Generic API response.
    """

    success: bool

    message: str

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
    )

class ErrorResponse(APIResponse):
    """
    Standard API error response.
    """

    error_code: str

    details: dict[str, Any] | None = None

class HealthResponse(BaseSchema):
    """
    Application health response.
    """

    status: str

    version: str

    database: str

    ollama: str

    whisper: str

# ==========================================================
# User Schemas
# ==========================================================

class UserBase(BaseSchema):
    """
    Shared user fields.
    """

    full_name: str = Field(
        min_length=2,
        max_length=120,
        examples=["Aswin Kumar"],
    )

    email: EmailStr

    phone_number: str = Field(
        min_length=10,
        max_length=20,
        examples=["+919876543210"],
    )

    preferred_language: str = Field(
        default="en",
        max_length=20,
    )


    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        """
        Basic phone number validation.
        """

        cleaned = value.replace("+", "").replace(" ", "")

        if not cleaned.isdigit():
            raise ValueError(
                "Phone number must contain only digits"
            )

        return value

class UserRegistrationRequest(UserBase):
    """
    User registration request.
    """

    user_id: str = Field(
        min_length=3,
        max_length=64,
        examples=["user_001"],
    )

    # Base64-encoded embeddings generated during enrollment
    speaker_embedding: list[float] = Field(
        min_length=1,
    )

    face_embedding: list[float] = Field(
        min_length=1,
    )

class UserUpdateRequest(BaseSchema):
    """
    Partial user profile update.
    """

    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )

    email: EmailStr | None = None

    phone_number: str | None = Field(
        default=None,
        min_length=10,
        max_length=20,
    )

    preferred_language: str | None = Field(
        default=None,
        max_length=20,
    )

class UserResponse(UserBase):
    """
    Public user response model.
    """

    id: int

    user_id: str

    is_active: bool

    is_verified: bool

    failed_attempts: int

    created_at: datetime

    updated_at: datetime

    last_login_at: datetime | None = None

# ==========================================================
# Transaction Initiation Schemas
# ==========================================================

class TransactionInitiateRequest(BaseSchema):
    """
    Initial transaction request.
    """

    amount: float = Field(
        gt=0,
        le=1_000_000,
        examples=[2500.50],
    )

    recipient_id: str = Field(
        min_length=3,
        max_length=64,
        examples=["merchant_001"],
    )

    device_id: str = Field(
        min_length=3,
        max_length=128,
        examples=["android_pixel_7"],
    )

    audio_duration_seconds: float = Field(
        gt=0,
        le=10,
        examples=[4.2],
    )

    audio_size_mb: float = Field(
        gt=0,
        le=5,
        examples=[1.8],
    )

    has_face_snapshot: bool = Field(
        default=True,
    )

class RiskAssessmentResponse(BaseSchema):
    """
    Internal risk assessment result.
    """

    transaction_id: str

    risk_level: str = Field(
        examples=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    )

    speaker_score: float = Field(
        ge=0,
        le=1,
    )

    face_score: float = Field(
        ge=0,
        le=1,
    )

    fraud_score: float = Field(
        ge=0,
        le=1,
    )

    replay_attack: bool = False

    requires_verification: bool = False

class PendingOTPResponse(APIResponse):
    """
    Returned when OTP verification is required.
    """

    transaction_id: str

    status: str = Field(
        default="PENDING_OTP",
    )

    expires_at: datetime

    verification_method: str = Field(
        default="otp",
    )

class PendingChallengeResponse(APIResponse):
    """
    Returned when voice challenge verification is required.
    """

    transaction_id: str

    status: str = Field(
        default="PENDING_CHALLENGE",
    )

    challenge_phrase: str

    expires_at: datetime

    verification_method: str = Field(
        default="voice_challenge",
    )

class TransactionSuccessResponse(APIResponse):
    """
    Returned when transaction is approved.
    """

    transaction_id: str

    status: str = Field(
        default="SUCCESS",
    )

    amount: float

    risk_level: str

    xai_summary: str

class TransactionFraudResponse(ErrorResponse):
    """
    Returned when transaction is blocked for fraud.
    """

    transaction_id: str

    status: str = Field(
        default="FAILED_FRAUD",
    )

    risk_level: str = Field(
        default="CRITICAL",
    )

    replay_attack: bool = False

# ==========================================================
# Unified Initiation Response
# ==========================================================

TransactionInitiateResponse = (
    TransactionSuccessResponse
    | PendingOTPResponse
    | PendingChallengeResponse
    | TransactionFraudResponse
)

# ==========================================================
# Transaction Verification Schemas
# ==========================================================

class VerificationBase(BaseSchema):
    """
    Shared verification fields.
    """

    transaction_id: str = Field(
        min_length=8,
        max_length=64,
        examples=["TXN-ABC12345"],
    )

    device_id: str = Field(
        min_length=3,
        max_length=128,
        examples=["android_pixel_7"],
    )

class OTPVerificationRequest(VerificationBase):
    """
    OTP verification request.
    """

    otp_code: str = Field(
        min_length=6,
        max_length=6,
        examples=["483291"],
    )


    @field_validator("otp_code")
    @classmethod
    def validate_otp(cls, value: str) -> str:
        """
        Ensure OTP contains only digits.
        """

        if not value.isdigit():
            raise ValueError(
                "OTP must contain only digits"
            )

        return value

class ChallengeVerificationRequest(VerificationBase):
    """
    Voice challenge verification request.
    """

    audio_duration_seconds: float = Field(
        gt=0,
        le=10,
        examples=[3.8],
    )

    audio_size_mb: float = Field(
        gt=0,
        le=5,
        examples=[1.2],
    )

    challenge_attempt: int = Field(
        ge=1,
        le=3,
        default=1,
    )

class VerificationSuccessResponse(APIResponse):
    """
    Returned when verification succeeds and the
    transaction is finalized.
    """

    transaction_id: str

    status: str = Field(
        default="SUCCESS",
    )

    amount: float

    risk_level: str

    verification_method: str = Field(
        examples=["otp", "voice_challenge"],
    )

    xai_summary: str

    processing_time_ms: float = Field(
        ge=0,
    )

class VerificationFailureResponse(ErrorResponse):
    """
    Returned when verification fails.
    """

    transaction_id: str

    status: str = Field(
        default="VERIFICATION_FAILED",
    )

    verification_method: str

    remaining_attempts: int = Field(
        ge=0,
        le=3,
    )

    risk_level: str

class TransactionExpiredResponse(ErrorResponse):
    """
    Returned when the pending transaction has expired.
    """

    transaction_id: str

    status: str = Field(
        default="EXPIRED",
    )

    expired_at: datetime

    retry_allowed: bool = True

# ==========================================================
# Unified Verify Response
# ==========================================================

TransactionVerifyResponse = (
    VerificationSuccessResponse
    | VerificationFailureResponse
    | TransactionExpiredResponse
)

# ==========================================================
# Transaction History Schemas
# ==========================================================

class TransactionSummary(BaseSchema):
    """
    Lightweight transaction card for list views.
    """

    transaction_id: str

    amount: float

    status: str

    risk_level: str

    created_at: datetime

    replay_attack: bool = False

class LedgerEntry(BaseSchema):
    """
    Statement-style ledger entry.
    """

    transaction_id: str

    amount: float

    entry_type: str = Field(
        examples=["debit", "credit"],
    )

    description: str

    balance_after: float | None = None

    created_at: datetime

class TransactionResponse(BaseSchema):
    """
    Detailed transaction response.
    """

    id: int

    transaction_id: str

    user_id: str

    amount: float

    status: str

    risk_level: str

    success: bool

    speaker_score: float

    face_score: float

    fraud_score: float

    replay_attack: bool

    xai_reason: str

    processing_time_ms: float

    created_at: datetime

    updated_at: datetime