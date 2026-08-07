"""CPU-isolated OpenCV preprocessing for facial liveness analysis."""

from __future__ import annotations

from time import perf_counter

import cv2
import numpy as np
from loguru import logger


class LivenessPreprocessor:
    """Prepare OpenCV frames for downstream liveness analyzers."""

    def prepare_frame(
        self,
        img_matrix: np.ndarray,
        target_size: tuple[int, int] = (256, 256),
    ) -> np.ndarray:
        """Convert BGR to RGB, center-crop, and resize a frame."""
        started_at = perf_counter()
        try:
            if not isinstance(img_matrix, np.ndarray):
                raise ValueError("Image frame must be a NumPy array.")
            if img_matrix.ndim != 3 or img_matrix.shape[2] != 3:
                raise ValueError("Image frame must be a three-channel BGR matrix.")
            if img_matrix.size == 0:
                raise ValueError("Image frame cannot be empty.")

            target_width, target_height = target_size
            if target_width <= 0 or target_height <= 0:
                raise ValueError("Target dimensions must be positive integers.")

            rgb_frame = cv2.cvtColor(img_matrix, cv2.COLOR_BGR2RGB)
            source_height, source_width = rgb_frame.shape[:2]
            target_ratio = target_width / target_height
            source_ratio = source_width / source_height

            if source_ratio > target_ratio:
                crop_width = max(1, int(round(source_height * target_ratio)))
                left = (source_width - crop_width) // 2
                cropped = rgb_frame[:, left : left + crop_width]
            else:
                crop_height = max(1, int(round(source_width / target_ratio)))
                top = (source_height - crop_height) // 2
                cropped = rgb_frame[top : top + crop_height, :]

            prepared = cv2.resize(
                cropped,
                (target_width, target_height),
                interpolation=cv2.INTER_AREA,
            )
            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                source_shape=img_matrix.shape,
                target_size=target_size,
            ).info("Liveness frame preprocessing completed.")
            return np.ascontiguousarray(prepared)
        except ValueError:
            raise
        except Exception as exc:
            logger.bind(error=str(exc)).exception(
                "Liveness frame preprocessing failed."
            )
            raise ValueError("Image frame could not be prepared.") from exc

    def normalize_intensity(self, img_matrix: np.ndarray) -> np.ndarray:
        """Normalize image intensity values to contiguous float32 values in 0–1."""
        started_at = perf_counter()
        try:
            if not isinstance(img_matrix, np.ndarray) or img_matrix.size == 0:
                raise ValueError("Image frame must be a non-empty NumPy array.")
            if not np.issubdtype(img_matrix.dtype, np.number):
                raise ValueError("Image frame must contain numeric pixel values.")

            normalized = np.asarray(img_matrix, dtype=np.float32) / np.float32(255.0)
            normalized = np.clip(normalized, 0.0, 1.0)
            if not np.isfinite(normalized).all():
                raise ValueError("Normalized frame contains non-finite values.")

            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                shape=normalized.shape,
            ).info("Liveness frame intensity normalization completed.")
            return np.ascontiguousarray(normalized, dtype=np.float32)
        except ValueError:
            raise
        except Exception as exc:
            logger.bind(error=str(exc)).exception(
                "Liveness intensity normalization failed."
            )
            raise ValueError("Image intensity could not be normalized.") from exc


__all__ = ("LivenessPreprocessor",)
