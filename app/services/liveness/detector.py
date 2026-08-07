"""CPU-isolated geometric and texture-based face liveness analysis."""

from __future__ import annotations

from time import perf_counter

import cv2
import numpy as np
from loguru import logger

from app.core.config import settings


class LivenessDetector:
    """Estimate single-frame liveness using deterministic CPU heuristics."""

    def __init__(self) -> None:
        self._face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self._eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_eye_tree_eyeglasses.xml"
        )
        if self._face_cascade.empty() or self._eye_cascade.empty():
            raise RuntimeError("OpenCV facial landmark cascades could not be loaded.")

    def analyze_liveness(self, img_matrix: np.ndarray) -> float:
        """Return a bounded single-frame structural liveness confidence score."""
        started_at = perf_counter()
        try:
            if not isinstance(img_matrix, np.ndarray):
                raise ValueError("Liveness input must be a NumPy array.")
            if img_matrix.ndim != 3 or img_matrix.shape[2] != 3:
                raise ValueError("Liveness input must be a normalized RGB matrix.")
            if img_matrix.size == 0 or not np.isfinite(img_matrix).all():
                raise ValueError("Liveness input contains invalid pixel values.")

            normalized = np.clip(img_matrix.astype(np.float32), 0.0, 1.0)
            frame = np.rint(normalized * 255.0).astype(np.uint8)
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

            faces = self._face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(64, 64),
            )
            if len(faces) == 0:
                logger.bind(latency_ms=round((perf_counter() - started_at) * 1000, 2)).warning(
                    "Liveness analysis found no face."
                )
                return 0.0

            x, y, width, height = max(faces, key=lambda box: int(box[2]) * int(box[3]))
            face_gray = gray[y : y + height, x : x + width]
            upper_face = face_gray[: max(1, height // 2), :]
            eyes = self._eye_cascade.detectMultiScale(
                upper_face,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(12, 12),
            )
            eye_score = min(len(eyes), 2) / 2.0

            laplacian_variance = float(cv2.Laplacian(face_gray, cv2.CV_32F).var())
            texture_score = float(np.clip(laplacian_variance / 500.0, 0.0, 1.0))

            gradient_x = cv2.Sobel(face_gray, cv2.CV_32F, 1, 0, ksize=3)
            gradient_y = cv2.Sobel(face_gray, cv2.CV_32F, 0, 1, ksize=3)
            gradient_energy = float(np.mean(cv2.magnitude(gradient_x, gradient_y)))
            gradient_score = float(np.clip(gradient_energy / 80.0, 0.0, 1.0))

            hsv_face = cv2.cvtColor(frame[y : y + height, x : x + width], cv2.COLOR_RGB2HSV)
            reflection_ratio = float(
                np.mean((hsv_face[..., 1] < 35) & (hsv_face[..., 2] > 240))
            )
            reflection_score = float(np.clip(1.0 - reflection_ratio * 8.0, 0.0, 1.0))

            spectrum = np.fft.fftshift(np.fft.fft2(face_gray.astype(np.float32)))
            magnitude = np.abs(spectrum)
            rows, columns = magnitude.shape
            center_row, center_column = rows // 2, columns // 2
            radius = max(2, min(rows, columns) // 8)
            low_frequency = magnitude[
                center_row - radius : center_row + radius,
                center_column - radius : center_column + radius,
            ].sum()
            total_frequency = magnitude.sum() + np.finfo(np.float32).eps
            high_frequency_ratio = float(1.0 - low_frequency / total_frequency)

            geometry_score = float(np.clip((width * height) / (gray.size * 0.35), 0.0, 1.0))
            score = (
                0.25 * eye_score
                + 0.25 * texture_score
                + 0.20 * gradient_score
                + 0.20 * reflection_score
                + 0.10 * geometry_score
            )

            flat_print_marker = laplacian_variance < 18.0
            screen_marker = reflection_ratio > 0.08 or high_frequency_ratio > 0.92
            if flat_print_marker or screen_marker:
                score = min(
                    score,
                    max(0.0, settings.LIVENESS_CRITICAL_THRESHOLD - 0.01),
                )

            confidence = float(np.clip(score, 0.0, 1.0))
            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                confidence=round(confidence, 4),
                eye_score=round(eye_score, 4),
                texture_score=round(texture_score, 4),
                gradient_score=round(gradient_score, 4),
                reflection_ratio=round(reflection_ratio, 4),
                high_frequency_ratio=round(high_frequency_ratio, 4),
            ).info("CPU liveness analysis completed.")
            return confidence
        except ValueError:
            raise
        except Exception as exc:
            logger.bind(error=str(exc)).exception("CPU liveness analysis failed.")
            return 0.0


__all__ = ("LivenessDetector",)
