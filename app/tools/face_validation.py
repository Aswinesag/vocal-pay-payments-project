"""Manual real-camera validation utility for the configured face provider."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np

from app.core.logger import EnterpriseLogger, get_logger
from app.services.face_service import FaceDetection, FaceProviderError
from app.services.providers import (
    get_face_verification_provider,
    shutdown_face_verification_providers,
)


VALIDATION_COMPONENT: Final[str] = "FACE_VALIDATION"
WINDOW_NAME: Final[str] = "VocalPay - Live Face Validation"
DEFAULT_CAMERA_INDEX: Final[int] = 0
STABILITY_WINDOW_SIZE: Final[int] = 20

logger: Final[EnterpriseLogger] = get_logger(VALIDATION_COMPONENT)


@dataclass(frozen=True, slots=True)
class _EmbeddingDiagnostics:
    """Display-safe metadata derived from one live embedding."""

    shape: tuple[int, ...]
    dtype: str
    norm: float
    first_values: tuple[float, ...]
    stability: float | None


def _calculate_embedding_diagnostics(
    embedding: object,
    history: deque[np.ndarray],
) -> _EmbeddingDiagnostics:
    """Calculate non-persistent embedding diagnostics and stability."""

    array = np.asarray(embedding, dtype=np.float32).reshape(-1)
    if array.size == 0:
        raise FaceProviderError("Extracted face embedding is empty.")

    norm = float(np.linalg.norm(array))
    if norm == 0.0:
        raise FaceProviderError("Extracted face embedding has zero norm.")

    normalized = array / norm
    stability: float | None = None
    if history:
        stability = float(
            np.mean(
                [
                    np.clip(np.dot(previous, normalized), -1.0, 1.0)
                    for previous in history
                ]
            )
        )
    history.append(normalized)

    return _EmbeddingDiagnostics(
        shape=tuple(np.asarray(embedding).shape),
        dtype=str(np.asarray(embedding).dtype),
        norm=norm,
        first_values=tuple(float(value) for value in array[:5]),
        stability=stability,
    )


def _draw_detection(frame: np.ndarray, detection: FaceDetection) -> None:
    """Draw one provider-independent face detection on a frame."""

    x1, y1, x2, y2 = (
        int(round(value)) for value in detection.bounding_box
    )
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    for x, y in detection.landmarks:
        cv2.circle(
            frame,
            (int(round(x)), int(round(y))),
            2,
            (0, 255, 255),
            -1,
        )


def _draw_status(frame: np.ndarray, lines: list[str]) -> None:
    """Render readable validation status lines."""

    for index, line in enumerate(lines):
        y = 28 + index * 24
        cv2.putText(
            frame,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )


async def run_live_face_validation() -> None:
    """Run interactive webcam validation for the configured face provider."""

    capture: cv2.VideoCapture | None = None
    provider = None
    history: deque[np.ndarray] = deque(maxlen=STABILITY_WINDOW_SIZE)
    previous_frame_time = time.perf_counter()
    last_console_report = 0.0

    logger.info("Live face validation starting.")
    try:
        provider = await get_face_verification_provider()
        capture = cv2.VideoCapture(DEFAULT_CAMERA_INDEX)
        if not capture.isOpened():
            raise RuntimeError("Unable to open the default webcam.")

        while True:
            captured, frame = capture.read()
            if not captured or frame is None:
                raise RuntimeError("Unable to capture a webcam frame.")

            current_time = time.perf_counter()
            elapsed = max(current_time - previous_frame_time, 1e-9)
            fps = 1.0 / elapsed
            previous_frame_time = current_time
            lines = [f"Provider: {provider.name}", f"FPS: {fps:.1f}"]

            try:
                detections = await provider.detect_faces(image=frame)
                if not detections:
                    history.clear()
                    lines.extend(
                        ["Face: No face detected", "Embedding: Not extracted"]
                    )
                elif len(detections) > 1:
                    history.clear()
                    lines.extend(
                        [
                            "Face: Multiple faces detected",
                            "Embedding: Not extracted",
                        ]
                    )
                    for detection in detections:
                        _draw_detection(frame, detection)
                else:
                    detection = detections[0]
                    _draw_detection(frame, detection)
                    embedding = await provider.extract_embedding(image=frame)
                    diagnostics = _calculate_embedding_diagnostics(
                        embedding,
                        history,
                    )
                    stability = (
                        "collecting"
                        if diagnostics.stability is None
                        else f"{diagnostics.stability:.4f}"
                    )
                    first_values = ", ".join(
                        f"{value:.4f}"
                        for value in diagnostics.first_values
                    )
                    lines.extend(
                        [
                            "Face: Detected",
                            "Embedding: Extracted",
                            f"Shape: {diagnostics.shape}",
                            f"Dtype: {diagnostics.dtype}",
                            f"Norm: {diagnostics.norm:.4f}",
                            f"First 5: [{first_values}]",
                            f"Stability: {stability}",
                        ]
                    )

                    if current_time - last_console_report >= 1.0:
                        logger.info(
                            "Live face embedding extracted.",
                            provider=provider.name,
                            embedding_shape=diagnostics.shape,
                            embedding_dtype=diagnostics.dtype,
                            embedding_norm=diagnostics.norm,
                            embedding_first_values=diagnostics.first_values,
                            embedding_stability=diagnostics.stability,
                        )
                        last_console_report = current_time

            except FaceProviderError as exc:
                history.clear()
                lines.extend(
                    [f"Provider error: {exc}", "Embedding: Not extracted"]
                )

            lines.append("Press Q to exit")
            _draw_status(frame, lines)
            cv2.imshow(WINDOW_NAME, frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except (RuntimeError, cv2.error) as exc:
        logger.error(f"Live face validation failed: {exc}")
        raise
    finally:
        if capture is not None:
            capture.release()
        cv2.destroyAllWindows()
        try:
            await shutdown_face_verification_providers()
        except FaceProviderError as exc:
            logger.error(f"Face provider shutdown failed: {exc}")
        logger.info("Live face validation stopped cleanly.")


__all__ = ["run_live_face_validation"]
