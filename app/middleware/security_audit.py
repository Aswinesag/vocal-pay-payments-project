"""Security auditing middleware for blocked VocalPay API requests."""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any
from urllib.parse import parse_qs

from fastapi import HTTPException, Request
from loguru import logger
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.database.database import AsyncSessionLocal
from app.database.models import AuditLog, User


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """Record security-relevant request failures without blocking responses."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Measure a request and persist an audit row when access is blocked."""
        context = await self._extract_context(request)
        started_at = perf_counter()

        try:
            response = await call_next(request)
        except HTTPException as exc:
            latency_ms = round((perf_counter() - started_at) * 1000.0, 2)
            if exc.status_code in {401, 403}:
                await self._write_security_audit(
                    request=request,
                    context=context,
                    status_code=exc.status_code,
                    latency_ms=latency_ms,
                )
            raise
        except Exception:
            latency_ms = round((perf_counter() - started_at) * 1000.0, 2)
            logger.bind(
                method=request.method,
                path=request.url.path,
                latency_ms=latency_ms,
            ).exception("Unhandled request failure observed by security middleware.")
            raise

        latency_ms = round((perf_counter() - started_at) * 1000.0, 2)
        if response.status_code in {401, 403}:
            await self._write_security_audit(
                request=request,
                context=context,
                status_code=response.status_code,
                latency_ms=latency_ms,
            )

        logger.bind(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        ).debug("Security-audited request completed.")
        return response

    async def _extract_context(self, request: Request) -> dict[str, str | None]:
        """Extract non-secret request identifiers from headers or small text bodies."""
        user_id = request.headers.get("X-User-ID") or request.query_params.get("user_id")
        transaction_id = (
            request.headers.get("X-Transaction-ID")
            or request.query_params.get("transaction_id")
        )
        content_type = request.headers.get("content-type", "").casefold()

        try:
            body = await request.body()
            payload: dict[str, Any] = {}
            if body and "application/json" in content_type:
                decoded = json.loads(body)
                if isinstance(decoded, dict):
                    payload = decoded
            elif body and "application/x-www-form-urlencoded" in content_type:
                fields = parse_qs(body.decode("utf-8", errors="strict"), keep_blank_values=False)
                payload = {key: values[0] for key, values in fields.items() if values}

            candidate_user = payload.get("user_id")
            candidate_transaction = payload.get("transaction_id")
            if user_id is None and isinstance(candidate_user, str):
                user_id = candidate_user
            if transaction_id is None and isinstance(candidate_transaction, str):
                transaction_id = candidate_transaction
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            logger.bind(path=request.url.path).debug(
                "Request context body could not be decoded safely."
            )

        return {
            "user_id": user_id[:64] if user_id else None,
            "transaction_id": transaction_id[:64] if transaction_id else None,
        }

    async def _write_security_audit(
        self,
        *,
        request: Request,
        context: dict[str, str | None],
        status_code: int,
        latency_ms: float,
    ) -> None:
        """Persist one blocked-request audit record in an isolated transaction."""
        client_ip = request.client.host if request.client is not None else None
        session = AsyncSessionLocal()
        try:
            user_id = context["user_id"]
            if user_id is not None:
                known_user = await session.scalar(
                    select(User.user_id).where(User.user_id == user_id)
                )
                if known_user is None:
                    user_id = None

            session.add(
                AuditLog(
                    transaction_id=context["transaction_id"],
                    user_id=user_id,
                    endpoint=request.url.path[:255],
                    method=request.method[:10],
                    event_type="SECURITY_REQUEST_BLOCKED",
                    status=str(status_code),
                    message="Request blocked by VocalPay security policy.",
                    client_ip=client_ip[:64] if client_ip else None,
                    user_agent=request.headers.get("user-agent"),
                    processing_time_ms=latency_ms,
                )
            )
            await session.commit()
            logger.bind(
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                latency_ms=latency_ms,
                client_ip=client_ip,
            ).warning("Blocked request persisted to the security audit log.")
        except Exception as exc:
            await session.rollback()
            logger.bind(error=str(exc), path=request.url.path).exception(
                "Security audit persistence failed."
            )
        finally:
            await session.close()


__all__ = ("SecurityAuditMiddleware",)
