"""User biometric enrollment endpoint."""

from __future__ import annotations

from typing import Annotated

import numpy as np
import torch
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from loguru import logger
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.converters import async_upload_to_numpy, async_upload_to_waveform
from app.database.database import get_async_db
from app.database.models import User
from app.services.providers.provider_factory import (
    get_face_verification_provider,
    get_speaker_verification_provider,
)


router = APIRouter(prefix="/users", tags=["users"])


class EnrollmentResponse(BaseModel):
    """Public result of a completed biometric enrollment."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    user_id: str
    face_embedding_dimensions: int
    speaker_embedding_dimensions: int


@router.post(
    "/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_user(
    user_id: Annotated[str, Form(min_length=3, max_length=64)],
    full_name: Annotated[str, Form(min_length=2, max_length=120)],
    email: Annotated[EmailStr, Form()],
    phone_number: Annotated[str, Form(min_length=10, max_length=20)],
    audio_file: Annotated[UploadFile, File()],
    photo_file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> EnrollmentResponse:
    """Enroll one user with face and speaker biometric embeddings."""
    try:
        duplicate = await db.scalar(
            select(User.id).where(
                (User.user_id == user_id)
                | (User.email == str(email))
                | (User.phone_number == phone_number)
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User ID, email, or phone number is already enrolled.",
            )

        waveform = await async_upload_to_waveform(audio_file)
        image = await async_upload_to_numpy(photo_file)

        face_provider = get_face_verification_provider()
        face_embedding_raw = await face_provider.extract_embedding(image=image)
        face_embedding = np.asarray(
            face_embedding_raw,
            dtype=np.float32,
        ).reshape(-1)

        voice_provider = get_speaker_verification_provider()
        voice_tensor = torch.from_numpy(waveform).unsqueeze(0)
        voice_embedding_raw = await voice_provider.extract_embedding(voice_tensor)
        if isinstance(voice_embedding_raw, torch.Tensor):
            speaker_embedding = (
                voice_embedding_raw.detach().cpu().float().reshape(-1).tolist()
            )
        else:
            speaker_embedding = np.asarray(
                voice_embedding_raw,
                dtype=np.float32,
            ).reshape(-1).tolist()

        face_embedding_list = face_embedding.tolist()
        if not face_embedding_list or not speaker_embedding:
            raise ValueError("Biometric provider returned an empty embedding.")

        user = User(
            user_id=user_id,
            full_name=full_name,
            email=str(email),
            phone_number=phone_number,
            speaker_embedding=speaker_embedding,
            face_embedding=face_embedding_list,
            is_active=True,
            is_verified=True,
            failed_attempts=0,
            preferred_language="en",
        )
        db.add(user)
        await db.commit()

        logger.bind(
            user_id=user_id,
            face_dimensions=len(face_embedding_list),
            speaker_dimensions=len(speaker_embedding),
        ).info("User biometric enrollment completed.")

        return EnrollmentResponse(
            success=True,
            user_id=user_id,
            face_embedding_dimensions=len(face_embedding_list),
            speaker_embedding_dimensions=len(speaker_embedding),
        )
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError as exc:
        await db.rollback()
        logger.bind(user_id=user_id).warning(
            "Enrollment rejected by a unique database constraint."
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User ID, email, or phone number is already enrolled.",
        ) from exc
    except ValueError as exc:
        await db.rollback()
        logger.bind(user_id=user_id, error=str(exc)).warning(
            "User enrollment input was rejected."
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        await db.rollback()
        logger.bind(user_id=user_id, error=str(exc)).exception(
            "User biometric enrollment failed."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User enrollment failed.",
        ) from exc
