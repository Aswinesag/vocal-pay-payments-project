from __future__ import annotations
import asyncio
from typing import Final
from app.core.config import settings
from app.services.face_service import (
    FaceProviderError,
    FaceVerificationProvider,
)
from .insightface_provider import (
    InsightFaceProvider,
)

_FACE_PROVIDER_REGISTRY: Final[
    dict[str, type[FaceVerificationProvider]]
] = {
    "INSIGHTFACE": InsightFaceProvider,
}
_PROVIDER_INSTANCES: dict[
    str,
    FaceVerificationProvider,
] = {}
_PROVIDER_LOCK = asyncio.Lock()

def _get_provider_class() -> type[
    FaceVerificationProvider
]:
    """
    Resolve the configured face provider.
    """

    provider_name = (
        settings.FACE_VERIFICATION_PROVIDER
        .strip()
        .upper()
    )

    try:
        return _FACE_PROVIDER_REGISTRY[
            provider_name
        ]

    except KeyError as exc:

        raise FaceProviderError(
            f"Unknown face provider '{provider_name}'."
        ) from exc

async def get_face_verification_provider(
) -> FaceVerificationProvider:
    """
    Return the configured singleton provider.
    """

    provider_class = _get_provider_class()

    provider_name = provider_class.__name__

    async with _PROVIDER_LOCK:

        provider = _PROVIDER_INSTANCES.get(
            provider_name,
        )

        if provider is not None:
            return provider

        provider = provider_class()

        _PROVIDER_INSTANCES[
            provider_name
        ] = provider

        return provider

async def shutdown_face_verification_providers(
) -> None:
    """
    Shutdown every initialized provider.
    """

    async with _PROVIDER_LOCK:

        providers = tuple(
            _PROVIDER_INSTANCES.values()
        )

        _PROVIDER_INSTANCES.clear()

    errors: list[Exception] = []

    for provider in providers:

        try:

            await provider.shutdown()

        except Exception as exc:

            errors.append(exc)

    if errors:

        raise FaceProviderError(
            "Failed to shutdown one or more "
            "face providers."
        )

__all__ = [
    "get_face_verification_provider",
    "shutdown_face_verification_providers",
]