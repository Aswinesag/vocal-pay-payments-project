"""
app/demo_main.py

VocalPay End-to-End Demo Sandbox

A dedicated, standalone FastAPI entry point used to demonstrate the
complete two-step, multi-risk transaction lifecycle without requiring
the full deep-learning stack (InsightFace / SpeechBrain / Faster-Whisper
/ Ollama) to be loaded. All biometric and agentic-AI computation is
mocked at the route layer; the database layer (models.py / schemas.py /
crud.py / database.py) is the real, production persistence path.

Run with:
    uvicorn app.demo_main:app --reload --port 8001

Project:
A Secure Voice-based Financial Transaction System Using
Multimodal Biometrics and Agentic AI Fraud Detection
"""

from __future__ import annotations

import random
import secrets
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    CHALLENGE_PREFIX,
    CHALLENGE_WORDS,
    DEFAULT_OTP_LENGTH,
    MODEL_OLLAMA,
    OTP_DIGITS,
    REPLAY_ATTACK_MESSAGE,
    RiskLevel,
    TransactionStatus,
)
from app.core.logger import get_logger
from app.database import crud
from app.database.database import get_db_session, init_db
from app.database.models import FraudEvent, PendingTransaction, Transaction, User
from app.database.schemas import UserRegistrationRequest

# ==========================================================
# Demo Logger
# ==========================================================

demo_logger = get_logger("DEMO")

# ==========================================================
# Demo Constants
# ==========================================================

DEMO_USER_ID = "demo_user_001"

PENDING_WINDOW_MINUTES = 5

MAX_OTP_ATTEMPTS = 3

# In-memory attempt tracker keyed by transaction_id. This is a demo-only
# convenience — the locked schema does not persist per-attempt counters
# on PendingTransaction, so attempt state does not need to survive a
# process restart for sandbox purposes.
_otp_attempts: dict[str, int] = defaultdict(int)


# ==========================================================
# Demo Request / Response Schemas
# ==========================================================
# Kept local to this sandbox file so the locked production schemas in
# app/database/schemas.py remain untouched.

class DemoInitiateRequest(BaseModel):
    """
    Demo transaction initiation request.

    `scenario` deterministically drives which mocked biometric /
    fraud-engine outcome is produced, so the lifecycle can be
    demonstrated reliably without live model inference.
    """

    amount: float = Field(gt=0, le=1_000_000, examples=[2500.0])
    recipient_id: str = Field(min_length=3, max_length=64, examples=["merchant_001"])
    device_id: str = Field(min_length=3, max_length=128, examples=["demo_device_01"])
    scenario: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        examples=["LOW"],
    )


class DemoVerifyRequest(BaseModel):
    """
    Demo Step 2 resumption request.

    Only one of `otp_code` / `challenge_response` is required,
    depending on the pending transaction's verification mode.
    """

    transaction_id: str = Field(min_length=8, max_length=64)
    otp_code: str | None = Field(default=None, min_length=6, max_length=6)
    challenge_response: str | None = Field(default=None, max_length=256)


class DemoInitiateResponse(BaseModel):
    success: bool
    transaction_id: str
    status: str
    risk_level: str
    message: str
    speaker_score: float | None = None
    face_score: float | None = None
    fraud_score: float | None = None
    xai_reason: str | None = None
    verification_method: str | None = None
    challenge_phrase: str | None = None
    expires_at: datetime | None = None
    amount: float | None = None


class DemoVerifyResponse(BaseModel):
    success: bool
    transaction_id: str
    status: str
    message: str
    verification_method: str | None = None
    remaining_attempts: int | None = None
    xai_reason: str | None = None
    amount: float | None = None
    risk_level: str | None = None


# ==========================================================
# Mock Biometric / Agentic AI Layer
# ==========================================================
# Temporary stand-ins for the scaffolded deep-learning services.
# Each function is a drop-in placeholder for its real counterpart
# (librosa DSP gate, SpeechBrain, InsightFace, Faster-Whisper, Ollama)
# and is intentionally isolated so it can be swapped out without
# touching route logic.

