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