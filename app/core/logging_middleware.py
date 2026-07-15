"""
app/core/logging_middleware.py

FastAPI Request Logging Middleware

Project:
A Secure Voice-based Financial Transaction System Using
Multimodal Biometrics and Agentic AI Fraud Detection
"""

from __future__ import annotations
from fastapi.responses import JSONResponse

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

from app.core.logger import (
    api_logger,
)
from app.core.log_context import (
    initialize_request_context,
    clear_context,
)

# ==========================================================
# Request Logging Middleware
# ==========================================================


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware responsible for:

    • Request context initialization
    • Request logging
    • Response logging
    • Performance metrics
    • Exception logging
    • Context cleanup

    Every HTTP request passes through this middleware.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """
        Process every incoming HTTP request.

        Responsibilities implemented in Section 2:
        - Initialize request context
        - Extract client metadata
        - Start request timer
        - Guarantee context cleanup
        """

        start_time = time.perf_counter()

        # --------------------------------------------------
        # Client Information
        # --------------------------------------------------

        client_ip = "-"

        if request.client:
            client_ip = request.client.host

        user_agent = request.headers.get(
            "User-Agent",
            "Unknown",
        )

        # --------------------------------------------------
        # User Identification
        # --------------------------------------------------
        #
        # Authentication will be implemented later.
        # Until then we allow clients to pass an optional
        # X-User-ID header.
        #
        # If absent, we use "anonymous".
        #
        # --------------------------------------------------

        user_id = request.headers.get(
            "X-User-ID",
            "anonymous",
        )

        # --------------------------------------------------
        # Initialize Request Context
        # --------------------------------------------------

        context = initialize_request_context(
            user_id=user_id,
            client_ip=client_ip,
            user_agent=user_agent,
            endpoint=request.url.path,
            method=request.method,
        )

        try:

            # ==================================================
            # Incoming Request
            # ==================================================

            api_logger.info(
                "Incoming API request.",
                endpoint=request.url.path,
                method=request.method,
                client_ip=client_ip,
            )

            # Process request
            response = await call_next(request)

            processing_time = round(
                (time.perf_counter() - start_time) * 1000,
                2,
            )

            response.headers["X-Request-ID"] = context.request_id
            response.headers["X-Processing-Time"] = f"{processing_time} ms"

            # ==================================================
            # Successful Response
            # ==================================================

            api_logger.info(
                "API request completed.",
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                processing_time_ms=processing_time,
            )

            api_logger.info(
                "API performance metrics.",
                event="API_PERFORMANCE",
                endpoint=request.url.path,
                processing_time_ms=processing_time,
                status_code=response.status_code,
            )

            return response

        except Exception as exc:

            processing_time = round(
                (time.perf_counter() - start_time) * 1000,
                2,
            )

            api_logger.exception(
                "Unhandled exception during request processing.",
                endpoint=request.url.path,
                method=request.method,
                processing_time_ms=processing_time,
                exception_type=type(exc).__name__,
            )

            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Internal server error.",
                    "request_id": context.request_id,
                },
                headers={
                    "X-Request-ID": context.request_id,
                    "X-Processing-Time": f"{processing_time} ms",
                },
            )

        finally:

            elapsed_ms = round(
                (time.perf_counter() - start_time) * 1000,
                2,
            )

            request.state.processing_time_ms = elapsed_ms
            request.state.request_context = context

            api_logger.debug(
                "Request context cleared.",
                processing_time_ms=elapsed_ms,
            )

            clear_context()