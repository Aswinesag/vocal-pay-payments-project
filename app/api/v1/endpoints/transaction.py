"""Conditional two-step transaction state-machine endpoints."""

from __future__ import annotations

import secrets
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Any

import cv2
import numpy as np
import torch
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from loguru import logger
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audio_dsp import detect_replay_attack
from app.core.config import settings
from app.core.converters import async_upload_to_numpy, async_upload_to_waveform
from app.database.crud import freeze_transaction, get_active_transaction, invalidate_transaction
from app.database.database import get_async_db
from app.database.models import PendingTransaction, User
from app.services.ollama_service import OllamaService
from app.services.providers.provider_factory import (
    get_face_verification_provider,
    get_speaker_verification_provider,
)


router = APIRouter(prefix="/transactions", tags=["transactions"])
ollama_service = OllamaService()


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
    user_id: Annotated[str, Form(min_length=1)],
    amount: Annotated[float, Form(gt=0)],
    audio_file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> TransactionResponse:
    """Run DSP and voice risk gates before approval or step-up freezing."""
    audio_path: Path | None = None
    try:
        audio_bytes = await audio_file.read()
        if not audio_bytes:
            raise HTTPException(status_code=422, detail="Audio file is empty.")
        suffix = Path(audio_file.filename or "voice.wav").suffix or ".wav"
        with NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary.write(audio_bytes)
            audio_path = Path(temporary.name)

        if detect_replay_attack(str(audio_path)):
            logger.bind(user_id=user_id).warning("DSP replay gate blocked transaction.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"risk_tier": "CRITICAL", "status": "BLOCKED"},
            )

        user = await db.scalar(select(User).where(User.user_id == user_id))
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        await audio_file.seek(0)
        waveform = await async_upload_to_waveform(audio_file)
        voice_provider = get_speaker_verification_provider()
        live_embedding = await voice_provider.extract_embedding(
            torch.from_numpy(waveform).unsqueeze(0)
        )
        voice_result: Any = await voice_provider.verify_speaker(
            enrolled_embedding=user.speaker_embedding,
            live_embedding=live_embedding,
        )
        speaker_score = float(voice_result.confidence)

        decision = await ollama_service.evaluate_transaction_context(
            amount=amount,
            speaker_score=speaker_score,
            face_score=1.0,
            liveness_score=1.0,
            is_replay=False,
        )
        risk_tier = str(decision["risk_tier"])
        rationale = str(decision["explainable_ai_rationale"])

        if risk_tier == "LOW":
            return TransactionResponse(
                success=True,
                status="SUCCESS",
                risk_tier=risk_tier,
                rationale=rationale,
            )
        if risk_tier not in {"MEDIUM", "HIGH"}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"risk_tier": "CRITICAL", "status": "BLOCKED"},
            )

        verification_secret = f"{secrets.randbelow(1_000_000):06d}"
        pending = await freeze_transaction(
            db,
            user_id=user_id,
            amount=amount,
            status="PENDING_VERIFICATION",
            verification_secret=verification_secret,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "status": pending.status,
                "risk_tier": risk_tier,
                "transaction_id": pending.transaction_id,
                "action": "SUBMIT_OTP_OR_FACE_VERIFICATION",
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
        logger.bind(user_id=user_id, error=str(exc)).exception("Transaction initiation failed.")
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
) -> TransactionResponse:
    """Consume an active OTP or biometric challenge exactly once."""
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
        if otp_code is not None:
            verified = secrets.compare_digest(pending.verification_secret, otp_code)
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
                live_embedding = await face_provider.extract_embedding(image=image)
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
