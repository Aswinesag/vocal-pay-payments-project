"""Provider registry and lifecycle management for voice verification."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Final, TypeAlias, cast

from app.core.config import settings
from app.services.providers.speechbrain_provider import SpeechBrainProvider
from app.services.voice_service import (
    SpeakerVerificationProvider,
    VoiceProviderError,
    VoiceValidationError,
    _log_voice_failure,
    _log_voice_operation,
    _log_voice_step,
)


ProviderFactory: TypeAlias = Callable[[], SpeakerVerificationProvider]

DEFAULT_SPEAKER_PROVIDER: Final[str] = "SpeechBrain"

_provider_registry: dict[str, ProviderFactory] = {}
_provider_display_names: dict[str, str] = {}
_provider_instances: dict[str, SpeakerVerificationProvider] = {}
_registry_lock: Final[RLock] = RLock()


def _normalize_provider_name(provider_name: str) -> str:
    """Validate and normalize a provider registry key."""

    if not isinstance(provider_name, str) or not provider_name.strip():
        raise VoiceValidationError("Speaker provider name cannot be empty.")

    return provider_name.strip().casefold()


def _register_speaker_verification_provider(
    provider_name: str,
    provider_factory: ProviderFactory,
) -> None:
    """Register a provider constructor under a deterministic name."""

    normalized_name = _normalize_provider_name(provider_name)
    if not callable(provider_factory):
        raise VoiceValidationError("Speaker provider factory must be callable.")

    with _registry_lock:
        if normalized_name in _provider_registry:
            raise VoiceValidationError(
                f"Speaker provider '{provider_name.strip()}' is already registered."
            )

        _provider_registry[normalized_name] = provider_factory
        _provider_display_names[normalized_name] = provider_name.strip()

    _log_voice_operation(
        "PROVIDER_REGISTERED",
        provider=provider_name.strip(),
    )


def _configured_provider_name() -> str:
    """Return the explicitly configured provider or the production default."""

    provider_name = settings.SPEAKER_VERIFICATION_PROVIDER
    _normalize_provider_name(provider_name)

    _log_voice_step(
        "PROVIDER_CONFIGURATION_SELECTION",
        outcome="SELECTED",
        provider=provider_name.strip(),
    )
    return provider_name.strip()


def _create_provider(
    normalized_name: str,
    provider_factory: ProviderFactory,
) -> SpeakerVerificationProvider:
    """Create and validate one registered provider instance."""

    display_name = _provider_display_names[normalized_name]
    try:
        provider = provider_factory()
    except (VoiceValidationError, VoiceProviderError):
        raise
    except Exception as exc:
        raise VoiceProviderError(
            f"Speaker provider '{display_name}' could not be created."
        ) from exc

    if not isinstance(provider, SpeakerVerificationProvider):
        raise VoiceProviderError(
            f"Speaker provider '{display_name}' does not implement the provider contract."
        )

    _log_voice_operation(
        "PROVIDER_CREATED",
        provider=provider.name,
    )
    return cast(SpeakerVerificationProvider, provider)


def get_speaker_verification_provider(
    provider_name: str | None = None,
) -> SpeakerVerificationProvider:
    """Return the configured singleton speaker-verification provider."""

    selected_name = (
        _configured_provider_name() if provider_name is None else provider_name
    )
    normalized_name = _normalize_provider_name(selected_name)

    with _registry_lock:
        provider_factory = _provider_registry.get(normalized_name)
        if provider_factory is None:
            raise VoiceProviderError(
                f"Unknown speaker verification provider '{selected_name.strip()}'."
            )

        existing_provider = _provider_instances.get(normalized_name)
        if existing_provider is not None:
            _log_voice_step(
                "PROVIDER_RETRIEVAL",
                outcome="REUSED",
                provider=existing_provider.name,
            )
            return existing_provider

        provider = _create_provider(normalized_name, provider_factory)
        _provider_instances[normalized_name] = provider
        return provider


async def shutdown_speaker_verification_providers() -> None:
    """Shut down created providers and reset the reusable singleton cache."""

    with _registry_lock:
        providers = tuple(_provider_instances.values())
        _provider_instances.clear()

    for provider in providers:
        initialized = getattr(provider, "initialized", None)
        if initialized is False:
            _log_voice_step(
                "PROVIDER_SHUTDOWN",
                outcome="SKIPPED",
                provider=provider.name,
            )
            continue

        shutdown = getattr(provider, "shutdown", None)
        if not callable(shutdown):
            continue

        try:
            await shutdown()
        except Exception:
            error = VoiceProviderError(
                f"Speaker provider '{provider.name}' failed to shut down."
            )
            _log_voice_failure(
                "PROVIDER_SHUTDOWN",
                error,
                provider=provider.name,
            )

    _log_voice_operation(
        "PROVIDER_REGISTRY_CLEANUP",
        provider="registry",
    )


_register_speaker_verification_provider(
    DEFAULT_SPEAKER_PROVIDER,
    SpeechBrainProvider,
)


__all__ = (
    "get_speaker_verification_provider",
    "shutdown_speaker_verification_providers",
)
