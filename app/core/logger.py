"""
app/core/logger.py

Enterprise Logging Framework V3

Project:
A Secure Voice-based Financial Transaction System Using
Multimodal Biometrics and Agentic AI Fraud Detection
"""

from __future__ import annotations

import copy
import json
import logging
import logging.handlers
import queue
import socket
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.constants import (
    DEFAULT_REQUEST_ID,
    DEFAULT_SESSION_ID,
    DEFAULT_TRANSACTION_ID,
    DEFAULT_USER_ID,
    LOGGER_NAME,
)
from app.core.log_context import get_context

# ==========================================================
# Application Metadata
# ==========================================================

HOSTNAME = socket.gethostname()

PROCESS_ID = None

THREAD_NAME = None


# ==========================================================
# Context Aware Queue Handler
# ==========================================================


class ContextQueueHandler(logging.handlers.QueueHandler):
    """
    QueueHandler that preserves request context before the
    LogRecord leaves the request thread.

    ContextVars cannot be accessed reliably from the listener
    thread, therefore we copy them into the LogRecord here.
    """

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:

        record = copy.copy(record)

        ctx = get_context()

        record.request_id = ctx.request_id or DEFAULT_REQUEST_ID
        record.transaction_id = (
            ctx.transaction_id or DEFAULT_TRANSACTION_ID
        )
        record.session_id = (
            ctx.session_id or DEFAULT_SESSION_ID
        )
        record.user_id = (
            ctx.user_id or DEFAULT_USER_ID
        )
        record.client_ip = ctx.client_ip
        record.user_agent = ctx.user_agent
        record.endpoint = ctx.endpoint
        record.method = ctx.method

        record.hostname = HOSTNAME

        record.process_id = record.process

        record.thread_name = record.threadName

        if not hasattr(record, "component"):
            record.component = "SYSTEM"

        return super().prepare(record)


# ==========================================================
# JSON Formatter
# ==========================================================


