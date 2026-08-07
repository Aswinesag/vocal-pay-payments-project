"""In-memory converters for uploaded biometric media."""

from __future__ import annotations

from io import BytesIO

import cv2
import librosa
import numpy as np
from fastapi import UploadFile


async def async_upload_to_numpy(file: UploadFile) -> np.ndarray:
    """Decode an uploaded image into a validated OpenCV BGR matrix."""
    payload = await file.read()
    if not payload:
        raise ValueError("Uploaded image is empty.")

    encoded = np.frombuffer(payload, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ValueError("Uploaded image could not be decoded.")

    return np.ascontiguousarray(image)


async def async_upload_to_waveform(file: UploadFile) -> np.ndarray:
    """Decode uploaded audio into a mono 16 kHz float32 waveform."""
    payload = await file.read()
    if not payload:
        raise ValueError("Uploaded audio is empty.")

    waveform, _sample_rate = librosa.load(
        BytesIO(payload),
        sr=16_000,
        mono=True,
        dtype=np.float32,
    )
    waveform = np.asarray(waveform, dtype=np.float32)
    if waveform.ndim != 1 or waveform.size == 0:
        raise ValueError("Uploaded audio could not be decoded.")
    if not np.isfinite(waveform).all():
        raise ValueError("Uploaded audio contains non-finite samples.")

    return np.ascontiguousarray(waveform)
