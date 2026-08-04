"""Tests for speaker-verification provider registry and lifecycle."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import cast
from unittest.mock import AsyncMock

import pytest

import app.services.providers.provider_factory as factory
from app.services.providers import (
    get_speaker_verification_provider,
    shutdown_speaker_verification_providers,
)
from app.services.providers.speechbrain_provider import SpeechBrainProvider
from app.services.voice_service import (
    SpeakerVerificationProvider,
    SpeakerVerificationResult,
    VoiceProviderError,
    VoiceValidationError,
)


@dataclass
class _TestProvider:
    name: str = "TestProvider"
    initialized: bool = True
    shutdown_error: Exception | None = None
    shutdown_calls: int = 0

    async def verify_speaker(
        self,
        *,
        enrolled_embedding: object,
        live_embedding: object,
    ) -> SpeakerVerificationResult:
        return SpeakerVerificationResult(
            verified=True,
            confidence=1.0,
            replay_detected=False,
            provider=self.name,
            metadata={},
        )

    async def shutdown(self) -> None:
        self.shutdown_calls += 1
        if self.shutdown_error is not None:
            raise self.shutdown_error


@pytest.fixture(autouse=True)
def _restore_factory_state(monkeypatch: pytest.MonkeyPatch):
    registry = factory._provider_registry.copy()
    display_names = factory._provider_display_names.copy()
    factory._provider_instances.clear()
    monkeypatch.setattr(
        factory.settings,
        "SPEAKER_VERIFICATION_PROVIDER",
        factory.DEFAULT_SPEAKER_PROVIDER,
    )

    yield

    factory._provider_instances.clear()
    factory._provider_registry.clear()
    factory._provider_registry.update(registry)
    factory._provider_display_names.clear()
    factory._provider_display_names.update(display_names)


def test_default_provider_is_registered() -> None:
    assert "speechbrain" in factory._provider_registry


def test_register_future_provider() -> None:
    factory._register_speaker_verification_provider(
        "TestProvider",
        _TestProvider,
    )

    provider = get_speaker_verification_provider("testprovider")

    assert isinstance(provider, _TestProvider)


def test_duplicate_registration_rejected() -> None:
    with pytest.raises(VoiceValidationError, match="already registered"):
        factory._register_speaker_verification_provider(
            " speechbrain ",
            SpeechBrainProvider,
        )


@pytest.mark.parametrize("provider_name", ["", "   ", cast(str, None)])
def test_invalid_registration_name_rejected(provider_name: str) -> None:
    with pytest.raises(VoiceValidationError):
        factory._register_speaker_verification_provider(
            provider_name,
            _TestProvider,
        )


def test_non_callable_provider_factory_rejected() -> None:
    with pytest.raises(VoiceValidationError, match="callable"):
        factory._register_speaker_verification_provider(
            "Invalid",
            cast(factory.ProviderFactory, object()),
        )


def test_provider_missing_contract_rejected() -> None:
    factory._register_speaker_verification_provider(
        "Invalid",
        cast(factory.ProviderFactory, object),
    )

    with pytest.raises(VoiceProviderError, match="provider contract"):
        get_speaker_verification_provider("Invalid")


def test_unknown_provider_lookup_rejected() -> None:
    with pytest.raises(VoiceProviderError, match="Unknown"):
        get_speaker_verification_provider("Unavailable")


def test_factory_returns_speechbrain_provider() -> None:
    provider = get_speaker_verification_provider()

    assert isinstance(provider, SpeechBrainProvider)
    assert isinstance(provider, SpeakerVerificationProvider)


def test_factory_reuses_singleton_provider() -> None:
    first = get_speaker_verification_provider()
    second = get_speaker_verification_provider("SPEECHBRAIN")

    assert first is second


def test_thread_safe_factory_retrieval_returns_one_instance() -> None:
    with ThreadPoolExecutor(max_workers=12) as executor:
        providers = list(
            executor.map(
                lambda _: get_speaker_verification_provider(),
                range(100),
            )
        )

    assert len({id(provider) for provider in providers}) == 1


def test_default_configuration_selects_speechbrain() -> None:
    assert factory._configured_provider_name() == "SpeechBrain"


def test_explicit_configuration_selects_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory._register_speaker_verification_provider(
        "TestProvider",
        _TestProvider,
    )
    monkeypatch.setattr(
        factory.settings,
        "SPEAKER_VERIFICATION_PROVIDER",
        "TestProvider",
    )

    provider = get_speaker_verification_provider()

    assert isinstance(provider, _TestProvider)


def test_empty_provider_configuration_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        factory.settings,
        "SPEAKER_VERIFICATION_PROVIDER",
        "   ",
    )

    with pytest.raises(VoiceValidationError):
        get_speaker_verification_provider()


def test_unknown_provider_configuration_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        factory.settings,
        "SPEAKER_VERIFICATION_PROVIDER",
        "Unknown",
    )

    with pytest.raises(VoiceProviderError, match="Unknown"):
        get_speaker_verification_provider()


def test_provider_creation_failure_is_wrapped() -> None:
    def fail_creation() -> SpeakerVerificationProvider:
        raise RuntimeError("construction failed")

    factory._register_speaker_verification_provider(
        "Broken",
        fail_creation,
    )

    with pytest.raises(VoiceProviderError, match="could not be created"):
        get_speaker_verification_provider("Broken")


@pytest.mark.asyncio
async def test_shutdown_initialized_provider() -> None:
    provider = cast(
        SpeechBrainProvider,
        get_speaker_verification_provider(),
    )
    provider._initialized = True
    provider._model = object()
    shutdown = AsyncMock(wraps=provider.shutdown)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(provider, "shutdown", shutdown)
        await shutdown_speaker_verification_providers()

    shutdown.assert_awaited_once()
    assert provider.initialized is False
    assert factory._provider_instances == {}


@pytest.mark.asyncio
async def test_shutdown_skips_uninitialized_provider() -> None:
    provider = cast(
        SpeechBrainProvider,
        get_speaker_verification_provider(),
    )
    shutdown = AsyncMock(wraps=provider.shutdown)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(provider, "shutdown", shutdown)
        await shutdown_speaker_verification_providers()

    shutdown.assert_not_awaited()
    assert factory._provider_instances == {}


@pytest.mark.asyncio
async def test_shutdown_without_provider_creation() -> None:
    await shutdown_speaker_verification_providers()

    assert factory._provider_instances == {}


@pytest.mark.asyncio
async def test_multiple_shutdown_calls_are_safe() -> None:
    provider = _TestProvider()
    factory._register_speaker_verification_provider(
        provider.name,
        lambda: provider,
    )
    get_speaker_verification_provider(provider.name)

    await shutdown_speaker_verification_providers()
    await shutdown_speaker_verification_providers()

    assert provider.shutdown_calls == 1


@pytest.mark.asyncio
async def test_partial_shutdown_failure_does_not_stop_cleanup() -> None:
    broken = _TestProvider(
        name="Broken",
        shutdown_error=RuntimeError("shutdown failed"),
    )
    healthy = _TestProvider(name="Healthy")
    factory._register_speaker_verification_provider(
        broken.name,
        lambda: broken,
    )
    factory._register_speaker_verification_provider(
        healthy.name,
        lambda: healthy,
    )
    get_speaker_verification_provider(broken.name)
    get_speaker_verification_provider(healthy.name)

    await shutdown_speaker_verification_providers()

    assert broken.shutdown_calls == 1
    assert healthy.shutdown_calls == 1
    assert factory._provider_instances == {}


@pytest.mark.asyncio
async def test_registry_is_reusable_after_shutdown() -> None:
    first = get_speaker_verification_provider()
    await shutdown_speaker_verification_providers()
    second = get_speaker_verification_provider()

    assert first is not second
    assert isinstance(second, SpeechBrainProvider)


def test_provider_package_public_api() -> None:
    import app.services.providers as providers

    assert providers.__all__ == (
        "get_speaker_verification_provider",
        "shutdown_speaker_verification_providers",
    )