class JsonFormatter(logging.Formatter):
    """
    Writes structured JSON logs for audit purposes.
    """

    def format(self, record: logging.LogRecord) -> str:

        payload = {

            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),

            "level": record.levelname,

            "component": getattr(
                record,
                "component",
                "SYSTEM",
            ),

            "message": record.getMessage(),

            "request_id": getattr(
                record,
                "request_id",
                DEFAULT_REQUEST_ID,
            ),

            "transaction_id": getattr(
                record,
                "transaction_id",
                DEFAULT_TRANSACTION_ID,
            ),

            "session_id": getattr(
                record,
                "session_id",
                DEFAULT_SESSION_ID,
            ),

            "user_id": getattr(
                record,
                "user_id",
                DEFAULT_USER_ID,
            ),

            "client_ip": getattr(
                record,
                "client_ip",
                "-",
            ),

            "endpoint": getattr(
                record,
                "endpoint",
                "-",
            ),

            "method": getattr(
                record,
                "method",
                "-",
            ),

            "hostname": getattr(
                record,
                "hostname",
                HOSTNAME,
            ),

            "process": getattr(
                record,
                "process_id",
                record.process,
            ),

            "thread": getattr(
                record,
                "thread_name",
                threading.current_thread().name,
            ),

            "module": record.module,

            "function": record.funcName,

            "line": record.lineno,
        }

        # Preserve any custom metadata supplied using
        # logger.info(..., extra={...})

        reserved = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
        }

        for key, value in record.__dict__.items():

            if key not in reserved:

                payload[key] = value

        if record.exc_info:

            payload["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )


# ==========================================================
# Console Formatter
# ==========================================================


class ConsoleFormatter(logging.Formatter):
    """
    Human readable formatter for terminal output.
    """

    default_time_format = "%Y-%m-%d %H:%M:%S"

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:

        timestamp = self.formatTime(record)

        component = getattr(
            record,
            "component",
            "SYSTEM",
        ).ljust(10)

        request = getattr(
            record,
            "request_id",
            DEFAULT_REQUEST_ID,
        )

        message = record.getMessage()

        line = (
            f"{timestamp} | "
            f"{record.levelname:<8} | "
            f"{request:<12} | "
            f"{component} | "
            f"{message}"
        )

        if record.exc_info:

            line += (
                "\n"
                + self.formatException(
                    record.exc_info
                )
            )

        return line

        # ==========================================================
# Context Filter
# ==========================================================


class ContextFilter(logging.Filter):
    """
    Ensures every LogRecord contains the required enterprise
    logging attributes.

    Since ContextQueueHandler already injects the request
    context, this filter only guarantees that optional
    attributes always exist.
    """

    def filter(self, record: logging.LogRecord) -> bool:

        defaults = {
            "component": "SYSTEM",
            "request_id": DEFAULT_REQUEST_ID,
            "transaction_id": DEFAULT_TRANSACTION_ID,
            "session_id": DEFAULT_SESSION_ID,
            "user_id": DEFAULT_USER_ID,
            "client_ip": "-",
            "user_agent": "-",
            "endpoint": "-",
            "method": "-",
            "hostname": HOSTNAME,
            "process_id": record.process,
            "thread_name": record.threadName,
        }

        for key, value in defaults.items():

            if not hasattr(record, key):
                setattr(record, key, value)

        return True


# ==========================================================
# Logger Manager
# ==========================================================


class LoggerManager:
    """
    Singleton responsible for configuring the application's
    logging infrastructure.

    Features
    --------
    • Queue based logging
    • Console logging
    • Rotating application logs
    • Structured JSON audit logs
    • Thread-safe
    """

    _instance = None

    def __new__(cls):

        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __init__(self):

        if getattr(self, "_initialized", False):
            return

        self._initialized = True

        self.queue: queue.Queue = queue.Queue(-1)

        self.listener: logging.handlers.QueueListener | None = None

        self.logger = logging.getLogger(LOGGER_NAME)

        self._configure()

    # ------------------------------------------------------

    def _console_handler(self) -> logging.Handler:

        handler = logging.StreamHandler(sys.stdout)

        handler.setFormatter(ConsoleFormatter())

        handler.setLevel(
            getattr(logging, settings.LOG_LEVEL.upper())
        )

        handler.addFilter(ContextFilter())

        return handler

    # ------------------------------------------------------

    def _application_handler(self) -> logging.Handler:

        log_dir = Path(settings.LOG_DIRECTORY)

        log_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / "application.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=10,
            encoding="utf-8",
        )

        handler.setFormatter(

            logging.Formatter(

                fmt=(
                    "%(asctime)s | "
                    "%(levelname)-8s | "
                    "%(component)-10s | "
                    "%(request_id)s | "
                    "%(message)s"
                ),

                datefmt="%Y-%m-%d %H:%M:%S",

            )

        )

        handler.setLevel(
            getattr(logging, settings.LOG_LEVEL.upper())
        )

        handler.addFilter(ContextFilter())

        return handler

    # ------------------------------------------------------

    def _audit_handler(self) -> logging.Handler:

        log_dir = Path(settings.LOG_DIRECTORY)

        handler = logging.handlers.RotatingFileHandler(

            filename=log_dir / "audit.log",

            maxBytes=20 * 1024 * 1024,

            backupCount=20,

            encoding="utf-8",

        )

        handler.setFormatter(JsonFormatter())

        handler.setLevel(logging.INFO)

        handler.addFilter(ContextFilter())

        return handler

    # ------------------------------------------------------

    def _configure(self):

        self.logger.handlers.clear()

        self.logger.setLevel(
            getattr(logging, settings.LOG_LEVEL.upper())
        )

        self.logger.propagate = False

        queue_handler = ContextQueueHandler(self.queue)

        self.logger.addHandler(queue_handler)

        self.listener = logging.handlers.QueueListener(

            self.queue,

            self._console_handler(),

            self._application_handler(),

            self._audit_handler(),

            respect_handler_level=True,

        )

        self.listener.start()

    # ------------------------------------------------------

    def shutdown(self):

        if self.listener is not None:

            self.listener.stop()

            self.listener = None

    # ------------------------------------------------------

    @property
    def root_logger(self) -> logging.Logger:

        return self.logger


# ==========================================================
# Singleton Instance
# ==========================================================

_logger_manager = LoggerManager()

_base_logger = _logger_manager.root_logger

# ==========================================================
# Enterprise Logger Adapter
# ==========================================================

from typing import Optional