def mock_dsp_replay_detector(scenario: str) -> bool:
    """
    Stand-in for the CPU-bound librosa replay-attack DSP gate.

    Runs before any GPU model is touched. Returning True means a
    synthetic/replayed voice signature was detected and every
    downstream biometric + LLM pipeline is skipped entirely.
    """

    return scenario == "CRITICAL"


def mock_speaker_verification(scenario: str) -> float:
    """Stand-in for SpeechBrain ECAPA-TDNN cosine similarity (CPU)."""

    return {
        "LOW": 0.96,
        "MEDIUM": 0.81,
        "HIGH": 0.63,
    }.get(scenario, 0.0)


def mock_face_verification(scenario: str) -> float:
    """Stand-in for InsightFace embedding similarity (CUDA)."""

    return {
        "LOW": 0.94,
        "MEDIUM": 0.78,
        "HIGH": 0.60,
    }.get(scenario, 0.0)


def mock_ollama_fraud_reasoning(
    scenario: str,
    speaker_score: float,
    face_score: float,
) -> tuple[float, str]:
    """
    Stand-in for the local Llama-3.2-3B agentic auditor.

    Returns a (fraud_score, xai_reason) pair, mirroring the real
    agent's native-JSON-grammar output shape.
    """

    fraud_scores = {"LOW": 0.05, "MEDIUM": 0.42, "HIGH": 0.71}
    fraud_score = fraud_scores.get(scenario, 0.0)

    reason = (
        f"[{MODEL_OLLAMA} mock] speaker_similarity={speaker_score:.2f}, "
        f"face_similarity={face_score:.2f} -> risk bucket '{scenario}' "
        f"assigned with fraud_score={fraud_score:.2f}."
    )

    return fraud_score, reason


def mock_whisper_challenge_transcription(challenge_phrase: str) -> str:
    """
    Stand-in for Faster-Whisper re-transcribing the HIGH-risk voice
    challenge clip. The sandbox simulates a clean, successful
    transcription so the full lifecycle can resolve deterministically.
    """

    return challenge_phrase


def generate_otp() -> str:
    return "".join(secrets.choice(OTP_DIGITS) for _ in range(DEFAULT_OTP_LENGTH))


def generate_challenge_phrase() -> str:
    words = random.sample(CHALLENGE_WORDS, 2)
    return f"{CHALLENGE_PREFIX} {words[0]} {words[1]}"


def new_transaction_id() -> str:
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ==========================================================
# Demo User Bootstrap
# ==========================================================

async def ensure_demo_user(session: AsyncSession) -> User:
    """
    Ensures a demo user exists so PendingTransaction / Transaction
    foreign keys resolve cleanly. Uses placeholder embedding vectors
    only — no real biometric enrollment happens in the sandbox.
    """

    existing = await crud.get_user_by_user_id(session, DEMO_USER_ID)

    if existing is not None:
        return existing

    demo_logger.info(
        "Bootstrapping demo user for sandbox lifecycle.",
        user_id=DEMO_USER_ID,
    )

    registration = UserRegistrationRequest(
        user_id=DEMO_USER_ID,
        full_name="VocalPay Demo User",
        email="demo.user@vocalpay-sandbox.io",
        phone_number="+910000000000",
        preferred_language="en",
        speaker_embedding=[0.0] * 192,
        face_embedding=[0.0] * 512,
    )

    return await crud.create_user(session, registration)


# ==========================================================
# Application Lifespan
# ==========================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    demo_logger.info("VocalPay demo sandbox starting up.")

    init_db()

    async with get_db_session() as session:
        await ensure_demo_user(session)

    demo_logger.info("Demo sandbox startup complete. Database schema mounted.")

    yield

    demo_logger.info("VocalPay demo sandbox shutting down.")


# ==========================================================
# FastAPI Application
# ==========================================================

