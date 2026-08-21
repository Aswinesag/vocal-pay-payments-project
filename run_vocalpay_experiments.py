"""Offline empirical benchmark harness for the VocalPay inference pipeline.

This utility does not invoke HTTP endpoints or mutate database state. It executes
the production DSP, SpeechBrain, inference coordinator, and Ollama service
directly, while sampling host and optional NVIDIA resources every 10 ms.

Example:
    python run_vocalpay_experiments.py \
        --reference-audio samples/genuine_reference.wav \
        --impostor-audio samples/impostor_01.wav \
        --impostor-audio samples/impostor_02.wav
"""

# flake8: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import csv
import math
import os
import random
import statistics
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, time
from typing import Any

# Prevent the optional Albumentations update probe triggered transitively by the
# provider package initializer. Model checkpoint access is separate and must
# already be cached for a fully offline trial.
os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")

import librosa
import numpy as np
import psutil
import soundfile as sf
from loguru import logger

from app.core.audio_dsp import ANALYSIS_SAMPLE_RATE, detect_replay_attack
from app.core.config import settings
from app.core.inference_coordinator import isolate_model_inference
from app.services.ollama_service import OllamaService
from app.services.providers.speechbrain_provider import SpeechBrainProvider


DEFAULT_ITERATIONS = 20
DEFAULT_DEGRADATION_TRIALS = 10
DEFAULT_OUTPUT = Path("vocalpay_performance_metrics.csv")
RESOURCE_SAMPLE_INTERVAL_SECONDS = 0.010
VRAM_CEILING_MB = 4096.0
THRESHOLDS = (0.60, 0.72, 0.85)


@dataclass(slots=True)
class ResourceSample:
    """One 10 ms resource observation associated with an active stage."""

    timestamp_epoch_s: float
    elapsed_ms: float
    iteration: int | None
    stage: str
    process_rss_mb: float
    system_ram_used_mb: float
    system_ram_percent: float
    cpu_percent: float
    gpu_vram_used_mb: float | None
    gpu_vram_total_mb: float | None
    gpu_vram_percent: float | None


@dataclass(slots=True)
class IterationMetric:
    """Measured latency and outcome for one production-pipeline trial."""

    iteration: int
    cold_start: bool
    dsp_latency_ms: float | None
    speechbrain_latency_ms: float | None
    ollama_latency_ms: float | None
    end_to_end_latency_ms: float
    replay_detected: bool | None
    speaker_score: float | None
    risk_tier: str | None
    error: str | None


@dataclass(slots=True)
class AcousticMetric:
    """One real speaker-embedding score under a controlled condition."""

    subject_class: str
    source_file: str
    condition: str
    trial: int
    similarity_score: float | None
    dsp_replay_detected: bool | None
    extraction_latency_ms: float | None
    error: str | None


@dataclass(slots=True)
class ThresholdMetric:
    """Observed FAR/FRR for one condition and decision threshold."""

    condition: str
    threshold: float
    genuine_trials: int
    impostor_trials: int
    false_rejections: int
    false_acceptances: int
    frr: float | None
    far: float | None


@dataclass(slots=True)
class StageInterval:
    """Monotonic execution interval used to audit model-stage overlap."""

    iteration: int | None
    stage: str
    started_s: float
    finished_s: float


