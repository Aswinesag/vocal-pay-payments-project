"""Standalone hardware-assisted biometric enrollment client."""

from __future__ import annotations

import asyncio
from pathlib import Path

import cv2
import httpx
import sounddevice as sd
from scipy.io import wavfile


ENROLLMENT_URL = "http://127.0.0.1:8000/api/v1/users/enroll"
FACE_PATH = Path("temp_enroll_face.jpg")
VOICE_PATH = Path("temp_enroll_voice.wav")
SAMPLE_RATE = 16_000
RECORDING_SECONDS = 5


async def enroll_biometric_profile() -> None:
    """Capture local biometric samples and submit one enrollment request."""
    print("[1/3] Opening the default webcam...")
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError("Unable to open the default webcam.")

    try:
        captured, frame = camera.read()
        if not captured or frame is None or frame.size == 0:
            raise RuntimeError("Unable to capture a valid webcam frame.")
        if not cv2.imwrite(str(FACE_PATH), frame):
            raise RuntimeError("Unable to save the enrollment face image.")
        print(f"      Face snapshot saved to {FACE_PATH}.")
    finally:
        camera.release()
        print("      Webcam released.")

    print("[2/3] Recording five seconds of enrollment speech...")
    recording = sd.rec(
        int(RECORDING_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    wavfile.write(VOICE_PATH, SAMPLE_RATE, recording)
    print(f"      Voice recording saved to {VOICE_PATH}.")

    print(f"[3/3] Submitting enrollment to {ENROLLMENT_URL}...")
    metadata = {
        "user_id": "real_human_01",
        "full_name": "Aswin",
        "email": "aswin@vocalpay.com",
        "phone_number": "+1999888888",
    }

    with FACE_PATH.open("rb") as photo_stream, VOICE_PATH.open("rb") as audio_stream:
        files = {
            "photo_file": (FACE_PATH.name, photo_stream, "image/jpeg"),
            "audio_file": (VOICE_PATH.name, audio_stream, "audio/wav"),
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                ENROLLMENT_URL,
                data=metadata,
                files=files,
            )

    print("      Local enrollment file streams closed.")
    print(f"      Server response: HTTP {response.status_code}")
    print(f"      Response body: {response.text}")
    response.raise_for_status()
    print("Enrollment completed successfully.")


if __name__ == "__main__":
    asyncio.run(enroll_biometric_profile())