app = FastAPI(
    title="VocalPay End-to-End Demo Sandbox",
    description=(
        "Mentor-facing demonstration of the stateless, two-step "
        "multi-risk transaction lifecycle. Biometric and agentic-AI "
        "inference is mocked; database persistence is real."
    ),
    version="1.0.0-demo",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# Health Check
# ==========================================================

@app.get("/api/v1/demo/health", tags=["demo"])
async def demo_health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": "VocalPay End-to-End Demo Sandbox",
    }


# ==========================================================
# Step 1 — Initiate
# ==========================================================

@app.post(
    "/api/v1/demo/initiate",
    response_model=DemoInitiateResponse,
    tags=["demo"],
)
async def demo_initiate(payload: DemoInitiateRequest) -> DemoInitiateResponse:
    """
    Mocked equivalent of /api/v1/transaction/initiate.

    Routes into one of four deterministic scenarios so the full
    risk-tiered lifecycle can be shown to a mentor on demand.
    """

    transaction_id = new_transaction_id()

    demo_logger.info(
        "Transaction initiation started.",
        transaction_id=transaction_id,
        scenario=payload.scenario,
        amount=payload.amount,
    )

    # ------------------------------------------------------
    # VRAM-protection shortcut: cheap CPU DSP gate runs first,
    # before any GPU model is ever touched.
    # ------------------------------------------------------

    if mock_dsp_replay_detector(payload.scenario):

        demo_logger.warning(
            "DSP replay-attack shortcut triggered. Bypassing all "
            "downstream biometric and LLM compute.",
            transaction_id=transaction_id,
        )

        async with get_db_session() as session:
            fraud_event = FraudEvent(
                transaction_id=transaction_id,
                user_id=DEMO_USER_ID,
                event_type="REPLAY_ATTACK",
                risk_level=RiskLevel.CRITICAL.value,
                blocked=True,
                speaker_score=None,
                face_score=None,
                fraud_score=1.0,
                reason=REPLAY_ATTACK_MESSAGE,
                replay_attack=True,
            )
            await crud.create_fraud_event(session, fraud_event)

        demo_logger.error(
            "Transaction hard-blocked at DSP stage. Returning HTTP 401.",
            transaction_id=transaction_id,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "transaction_id": transaction_id,
                "status": TransactionStatus.BLOCKED.value,
                "risk_level": RiskLevel.CRITICAL.value,
                "message": REPLAY_ATTACK_MESSAGE,
            },
        )

    # ------------------------------------------------------
    # Sequential mock biometric pipeline
    # (InsightFace -> SpeechBrain -> Ollama, never concurrent)
    # ------------------------------------------------------

    speaker_score = mock_speaker_verification(payload.scenario)
    face_score = mock_face_verification(payload.scenario)
    fraud_score, xai_reason = mock_ollama_fraud_reasoning(
        payload.scenario, speaker_score, face_score
    )

    demo_logger.info(
        "Mock biometric + agentic reasoning complete.",
        transaction_id=transaction_id,
        speaker_score=speaker_score,
        face_score=face_score,
        fraud_score=fraud_score,
    )

    async with get_db_session() as session:

        # ---- LOW risk: resolve immediately, no freeze ----
        if payload.scenario == "LOW":

            transaction = Transaction(
                transaction_id=transaction_id,
                user_id=DEMO_USER_ID,
                amount=payload.amount,
                status=TransactionStatus.COMPLETED.value,
                risk_level=RiskLevel.LOW.value,
                success=True,
                speaker_score=speaker_score,
                face_score=face_score,
                fraud_score=fraud_score,
                xai_reason=xai_reason,
                processing_time_ms=42.0,
                replay_attack=False,
            )
            await crud.create_transaction(session, transaction)

            demo_logger.info(
                "LOW risk transaction auto-approved and ledgered.",
                transaction_id=transaction_id,
            )

            return DemoInitiateResponse(
                success=True,
                transaction_id=transaction_id,
                status=TransactionStatus.COMPLETED.value,
                risk_level=RiskLevel.LOW.value,
                message="Transaction approved automatically.",
                speaker_score=speaker_score,
                face_score=face_score,
                fraud_score=fraud_score,
                xai_reason=xai_reason,
                amount=payload.amount,
            )

        # ---- MEDIUM risk: freeze context, require OTP ----
        if payload.scenario == "MEDIUM":

            otp_code = generate_otp()
            expires_at = utc_now() + timedelta(minutes=PENDING_WINDOW_MINUTES)

            pending = PendingTransaction(
                transaction_id=transaction_id,
                user_id=DEMO_USER_ID,
                amount=payload.amount,
                risk_level=RiskLevel.MEDIUM.value,
                status=TransactionStatus.PENDING_OTP.value,
                verification_secret=otp_code,
                expires_at=expires_at,
                speaker_score=speaker_score,
                face_score=face_score,
                fraud_score=fraud_score,
                replay_attack=False,
            )
            await crud.create_pending_transaction(session, pending)

            demo_logger.info(
                "MEDIUM risk transaction frozen pending OTP. "
                "Connection closing.",
                transaction_id=transaction_id,
                expires_at=expires_at.isoformat(),
                demo_only_otp=otp_code,
            )

            return DemoInitiateResponse(
                success=True,
                transaction_id=transaction_id,
                status=TransactionStatus.PENDING_OTP.value,
                risk_level=RiskLevel.MEDIUM.value,
                message=(
                    "Additional verification required. OTP generated "
                    "(check server logs for this sandbox run)."
                ),
                speaker_score=speaker_score,
                face_score=face_score,
                fraud_score=fraud_score,
                verification_method="otp",
                expires_at=expires_at,
                amount=payload.amount,
            )

        # ---- HIGH risk: freeze context, require voice challenge ----
        challenge_phrase = generate_challenge_phrase()
        expires_at = utc_now() + timedelta(minutes=PENDING_WINDOW_MINUTES)

        pending = PendingTransaction(
            transaction_id=transaction_id,
            user_id=DEMO_USER_ID,
            amount=payload.amount,
            risk_level=RiskLevel.HIGH.value,
            status=TransactionStatus.PENDING_CHALLENGE.value,
            verification_secret=challenge_phrase,
            expires_at=expires_at,
            speaker_score=speaker_score,
            face_score=face_score,
            fraud_score=fraud_score,
            replay_attack=False,
        )
        await crud.create_pending_transaction(session, pending)

        demo_logger.info(
            "HIGH risk transaction frozen pending voice challenge. "
            "Connection closing.",
            transaction_id=transaction_id,
            expires_at=expires_at.isoformat(),
            challenge_phrase=challenge_phrase,
        )

        return DemoInitiateResponse(
            success=True,
            transaction_id=transaction_id,
            status=TransactionStatus.PENDING_CHALLENGE.value,
            risk_level=RiskLevel.HIGH.value,
            message="Voice challenge verification required.",
            speaker_score=speaker_score,
            face_score=face_score,
            fraud_score=fraud_score,
            verification_method="voice_challenge",
            challenge_phrase=challenge_phrase,
            expires_at=expires_at,
            amount=payload.amount,
        )