class StageTracker:
    """Thread-safe stage label and interval recorder for the sampler."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stage = "IDLE"
        self._iteration: int | None = None
        self._active_started_s: float | None = None
        self._intervals: list[StageInterval] = []
        self._overlap_attempts = 0

    @contextmanager
    def activate(self, stage: str, iteration: int | None) -> Iterator[None]:
        """Publish exactly one active benchmark stage for its duration."""
        started_s = perf_counter()
        with self._lock:
            if self._stage != "IDLE":
                self._overlap_attempts += 1
                raise RuntimeError(
                    f"Stage overlap attempted: active={self._stage}, new={stage}"
                )
            self._stage = stage
            self._iteration = iteration
            self._active_started_s = started_s
        try:
            yield
        finally:
            finished_s = perf_counter()
            with self._lock:
                self._intervals.append(
                    StageInterval(
                        iteration=iteration,
                        stage=stage,
                        started_s=started_s,
                        finished_s=finished_s,
                    )
                )
                self._stage = "IDLE"
                self._iteration = None
                self._active_started_s = None

    def snapshot(self) -> tuple[str, int | None]:
        """Return the current label atomically."""
        with self._lock:
            return self._stage, self._iteration

    @property
    def intervals(self) -> tuple[StageInterval, ...]:
        """Return an immutable interval snapshot."""
        with self._lock:
            return tuple(self._intervals)

    @property
    def overlap_attempts(self) -> int:
        """Return rejected nested-stage activations."""
        with self._lock:
            return self._overlap_attempts


class OptionalNvmlSampler:
    """Best-effort NVIDIA device telemetry without adding a dependency."""

    def __init__(self, gpu_index: int) -> None:
        self._module: Any | None = None
        self._handle: Any | None = None
        try:
            import pynvml  # type: ignore[import-not-found]

            pynvml.nvmlInit()
            self._module = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            logger.info("NVML telemetry enabled for GPU index {}.", gpu_index)
        except Exception as exc:
            logger.warning(
                "NVML unavailable; resource rows will contain CPU/RAM telemetry only: {}",
                exc,
            )

    @property
    def available(self) -> bool:
        """Return whether NVML initialized successfully."""
        return self._module is not None and self._handle is not None

    def read(self) -> tuple[float | None, float | None, float | None]:
        """Return used MB, total MB, and percentage for the selected GPU."""
        if self._module is None or self._handle is None:
            return None, None, None
        try:
            memory = self._module.nvmlDeviceGetMemoryInfo(self._handle)
            used_mb = float(memory.used) / (1024.0**2)
            total_mb = float(memory.total) / (1024.0**2)
            percent = (used_mb / total_mb * 100.0) if total_mb else 0.0
            return used_mb, total_mb, percent
        except Exception as exc:
            logger.debug("NVML sample failed: {}", exc)
            return None, None, None

    def close(self) -> None:
        """Release NVML state if it was initialized."""
        if self._module is not None:
            try:
                self._module.nvmlShutdown()
            except Exception:
                logger.debug("NVML shutdown failed.")


class ResourceMonitor:
    """Sample process, host, and optional GPU resources every 10 ms."""

    def __init__(self, tracker: StageTracker, gpu_index: int) -> None:
        self._tracker = tracker
        self._nvml = OptionalNvmlSampler(gpu_index)
        self._process = psutil.Process(os.getpid())
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="vocalpay-resource-sampler",
            daemon=True,
        )
        self._samples: list[ResourceSample] = []
        self._samples_lock = threading.Lock()
        self._benchmark_started_s = perf_counter()

    @property
    def nvml_available(self) -> bool:
        """Return whether GPU telemetry is present."""
        return self._nvml.available

    @property
    def samples(self) -> tuple[ResourceSample, ...]:
        """Return all collected observations."""
        with self._samples_lock:
            return tuple(self._samples)

    def start(self) -> None:
        """Start the resource sampler."""
        psutil.cpu_percent(interval=None)
        self._thread.start()

    def stop(self) -> None:
        """Stop and join the resource sampler."""
        self._stop_event.set()
        self._thread.join(timeout=5.0)
        self._nvml.close()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            observed_at = perf_counter()
            stage, iteration = self._tracker.snapshot()
            virtual_memory = psutil.virtual_memory()
            gpu_used, gpu_total, gpu_percent = self._nvml.read()
            sample = ResourceSample(
                timestamp_epoch_s=time(),
                elapsed_ms=(observed_at - self._benchmark_started_s) * 1000.0,
                iteration=iteration,
                stage=stage,
                process_rss_mb=self._process.memory_info().rss / (1024.0**2),
                system_ram_used_mb=(virtual_memory.total - virtual_memory.available)
                / (1024.0**2),
                system_ram_percent=float(virtual_memory.percent),
                cpu_percent=float(psutil.cpu_percent(interval=None)),
                gpu_vram_used_mb=gpu_used,
                gpu_vram_total_mb=gpu_total,
                gpu_vram_percent=gpu_percent,
            )
            with self._samples_lock:
                self._samples.append(sample)
            self._stop_event.wait(RESOURCE_SAMPLE_INTERVAL_SECONDS)


def parse_args() -> argparse.Namespace:
    """Parse reproducible experiment parameters."""
    parser = argparse.ArgumentParser(
        description="Run real VocalPay latency, resource, and threshold experiments."
    )
    parser.add_argument(
        "--reference-audio",
        type=Path,
        required=True,
        help="Clean WAV/audio recording from the enrolled genuine speaker.",
    )
    parser.add_argument(
        "--impostor-audio",
        type=Path,
        action="append",
        default=[],
        help=(
            "Audio from a non-enrolled speaker. Repeat for multiple impostors. "
            "Without this option FAR is reported as undefined."
        ),
    )
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument(
        "--degradation-trials",
        type=int,
        default=DEFAULT_DEGRADATION_TRIALS,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--gpu-index", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260820)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """Reject invalid or statistically unusable inputs."""
    paths = [args.reference_audio, *args.impostor_audio]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing audio input(s): " + ", ".join(missing))
    if args.iterations != DEFAULT_ITERATIONS:
        logger.warning(
            "Paper protocol specifies 20 iterations; requested {}.", args.iterations
        )
    if args.iterations < 2:
        raise ValueError("At least two pipeline iterations are required.")
    if args.degradation_trials < 2:
        raise ValueError("At least two degradation trials are required.")
    if args.gpu_index < 0:
        raise ValueError("GPU index cannot be negative.")


def load_waveform(path: Path) -> np.ndarray:
    """Load one finite mono 16 kHz waveform using production-compatible rules."""
    waveform, _ = librosa.load(
        path,
        sr=ANALYSIS_SAMPLE_RATE,
        mono=True,
        dtype=np.float32,
    )
    waveform = np.ascontiguousarray(waveform, dtype=np.float32)
    if waveform.ndim != 1 or waveform.size == 0:
        raise ValueError(f"Audio is empty or invalid: {path}")
    if not np.isfinite(waveform).all():
        raise ValueError(f"Audio contains non-finite samples: {path}")
    return waveform


def normalized_similarity(
    embedding_a: Sequence[float], embedding_b: Sequence[float]
) -> float:
    """Match the provider's cosine-to-[0,1] score transformation."""
    vector_a = np.asarray(embedding_a, dtype=np.float32).reshape(-1)
    vector_b = np.asarray(embedding_b, dtype=np.float32).reshape(-1)
    if vector_a.shape != vector_b.shape or vector_a.size == 0:
        raise ValueError("Embedding dimensions do not match.")
    denominator = float(np.linalg.norm(vector_a) * np.linalg.norm(vector_b))
    if denominator <= np.finfo(np.float32).eps:
        raise ValueError("Cannot compare zero-norm embeddings.")
    cosine = float(np.dot(vector_a, vector_b) / denominator)
    return float(np.clip((cosine + 1.0) / 2.0, 0.0, 1.0))


