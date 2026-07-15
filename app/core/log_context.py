"""
app/core/log_context.py

Request Context Management

This module provides asynchronous request-scoped context using
Python ContextVar.

Every incoming HTTP request receives its own isolated context,
which is automatically available throughout the complete
processing pipeline.

Project:
A Secure Voice-based Financial Transaction System Using
Multimodal Biometrics and Agentic AI Fraud Detection.

Author:
Aswin Kumar
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, asdict
from typing import Optional
from uuid import uuid4

from app.core.constants import (
    DEFAULT_REQUEST_ID,
    DEFAULT_SESSION_ID,
    DEFAULT_TRANSACTION_ID,
    DEFAULT_USER_ID,
)

# ==========================================================
# Context Data Model
# ==========================================================


@dataclass(slots=True)
class RequestContext:
    """
    Immutable request-scoped context.

    Every HTTP request gets one instance.
    """

    request_id: str = DEFAULT_REQUEST_ID

    transaction_id: str = DEFAULT_TRANSACTION_ID

    user_id: str = DEFAULT_USER_ID

    session_id: str = DEFAULT_SESSION_ID

    client_ip: str = "-"

    user_agent: str = "-"

    endpoint: str = "-"

    method: str = "-"

    def to_dict(self) -> dict[str, str]:
        """Return context as a dictionary."""
        return asdict(self)


# ==========================================================
# Context Variable
# ==========================================================

_request_context: ContextVar[RequestContext] = ContextVar(
    "request_context",
    default=RequestContext(),
)

# ==========================================================
# ID Generation
# ==========================================================


def generate_request_id() -> str:
    """
    Generate a unique request identifier.

    Example:
        REQ-7F4A92C8
    """
    return f"REQ-{uuid4().hex[:8].upper()}"


def generate_transaction_id() -> str:
    """
    Generate a unique transaction identifier.

    Example:
        TXN-8B17A0F3
    """
    return f"TXN-{uuid4().hex[:8].upper()}"


def generate_session_id() -> str:
    """
    Generate a unique session identifier.
    """
    return f"SES-{uuid4().hex[:8].upper()}"


# ==========================================================
# Context Operations
# ==========================================================


def get_context() -> RequestContext:
    """
    Get the current request context.
    """
    return _request_context.get()


def set_context(context: RequestContext) -> None:
    """
    Replace the current request context.
    """
    _request_context.set(context)


def clear_context() -> None:
    """
    Reset the request context after request completion.
    """
    _request_context.set(RequestContext())


# ==========================================================
# Context Update Helpers
# ==========================================================


def update_context(
    *,
    request_id: Optional[str] = None,
    transaction_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    endpoint: Optional[str] = None,
    method: Optional[str] = None,
) -> RequestContext:
    """
    Update only supplied fields while preserving the rest.

    Returns
    -------
    RequestContext
        Updated context.
    """

    current = get_context()

    updated = RequestContext(
        request_id=request_id or current.request_id,
        transaction_id=transaction_id or current.transaction_id,
        user_id=user_id or current.user_id,
        session_id=session_id or current.session_id,
        client_ip=client_ip or current.client_ip,
        user_agent=user_agent or current.user_agent,
        endpoint=endpoint or current.endpoint,
        method=method or current.method,
    )

    set_context(updated)

    return updated


# ==========================================================
# Convenience Getters
# ==========================================================


def get_request_id() -> str:
    return get_context().request_id


def get_transaction_id() -> str:
    return get_context().transaction_id


def get_user_id() -> str:
    return get_context().user_id


def get_session_id() -> str:
    return get_context().session_id


def get_client_ip() -> str:
    return get_context().client_ip


def get_user_agent() -> str:
    return get_context().user_agent


# ==========================================================
# Bootstrap Helpers
# ==========================================================


def initialize_request_context(
    *,
    user_id: str = DEFAULT_USER_ID,
    client_ip: str = "-",
    user_agent: str = "-",
    endpoint: str = "-",
    method: str = "-",
) -> RequestContext:
    """
    Create and register a fresh request context.

    This function should be called once by the
    logging middleware for every incoming request.
    """

    context = RequestContext(
        request_id=generate_request_id(),
        transaction_id=generate_transaction_id(),
        session_id=generate_session_id(),
        user_id=user_id,
        client_ip=client_ip,
        user_agent=user_agent,
        endpoint=endpoint,
        method=method,
    )

    set_context(context)

    return context