# ==========================================================
# Step 2 — Verify
# ==========================================================

@app.post(
    "/api/v1/demo/verify",
    response_model=DemoVerifyResponse,
    tags=["demo"],
)
async def demo_verify(payload: DemoVerifyRequest) -> DemoVerifyResponse:
    """
    Mocked equivalent of /api/v1/transaction/verify.

    Rehydrates the frozen context from PendingTransaction and resolves
    it into a permanent Transaction ledger row, invalidating the
    pending record so it cannot be replayed.
    """

    demo_logger.info(
        "Verification requested.",
        transaction_id=payload.transaction_id,
    )

    async with get_db_session() as session:

        pending = await crud.get_pending_transaction_by_transaction_id(
            session, payload.transaction_id
        )

        if pending is None:
            demo_logger.warning(
                "Verification attempted against unknown transaction_id.",
                transaction_id=payload.transaction_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pending transaction found for this transaction_id.",
            )

        if pending.expires_at < utc_now():

            demo_logger.warning(
                "Pending transaction expired before verification.",
                transaction_id=payload.transaction_id,
            )

            await crud.delete_pending_transaction(session, pending)
            _otp_attempts.pop(payload.transaction_id, None)

            return DemoVerifyResponse(
                success=False,
                transaction_id=payload.transaction_id,
                status=TransactionStatus.EXPIRED.value,
                message="Pending transaction has expired.",
            )

        if pending.status == TransactionStatus.PENDING_OTP.value:

            if not payload.otp_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="otp_code is required for this transaction.",
                )

            if payload.otp_code != pending.verification_secret:

                _otp_attempts[payload.transaction_id] += 1
                remaining = max(
                    0, MAX_OTP_ATTEMPTS - _otp_attempts[payload.transaction_id]
                )

                demo_logger.warning(
                    "OTP mismatch on verification attempt.",
                    transaction_id=payload.transaction_id,
                    remaining_attempts=remaining,
                )

                if remaining == 0:
                    await crud.delete_pending_transaction(session, pending)
                    _otp_attempts.pop(payload.transaction_id, None)

                return DemoVerifyResponse(
                    success=False,
                    transaction_id=payload.transaction_id,
                    status="VERIFICATION_FAILED",
                    message="Invalid or expired OTP.",
                    verification_method="otp",
                    remaining_attempts=remaining,
                    risk_level=pending.risk_level,
                )

            demo_logger.info(
                "OTP verified successfully. Finalizing ledger.",
                transaction_id=payload.transaction_id,
            )

            xai_reason = (
                f"[{MODEL_OLLAMA} mock] MEDIUM risk transaction resolved via "
                f"OTP verification."
            )
            verification_method = "otp"

        elif pending.status == TransactionStatus.PENDING_CHALLENGE.value:

            transcribed = mock_whisper_challenge_transcription(
                pending.verification_secret
            )

            if transcribed.strip().lower() != pending.verification_secret.strip().lower():

                demo_logger.warning(
                    "Voice challenge transcription mismatch.",
                    transaction_id=payload.transaction_id,
                )

                return DemoVerifyResponse(
                    success=False,
                    transaction_id=payload.transaction_id,
                    status="VERIFICATION_FAILED",
                    message="Voice challenge verification failed.",
                    verification_method="voice_challenge",
                    risk_level=pending.risk_level,
                )

            demo_logger.info(
                "Voice challenge phrase matched. Finalizing ledger.",
                transaction_id=payload.transaction_id,
            )

            xai_reason = (
                f"[{MODEL_OLLAMA} mock] HIGH risk transaction resolved via "
                f"matched voice challenge phrase."
            )
            verification_method = "voice_challenge"

        else:
            demo_logger.error(
                "Pending transaction in unexpected state.",
                transaction_id=payload.transaction_id,
                status=pending.status,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unexpected pending status '{pending.status}'.",
            )

        transaction = Transaction(
            transaction_id=pending.transaction_id,
            user_id=pending.user_id,
            amount=pending.amount,
            status=TransactionStatus.COMPLETED.value,
            risk_level=pending.risk_level,
            success=True,
            speaker_score=pending.speaker_score,
            face_score=pending.face_score,
            fraud_score=pending.fraud_score,
            xai_reason=xai_reason,
            processing_time_ms=88.0,
            replay_attack=pending.replay_attack,
        )
        await crud.create_transaction(session, transaction)
        await crud.delete_pending_transaction(session, pending)
        _otp_attempts.pop(payload.transaction_id, None)

        demo_logger.info(
            "Transaction finalized and pending record invalidated.",
            transaction_id=payload.transaction_id,
        )

        return DemoVerifyResponse(
            success=True,
            transaction_id=payload.transaction_id,
            status=TransactionStatus.COMPLETED.value,
            message="Transaction verified and completed successfully.",
            verification_method=verification_method,
            amount=pending.amount,
            risk_level=pending.risk_level,
            xai_reason=xai_reason,
        )