async def extract_speaker_embedding(
    provider: SpeechBrainProvider,
    waveform: np.ndarray,
) -> list[float]:
    """Run the production CPU provider under the global inference guard."""
    async with isolate_model_inference("speechbrain-experiment"):
        result = await asyncio.to_thread(provider.extract_embedding, waveform)
    return [float(value) for value in result]


def degrade_waveform(
    waveform: np.ndarray,
    condition: str,
    rng: np.random.Generator,
) -> np.ndarray:
    """Apply a controlled signal transformation without fabricating scores."""
    source = np.asarray(waveform, dtype=np.float32)
    peak = max(float(np.max(np.abs(source))), np.finfo(np.float32).eps)
    if condition == "A_CLEAN_BASELINE":
        gain = float(rng.uniform(0.95, 1.05))
        noise = rng.normal(0.0, peak * 0.001, source.size)
        transformed = source * gain + noise
    elif condition == "B_AMBIENT_NOISE":
        gain = float(rng.uniform(0.55, 0.80))
        signal_rms = max(float(np.sqrt(np.mean(source**2))), 1e-6)
        target_snr_db = float(rng.uniform(10.0, 18.0))
        noise_rms = signal_rms / (10.0 ** (target_snr_db / 20.0))
        noise = rng.normal(0.0, noise_rms, source.size)
        transformed = source * gain + noise
    elif condition == "C_CLIPPED_SATURATION":
        normalized = source / peak
        drive = float(rng.uniform(3.5, 6.0))
        clipped = np.clip(normalized * drive, -0.35, 0.35)
        quantization_levels = 64.0
        transformed = np.round(clipped * quantization_levels) / quantization_levels
    else:
        raise ValueError(f"Unknown acoustic condition: {condition}")
    return np.ascontiguousarray(np.clip(transformed, -1.0, 1.0), dtype=np.float32)


