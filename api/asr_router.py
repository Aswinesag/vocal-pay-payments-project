import io
from fastapi import APIRouter, UploadFile, File, HTTPException
import numpy as np
import soundfile as sf
import traceback

from schemas.audio import AudioTranscriptionResponse
from services.whisper_service import WhisperService

router = APIRouter()
whisper_service = WhisperService()


@router.post("/transcribe", response_model=AudioTranscriptionResponse)
async def transcribe_audio(user_id: str, file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()
        audio_np, sample_rate = sf.read(io.BytesIO(audio_bytes))

        if sample_rate < 8000:
            raise HTTPException(status_code=400, detail="Sample rate too low")

        transcription, confidence, processing_time = await whisper_service.transcribe(
            audio_np=audio_np,
            sample_rate=sample_rate
        )

        return AudioTranscriptionResponse(
            user_id=user_id,
            transcription=transcription,
            confidence=confidence,
            processing_time_ms=processing_time
        )

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
    )