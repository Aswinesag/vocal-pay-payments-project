"""Process-wide serialization guard for heavy model inference."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from loguru import logger


_INFERENCE_LOCK = asyncio.Lock()


@asynccontextmanager
async def isolate_model_inference(stage: str) -> AsyncIterator[None]:
    """Serialize one heavy model stage across all tasks in this process."""
    normalized_stage = stage.strip()
    if not normalized_stage:
        raise ValueError("Inference stage must be a non-empty string.")

    wait_started_at = perf_counter()
    logger.info(
        "Inference stage '{}' waiting for the global execution lock.",
        normalized_stage,
    )

    async with _INFERENCE_LOCK:
        acquired_at = perf_counter()
        wait_seconds = acquired_at - wait_started_at
        logger.info(
            "Inference stage '{}' acquired the global execution lock "
            "after {:.6f} seconds.",
            normalized_stage,
            wait_seconds,
        )

        try:
            yield
        finally:
            completed_at = perf_counter()
            residency_seconds = completed_at - acquired_at
            logger.info(
                "Inference stage '{}' releasing the global execution lock "
                "after {:.6f} seconds of processing residency.",
                normalized_stage,
                residency_seconds,
            )


__all__ = ("isolate_model_inference",)
