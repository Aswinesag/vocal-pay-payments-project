"""Process-local RAM and CUDA cache optimization utilities."""

from __future__ import annotations

import gc

import psutil
import torch
from loguru import logger


async def optimize_hardware_memory() -> dict:
    """Collect Python garbage, purge CUDA caches, and return memory metrics."""
    collected_blocks = gc.collect()
    cuda_available = torch.cuda.is_available()
    vram_freed = False
    vram_allocated_mb = 0.0
    vram_peak_mb = 0.0
    vram_total_mb = 0.0
    vram_available_mb = 0.0

    if cuda_available:
        torch.cuda.empty_cache()
        vram_freed = True
        device = torch.cuda.current_device()
        vram_allocated_mb = torch.cuda.memory_allocated(device) / (1024.0**2)
        vram_peak_mb = torch.cuda.max_memory_allocated(device) / (1024.0**2)
        vram_total_mb = torch.cuda.get_device_properties(device).total_memory / (
            1024.0**2
        )
        vram_available_mb = max(0.0, vram_total_mb - vram_allocated_mb)

    memory = psutil.virtual_memory()
    ram_usage_percent = round(float(memory.percent), 2)
    ram_available_mb = memory.available / (1024.0**2)

    logger.bind(
        collected_blocks=collected_blocks,
        ram_usage_percent=ram_usage_percent,
        ram_available_mb=round(ram_available_mb, 2),
        cuda_available=cuda_available,
        vram_freed=vram_freed,
        vram_allocated_mb=round(vram_allocated_mb, 2),
        vram_peak_mb=round(vram_peak_mb, 2),
        vram_total_mb=round(vram_total_mb, 2),
        vram_available_mb=round(vram_available_mb, 2),
    ).info("Hardware memory optimization completed.")

    return {
        "ram_usage_percent": ram_usage_percent,
        "vram_freed": vram_freed,
        "status": "OPTIMIZED",
    }


__all__ = ("optimize_hardware_memory",)
