"""In-memory converters for uploaded biometric media."""

from __future__ import annotations

from io import BytesIO

import av
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

    try:
        waveform, _sample_rate = librosa.load(
            BytesIO(payload),
            sr=16_000,
            mono=True,
            dtype=np.float32,
        )
    except Exception:
        waveform = _decode_compressed_audio(payload)
    waveform = np.asarray(waveform, dtype=np.float32)
    if waveform.ndim != 1 or waveform.size == 0:
        raise ValueError("Uploaded audio could not be decoded.")
    if not np.isfinite(waveform).all():
        raise ValueError("Uploaded audio contains non-finite samples.")

    return np.ascontiguousarray(waveform)


def _decode_compressed_audio(payload: bytes) -> np.ndarray:
    """Decode browser media containers such as WebM entirely in memory."""
    chunks: list[np.ndarray] = []
    try:
        with av.open(BytesIO(payload), mode="r") as container:
            if not container.streams.audio:
                raise ValueError("Uploaded media does not contain an audio stream.")

            resampler = av.AudioResampler(format="flt", layout="mono", rate=16_000)
            for frame in container.decode(audio=0):
                for resampled in resampler.resample(frame):
                    chunks.append(
                        np.asarray(resampled.to_ndarray(), dtype=np.float32).reshape(-1)
                    )
            for resampled in resampler.resample(None):
                chunks.append(
                    np.asarray(resampled.to_ndarray(), dtype=np.float32).reshape(-1)
                )
    except (ValueError, av.error.FFmpegError) as exc:
        raise ValueError("Uploaded audio format could not be decoded.") from exc

    if not chunks:
        raise ValueError("Uploaded audio format could not be decoded.")
    return np.concatenate(chunks).astype(np.float32, copy=False)
