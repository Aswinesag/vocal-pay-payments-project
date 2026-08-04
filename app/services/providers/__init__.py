"""Public speaker-verification provider infrastructure."""

from app.services.providers.provider_factory import (
    get_speaker_verification_provider,
    shutdown_speaker_verification_providers,
)

__all__ = (
    "get_speaker_verification_provider",
    "shutdown_speaker_verification_providers",
)