def calculate_overlap(intervals: Sequence[StageInterval]) -> tuple[int, float]:
    """Return interval-overlap count and total overlapping milliseconds."""
    model_intervals = sorted(
        (
            interval
            for interval in intervals
            if interval.stage.startswith(("SPEECHBRAIN", "OLLAMA"))
        ),
        key=lambda interval: interval.started_s,
    )
    overlap_count = 0
    overlap_seconds = 0.0
    for previous, current in zip(model_intervals, model_intervals[1:]):
        overlap = min(previous.finished_s, current.finished_s) - max(
            previous.started_s, current.started_s
        )
        if overlap > 0.0:
            overlap_count += 1
            overlap_seconds += overlap
    return overlap_count, overlap_seconds * 1000.0


async def run_pipeline_trials(
    reference_path: Path,
    iterations: int,
    tracker: StageTracker,
    voice_provider: SpeechBrainProvider,
) -> tuple[list[IterationMetric], list[float]]:
    """Run the real DSP -> SpeechBrain -> Ollama sequence repeatedly."""
    waveform = load_waveform(reference_path)
    ollama = OllamaService()
    metrics: list[IterationMetric] = []
    reference_embedding: list[float] | None = None

    for iteration in range(1, iterations + 1):
        lifecycle_started = perf_counter()
        dsp_ms: float | None = None
        speech_ms: float | None = None
        ollama_ms: float | None = None
        replay_detected: bool | None = None
        speaker_score: float | None = None
        risk_tier: str | None = None
        error: str | None = None
        logger.info(
            "Starting transaction benchmark iteration {}/{}.", iteration, iterations
        )
        try:
            stage_started = perf_counter()
            with tracker.activate("DSP_REPLAY_FILTER", iteration):
                replay_detected = await asyncio.to_thread(
                    detect_replay_attack, str(reference_path)
                )
            dsp_ms = (perf_counter() - stage_started) * 1000.0

            stage_started = perf_counter()
            with tracker.activate("SPEECHBRAIN_VECTOR_EXTRACTION", iteration):
                embedding = await extract_speaker_embedding(voice_provider, waveform)
            speech_ms = (perf_counter() - stage_started) * 1000.0
            if reference_embedding is None:
                reference_embedding = embedding
            speaker_score = normalized_similarity(reference_embedding, embedding)

            stage_started = perf_counter()
            with tracker.activate("OLLAMA_RISK_INFERENCE", iteration):
                decision = await ollama.evaluate_transaction_context(
                    amount=150.0,
                    speaker_score=speaker_score,
                    face_score=0.0,
                    liveness_score=0.0,
                    is_replay=bool(replay_detected),
                    network_country="India",
                )
            ollama_ms = (perf_counter() - stage_started) * 1000.0
            risk_tier = str(decision["risk_tier"])
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            logger.exception("Pipeline iteration {} failed.", iteration)

        metrics.append(
            IterationMetric(
                iteration=iteration,
                cold_start=iteration == 1,
                dsp_latency_ms=dsp_ms,
                speechbrain_latency_ms=speech_ms,
                ollama_latency_ms=ollama_ms,
                end_to_end_latency_ms=(perf_counter() - lifecycle_started) * 1000.0,
                replay_detected=replay_detected,
                speaker_score=speaker_score,
                risk_tier=risk_tier,
                error=error,
            )
        )

    if reference_embedding is None:
        raise RuntimeError("No SpeechBrain reference embedding was produced.")
    return metrics, reference_embedding


