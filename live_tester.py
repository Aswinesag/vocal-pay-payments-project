"""Standalone live hardware client for the VocalPay transaction state machine."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import cv2
import httpx
import sounddevice as sd
from scipy.io import wavfile


INITIATE_URL = "http://127.0.0.1:8000/api/v1/transactions/initiate"
VERIFY_URL = "http://127.0.0.1:8000/api/v1/transactions/verify"
VOICE_PATH = Path("temp_checkout_voice.wav")
FACE_PATH = Path("temp_checkout_face.jpg")
SAMPLE_RATE = 16_000
RECORDING_SECONDS = 4
STEP_UP_STATUSES = {"PENDING_CHALLENGE", "PENDING_VERIFICATION"}


async def run_live_transaction() -> None:
    """Execute checkout initiation and conditional webcam verification."""
    print(
        "🎙️ CONVERSATIONAL BANKING CHANNEL ACTIVE: Press Enter and speak your "
        "checkout authorization naturally (e.g., 'Authorize transaction for 750 "
        "dollars')."
    )
    input()
    print("🎙️ Preparing audio driver... Release the key and get ready.")
    time.sleep(0.5)
    print("🔴 RECORDING NOW... Speak clearly into your microphone!")
    recording = sd.rec(
        int(RECORDING_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    wavfile.write(VOICE_PATH, SAMPLE_RATE, recording)
    print(f"Voice authorization saved to {VOICE_PATH}.")

    async with httpx.AsyncClient(timeout=180.0) as client:
        print("Submitting checkout initiation request...")
        with VOICE_PATH.open("rb") as audio_stream:
            initiate_response = await client.post(
                INITIATE_URL,
                files={
                    "audio_file": (
                        VOICE_PATH.name,
                        audio_stream,
                        "audio/wav",
                    )
                },
            )

        print(f"Initiation response: HTTP {initiate_response.status_code}")
        print(initiate_response.text)

        if initiate_response.status_code == httpx.codes.OK:
            print("Transaction auto-approved. Webcam verification was not required.")
            return

        if initiate_response.status_code == httpx.codes.NOT_FOUND:
            print(
                "🚫 VOICE IDENTITY MISMATCH: Your live voice did not match any "
                "enrolled biometric profile. Transaction denied."
            )
            return

        if initiate_response.status_code != httpx.codes.FORBIDDEN:
            try:
                initiate_response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == httpx.codes.UNAUTHORIZED:
                    try:
                        blocked_payload = exc.response.json()
                    except ValueError:
                        blocked_payload = {}
                    if isinstance(blocked_payload, dict):
                        print(
                            "🚨 TRANSACTION HARD-BLOCKED: CPU-bound DSP Gate "
                            "intercepted a Critical Voice Replay signature. "
                            "Access Denied."
                        )
                        return
                raise
            raise RuntimeError("Unexpected transaction initiation response.")

        response_payload = initiate_response.json()
        detail = response_payload.get("detail", response_payload)
        if not isinstance(detail, dict):
            raise RuntimeError("Step-up response did not contain a data dictionary.")

        pending_status = detail.get("status")
        transaction_id = detail.get("transaction_id")
        if pending_status not in STEP_UP_STATUSES:
            raise RuntimeError(f"Unexpected step-up status: {pending_status!r}")
        if not isinstance(transaction_id, str) or not transaction_id:
            raise RuntimeError("Step-up response did not contain a transaction ID.")

        print(f"Step-up authentication required for {transaction_id}.")
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            camera.release()
            raise RuntimeError("Unable to open the default webcam.")

        try:
            captured, frame = camera.read()
            if not captured or frame is None or frame.size == 0:
                raise RuntimeError("Unable to capture a valid webcam frame.")
            if not cv2.imwrite(str(FACE_PATH), frame):
                raise RuntimeError("Unable to save the step-up face image.")
        finally:
            camera.release()
            print("Webcam released.")

        print("Submitting webcam step-up verification...")
        with FACE_PATH.open("rb") as photo_stream:
            verify_response = await client.post(
                VERIFY_URL,
                data={"transaction_id": transaction_id},
                files={
                    "photo_file": (
                        FACE_PATH.name,
                        photo_stream,
                        "image/jpeg",
                    )
                },
            )

        print(f"Verification response: HTTP {verify_response.status_code}")
        print(verify_response.text)
        if verify_response.status_code == httpx.codes.UNAUTHORIZED:
            print(
                "🚨 STEP-UP VERIFICATION DENIED: No valid matching face was "
                "detected. The transaction remains incomplete."
            )
            return
        verify_response.raise_for_status()
        print("Transaction finalized successfully after webcam verification.")


if __name__ == "__main__":
    asyncio.run(run_live_transaction())
