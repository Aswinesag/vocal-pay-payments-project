"""Lightweight FastAPI dependencies for application state and request context."""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone

from fastapi import Request

from app.core.config import Settings, settings
from app.core.constants import PROJECT_VERSION
from app.core.log_context import RequestContext, get_context
from app.core.logger import EnterpriseLogger, system_logger


def get_settings() -> Settings:
    """Return the process-wide validated application settings."""
    return settings


def get_logger() -> EnterpriseLogger:
    """Return the process-wide system logger."""
    return system_logger


def get_request_context(request: Request) -> RequestContext:
    """Return the request context established by application middleware."""
    context = getattr(request.state, "context", None)
    if context is None:
        context = get_context()

    if not isinstance(context, RequestContext):
        raise RuntimeError("A valid RequestContext is not available.")

    return context


def get_request_id() -> str:
    """Return the active request identifier."""
    return get_context().request_id


def get_transaction_id() -> str:
    """Return the active transaction identifier."""
    return get_context().transaction_id


def get_application_health() -> dict[str, object]:
    """Return lightweight application health information."""
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": PROJECT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def is_application_ready() -> bool:
    """Return whether core application configuration is available."""
    return settings.APP_NAME != "" and settings.DATABASE_URL != ""


def get_runtime_information() -> dict[str, str]:
    """Return non-sensitive runtime information."""
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "application": settings.APP_NAME,
        "version": PROJECT_VERSION,
    }


def initialize_dependencies() -> None:
    """Initialize lightweight application dependencies."""
    system_logger.info("Initializing VocalPay core dependencies.")
    system_logger.info("VocalPay core dependencies initialized.")


def shutdown_dependencies() -> None:
    """Complete lightweight dependency shutdown."""
    system_logger.info("VocalPay core dependencies shut down.")


__all__ = (
    "get_settings",
    "get_logger",
    "get_request_context",
    "get_request_id",
    "get_transaction_id",
    "get_application_health",
    "is_application_ready",
    "get_runtime_information",
    "initialize_dependencies",
    "shutdown_dependencies",
)