class EnterpriseLogger:
    """
    High-level logging interface for application modules.

    Example
    -------
    logger = get_logger("ASR")

    logger.info("Loading Whisper model...")

    logger.log_model_inference(...)

    logger.log_fraud_score(...)
    """

    def __init__(self, component: str):

        self.component = component.upper()

    # ------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------

    def _extra(
        self,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:

        payload = {
            "component": self.component,
        }

        if extra:
            payload.update(extra)

        return payload

    # ------------------------------------------------------
    # Standard logging
    # ------------------------------------------------------

    def debug(
        self,
        message: str,
        **extra,
    ):

        _base_logger.debug(
            message,
            extra=self._extra(extra),
        )

    def info(
        self,
        message: str,
        **extra,
    ):

        _base_logger.info(
            message,
            extra=self._extra(extra),
        )

    def warning(
        self,
        message: str,
        **extra,
    ):

        _base_logger.warning(
            message,
            extra=self._extra(extra),
        )

    def error(
        self,
        message: str,
        **extra,
    ):

        _base_logger.error(
            message,
            extra=self._extra(extra),
        )

    def critical(
        self,
        message: str,
        **extra,
    ):

        _base_logger.critical(
            message,
            extra=self._extra(extra),
        )

    def exception(
        self,
        message: str,
        **extra,
    ):

        _base_logger.exception(
            message,
            extra=self._extra(extra),
        )

    # ======================================================
    # AI Logging
    # ======================================================

    def log_model_inference(
        self,
        *,
        model: str,
        latency_ms: float,
        confidence: float,
        status: str,
        metadata: Optional[dict[str, Any]] = None,
    ):

        payload = {

            "event": "MODEL_INFERENCE",

            "model": model,

            "latency_ms": round(latency_ms, 2),

            "confidence": round(confidence, 4),

            "status": status,

        }

        if metadata:
            payload.update(metadata)

        self.info(
            "AI model inference completed.",
            **payload,
        )

    # ======================================================
    # Speaker Verification
    # ======================================================

    def log_speaker_verification(
        self,
        *,
        similarity: float,
        threshold: float,
        verified: bool,
    ):

        self.info(

            "Speaker verification completed.",

            event="SPEAKER_VERIFICATION",

            similarity=round(similarity, 4),

            threshold=round(threshold, 4),

            verified=verified,

        )

    # ======================================================
    # Face Recognition
    # ======================================================

    def log_face_verification(
        self,
        *,
        similarity: float,
        verified: bool,
    ):

        self.info(

            "Face verification completed.",

            event="FACE_VERIFICATION",

            similarity=round(similarity, 4),

            verified=verified,

        )

    # ======================================================
    # Liveness
    # ======================================================

    def log_liveness(
        self,
        *,
        score: float,
        passed: bool,
    ):

        self.info(

            "Liveness verification completed.",

            event="LIVENESS",

            liveness_score=round(score, 4),

            passed=passed,

        )

    # ======================================================
    # Fraud Engine
    # ======================================================

    def log_fraud_score(
        self,
        *,
        score: float,
        risk_level: str,
        decision: str,
    ):

        self.info(

            "Fraud analysis completed.",

            event="FRAUD_ANALYSIS",

            fraud_score=round(score, 4),

            risk_level=risk_level,

            decision=decision,

        )

    # ======================================================
    # Transaction
    # ======================================================

    def log_transaction(
        self,
        *,
        amount: float,
        recipient: str,
        intent: str,
        status: str,
    ):

        self.info(

            "Transaction processed.",

            event="TRANSACTION",

            amount=amount,

            recipient=recipient,

            intent=intent,

            status=status,

        )

    # ======================================================
    # Security
    # ======================================================

    def log_security_event(
        self,
        *,
        event: str,
        severity: str,
        reason: str,
    ):

        self.warning(

            reason,

            event=event,

            severity=severity,

        )


# ==========================================================
# Logger Factory
# ==========================================================

_LOGGER_CACHE: dict[str, EnterpriseLogger] = {}


def get_logger(
    component: str,
) -> EnterpriseLogger:
    """
    Returns a singleton logger for the given component.
    """

    component = component.upper()

    if component not in _LOGGER_CACHE:

        _LOGGER_CACHE[component] = EnterpriseLogger(
            component
        )

    return _LOGGER_CACHE[component]


# ==========================================================
# Predefined Loggers
# ==========================================================

system_logger = get_logger("SYSTEM")

api_logger = get_logger("API")

asr_logger = get_logger("ASR")

speaker_logger = get_logger("SPEAKER")

face_logger = get_logger("FACE")

liveness_logger = get_logger("LIVENESS")

fraud_logger = get_logger("FRAUD")

agent_logger = get_logger("AGENT")