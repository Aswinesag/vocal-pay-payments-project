import time
import torch
import whisper
import numpy as np
from typing import Tuple


class WhisperService:
    _instance = None

    def __new__(cls, model_size: str = "base"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_model(model_size)
        return cls._instance

    def _init_model(self, model_size: str):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = whisper.load_model(model_size, device=self.device)

    async def transcribe(
        self,
        audio_np: np.ndarray,
        sample_rate: int,
        language: str = "en"
    ) -> Tuple[str, float, float]:
        
        start_time = time.time()

        if audio_np.ndim != 1:
            raise ValueError("Audio must be mono channel")

        # Normalize audio
        audio_np = audio_np.astype(np.float32)
        audio_np /= np.max(np.abs(audio_np) + 1e-9)

        result = self.model.transcribe(
            audio_np,
            language=language,
            fp16=(self.device == "cuda")
        )
        print(result)

        transcription = result["text"].strip()
        segments = result.get("segments", [])

        if not segments:
            confidence = 0.0
        else:
            confidence = float(np.mean([float(segment.get("avg_logprob", 0.0)) for segment in segments]))

        processing_time = (time.time() - start_time) * 1000

        return transcription, confidence, processing_time