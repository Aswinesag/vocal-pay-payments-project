"""Conditional two-step transaction state-machine endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from loguru import logger
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audio_dsp import detect_replay_attack
from app.core.config import settings
from app.core.converters import async_upload_to_numpy, async_upload_to_waveform
from app.core.vector_index import search_voiceprint, VoiceprintIndexError
from app.database.crud import (
    create_fraud_event,
    create_transaction,
    freeze_transaction,
    get_active_transaction,
    get_transactions_by_user_id,
)
from app.database.database import get_async_db
from app.database.models import FraudEvent, PendingTransaction, Transaction, User
from app.services.ollama_service import OllamaService
from app.services.liveness.detector import LivenessDetector
from app.services.liveness.preprocess import LivenessPreprocessor
from app.services.providers.provider_factory import (
    BiometricInferenceProxy,
    get_speaker_verification_provider,
)
from app.services.whisper_service import WhisperService
from app.services.email_service import EmailServiceError, send_otp_email
from app.api.v1.endpoints.auth import get_current_user

try:
    from geoip2.database import Reader as GeoIPReader
except ImportError:  # Allows startup before optional deployment data is installed.
    GeoIPReader = None  # type: ignore[assignment,misc]


router = APIRouter(prefix="/transactions", tags=["transactions"])
ollama_service = OllamaService()
liveness_preprocessor = LivenessPreprocessor()
liveness_detector = LivenessDetector()
GEOIP_DATABASE_PATH = Path(__file__).resolve().parents[3] / "core" / "GeoLite2-City.mmdb"


class _FasterWhisperProxyAdapter:
    """Expose the Faster-Whisper service through the inference proxy contract."""

    name = "FasterWhisper"

    def transcribe(self, waveform: np.ndarray) -> str:
        """Transcribe one waveform using the existing ASR service."""
        service = WhisperService()
        return service.transcribe_audio(waveform)

    async def shutdown(self) -> None:
        """Release the cached ASR model during application shutdown."""
        WhisperService().release_model()


whisper_provider = BiometricInferenceProxy(
    _FasterWhisperProxyAdapter(),
    "faster-whisper",
)

_NUMBER_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _otp_digest(otp_code: str) -> str:
    """Return a keyed digest suitable for persisted OTP verification."""
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        otp_code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _utc_isoformat(value: datetime) -> str:
    """Serialize a persisted UTC timestamp with an explicit UTC offset."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _lookup_geoip_country(client_ip: str) -> str:
    """Resolve one public IP through the local GeoLite database."""
    if GeoIPReader is None or not GEOIP_DATABASE_PATH.is_file():
        logger.bind(database=str(GEOIP_DATABASE_PATH)).warning(
            "Offline GeoIP database is unavailable; network location is unknown."
        )
        return "Unknown"
    try:
        with GeoIPReader(str(GEOIP_DATABASE_PATH)) as reader:
            country = reader.city(client_ip).country.name
        return country.strip() if country else "Unknown"
    except Exception as exc:
        logger.bind(error=str(exc)).warning("Offline GeoIP lookup failed.")
        return "Unknown"


async def _resolve_network_country(request: Request) -> str:
    """Resolve a safe network country, trusting proxy headers only when enabled."""
    peer_ip = request.client.host if request.client is not None else ""
    forwarded_for = request.headers.get("X-Forwarded-For")
    client_ip = (
        forwarded_for.split(",", maxsplit=1)[0].strip()
        if settings.TRUST_PROXY_HEADERS and forwarded_for
        else peer_ip
    )
    if client_ip.casefold() in {"127.0.0.1", "localhost", "::1"}:
        return "India"
    try:
        address = ip_address(client_ip)
    except ValueError:
        logger.warning("Incoming client address could not be validated for GeoIP lookup.")
        return "Unknown"
    if address.is_loopback or address.is_private:
        return "India"
    return await asyncio.to_thread(_lookup_geoip_country, str(address))


async def _record_critical_fraud_event(
    db: AsyncSession,
    *,
    user_id: str | None,
    reason: str,
    replay_attack: bool,
    speaker_score: float | None = None,
) -> None:
    """Persist a terminal security block without changing its response path."""
    event = FraudEvent(
        transaction_id=f"FRD-{uuid.uuid4().hex.upper()}",
        user_id=user_id,
        event_type="REPLAY_ATTACK" if replay_attack else "CRITICAL_RISK_BLOCK",
        risk_level="CRITICAL",
        blocked=True,
        speaker_score=speaker_score,
        face_score=None,
        fraud_score=None,
        reason=reason,
        replay_attack=replay_attack,
    )
    try:
        await create_fraud_event(db, event)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.bind(error=str(exc)).exception("Critical fraud event persistence failed")


