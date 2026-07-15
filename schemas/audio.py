from pydantic import BaseModel, Field
from typing import Optional


class AudioTranscriptionRequest(BaseModel):
    sample_rate: int = Field(..., gt=0)
    language: Optional[str] = Field(default="en")
    user_id: str


class AudioTranscriptionResponse(BaseModel):
    user_id: str
    transcription: str
    confidence: float
    processing_time_ms: float