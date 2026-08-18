"""Conditional two-step transaction state-machine endpoints."""

from __future__ import annotations

import secrets
import re
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Annotated, Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from loguru import logger
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audio_dsp import detect_replay_attack
from app.core.config import settings
from app.core.converters import async_upload_to_numpy, async_upload_to_waveform
from app.core.vector_index import search_voiceprint, VoiceprintIndexError
from app.database.crud import create_transaction, freeze_transaction, get_active_transaction, get_transactions_by_user_id, invalidate_transaction
from app.database.database import get_async_db
from app.database.models import PendingTransaction, Transaction, User
from app.services.ollama_service import OllamaService
from app.services.providers.provider_factory import (
    BiometricInferenceProxy,
    get_face_verification_provider,
    get_speaker_verification_provider,
)
from app.services.whisper_service import WhisperService
from app.api.v1.endpoints.auth import get_current_user


router = APIRouter(prefix="/transactions", tags=["transactions"])
ollama_service = OllamaService()


class _FasterWhisperProxyAdapter:
    """Expose the Faster-Whisper service through the inference proxy contract."""

    name = "FasterWhisper"

    def transcribe(self, waveform: np.ndarray) -> str:
        """Transcribe one waveform using the existing ASR service."""
        service = WhisperService()
        try:
            return service.transcribe_audio(waveform)
        finally:
            service.release_model()


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
            )
            logger.info(
                f"🔐 SECURITY STEP-UP ACTIVATED: Generated voice challenge phrase "
                f"for HIGH-risk transaction: {challenge_phrase}"
            )
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
                    "expires_at": pending.expires_at.isoformat(),
                    "rationale": "Transaction amount requires mandatory voice challenge verification.",
                },
            )

        decision = await ollama_service.evaluate_transaction_context(
            amount=extracted_amount,
            speaker_score=speaker_score,
            face_score=0.0,
            liveness_score=0.0,
            is_replay=False,
        )
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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"risk_tier": "CRITICAL", "status": "BLOCKED"},
            )

        # Generate 6-digit OTP for MEDIUM risk
        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        
        # Determine status based on risk tier
        status_value = "PENDING_OTP" if risk_tier == "MEDIUM" else "PENDING_VERIFICATION"
        
        pending = await freeze_transaction(
            db,
            user_id=resolved_user_id,
            amount=extracted_amount,
            status=status_value,
            verification_secret=otp_code,
        )
        logger.info(
            f"🔐 SECURITY STEP-UP ACTIVATED ({risk_tier}): Generated OTP {otp_code} "
            f"for user {user.email}"
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "status": pending.status,
                "risk_tier": risk_tier,
                "transaction_id": pending.transaction_id,
                "action": "SUBMIT_OTP" if risk_tier == "MEDIUM" else "SUBMIT_VERIFICATION",
                "otp_code": otp_code if risk_tier == "MEDIUM" else None,  # Include OTP in response (in production, send via email/SMS)
                "expires_at": pending.expires_at.isoformat(),
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
    """Consume an active OTP, voice challenge, or biometric challenge exactly once."""
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
            raise HTTPException(status_code=401, detail="Transaction is expired or inactive.")

        verified = False
        
        # Path 1: OTP Verification (MEDIUM risk)
        if otp_code is not None:
            verified = secrets.compare_digest(pending.verification_secret, otp_code)
            logger.bind(transaction_id=transaction_id).info(f"OTP verification: {verified}")
        
        # Path 2: Voice Challenge Verification (HIGH risk)
        elif audio_file is not None:
            audio_waveform = await async_upload_to_waveform(audio_file)
            transcription = str(await whisper_provider.transcribe(audio_waveform)).strip()
            
            # Compare transcription to challenge secret (case-insensitive, fuzzy match)
            expected = pending.verification_secret.lower().strip()
            actual = transcription.lower().strip()
            
            # Simple fuzzy matching (can be enhanced with Levenshtein distance)
            verified = expected in actual or actual in expected
            
            logger.bind(
                transaction_id=transaction_id,
                expected=expected,
                actual=actual,
                verified=verified
            ).info("Voice challenge verification completed")
        
        # Path 3: Face Verification (alternative to voice)
        elif photo_file is not None:
            image = await async_upload_to_numpy(photo_file)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            brightness = float(np.mean(gray))
            liveness_score = min(1.0, sharpness / 150.0) if 25.0 <= brightness <= 230.0 else 0.0
            if liveness_score >= settings.LIVENESS_CRITICAL_THRESHOLD:
                user = await db.scalar(select(User).where(User.user_id == pending.user_id))
                if user is None:
                    raise HTTPException(status_code=404, detail="User not found.")
                face_provider = get_face_verification_provider()
                try:
                    live_embedding = await face_provider.extract_embedding(image=image)
                except ValueError as exc:
                    logger.bind(transaction_id=transaction_id).warning(
                        "Step-up verification denied because no face was detected."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Face verification failed: no face detected.",
                    ) from exc
                face_result: Any = await face_provider.verify_face(
                    enrolled_embedding=user.face_embedding,
                    live_embedding=live_embedding,
                )
                verified = bool(face_result.verified)

        if not verified:
            raise HTTPException(status_code=401, detail="Verification failed.")

        await invalidate_transaction(db, pending)
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