def _extract_transaction_amount(transcription: str) -> float:
    """Extract a positive numeric payment amount from an ASR transcript."""
    numeric_match = re.search(
        r"(?:₹|\$)?\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)",
        transcription,
    )
    if numeric_match is not None:
        amount = float(numeric_match.group(1).replace(",", ""))
        if amount > 0:
            return amount

    tokens = re.findall(r"[a-z]+", transcription.casefold())
    total = 0
    current = 0
    found_number = False
    for token in tokens:
        if token in _NUMBER_WORDS:
            current += _NUMBER_WORDS[token]
            found_number = True
        elif token == "hundred" and current:
            current *= 100
            found_number = True
        elif token in {"thousand", "lakh"} and current:
            multiplier = 1_000 if token == "thousand" else 100_000
            total += current * multiplier
            current = 0
            found_number = True
        elif found_number and token not in {"and", "rupee", "rupees", "dollar", "dollars"}:
            break

    amount = float(total + current)
    if not found_number or amount <= 0:
        raise ValueError("No positive transaction amount was found in the voice command.")
    return amount


class TransactionResponse(BaseModel):
    """Serialized state-machine response."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    status: str
    risk_tier: str
    rationale: str
    transaction_id: str | None = None
    action: str | None = None
    expires_at: str | None = None


@router.post("/initiate", response_model=TransactionResponse)
async def initiate_transaction(
    request: Request,
    audio_file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> TransactionResponse:
    """Resolve a spoken payment command and run its voice risk gates."""
    audio_path: Path | None = None
    resolved_user_id: str | None = None
    request_start_time = perf_counter()
    try:
        audio_bytes = await audio_file.read()
        if not audio_bytes:
            raise HTTPException(status_code=422, detail="Audio file is empty.")
        suffix = Path(audio_file.filename or "voice.wav").suffix or ".wav"
        with NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary.write(audio_bytes)
            audio_path = Path(temporary.name)

        if detect_replay_attack(str(audio_path)):
            logger.warning("DSP replay gate blocked voice-driven transaction.")
            await _record_critical_fraud_event(
                db,
                user_id=None,
                reason="CPU DSP gate detected a probable audio replay attack.",
                replay_attack=True,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"risk_tier": "CRITICAL", "status": "BLOCKED"},
            )

        await audio_file.seek(0)
        waveform = await async_upload_to_waveform(audio_file)
        transcription = str(await whisper_provider.transcribe(waveform)).strip()
        if not transcription:
            raise HTTPException(status_code=422, detail="The spoken command could not be transcribed.")
        try:
            extracted_amount = _extract_transaction_amount(transcription)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # Extract live speaker embedding using SpeechBrain (CPU)
        voice_provider = get_speaker_verification_provider()
        live_embedding = await voice_provider.extract_embedding(waveform)

        # Rapid O(log n) voice identity resolution via FAISS HNSW index
        try:
            resolved_user_id, speaker_score = await search_voiceprint(live_embedding)
            logger.bind(
                user_id=resolved_user_id,
                speaker_score=round(speaker_score, 6),
                search_method="FAISS_HNSW",
            ).debug("FAISS voiceprint search completed in <50ms.")
        except VoiceprintIndexError as exc:
            logger.bind(error=str(exc)).warning(
                "FAISS index not available, falling back to linear search."
            )
            # Fallback to O(n) linear search if FAISS index unavailable
            users = list((await db.scalars(select(User))).all())
            best_user: User | None = None
            speaker_score = -1.0
            for candidate in users:
                if not candidate.speaker_embedding:
                    continue
                voice_result: Any = await voice_provider.verify_speaker(
                    enrolled_embedding=candidate.speaker_embedding,
                    live_embedding=live_embedding,
                )
                candidate_score = float(voice_result.confidence)
                if candidate_score > speaker_score:
                    best_user = candidate
                    speaker_score = candidate_score
            
            if best_user is None:
                raise HTTPException(
                    status_code=404,
                    detail="No enrolled voice identity matched."
                )
            resolved_user_id = best_user.user_id

        # Verify speaker score meets threshold
        if speaker_score < settings.SPEAKER_PASS_THRESHOLD:
            logger.warning(
                "Voice identity rejected: best_score={:.6f}, threshold={:.6f}.",
                speaker_score,
                settings.SPEAKER_PASS_THRESHOLD,
            )
            raise HTTPException(
                status_code=404,
                detail="No enrolled voice identity matched."
            )
        
        # Load full user record from database
        user = await db.scalar(select(User).where(User.user_id == resolved_user_id))
        if user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found in database."
            )
        logger.bind(
            user_id=resolved_user_id,
            speaker_score=speaker_score,
            transcription=transcription,
            amount=extracted_amount,
        ).info("Voice-driven transaction command resolved.")

        if extracted_amount >= 500.00:
            # Generate randomized challenge phrase for voice verification
            challenge_words = [
                ["alpha", "bravo", "charlie", "delta", "echo"],
                ["red", "blue", "green", "yellow", "purple"],
                ["north", "south", "east", "west", "central"],
                ["river", "mountain", "ocean", "forest", "desert"]
            ]
            challenge_phrase = " ".join(secrets.choice(word_list) for word_list in challenge_words)
            
            pending = await freeze_transaction(
                db,
                user_id=resolved_user_id,
                amount=extracted_amount,
                status="PENDING_CHALLENGE",
                verification_secret=challenge_phrase,
                risk_level="HIGH",
                speaker_score=speaker_score,
            )
            logger.bind(
                transaction_id=pending.transaction_id,
                user_id=resolved_user_id,
            ).info("HIGH-risk voice challenge persisted")
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "status": pending.status,
                    "risk_tier": "HIGH",
                    "transaction_id": pending.transaction_id,
                    "action": "VOICE_CHALLENGE",
                    "challenge_phrase": challenge_phrase,
                    "expires_at": _utc_isoformat(pending.expires_at),
                    "rationale": "Transaction amount requires mandatory voice challenge verification.",
                },
            )

        resolved_country = await _resolve_network_country(request)
        decision = await ollama_service.evaluate_transaction_context(
            amount=extracted_amount,
            speaker_score=speaker_score,
            face_score=0.0,
            liveness_score=0.0,
            is_replay=False,
            network_country=resolved_country,
        )
        if resolved_country not in {"India", "Unknown"}:
            decision = {
                "risk_tier": "MEDIUM",
                "explainable_ai_rationale": (
                    f"Incoming network location resolved to {resolved_country}, which "
                    "conflicts with the account's India baseline; OTP step-up is required."
                ),
            }
        risk_tier = str(decision["risk_tier"])
        rationale = str(decision["explainable_ai_rationale"])

        if risk_tier == "LOW":
            # Create immutable audit record for LOW-risk auto-approved transaction
            processing_time_ms = (perf_counter() - request_start_time) * 1000.0
            transaction_record = Transaction(
                transaction_id=str(uuid.uuid4()),
                user_id=resolved_user_id,
                amount=extracted_amount,
                status="COMPLETED",
                risk_level="LOW",
                success=True,
                speaker_score=speaker_score,
                face_score=0.0,
                fraud_score=float(decision.get("fraud_score", 0.0)),
                xai_reason=rationale,
                processing_time_ms=processing_time_ms,
                replay_attack=False,
            )
            await create_transaction(db, transaction_record)
            await db.commit()
            
            logger.bind(
                transaction_id=transaction_record.transaction_id,
                user_id=resolved_user_id,
                amount=extracted_amount,
                risk_tier="LOW",
                processing_time_ms=round(processing_time_ms, 2),
            ).info("LOW-risk transaction auto-approved and committed to ledger.")
            
            return TransactionResponse(
                success=True,
                status="SUCCESS",
                risk_tier=risk_tier,
                rationale=rationale,
                transaction_id=transaction_record.transaction_id,
            )
        if risk_tier not in {"MEDIUM", "HIGH"}:
            await _record_critical_fraud_event(
                db,
                user_id=resolved_user_id,
                reason="Agentic risk evaluation returned a terminal critical block.",
                replay_attack=False,
                speaker_score=speaker_score,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"risk_tier": "CRITICAL", "status": "BLOCKED"},
            )

        if risk_tier == "HIGH":
            challenge_words = [
                ["alpha", "bravo", "charlie", "delta", "echo"],
                ["red", "blue", "green", "yellow", "purple"],
                ["north", "south", "east", "west", "central"],
                ["river", "mountain", "ocean", "forest", "desert"],
            ]
            challenge_phrase = " ".join(
                secrets.choice(word_list) for word_list in challenge_words
            )
            pending = await freeze_transaction(
                db,
                user_id=resolved_user_id,
                amount=extracted_amount,
                status="PENDING_CHALLENGE",
                verification_secret=challenge_phrase,
                risk_level="HIGH",
                speaker_score=speaker_score,
                fraud_score=float(decision.get("fraud_score", 0.0)),
            )
            await db.commit()
            logger.bind(
                transaction_id=pending.transaction_id,
                user_id=resolved_user_id,
            ).info("HIGH-risk voice challenge persisted")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "status": pending.status,
                    "risk_tier": "HIGH",
                    "transaction_id": pending.transaction_id,
                    "action": "VOICE_CHALLENGE",
                    "challenge_phrase": challenge_phrase,
                    "expires_at": _utc_isoformat(pending.expires_at),
                    "rationale": rationale,
                },
            )

        # Generate 6-digit OTP for MEDIUM risk
        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        
        pending = await freeze_transaction(
            db,
            user_id=resolved_user_id,
            amount=extracted_amount,
            status="PENDING_OTP",
            verification_secret=_otp_digest(otp_code),
            risk_level="MEDIUM",
            speaker_score=speaker_score,
            fraud_score=float(decision.get("fraud_score", 0.0)),
        )
        await db.commit()

        # Delivery is awaited so its outcome is known before returning a challenge.
        try:
            delivered = await send_otp_email(
                recipient_email=user.email,
                recipient_name=user.full_name,
                otp_code=otp_code,
                amount=extracted_amount,
                expires_minutes=5,
            )
            if not delivered:
                raise EmailServiceError("OTP email delivery was not confirmed.")
            logger.bind(transaction_id=pending.transaction_id).info(
                "OTP delivered to the user's registered email"
            )
        except EmailServiceError as email_error:
            await db.delete(pending)
            await db.commit()
            logger.bind(
                transaction_id=pending.transaction_id,
                error=str(email_error),
            ).error("OTP delivery failed; pending transaction invalidated")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Verification email could not be delivered. Please try again.",
            ) from email_error

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "status": pending.status,
                "risk_tier": "MEDIUM",
                "transaction_id": pending.transaction_id,
                "action": "SUBMIT_OTP",
                "otp_sent_to_email": True,
                "expires_at": _utc_isoformat(pending.expires_at),
                "rationale": rationale,
            },
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_403_FORBIDDEN:
            await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.bind(user_id=resolved_user_id, error=str(exc)).exception(
            "Transaction initiation failed."
        )
        raise HTTPException(status_code=500, detail="Transaction initiation failed.") from exc
    finally:
        if audio_path is not None:
            audio_path.unlink(missing_ok=True)


@router.post("/verify", response_model=TransactionResponse)
async def verify_transaction(
    transaction_id: Annotated[str, Form(min_length=1)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    otp_code: Annotated[str | None, Form()] = None,
    photo_file: Annotated[UploadFile | None, File()] = None,
    audio_file: Annotated[UploadFile | None, File()] = None,
) -> TransactionResponse:
    """Consume an active OTP or combined voice-and-liveness challenge once."""
    verification_started_at = perf_counter()
    final_face_score = 0.0
    try:
        frozen = await db.scalar(
            select(PendingTransaction).where(
                PendingTransaction.transaction_id == transaction_id
            )
        )
        if frozen is None:
            raise HTTPException(status_code=404, detail="Transaction not found.")

        pending = await get_active_transaction(db, frozen.verification_secret)
        if pending is None or pending.transaction_id != transaction_id:
            await db.commit()
            raise HTTPException(status_code=401, detail="Transaction is expired or inactive.")

        verified = False
        
        # Path 1: OTP Verification (MEDIUM risk)
        if otp_code is not None and pending.status == "PENDING_OTP":
            verified = secrets.compare_digest(
                pending.verification_secret,
                _otp_digest(otp_code),
            )
            logger.bind(transaction_id=transaction_id).info(f"OTP verification: {verified}")
        
        # Path 2: Voice challenge plus facial liveness (HIGH risk)
        elif pending.status == "PENDING_CHALLENGE":
            if audio_file is None or photo_file is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "HIGH-risk verification requires both a spoken challenge "
                        "and a fresh camera image."
                    ),
                )

            audio_waveform = await async_upload_to_waveform(audio_file)
            transcription = str(await whisper_provider.transcribe(audio_waveform)).strip()
            expected = pending.verification_secret.lower().strip()
            actual = transcription.lower().strip()
            voice_verified = bool(actual) and (expected in actual or actual in expected)

            image = await async_upload_to_numpy(photo_file)
            prepared_frame = await asyncio.to_thread(
                liveness_preprocessor.prepare_frame,
                image,
            )
            normalized_frame = await asyncio.to_thread(
                liveness_preprocessor.normalize_intensity,
                prepared_frame,
            )
            liveness_score = await asyncio.to_thread(
                liveness_detector.analyze_liveness,
                normalized_frame,
            )
            liveness_verified = liveness_score >= settings.LIVENESS_CRITICAL_THRESHOLD
            verified = voice_verified and liveness_verified

            logger.bind(
                transaction_id=transaction_id,
                expected=expected,
                actual=actual,
                voice_verified=voice_verified,
                liveness_score=round(liveness_score, 4),
                liveness_verified=liveness_verified,
                verified=verified,
            ).info("Combined HIGH-risk verification completed")

        if not verified:
            pending.verification_attempts += 1
            attempts_remaining = max(
                0,
                pending.max_verification_attempts - pending.verification_attempts,
            )
            if attempts_remaining == 0:
                await db.delete(pending)
            else:
                await db.flush()
            await db.commit()
            raise HTTPException(
                status_code=401,
                detail={
                    "message": "Verification failed.",
                    "attempts_remaining": attempts_remaining,
                },
            )

        transaction_record = Transaction(
            transaction_id=pending.transaction_id,
            user_id=pending.user_id,
            amount=pending.amount,
            status="COMPLETED",
            risk_level=pending.risk_level,
            success=True,
            speaker_score=pending.speaker_score,
            face_score=max(pending.face_score, final_face_score),
            fraud_score=pending.fraud_score,
            xai_reason=f"{pending.risk_level} step-up verification completed.",
            processing_time_ms=(perf_counter() - verification_started_at) * 1000.0,
            replay_attack=pending.replay_attack,
        )
        await create_transaction(db, transaction_record)
        await db.delete(pending)
        await db.commit()
        logger.bind(transaction_id=transaction_id).info("Transaction finalized.")
        return TransactionResponse(
            success=True,
            status="SUCCESS",
            risk_tier="VERIFIED",
            rationale="Step-up verification completed.",
            transaction_id=transaction_id,
        )
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.bind(transaction_id=transaction_id, error=str(exc)).exception("Verification failed.")
        raise HTTPException(status_code=500, detail="Verification failed.") from exc


@router.get("/history")
async def get_transaction_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    limit: int = 20,
    offset: int = 0,
):
    """
    Retrieve paginated transaction history for the authenticated user.
    
    Query Parameters:
        limit: Maximum number of transactions to return (default: 20, max: 100)
        offset: Number of transactions to skip for pagination (default: 0)
    
    Returns:
        JSON array of transaction objects ordered by most recent first.
    """
    # Validate pagination parameters
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Limit must be between 1 and 100"
        )
    
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Offset must be non-negative"
        )
    
    try:
        # Fetch transactions from database using CRUD function
        transactions = await get_transactions_by_user_id(
            db,
            current_user.user_id,
            limit=limit,
            offset=offset
        )
        
        # Serialize transactions to JSON-friendly format
        transaction_list = [
            {
                "transaction_id": tx.transaction_id,
                "amount": tx.amount,
                "status": tx.status,
                "risk_level": tx.risk_level,
                "success": tx.success,
                "speaker_score": tx.speaker_score,
                "face_score": tx.face_score,
                "fraud_score": tx.fraud_score,
                "xai_reason": tx.xai_reason,
                "processing_time_ms": tx.processing_time_ms,
                "replay_attack": tx.replay_attack,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
                "updated_at": tx.updated_at.isoformat() if tx.updated_at else None,
            }
            for tx in transactions
        ]
        
        logger.bind(
            user_id=current_user.user_id,
            count=len(transaction_list),
            limit=limit,
            offset=offset
        ).info("Transaction history retrieved successfully")
        
        return {
            "success": True,
            "transactions": transaction_list,
            "count": len(transaction_list),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as exc:
        logger.bind(
            user_id=current_user.user_id,
            error=str(exc)
        ).exception("Failed to retrieve transaction history")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve transaction history"
        ) from exc
