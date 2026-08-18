"""Tests for the process-wide biometric provider proxy factory."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from app.services.providers.provider_factory import (
    BiometricInferenceProxy,
    BiometricProviderFactory,
    get_face_verification_provider,
    get_speaker_verification_provider,
)


@dataclass
class _Provider:
    name: str = "TestProvider"
    initialized: bool = False
    loads: int = 0
    calls: int = 0
    shutdowns: int = 0

    def _ensure_model_loaded(self) -> None:
        self.loads += 1
        self.initialized = True

    def extract_embedding(self, value: object) -> object:
        self.calls += 1
        return value

    async def shutdown(self) -> None:
        self.shutdowns += 1
        self.initialized = False


@pytest.fixture(autouse=True)
def restore_factory_state() -> None:
    builders = BiometricProviderFactory._builders.copy()
    instances = BiometricProviderFactory._instances.copy()
    BiometricProviderFactory._instances.clear()
    yield
    BiometricProviderFactory._builders.clear()
    BiometricProviderFactory._builders.update(builders)
    BiometricProviderFactory._instances.clear()
    BiometricProviderFactory._instances.update(instances)


def test_default_providers_are_registered() -> None:
    assert {"speechbrain", "insightface"}.issubset(
        BiometricProviderFactory._builders
    )


def test_register_and_get_cached_proxy() -> None:
    BiometricProviderFactory.register("test", _Provider)
    first = BiometricProviderFactory.get("test")
    second = BiometricProviderFactory.get("TEST")
    assert isinstance(first, BiometricInferenceProxy)
    assert first is second


@pytest.mark.parametrize("tag", ["", "   "])
def test_invalid_provider_tag_is_rejected(tag: str) -> None:
    with pytest.raises(ValueError):
        BiometricProviderFactory.register(tag, _Provider)


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(LookupError):
        BiometricProviderFactory.get("missing")


@pytest.mark.asyncio
async def test_proxy_loads_once_and_serializes_execution() -> None:
    provider = _Provider()
    proxy = BiometricInferenceProxy(provider, "test")
    with patch(
        "app.services.providers.provider_factory.isolate_model_inference"
    ) as isolate:
        context = AsyncMock()
        context.__aenter__.return_value = None
        context.__aexit__.return_value = False
        isolate.return_value = context
        assert await proxy.extract_embedding([1.0]) == [1.0]
        assert await proxy.extract_embedding([2.0]) == [2.0]
    assert provider.loads == 1
    assert provider.calls == 2
    assert isolate.call_count == 2


@pytest.mark.asyncio
async def test_factory_shutdown_evicts_and_closes_instances() -> None:
    provider = _Provider()
    BiometricProviderFactory.register("test", lambda: provider)
    BiometricProviderFactory.get("test")
    await BiometricProviderFactory.shutdown()
    assert provider.shutdowns == 1
    assert "test" not in BiometricProviderFactory._instances


def test_public_provider_accessors_return_cached_proxies() -> None:
    assert get_speaker_verification_provider() is get_speaker_verification_provider()
    assert get_face_verification_provider() is get_face_verification_provider()