async def run_acoustic_experiment(
    reference_path: Path,
    impostor_paths: Sequence[Path],
    reference_embedding: Sequence[float],
    trials: int,
    seed: int,
    tracker: StageTracker,
    voice_provider: SpeechBrainProvider,
) -> list[AcousticMetric]:
    """Measure real embedding stability across controlled degradations."""
    sources = [("genuine", reference_path), *[("impostor", p) for p in impostor_paths]]
    conditions = ("A_CLEAN_BASELINE", "B_AMBIENT_NOISE", "C_CLIPPED_SATURATION")
    metrics: list[AcousticMetric] = []

    with TemporaryDirectory(prefix="vocalpay_acoustic_") as temp_directory:
        temp_root = Path(temp_directory)
        for source_index, (subject_class, source_path) in enumerate(sources):
            waveform = load_waveform(source_path)
            for condition_index, condition in enumerate(conditions):
                for trial in range(1, trials + 1):
                    rng = np.random.default_rng(
                        seed + source_index * 100_000 + condition_index * 1_000 + trial
                    )
                    transformed = degrade_waveform(waveform, condition, rng)
                    transient_path = temp_root / (
                        f"{subject_class}_{source_index}_{condition}_{trial}.wav"
                    )
                    sf.write(
                        transient_path,
                        transformed,
                        ANALYSIS_SAMPLE_RATE,
                        subtype="FLOAT",
                    )
                    replay: bool | None = None
                    similarity: float | None = None
                    extraction_ms: float | None = None
                    error: str | None = None
                    try:
                        with tracker.activate("DSP_ACOUSTIC_DIAGNOSTIC", None):
                            replay = await asyncio.to_thread(
                                detect_replay_attack, str(transient_path)
                            )
                        started = perf_counter()
                        with tracker.activate(
                            f"SPEECHBRAIN_ACOUSTIC_{condition}", None
                        ):
                            embedding = await extract_speaker_embedding(
                                voice_provider, transformed
                            )
                        extraction_ms = (perf_counter() - started) * 1000.0
                        similarity = normalized_similarity(
                            reference_embedding, embedding
                        )
                    except Exception as exc:
                        error = f"{type(exc).__name__}: {exc}"
                        logger.exception(
                            "Acoustic trial failed for {} / {} / {}.",
                            subject_class,
                            condition,
                            trial,
                        )
                    metrics.append(
                        AcousticMetric(
                            subject_class=subject_class,
                            source_file=str(source_path),
                            condition=condition,
                            trial=trial,
                            similarity_score=similarity,
                            dsp_replay_detected=replay,
                            extraction_latency_ms=extraction_ms,
                            error=error,
                        )
                    )
    return metrics


def evaluate_thresholds(metrics: Sequence[AcousticMetric]) -> list[ThresholdMetric]:
    """Calculate empirical FRR and FAR without inventing missing impostor data."""
    results: list[ThresholdMetric] = []
    conditions = sorted({metric.condition for metric in metrics})
    for condition in conditions:
        genuine_scores = [
            metric.similarity_score
            for metric in metrics
            if metric.condition == condition
            and metric.subject_class == "genuine"
            and metric.similarity_score is not None
        ]
        impostor_scores = [
            metric.similarity_score
            for metric in metrics
            if metric.condition == condition
            and metric.subject_class == "impostor"
            and metric.similarity_score is not None
        ]
        for threshold in THRESHOLDS:
            false_rejections = sum(score < threshold for score in genuine_scores)
            false_acceptances = sum(score >= threshold for score in impostor_scores)
            results.append(
                ThresholdMetric(
                    condition=condition,
                    threshold=threshold,
                    genuine_trials=len(genuine_scores),
                    impostor_trials=len(impostor_scores),
                    false_rejections=false_rejections,
                    false_acceptances=false_acceptances,
                    frr=(
                        (false_rejections / len(genuine_scores))
                        if genuine_scores
                        else None
                    ),
                    far=(
                        (false_acceptances / len(impostor_scores))
                        if impostor_scores
                        else None
                    ),
                )
            )
    return results


def finite_values(metrics: Sequence[IterationMetric], attribute: str) -> list[float]:
    """Extract successful finite numeric measurements."""
    values: list[float] = []
    for metric in metrics:
        value = getattr(metric, attribute)
        if value is not None and math.isfinite(float(value)):
            values.append(float(value))
    return values


def latency_statistics(
    metrics: Sequence[IterationMetric], attribute: str
) -> tuple[float | None, float | None, int]:
    """Return arithmetic mean, population standard deviation, and sample count."""
    values = finite_values(metrics, attribute)
    if not values:
        return None, None, 0
    return statistics.fmean(values), statistics.pstdev(values), len(values)


