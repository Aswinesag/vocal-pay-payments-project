"""User biometric enrollment endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from loguru import logger
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.converters import async_upload_to_numpy, async_upload_to_waveform
from app.core.vector_index import voiceprint_index
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

    status: str
    user_id: str
    message: str


@router.post(
    "/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_user(
    audio_file: Annotated[UploadFile, File()],
    photo_file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> EnrollmentResponse:
    """Attach biometric embeddings to the authenticated signup record."""
    user_id = current_user.user_id
    try:
        audio_content = await audio_file.read()
        photo_content = await photo_file.read()
        if not audio_content:
            raise ValueError("Audio upload cannot be empty.")
        if not photo_content:
            raise ValueError("Photo upload cannot be empty.")
        await audio_file.seek(0)
        await photo_file.seek(0)

        waveform = await async_upload_to_waveform(audio_file)
        image = await async_upload_to_numpy(photo_file)

        face_provider = get_face_verification_provider()
        face_result = await face_provider.extract_embedding(image=image)
        pure_face_list = [float(val) for val in getattr(face_result, "flatten", lambda: face_result)()]

        voice_provider = get_speaker_verification_provider()
        voice_result = await voice_provider.extract_embedding(waveform)
        pure_voice_list = [float(val) for val in getattr(voice_result, "flatten", lambda: voice_result)()]
        if not pure_face_list or not pure_voice_list:
            raise ValueError("Biometric provider returned an empty embedding.")

        current_user.speaker_embedding = pure_voice_list
        current_user.face_embedding = pure_face_list
        current_user.is_verified = True
        try:
            await db.commit()
            await db.refresh(current_user)
        except Exception as exc:
            await db.rollback()
            logger.bind(
                user_id=user_id,
                error=str(exc),
            ).error(
                "Enrollment commit failed."
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Enrollment database serialization or commit failed.",
            ) from exc

        try:
            await voiceprint_index.rebuild_index(db)
        except Exception as exc:
            logger.bind(user_id=user_id, error=str(exc)).warning(
                "Biometric enrollment succeeded, but the voice index refresh failed."
            )

        logger.bind(
            user_id=user_id,
            face_dimensions=len(pure_face_list),
            speaker_dimensions=len(pure_voice_list),
        ).info("User biometric enrollment completed.")

        return EnrollmentResponse(
            status="SUCCESS",
            user_id=user_id,
            message="Biometric card identity generated.",
        )
    except HTTPException:
        await db.rollback()
        raise
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
