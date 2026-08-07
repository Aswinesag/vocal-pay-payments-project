"""Two-step transaction state-machine endpoints."""

from __future__ import annotations

import secrets
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Any

import cv2
import numpy as np
import torch
import torchaudio
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from loguru import logger
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audio_dsp import detect_replay_attack
from app.database.crud import (
    freeze_transaction,
    get_active_transaction,
    invalidate_transaction,
)
from app.database.database import get_async_db
from app.database.models import User
from app.services.ollama_service import OllamaService
from app.services.providers.provider_factory import (
    get_face_verification_provider,
    get_speaker_verification_provider,
)


router = APIRouter(prefix="/transactions", tags=["transactions"])
ollama_service = OllamaService()


class TransactionStateResponse(BaseModel):
    """Serialized transaction state returned by both state-machine steps."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    status: str
    risk_tier: str
    explainable_ai_rationale: str
    transaction_id: str | None = None
    expires_at: str | None = None


@router.post(
    "/initiate",
    response_model=TransactionStateResponse,
)
async def initiate_transaction(
    user_id: Annotated[str, Form(min_length=1)],
    amount: Annotated[float, Form(gt=0)],
    audio_file: Annotated[UploadFile, File()],
    photo_file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> TransactionStateResponse:
    """Run the sequential transaction gate and freeze step-up state if needed."""
    audio_path: Path | None = None
    try:
        audio_bytes = await audio_file.read()
        if not audio_bytes:
            raise HTTPException(status_code=422, detail="Audio file is empty.")

        suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
        with NamedTemporaryFile(delete=False, suffix=suffix) as temporary_audio:
            temporary_audio.write(audio_bytes)
            audio_path = Path(temporary_audio.name)

        logger.bind(user_id=user_id).info("Transaction DSP gate started.")
        if detect_replay_attack(str(audio_path)):
            logger.bind(user_id=user_id).warning("Replay attack blocked at DSP gate.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "success": False,
                    "status": "BLOCKED",
                    "risk_tier": "CRITICAL",
                    "explainable_ai_rationale": "Audio replay signature detected.",
                },
            )

        user = await db.scalar(select(User).where(User.user_id == user_id))
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        photo_bytes = await photo_file.read()
        image = cv2.imdecode(
            np.frombuffer(photo_bytes, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        if image is None:
            raise HTTPException(status_code=422, detail="Photo file is invalid.")

        face_provider = get_face_verification_provider()
        voice_provider = get_speaker_verification_provider()

        live_face_embedding = await face_provider.extract_embedding(image=image)
        face_result: Any = await face_provider.verify_face(
            enrolled_embedding=user.face_embedding,
            live_embedding=live_face_embedding,
        )

        waveform, _sample_rate = torchaudio.load(str(audio_path))
        mono_waveform: torch.Tensor = waveform.mean(dim=0, keepdim=True)
        live_voice_embedding = await voice_provider.extract_embedding(mono_waveform)
        voice_result: Any = await voice_provider.verify_speaker(
            enrolled_embedding=user.speaker_embedding,
            live_embedding=live_voice_embedding,
        )

        face_score = float(face_result.confidence)
        speaker_score = float(voice_result.confidence)
        liveness_score = 1.0 if bool(face_result.liveness_checked) else 0.0

        decision = await ollama_service.evaluate_transaction_context(
            amount=amount,
            speaker_score=speaker_score,
            face_score=face_score,
            liveness_score=liveness_score,
            is_replay=False,
        )
        risk_tier = str(decision["risk_tier"])
        rationale = str(decision["explainable_ai_rationale"])

        if risk_tier == "LOW":
            return TransactionStateResponse(
                success=True,
                status="SUCCESS",
                risk_tier=risk_tier,
                explainable_ai_rationale=rationale,
            )

        if risk_tier in {"MEDIUM", "HIGH"}:
            verification_secret = f"{secrets.randbelow(1_000_000):06d}"
            pending = await freeze_transaction(
                db,
                user_id=user_id,
                amount=amount,
                status="PENDING_VERIFICATION",
                verification_secret=verification_secret,
            )
            await db.commit()
            return TransactionStateResponse(
                success=False,
                status="PENDING_VERIFICATION",
                risk_tier=risk_tier,
                explainable_ai_rationale=rationale,
                transaction_id=pending.transaction_id,
                expires_at=pending.expires_at.isoformat(),
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "status": "BLOCKED",
                "risk_tier": "CRITICAL",
                "explainable_ai_rationale": rationale,
            },
        )
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.bind(user_id=user_id, error=str(exc)).exception(
            "Transaction initiation failed."
        )
        raise HTTPException(status_code=500, detail="Transaction initiation failed.") from exc
    finally:
        if audio_path is not None:
            audio_path.unlink(missing_ok=True)


@router.post(
    "/verify",
    response_model=TransactionStateResponse,
)
async def verify_transaction(
    transaction_id: Annotated[str, Form(min_length=1)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    otp_code: Annotated[str | None, Form()] = None,
) -> TransactionStateResponse:
    """Consume an active step-up token exactly once."""
    try:
        pending = await get_active_transaction(db, otp_code or transaction_id)
        if pending is None or pending.transaction_id != transaction_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired transaction verification.",
            )
        if otp_code is None or not secrets.compare_digest(
            pending.verification_secret,
            otp_code,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid transaction verification code.",
            )

        await invalidate_transaction(db, pending)
        await db.commit()
        logger.bind(transaction_id=transaction_id).info(
            "Transaction verification completed and token invalidated."
        )
        return TransactionStateResponse(
            success=True,
            status="SUCCESS",
            risk_tier="VERIFIED",
            explainable_ai_rationale="Step-up verification completed.",
            transaction_id=transaction_id,
        )
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.bind(transaction_id=transaction_id, error=str(exc)).exception(
            "Transaction verification failed."
        )
        raise HTTPException(status_code=500, detail="Transaction verification failed.") from exc
