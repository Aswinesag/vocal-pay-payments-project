"""Concrete InsightFace provider for in-memory face verification."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np
from insightface.app import FaceAnalysis

from app.services.face_service import (
    FaceDetection,
    FaceEmbedding,
    FaceProviderError,
    FaceVerificationProvider,
    FaceVerificationResult,
)


DEFAULT_PROVIDER_NAME: Final[str] = "InsightFace"
DEFAULT_MODEL_NAME: Final[str] = "buffalo_l"
DEFAULT_DEVICE: Final[str] = "CPU"
DEFAULT_DETECTION_SIZE: Final[tuple[int, int]] = (640, 640)
DEFAULT_MODEL_CACHE: Final[Path] = (
    Path.home() / ".cache" / "vocalpay" / "insightface"
)
DEFAULT_VERIFICATION_THRESHOLD: Final[float] = 0.65


@dataclass(slots=True)
class InsightFaceProvider(FaceVerificationProvider):
    """InsightFace-based face verification provider."""

    _initialized: bool = field(default=False, init=False)
    _version: str = field(default="1.0", init=False)
    _device: str = DEFAULT_DEVICE
    _model_name: str = DEFAULT_MODEL_NAME
    _model_cache: Path = field(default=DEFAULT_MODEL_CACHE)
    _detection_size: tuple[int, int] = field(
        default=DEFAULT_DETECTION_SIZE
    )
    _app: FaceAnalysis | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        init=False,
        repr=False,
    )

    @property
    def name(self) -> str:
        """Return the stable provider name."""

        return DEFAULT_PROVIDER_NAME

    @property
    def version(self) -> str:
        """Return the provider implementation version."""

        return self._version

    @property
    def initialized(self) -> bool:
        """Return whether model initialization completed."""

        return self._initialized

    @property
    def model_loaded(self) -> bool:
        """Return whether a model application is available."""

        return self._app is not None

    async def _ensure_model_loaded(self) -> None:
        """Lazily initialize the InsightFace model exactly once."""

        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            try:
                self._model_cache.mkdir(parents=True, exist_ok=True)
                app = FaceAnalysis(
                    name=self._model_name,
                    root=str(self._model_cache),
                )
                app.prepare(
                    ctx_id=0 if self._device.upper() == "CUDA" else -1,
                    det_size=self._detection_size,
                )
            except Exception as exc:
                raise FaceProviderError(
                    "Failed to initialize InsightFace model."
                ) from exc

            self._app = app
            self._initialized = True

    def _validate_detected_faces(
        self,
        faces: Sequence[object],
    ) -> object:
        """Require exactly one detected face and return it."""

        if not faces:
            raise FaceProviderError(
                "No face detected in the supplied image."
            )
        if len(faces) > 1:
            raise FaceProviderError(
                "Multiple faces detected. Exactly one face is required."
            )
        return faces[0]

    async def detect_faces(
        self,
        *,
        image: object,
    ) -> tuple[FaceDetection, ...]:
        """Detect faces and expose only portable rendering metadata."""

        await self._ensure_model_loaded()
        if image is None:
            raise FaceProviderError("Input image cannot be None.")
        if self._app is None:
            raise FaceProviderError(
                "InsightFace model is not initialized."
            )

        try:
            faces = self._app.get(image)
            detections: list[FaceDetection] = []
            for face in faces:
                bounding_box = np.asarray(face.bbox, dtype=np.float32)
                if bounding_box.size != 4:
                    raise FaceProviderError(
                        "Detected face has an invalid bounding box."
                    )

                raw_landmarks = getattr(face, "kps", None)
                landmarks: tuple[tuple[float, float], ...] = ()
                if raw_landmarks is not None:
                    landmark_array = np.asarray(
                        raw_landmarks,
                        dtype=np.float32,
                    ).reshape(-1, 2)
                    landmarks = tuple(
                        (float(point[0]), float(point[1]))
                        for point in landmark_array
                    )

                detections.append(
                    FaceDetection(
                        bounding_box=tuple(
                            float(value) for value in bounding_box
                        ),
                        landmarks=landmarks,
                    )
                )
            return tuple(detections)
        except FaceProviderError:
            raise
        except Exception as exc:
            raise FaceProviderError("Face detection failed.") from exc

    async def extract_embedding(
        self,
        *,
        image: object,
    ) -> FaceEmbedding:
        """Extract one face embedding from an input image."""

        await self._ensure_model_loaded()
        if image is None:
            raise FaceProviderError("Input image cannot be None.")
        if self._app is None:
            raise FaceProviderError(
                "InsightFace model is not initialized."
            )

        try:
            faces = self._app.get(image)
            face = self._validate_detected_faces(faces)
            embedding = np.asarray(face.embedding, dtype=np.float32)
            if embedding.size == 0:
                raise FaceProviderError("Generated embedding is empty.")
            return embedding
        except FaceProviderError:
            raise
        except Exception as exc:
            raise FaceProviderError(
                "Failed to extract face embedding."
            ) from exc

    async def verify_face(
        self,
        *,
        enrolled_embedding: object,
        live_embedding: object,
    ) -> FaceVerificationResult:
        """Compare enrolled and live face embeddings."""

        await self._ensure_model_loaded()
        try:
            enrolled = np.asarray(enrolled_embedding, dtype=np.float32)
            live = np.asarray(live_embedding, dtype=np.float32)
        except Exception as exc:
            raise FaceProviderError("Invalid face embeddings.") from exc

        if enrolled.size == 0 or live.size == 0:
            raise FaceProviderError("Face embeddings cannot be empty.")
        if enrolled.shape != live.shape:
            raise FaceProviderError("Embedding dimensions do not match.")

        enrolled_norm = float(np.linalg.norm(enrolled))
        live_norm = float(np.linalg.norm(live))
        if enrolled_norm == 0.0 or live_norm == 0.0:
            raise FaceProviderError("Face embeddings cannot have zero norm.")

        similarity = float(
            np.dot(enrolled, live) / (enrolled_norm * live_norm)
        )
        similarity = max(-1.0, min(1.0, similarity))
        confidence = (similarity + 1.0) / 2.0

        return FaceVerificationResult(
            verified=confidence >= DEFAULT_VERIFICATION_THRESHOLD,
            confidence=confidence,
            face_detected=True,
            liveness_checked=False,
            provider=self.name,
            metadata={
                "similarity": similarity,
                "threshold": DEFAULT_VERIFICATION_THRESHOLD,
            },
        )

    async def shutdown(self) -> None:
        """
        Release all provider resources.

        InsightFace itself does not expose an explicit shutdown API,
        therefore we simply release references to allow Python's
        garbage collector to reclaim memory.
        """

        async with self._lock:
            self._app = None
            self._initialized = False
