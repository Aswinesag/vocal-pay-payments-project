"""CUDA-bound InsightFace facial verification provider."""

from __future__ import annotations

from threading import RLock
from time import perf_counter
from typing import ClassVar

import numpy as np
from insightface.app import FaceAnalysis
from loguru import logger

from app.core.config import settings
from app.services.face_service import (
    FaceDetection,
    FaceProviderError,
    FaceVerificationProvider,
    FaceVerificationResult,
)


class InsightFaceProvider(FaceVerificationProvider):
    """Thread-safe CUDA-only InsightFace verification provider."""

    _model: ClassVar[FaceAnalysis | None] = None
    _model_lock: ClassVar[RLock] = RLock()

    def __init__(
        self,
        _device: str = "cuda",
        _model_name: str | None = None,
    ) -> None:
        if settings.INSIGHTFACE_PROVIDER != "CUDAExecutionProvider":
            raise ValueError("InsightFace requires CUDAExecutionProvider.")

        self._model_name = _model_name or settings.INSIGHTFACE_MODEL
        self._device = _device
        self._app: FaceAnalysis | None = None

    def _ensure_model_loaded(self) -> None:
        """Load the shared model when called inside the inference coordinator."""
        if self._app is None:
            self._app = self._get_model()

    def _get_model(self) -> FaceAnalysis:
        """Load and prepare the process-wide CUDA model exactly once."""
        cls = type(self)
        if cls._model is not None:
            return cls._model

        with cls._model_lock:
            if cls._model is not None:
                return cls._model

            started_at = perf_counter()
            logger.info("InsightFace CUDA model loading started.")
            try:
                model = FaceAnalysis(
                    name=settings.INSIGHTFACE_MODEL,
                    providers=[
                        "CUDAExecutionProvider",
                        "CPUExecutionProvider",
                    ],
                )
                model.prepare(ctx_id=0, det_size=(640, 640))
            except Exception as exc:
                logger.bind(error=str(exc)).exception(
                    "InsightFace CUDA model loading failed."
                )
                raise FaceProviderError(
                    "InsightFace CUDA model could not be initialized."
                ) from exc

            cls._model = model
            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                provider="CUDAExecutionProvider",
            ).info("InsightFace CUDA model loaded.")
            return model

    @property
    def name(self) -> str:
        """Return the provider display name."""
        return "InsightFace"

    @property
    def version(self) -> str:
        """Return the provider implementation version."""
        return "1.0"

    @property
    def initialized(self) -> bool:
        """Return whether the shared CUDA model is loaded."""
        return type(self)._model is not None

    @property
    def model_loaded(self) -> bool:
        """Return whether the shared CUDA model is available."""
        return type(self)._model is not None

    def extract_embedding(
        self,
        img_matrix: np.ndarray | None = None,
        *,
        image: np.ndarray | None = None,
    ) -> list[float]:
        """Extract the normalized embedding of the largest centered face."""
        started_at = perf_counter()
        try:
            matrix = img_matrix if img_matrix is not None else image
            if not isinstance(matrix, np.ndarray) or matrix.ndim != 3:
                raise ValueError("Face input must be a BGR image matrix.")
            if matrix.size == 0:
                raise ValueError("Face input image cannot be empty.")

            self._ensure_model_loaded()
            if self._app is None:
                raise FaceProviderError("InsightFace model is unavailable.")
            faces = self._app.get(np.ascontiguousarray(matrix))
            if not faces:
                raise ValueError("No face detected in the supplied image.")

            image_height, image_width = matrix.shape[:2]
            center_x = image_width / 2.0
            center_y = image_height / 2.0

            def selection_score(face: object) -> float:
                bbox = np.asarray(getattr(face, "bbox"), dtype=np.float32)
                width = max(0.0, float(bbox[2] - bbox[0]))
                height = max(0.0, float(bbox[3] - bbox[1]))
                area = width * height
                face_x = float(bbox[0] + bbox[2]) / 2.0
                face_y = float(bbox[1] + bbox[3]) / 2.0
                distance = np.hypot(face_x - center_x, face_y - center_y)
                return area / (1.0 + float(distance))

            primary_face = max(faces, key=selection_score)
            embedding = np.asarray(
                getattr(primary_face, "normed_embedding"),
                dtype=np.float32,
            ).reshape(-1)
            if embedding.size == 0 or not np.isfinite(embedding).all():
                raise FaceProviderError("InsightFace returned an invalid embedding.")

            result = [float(value) for value in embedding]
            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                dimensions=len(result),
                detected_faces=len(faces),
            ).info("InsightFace embedding extraction completed.")
            return result
        except (ValueError, FaceProviderError):
            raise
        except Exception as exc:
            logger.bind(error=str(exc)).exception(
                "InsightFace embedding extraction failed."
            )
            raise FaceProviderError("Face embedding extraction failed.") from exc

    def calculate_similarity(
        self,
        embedding_a: list[float],
        embedding_b: list[float],
    ) -> float:
        """Return normalized cosine similarity within the inclusive 0–1 range."""
        started_at = perf_counter()
        try:
            vector_a = np.asarray(embedding_a, dtype=np.float32).reshape(-1)
            vector_b = np.asarray(embedding_b, dtype=np.float32).reshape(-1)
            if vector_a.size == 0 or vector_a.shape != vector_b.shape:
                raise ValueError("Face embeddings must have matching dimensions.")
            if not np.isfinite(vector_a).all() or not np.isfinite(vector_b).all():
                raise ValueError("Face embeddings contain non-finite values.")

            denominator = float(np.linalg.norm(vector_a) * np.linalg.norm(vector_b))
            if denominator == 0.0:
                raise ValueError("Face embeddings cannot have zero norm.")

            cosine = float(np.dot(vector_a, vector_b) / denominator)
            similarity = float(np.clip((cosine + 1.0) / 2.0, 0.0, 1.0))
            logger.bind(
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                similarity=round(similarity, 6),
            ).info("Face cosine similarity calculated.")
            return similarity
        except (ValueError, FaceProviderError):
            raise
        except Exception as exc:
            logger.bind(error=str(exc)).exception(
                "Face cosine similarity calculation failed."
            )
            raise FaceProviderError("Face similarity calculation failed.") from exc

    async def verify_face(
        self,
        *,
        enrolled_embedding: object,
        live_embedding: object,
    ) -> FaceVerificationResult:
        """Verify a live face embedding against its enrolled reference."""
        try:
            enrolled = np.asarray(
                enrolled_embedding, dtype=np.float32
            ).reshape(-1).tolist()
            live = np.asarray(live_embedding, dtype=np.float32).reshape(-1).tolist()
            confidence = self.calculate_similarity(enrolled, live)
            return FaceVerificationResult(
                verified=confidence >= settings.FACE_PASS_THRESHOLD,
                confidence=confidence,
                face_detected=True,
                liveness_checked=False,
                provider=self.name,
                metadata={"configured_device": self._device},
            )
        except FaceProviderError:
            raise
        except Exception as exc:
            raise FaceProviderError("Face verification failed.") from exc

    async def detect_faces(self, *, image: object) -> tuple[FaceDetection, ...]:
        """Return portable bounding boxes and landmarks for detected faces."""
        matrix = np.asarray(image)
        self._ensure_model_loaded()
        if self._app is None:
            raise FaceProviderError("InsightFace model is unavailable.")
        faces = self._app.get(matrix)
        return tuple(
            FaceDetection(
                bounding_box=tuple(float(value) for value in face.bbox),
                landmarks=tuple(
                    (float(point[0]), float(point[1]))
                    for point in np.asarray(getattr(face, "kps", ()))
                ),
            )
            for face in faces
        )

    async def shutdown(self) -> None:
        """Release the shared model so it can be initialized again safely."""
        cls = type(self)
        with cls._model_lock:
            self._app = None
            cls._model = None
        logger.info("InsightFace model reference released.")
