"""Lazy biometric provider construction with process-wide inference isolation."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from threading import RLock
from time import perf_counter
from typing import Final, TypeAlias, cast

import torch
from loguru import logger

from app.core.config import settings
from app.core.inference_coordinator import isolate_model_inference
from app.services.face_service import FaceVerificationProvider
from app.services.providers.insightface_provider import InsightFaceProvider
from app.services.providers.speechbrain_provider import SpeechBrainProvider
from app.services.voice_service import SpeakerVerificationProvider


ProviderBuilder: TypeAlias = Callable[[], object]

SPEECHBRAIN_PROVIDER: Final[str] = "speechbrain"
INSIGHTFACE_PROVIDER: Final[str] = "insightface"


def _vram_telemetry() -> dict[str, int | bool]:
    """Return non-sensitive CUDA allocator telemetry."""
    available = torch.cuda.is_available()
    return {
        "cuda_available": available,
        "allocated_bytes": torch.cuda.memory_allocated() if available else 0,
        "reserved_bytes": torch.cuda.memory_reserved() if available else 0,
    }


class BiometricInferenceProxy:
    """Serialize every supported execution call for one concrete provider."""

    __slots__ = ("_provider", "_provider_tag", "_initialized")

    def __init__(self, provider: object, provider_tag: str) -> None:
        normalized_tag = provider_tag.strip().casefold()
        if not normalized_tag:
            raise ValueError("Provider tag must be a non-empty string.")

        self._provider = provider
        self._provider_tag = normalized_tag
        self._initialized = False

    @property
    def name(self) -> str:
        """Return the concrete provider's stable display name."""
        name = getattr(self._provider, "name", self._provider_tag)
        return str(name)

    @property
    def version(self) -> str:
        """Return the concrete provider version when exposed."""
        return str(getattr(self._provider, "version", "unknown"))

    @property
    def initialized(self) -> bool:
        """Return whether lazy provider initialization has completed."""
        return bool(getattr(self._provider, "initialized", self._initialized))

    async def _initialize_locked(self) -> None:
        """Load the underlying model once while holding the global gate."""
        if self.initialized or self._initialized:
            return

        loader = getattr(self._provider, "_ensure_model_loaded", None)
        if not callable(loader):
            self._initialized = True
            return

        started_at = perf_counter()
        logger.bind(
            provider=self._provider_tag,
            **_vram_telemetry(),
        ).info("Biometric provider lazy initialization started.")

        result = loader()
        if inspect.isawaitable(result):
            await result

        self._initialized = True
        logger.bind(
            provider=self._provider_tag,
            loading_seconds=perf_counter() - started_at,
            **_vram_telemetry(),
        ).info("Biometric provider lazy initialization completed.")

    async def _execute(
        self,
        method_name: str,
        *args: object,
        **kwargs: object,
    ) -> object:
        """Execute one provider method under the process-wide model gate."""
        method = getattr(self._provider, method_name, None)
        if not callable(method):
            raise AttributeError(
                f"Provider '{self.name}' does not support '{method_name}'."
            )

        logger.bind(
            provider=self._provider_tag,
            operation=method_name,
            **_vram_telemetry(),
        ).debug("Biometric inference waiting for global lock.")

        async with isolate_model_inference(self._provider_tag):
            await self._initialize_locked()
            started_at = perf_counter()
            logger.bind(
                provider=self._provider_tag,
                operation=method_name,
                **_vram_telemetry(),
            ).info("Biometric inference lock acquired.")

            if inspect.iscoroutinefunction(method):
                result = await method(*args, **kwargs)
            else:
                result = await asyncio.to_thread(method, *args, **kwargs)

            logger.bind(
                provider=self._provider_tag,
                operation=method_name,
                execution_seconds=perf_counter() - started_at,
                **_vram_telemetry(),
            ).info("Biometric inference completed.")
            return result

    async def extract_embedding(
        self,
        *args: object,
        **kwargs: object,
    ) -> object:
        """Extract an embedding through the isolated provider."""
        return await self._execute("extract_embedding", *args, **kwargs)

    async def verify_speaker(
        self,
        *args: object,
        **kwargs: object,
    ) -> object:
        """Run isolated speaker verification."""
        return await self._execute("verify_speaker", *args, **kwargs)

    async def detect_faces(
        self,
        *args: object,
        **kwargs: object,
    ) -> object:
        """Run isolated face detection."""
        return await self._execute("detect_faces", *args, **kwargs)

    async def verify_face(
        self,
        *args: object,
        **kwargs: object,
    ) -> object:
        """Run isolated face verification."""
        return await self._execute("verify_face", *args, **kwargs)

    async def transcribe(
        self,
        *args: object,
        **kwargs: object,
    ) -> object:
        """Run isolated ASR transcription when supported."""
        return await self._execute("transcribe", *args, **kwargs)

    async def shutdown(self) -> None:
        """Release the underlying provider lifecycle safely."""
        shutdown = getattr(self._provider, "shutdown", None)
        if callable(shutdown):
            result = shutdown()
            if inspect.isawaitable(result):
                await result
        self._initialized = False


