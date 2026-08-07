"""Public speaker-verification provider infrastructure."""

from app.services.providers.provider_factory import (
    get_speaker_verification_provider,
    shutdown_speaker_verification_providers,
)
from .face_provider_factory import (
    get_face_verification_provider,
    shutdown_face_verification_providers,
)
__all__ = [
    "get_speaker_verification_provider",
    "shutdown_speaker_verification_providers",
    "get_face_verification_provider",
    "shutdown_face_verification_providers",
]