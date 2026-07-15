"""
app/core/exceptions.py

Custom exceptions for the Secure Voice Transaction System.

Project:
A Secure Voice-based Financial Transaction System Using
Multimodal Biometrics and Agentic AI Fraud Detection
"""

from __future__ import annotations

from typing import Any, Optional


# ==========================================================
# Base Application Exception
# ==========================================================

class VocalPayException(Exception):
    """
    Base exception for the entire application.

    Every project-specific exception should inherit from this
    class so that FastAPI can handle them uniformly.
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        status_code: int,
        details: Optional[dict[str, Any]] = None,
    ) -> None:

        super().__init__(message)

        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize the exception for API responses.
        """

        return {
            "success": False,
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:
        return (
            f"[{self.error_code}] "
            f"{self.message}"
        )


# ==========================================================
# Authentication
# ==========================================================

class AuthenticationError(VocalPayException):

    def __init__(
        self,
        message: str = "Authentication failed.",
        **kwargs,
    ) -> None:

        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
            details=kwargs,
        )


class AuthorizationError(VocalPayException):

    def __init__(
        self,
        message: str = "Access denied.",
        **kwargs,
    ) -> None:

        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
            details=kwargs,
        )


# ==========================================================
# Input Validation
# ==========================================================

class ValidationError(VocalPayException):

    def __init__(
        self,
        message: str = "Validation failed.",
        **kwargs,
    ) -> None:

        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=kwargs,
        )