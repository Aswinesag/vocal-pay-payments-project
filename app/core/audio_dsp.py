"""Lightweight CPU-based audio replay screening for VocalPay."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np


ROLLOFF_THRESHOLD = 4800.0
CENTROID_THRESHOLD = 2700.0


def detect_replay_attack(audio_path: str) -> bool:
    """Return whether spectral characteristics indicate speaker replay."""
    path = Path(audio_path)
    if not path.is_file():
        raise ValueError(f"Audio file does not exist: {audio_path}")

    samples, sample_rate = librosa.load(
        path,
        sr=None,
        mono=True,
    )
    if sample_rate <= 0 or samples.size == 0:
        raise ValueError("Audio input must contain decodable samples.")
    if not np.isfinite(samples).all():
        raise ValueError("Audio input contains non-finite sample values.")

    spectral_rolloff = librosa.feature.spectral_rolloff(
        y=samples,
        sr=sample_rate,
        roll_percent=0.85,
    )
    spectral_centroid = librosa.feature.spectral_centroid(
        y=samples,
        sr=sample_rate,
    )

    mean_rolloff = float(np.mean(spectral_rolloff))
    mean_centroid = float(np.mean(spectral_centroid))

    return (
        mean_rolloff >= ROLLOFF_THRESHOLD
        and mean_centroid >= CENTROID_THRESHOLD
    )