def fmt_number(value: float | None, digits: int = 2) -> str:
    """Format an optional measurement for CSV/Markdown output."""
    return "N/A" if value is None else f"{value:.{digits}f}"


def export_csv(
    output_path: Path,
    iterations: Sequence[IterationMetric],
    samples: Sequence[ResourceSample],
    acoustic: Sequence[AcousticMetric],
    thresholds: Sequence[ThresholdMetric],
    overlap_count: int,
    overlap_ms: float,
    tracker_overlap_attempts: int,
) -> None:
    """Write every raw and derived observation into one typed long-form CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "record_type",
        "timestamp_epoch_s",
        "elapsed_ms",
        "iteration",
        "cold_start",
        "stage",
        "process_rss_mb",
        "system_ram_used_mb",
        "system_ram_percent",
        "cpu_percent",
        "gpu_vram_used_mb",
        "gpu_vram_total_mb",
        "gpu_vram_percent",
        "dsp_latency_ms",
        "speechbrain_latency_ms",
        "ollama_latency_ms",
        "end_to_end_latency_ms",
        "replay_detected",
        "speaker_score",
        "risk_tier",
        "subject_class",
        "source_file",
        "condition",
        "trial",
        "similarity_score",
        "extraction_latency_ms",
        "threshold",
        "genuine_trials",
        "impostor_trials",
        "false_rejections",
        "false_acceptances",
        "frr",
        "far",
        "overlap_count",
        "overlap_ms",
        "tracker_overlap_attempts",
        "configured_speaker_threshold",
        "vram_ceiling_mb",
        "vram_ceiling_compliant",
        "error",
    ]

    def write_record(
        writer: csv.DictWriter[str], record_type: str, data: dict[str, Any]
    ) -> None:
        row = {name: "" for name in fieldnames}
        row["record_type"] = record_type
        row.update({key: value for key, value in data.items() if key in row})
        writer.writerow(row)

    with output_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for metric in iterations:
            write_record(writer, "pipeline_iteration", asdict(metric))
        for sample in samples:
            write_record(writer, "resource_sample", asdict(sample))
        for metric in acoustic:
            data = asdict(metric)
            data["replay_detected"] = data.pop("dsp_replay_detected")
            write_record(writer, "acoustic_trial", data)
        for metric in thresholds:
            write_record(writer, "threshold_summary", asdict(metric))
        write_record(
            writer,
            "concurrency_summary",
            {
                "overlap_count": overlap_count,
                "overlap_ms": overlap_ms,
                "tracker_overlap_attempts": tracker_overlap_attempts,
                "configured_speaker_threshold": settings.SPEAKER_PASS_THRESHOLD,
                "vram_ceiling_mb": VRAM_CEILING_MB,
                "vram_ceiling_compliant": (
                    max(
                        (
                            sample.gpu_vram_used_mb
                            for sample in samples
                            if sample.gpu_vram_used_mb is not None
                        ),
                        default=None,
                    )
                    <= VRAM_CEILING_MB
                    if any(sample.gpu_vram_used_mb is not None for sample in samples)
                    else "UNMEASURED"
                ),
            },
        )


def print_summary(
    iterations: Sequence[IterationMetric],
    samples: Sequence[ResourceSample],
    thresholds: Sequence[ThresholdMetric],
    overlap_count: int,
    overlap_ms: float,
    nvml_available: bool,
    output_path: Path,
) -> None:
    """Print copy-ready Markdown tables with explicit statistical definitions."""
    stage_rows = (
        ("CPU DSP replay filter", "dsp_latency_ms"),
        ("SpeechBrain extraction", "speechbrain_latency_ms"),
        ("Ollama risk inference", "ollama_latency_ms"),
        ("End-to-end lifecycle", "end_to_end_latency_ms"),
    )
    print("\n## VocalPay Experimental Summary\n")
    print(
        "Population standard deviation (σ) is computed over successful measured trials.\n"
    )
    print("| Stage | n | Mean μ (ms) | Std. dev. σ (ms) |")
    print("|---|---:|---:|---:|")
    for label, attribute in stage_rows:
        mean_value, deviation, count = latency_statistics(iterations, attribute)
        print(
            f"| {label} | {count} | {fmt_number(mean_value)} | "
            f"{fmt_number(deviation)} |"
        )

    peak_rss = max((sample.process_rss_mb for sample in samples), default=None)
    gpu_values = [
        sample.gpu_vram_used_mb
        for sample in samples
        if sample.gpu_vram_used_mb is not None
    ]
    peak_vram = max(gpu_values) if gpu_values else None
    vram_compliance = (
        "PASS" if peak_vram is not None and peak_vram <= VRAM_CEILING_MB else "FAIL"
    )
    if peak_vram is None:
        vram_compliance = "UNMEASURED"
    print("\n| Resource/isolation metric | Result |")
    print("|---|---:|")
    print(f"| Peak benchmark-process RSS (MB) | {fmt_number(peak_rss)} |")
    print(f"| Peak device VRAM used (MB) | {fmt_number(peak_vram)} |")
    print(f"| NVML telemetry available | {'Yes' if nvml_available else 'No'} |")
    print(f"| 4096 MB VRAM ceiling result | {vram_compliance} |")
    print(f"| Cross-model interval overlaps | {overlap_count} |")
    print(f"| Total cross-model overlap (ms) | {overlap_ms:.6f} |")

    print("\n| Condition | Threshold | Genuine n | Impostor n | FRR | FAR |")
    print("|---|---:|---:|---:|---:|---:|")
    for metric in thresholds:
        print(
            f"| {metric.condition} | {metric.threshold:.2f} | "
            f"{metric.genuine_trials} | {metric.impostor_trials} | "
            f"{fmt_number(metric.frr, 4)} | {fmt_number(metric.far, 4)} |"
        )
    if all(metric.far is None for metric in thresholds):
        print(
            "\nFAR is N/A because no impostor audio was supplied. "
            "Provide independent non-enrolled speakers for a defensible FAR estimate."
        )
    print(
        "\nConfigured production speaker threshold: "
        f"`{settings.SPEAKER_PASS_THRESHOLD:.2f}`. The `0.72` rows are an "
        "experimental candidate threshold and must not be described as deployed "
        "unless the production configuration is changed and revalidated."
    )
    print(f"\nRaw dataset: `{output_path.resolve()}`")


async def async_main(args: argparse.Namespace) -> None:
    """Execute all experiment phases and guarantee provider cleanup."""
    validate_args(args)
    if not math.isclose(settings.SPEAKER_PASS_THRESHOLD, 0.72, abs_tol=1e-9):
        logger.warning(
            "Experimental 0.72 threshold differs from deployed threshold {:.2f}.",
            settings.SPEAKER_PASS_THRESHOLD,
        )
    random.seed(args.seed)
    np.random.seed(args.seed)
    tracker = StageTracker()
    monitor = ResourceMonitor(tracker, args.gpu_index)
    voice_provider = SpeechBrainProvider(_device="cpu")
    monitor.start()
    try:
        iterations, reference_embedding = await run_pipeline_trials(
            args.reference_audio,
            args.iterations,
            tracker,
            voice_provider,
        )
        acoustic = await run_acoustic_experiment(
            args.reference_audio,
            args.impostor_audio,
            reference_embedding,
            args.degradation_trials,
            args.seed,
            tracker,
            voice_provider,
        )
    finally:
        monitor.stop()
        await voice_provider.shutdown()

    thresholds = evaluate_thresholds(acoustic)
    overlap_count, overlap_ms = calculate_overlap(tracker.intervals)
    export_csv(
        args.output,
        iterations,
        monitor.samples,
        acoustic,
        thresholds,
        overlap_count,
        overlap_ms,
        tracker.overlap_attempts,
    )
    print_summary(
        iterations,
        monitor.samples,
        thresholds,
        overlap_count,
        overlap_ms,
        monitor.nvml_available,
        args.output,
    )


def main() -> None:
    """Run the asynchronous benchmark with research-safe failure reporting."""
    args = parse_args()
    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        logger.warning("VocalPay experiment interrupted by the operator.")
        raise SystemExit(130) from None
    except Exception as exc:
        logger.exception("VocalPay experiment failed: {}", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
