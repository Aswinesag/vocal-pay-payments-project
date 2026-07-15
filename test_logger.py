"""
Enterprise Logger V3 Test

Run:
    python test_logger.py
"""

from pathlib import Path
import time

from app.core.log_context import (
    initialize_request_context,
    clear_context,
)

from app.core.logger import (
    _base_logger,
    asr_logger,
    speaker_logger,
    fraud_logger,
)

# =====================================================
# Initialize Context
# =====================================================

ctx = initialize_request_context(
    user_id="test_user_001",
    client_ip="127.0.0.1",
    user_agent="UnitTest",
    endpoint="/api/v1/asr/transcribe",
    method="POST",
)

print("\n========== REQUEST CONTEXT ==========")
print(ctx)

# =====================================================
# Enterprise Logger API Test
# =====================================================

print("\n========== ENTERPRISE LOGGER API ==========")

asr_logger.info("Whisper model initialized.")

asr_logger.log_model_inference(
    model="faster-whisper-small.en",
    latency_ms=812.4,
    confidence=0.978,
    status="SUCCESS",
)

speaker_logger.log_speaker_verification(
    similarity=0.92,
    threshold=0.80,
    verified=True,
)

fraud_logger.log_fraud_score(
    score=0.17,
    risk_level="LOW",
    decision="ALLOW",
)
# =====================================================
# Basic Logging
# =====================================================

print("\n========== BASIC LOGGING ==========")

_base_logger.info(
    "Application startup successful.",
    extra={
        "component": "SYSTEM"
    }
)

_base_logger.info(
    "ASR model loaded successfully.",
    extra={
        "component": "ASR"
    }
)

_base_logger.warning(
    "Speaker similarity below threshold.",
    extra={
        "component": "SPEAKER"
    }
)

_base_logger.error(
    "Face verification failed.",
    extra={
        "component": "FACE"
    }
)

# =====================================================
# AI Metadata
# =====================================================

print("\n========== AI METADATA ==========")

_base_logger.info(
    "Whisper transcription completed.",
    extra={
        "component": "ASR",
        "latency_ms": 823,
        "confidence": 0.9734,
        "language": "en",
    },
)

# =====================================================
# Fraud Engine
# =====================================================

print("\n========== FRAUD ENGINE ==========")

_base_logger.info(
    "Fraud analysis complete.",
    extra={
        "component": "FRAUD",
        "risk_score": 0.21,
        "risk_level": "LOW",
        "decision": "ALLOW",
    },
)

_base_logger.info(
    "Fraud analysis complete.",
    extra={
        "component": "FRAUD",
        "risk_score": 0.91,
        "risk_level": "CRITICAL",
        "decision": "BLOCK",
    },
)

# =====================================================
# Exception Test
# =====================================================

print("\n========== EXCEPTION ==========")

try:

    10 / 0

except Exception:

    _base_logger.exception(
        "Division by zero occurred.",
        extra={
            "component": "SYSTEM"
        }
    )

# =====================================================
# Multiple Queue Messages
# =====================================================

print("\n========== QUEUE TEST ==========")

for i in range(20):

    _base_logger.info(
        f"Queue message {i+1}",
        extra={
            "component": "QUEUE_TEST"
        }
    )

# Give QueueListener time to flush
time.sleep(2)

clear_context()

print("\n========== LOG FILES ==========")

log_dir = Path("logs")

print("application.log :", (log_dir / "application.log").exists())

print("audit.log       :", (log_dir / "audit.log").exists())

print("\nLogger V3 test completed.")