class BiometricProviderFactory:
    """Thread-safe lazy singleton registry for biometric provider proxies."""

    _lock: Final[RLock] = RLock()
    _builders: dict[str, ProviderBuilder] = {}
    _instances: dict[str, BiometricInferenceProxy] = {}

    @classmethod
    def register(cls, provider_tag: str, builder: ProviderBuilder) -> None:
        """Register one provider constructor without loading its model."""
        normalized_tag = provider_tag.strip().casefold()
        if not normalized_tag or not callable(builder):
            raise ValueError("A valid provider tag and builder are required.")

        with cls._lock:
            cls._builders[normalized_tag] = builder

    @classmethod
    def get(cls, provider_tag: str) -> BiometricInferenceProxy:
        """Return one cached lazy provider proxy."""
        normalized_tag = provider_tag.strip().casefold()
        with cls._lock:
            existing = cls._instances.get(normalized_tag)
            if existing is not None:
                logger.bind(provider=normalized_tag).debug(
                    "Reusing biometric provider singleton."
                )
                return existing

            builder = cls._builders.get(normalized_tag)
            if builder is None:
                raise LookupError(f"Unknown biometric provider: {provider_tag}")

            proxy = BiometricInferenceProxy(builder(), normalized_tag)
            cls._instances[normalized_tag] = proxy
            logger.bind(provider=normalized_tag).info(
                "Biometric provider singleton created for lazy loading."
            )
            return proxy

    @classmethod
    async def shutdown(cls) -> None:
        """Shut down and evict every cached provider proxy."""
        with cls._lock:
            providers = tuple(cls._instances.values())
            cls._instances.clear()

        for provider in providers:
            await provider.shutdown()


BiometricProviderFactory.register(
    SPEECHBRAIN_PROVIDER,
    lambda: SpeechBrainProvider(_device=settings.SPEECHBRAIN_DEVICE),
)
BiometricProviderFactory.register(
    INSIGHTFACE_PROVIDER,
    lambda: InsightFaceProvider(
        _device=settings.INSIGHTFACE_DEVICE,
        _model_name=settings.INSIGHTFACE_MODEL,
    ),
)


def get_speaker_verification_provider(
    provider_name: str | None = None,
) -> SpeakerVerificationProvider:
    """Return the serialized SpeechBrain-compatible provider singleton."""
    proxy = BiometricProviderFactory.get(provider_name or SPEECHBRAIN_PROVIDER)
    return cast(SpeakerVerificationProvider, proxy)


def get_face_verification_provider(
    provider_name: str | None = None,
) -> FaceVerificationProvider:
    """Return the serialized InsightFace-compatible provider singleton."""
    proxy = BiometricProviderFactory.get(provider_name or INSIGHTFACE_PROVIDER)
    return cast(FaceVerificationProvider, proxy)


async def shutdown_speaker_verification_providers() -> None:
    """Shut down all cached biometric providers."""
    await BiometricProviderFactory.shutdown()


__all__ = (
    "BiometricInferenceProxy",
    "BiometricProviderFactory",
    "get_speaker_verification_provider",
    "get_face_verification_provider",
    "shutdown_speaker_verification_providers",
)
