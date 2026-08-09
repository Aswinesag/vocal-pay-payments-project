# VocalPay — System Architecture Specification

**Document Class:** Immutable System Blueprint
**Scope:** This document is the authoritative architectural specification for the VocalPay codebase. Any LLM coding agent, code-completion tool, or human contributor MUST read this document in full before proposing, generating, or modifying any code in this repository. Deviations from the constraints defined herein require an explicit, deliberate architectural decision — not an incidental one.

**Status note:** Section 3 ("AI Hardware Shortcut") documents a *locked design specification* for a component that is not yet implemented in the current codebase (no `librosa`-based DSP gate module exists at the time of writing). It is recorded here as binding intent for future implementation, not as a description of shipped behavior. All other sections describe a mixture of already-implemented structure (database layer) and locked specification for scaffolded components (biometric services, agentic reasoning layer).

---

## 1. Executive Summary & Target Hardware

**Project Name:** VocalPay — A Secure Voice-based Financial Transaction System Using Multimodal Biometrics and Agentic AI Fraud Detection.

**Problem Domain:** VocalPay authenticates and authorizes financial transactions using a combination of voiceprint (speaker verification), facial biometrics, and an autonomous local LLM fraud-reasoning agent, without transmitting raw biometric data off-device and without relying on cloud-hosted inference.

### 1.1 Physical Hardware Ceiling

| Resource | Specification |
|---|---|
| CPU | Intel/AMD, laptop-class |
| System RAM | 16 GB |
| GPU | NVIDIA RTX 2050 Laptop GPU |
| VRAM | **Exactly 4 GB — hard ceiling, non-negotiable** |

This is not a soft target. The entire architecture is derived backward from the 4 GB VRAM ceiling. Any proposed change that increases peak VRAM residency, introduces concurrent GPU model residency, or assumes cloud/remote inference availability is architecturally non-compliant by default and must be rejected or explicitly re-scoped.

### 1.2 Core Mandate

1. **Maximize local edge inference.** No dependency on network-available inference endpoints for the core transaction path. The system must remain functional fully offline.
2. **Enforce zero cross-model VRAM concurrency.** At any given instant, at most one deep-learning model may hold CUDA-resident weights and activations. GPU-bound models are time-sliced, never parallelized against each other.
3. **Minimize memory footprint at every layer** — from the choice of a 3B-parameter local LLM over larger alternatives, to CPU-first pre-filtering before any GPU model is invoked, to lightweight embedding-based biometric storage instead of raw media retention.

---

## 2. System Directory Layout & Locked Data Tables

### 2.1 Locked File Structure

The following filenames and their responsibilities are **locked** and must not be renamed, merged, or restructured without an explicit architectural decision:

```
app/database/database.py    # SQLAlchemy 2.0 async engine, connection pool, session context providers
app/database/models.py      # SQLAlchemy 2.0 declarative ORM table mappings
app/database/schemas.py     # Pydantic v2 request/response validation models
app/database/crud.py        # Async Create/Read/Update/Delete persistence operations
```

The persistence layer is fully asynchronous: `database.py` exposes an async engine and an async session context manager (`get_db_session`), and `crud.py` operates exclusively through `AsyncSession`. No synchronous ORM session usage is permitted in the request path.

### 2.2 Biometric Privacy Constraint

Permanent user biometric identity is stored **exclusively as serialized numerical embedding vectors**, never as raw audio or image media:

- `User.speaker_embedding` — a JSON-serialized list of floats representing the voiceprint embedding (192-dimensional, consistent with ECAPA-TDNN / SpeechBrain-class speaker embedding models).
- `User.face_embedding` — a JSON-serialized list of floats representing the facial embedding (dimensionality determined by the InsightFace model variant in use).

No raw audio clips, waveform buffers, or facial imagery are persisted at rest under any circumstance. Any code path that writes raw audio bytes or image bytes to the `users` table, or to any permanent-storage table, is a privacy-architecture violation.

### 2.3 `PendingTransaction` — State-Freezing Ledger

Purpose: holds a transaction in a frozen, resumable state while it awaits MEDIUM or HIGH risk step-up verification. Rows in this table are **transient by design** — they are deleted on successful verification, on expiry, or on exhaustion of verification attempts, and must never be treated as permanent audit records.

| Field | Type | Purpose |
|---|---|---|
| `id` | Integer, PK | Surrogate key |
| `transaction_id` | String(64), unique, indexed | Client-facing correlation identifier across the initiate/verify boundary |
| `user_id` | String(64), FK → `users.user_id` | Owning user |
| `amount` | Float | Transaction amount under evaluation |
| `risk_level` | String(20) | Assigned tier: `MEDIUM` or `HIGH` (LOW resolves immediately and never reaches this table; CRITICAL is blocked before reaching this table) |
| `status` | String(30) | Lifecycle state, e.g. `PENDING_OTP`, `PENDING_CHALLENGE` |
| `verification_secret` | String(255) | The OTP digit string (MEDIUM) or the randomized challenge phrase (HIGH) the client must satisfy |
| `expires_at` | DateTime(tz-aware) | Hard 5-minute freeze window; enforced server-side on every `/verify` call |
| `speaker_score` | Float | Speaker-verification similarity captured at initiation |
| `face_score` | Float | Face-verification similarity captured at initiation |
| `fraud_score` | Float | Agentic risk-reasoning output captured at initiation |
| `replay_attack` | Boolean | Whether the DSP replay gate flagged the initiating audio (informational; CRITICAL results never reach this table) |
| `created_at` / `updated_at` | DateTime(tz-aware) | Standard timestamp mixin |

Indexes: `idx_pending_status` (status), `idx_pending_expires` (expires_at) — both required to keep expiry sweeps and status-based lookups cheap as pending volume grows.

### 2.4 `Transaction` — Permanent Audit Log Ledger

Purpose: the immutable financial record. A row is written here only once a transaction reaches a terminal resolved state (LOW auto-approval, or MEDIUM/HIGH successful step-up). This table is the system of record for compliance and mentor/reviewer audit purposes.

| Field | Type | Purpose |
|---|---|---|
| `id` | Integer, PK | Surrogate key |
| `transaction_id` | String(64), unique, indexed | Same identifier as its originating `PendingTransaction` row, where applicable |
| `user_id` | String(64), FK → `users.user_id` | Owning user |
| `amount` | Float | Final transacted amount |
| `status` | String(30) | Terminal status, e.g. `COMPLETED` |
| `risk_level` | String(20) | Final risk tier at resolution |
| `success` | Boolean | Whether the transaction was authorized |
| `speaker_score` / `face_score` / `fraud_score` | Float | Biometric and agentic scores at time of resolution |
| `xai_reason` | Text | The explainable-AI rationale string produced by the local agent — mandatory, never null, always human-readable |
| `processing_time_ms` | Float | End-to-end latency, retained for performance auditing on constrained hardware |
| `replay_attack` | Boolean | Historical flag carried through from initiation |
| `created_at` / `updated_at` | DateTime(tz-aware) | Standard timestamp mixin |

Indexes: `idx_transaction_status`, `idx_transaction_risk` — support reporting and dashboarding queries without full table scans.

**Auxiliary tables** (`FraudEvent`, `AuditLog`) exist as separate concerns: `FraudEvent` captures security-relevant blocks (e.g. CRITICAL replay-attack interceptions) independent of the transaction ledger, and `AuditLog` captures general request-level audit trail (endpoint, method, client IP, latency) independent of transaction outcome. These tables must not be conflated with `Transaction` — a blocked/fraudulent attempt is a `FraudEvent`, not a `Transaction`.

---

## 3. The AI Hardware Shortcut (CPU DSP Gatekeeper)

### 3.1 Rationale

Before any deep-learning model is loaded into system or GPU memory, a lightweight, CPU-bound digital signal processing (DSP) filter — implemented with `librosa` — screens the incoming audio for evidence of electronic playback (a speaker-replay spoofing attack). This gate is deliberately cheap: it must execute in negligible time on CPU alone, with zero GPU allocation, so that obviously fraudulent audio never triggers the expensive sequential biometric pipeline described in Section 4.

This is the primary VRAM-protection mechanism at the ingestion boundary: compute is rationed such that the most expensive resources (CUDA-resident models) are never invoked for input that a cheap heuristic can already reject.

### 3.2 Locked Detection Parameters

| Parameter | Threshold | Interpretation |
|---|---|---|
| Spectral Roll-off | **>= 4800 Hz** | Frequency below which a specified percentage (85%) of total spectral energy is contained. Replayed audio through consumer speaker hardware characteristically exhibits elevated roll-off values due to amplified high-frequency distortion artifacts introduced by the secondary recording path. |
| Spectral Centroid | **>= 2700 Hz** | The "center of mass" of the spectrum. Electronic playback and re-recording through a second microphone tends to introduce a brighter, more electronically-colored spectral centroid than natural live vocal production, shifting the energy distribution toward higher frequencies. |

**Detection rule:** if the analyzed audio segment exhibits spectral roll-off **at or above** the 4800 Hz threshold **in conjunction with** spectral centroid **at or above** the 2700 Hz threshold, the input is classified as a probable playback/replay artifact and the request is immediately escalated to **CRITICAL** risk.

**Implementation Reference:** These thresholds are enforced in `app/core/audio_dsp.py` as:
- `ROLLOFF_THRESHOLD = 4800.0`
- `CENTROID_THRESHOLD = 2700.0`

### 3.3 Enforcement Behavior

On CRITICAL classification via this gate:

- The request is hard-blocked with an HTTP 401 response.
- **No deep-learning model is invoked** — not InsightFace, not SpeechBrain, not Faster-Whisper, not the Ollama reasoning agent. This is a strict short-circuit, not a soft priority downgrade.
- A `FraudEvent` row is written (not a `Transaction` row) capturing `event_type = "REPLAY_ATTACK"`, `blocked = True`, and `replay_attack = True`.
- No `PendingTransaction` freeze occurs — CRITICAL is terminal and immediate.

Any future implementation of this gate must preserve this ordering guarantee: **DSP gate → (pass) → biometric pipeline**, never the reverse, and never in parallel.

---

## 4. Sequential Biometric Inference Pipeline

### 4.1 Model-to-Device Mapping

| Model | Device | Precision | Role |
|---|---|---|---|
| InsightFace | CUDA (`onnxruntime-gpu`) | Default ONNX precision | Facial embedding extraction / liveness-adjacent similarity scoring |
| SpeechBrain | CPU | Default | Speaker embedding extraction / voiceprint similarity scoring (ECAPA-TDNN class model) |
| Faster-Whisper | CUDA | **FP16** | Challenge-phrase transcription, invoked only during HIGH-risk Step 2 verification |

FP16 precision for Faster-Whisper is a deliberate VRAM-reduction choice — half the activation and weight memory footprint of FP32 — and must not be silently upgraded to FP32 without re-validating peak VRAM usage against the 4 GB ceiling.

### 4.2 Memory Isolation Mandate

The following rule is **immutable**: deep-learning models must be executed **sequentially**, wrapped in thread-safe locking, and must **never** hold concurrent residency such that two or more models are simultaneously allocated on the GPU.

Concretely:

- InsightFace inference must fully complete (including releasing any intermediate CUDA allocations it does not need to retain) before SpeechBrain or Faster-Whisper inference begins.
- SpeechBrain, although CPU-bound, is still included in the sequential lock ordering — the constraint is about deterministic, non-overlapping pipeline stages, not exclusively about GPU contention. This avoids unpredictable system RAM pressure spikes when CPU and GPU stages overlap on a 16 GB RAM ceiling.
- Faster-Whisper (CUDA, FP16) is only ever invoked during the HIGH-risk Step 2 `/verify` call, and only after any prior GPU model from the same request lifecycle has released its allocation.
- The lock construct guarding model invocation must be thread-safe and must serialize access across concurrent incoming requests, not just within a single request — two simultaneous HIGH-risk verifications must not be permitted to run Faster-Whisper concurrently.

Any code proposing `asyncio.gather`, thread pools, or process pools that would allow two GPU-bound model calls to execute concurrently is non-compliant and must be rejected.

---

## 5. Native Agentic Risk Matrix & 2-Step Lifecycle

### 5.1 Local Agent Framework Constraint

The fraud-reasoning agent is a stock, locally-hosted **Ollama `Llama-3.2-3B`** model. Its integration is deliberately minimal:

- **Prompt engineering only.** All reasoning behavior is achieved through carefully structured prompts against the base model — no fine-tuning, no adapters, assumed for this specification.
- **Native JSON grammar / structured output mode** is used to constrain the model's output to a well-formed JSON object (risk tier + XAI rationale string), rather than relying on post-hoc text parsing of free-form generation.
- **No orchestration frameworks.** LangChain, CrewAI, and similar multi-agent/tool-orchestration frameworks are explicitly excluded. These frameworks carry non-trivial Python-process memory overhead and abstraction layers that work against the system RAM and VRAM discipline mandated in Section 1. The agent is invoked as a single, direct call against the local Ollama server per transaction — not as a multi-step autonomous tool-using loop.

### 5.2 The Four Risk Tiers

| Tier | Resolution Path | Downstream Action |
|---|---|---|
| **LOW** | Immediate | Transaction auto-approved and written directly to the `Transaction` ledger. No freeze, no step-up. |
| **MEDIUM** | Step-up required | `PendingTransaction` frozen with `status = PENDING_OTP`; 6-digit numeric OTP generated and stored server-side as `verification_secret`. |
| **HIGH** | Step-up required | `PendingTransaction` frozen with `status = PENDING_CHALLENGE`; randomized text challenge phrase generated and stored server-side as `verification_secret`. |
| **CRITICAL** | Immediate hard block | Request rejected with HTTP 401 at the DSP gate (Section 3) or post-biometric fraud-reasoning stage; recorded as a `FraudEvent`, never a `Transaction`. |

Risk-tier assignment is produced by the agentic reasoning stage (Section 5.1) evaluating the biometric telemetry (`speaker_score`, `face_score`) from Section 4, except for CRITICAL classifications originating from the Section 3 DSP gate, which bypass the agent entirely.

### 5.3 Stateless 2-Step API Lifecycle

The system exposes exactly two endpoints governing the transaction lifecycle. The lifecycle is **stateless between steps** — no in-memory session state is held across the two calls; all resumable context is persisted to and rehydrated from SQLite via `crud.py`.

#### Step 1 — `POST /api/v1/transaction/initiate`

Ingests `user_id`, `amount`, live audio, and a photo. Executes, in strict order:

1. CPU DSP replay gate (Section 3) — CRITICAL short-circuits here.
2. Sequential biometric pipeline (Section 4) — InsightFace → SpeechBrain.
3. Agentic risk reasoning (Section 5.1) over the resulting biometric telemetry.
4. Branch on assigned tier:
   - **LOW** → write `Transaction`, return success immediately.
   - **MEDIUM / HIGH** → write `PendingTransaction` via `crud.py` with a 5-minute `expires_at` window, then the connection is dropped. The client does not hold an open connection awaiting step-up; it must reconnect for Step 2.

#### Step 2 — `POST /api/v1/transaction/verify`

Client submits `transaction_id` plus proof of step-up. Server queries `crud.py` to rehydrate the frozen `PendingTransaction` context. Behavior branches on the persisted `status`:

- **`PENDING_OTP` (MEDIUM):** the submitted OTP is validated via direct string comparison against `verification_secret`. No model inference occurs on this path — it is intentionally the cheapest possible verification path.
- **`PENDING_CHALLENGE` (HIGH):** a freshly submitted voice clip is transcribed via Faster-Whisper (CUDA, FP16 — Section 4.1) and string-matched against the persisted challenge phrase in `verification_secret`.

On successful verification (either path):
- A `Transaction` row is written to the permanent ledger with `xai_reason` explaining the resolution path.
- The originating `PendingTransaction` row is deleted, invalidating the `transaction_id`/secret pair to prevent verification-token replay.

On expiry (`expires_at` has passed) or on exhaustion of verification attempts, the `PendingTransaction` row is deleted without producing a `Transaction` row, and the transaction is terminally failed — the client must re-initiate from Step 1 if they wish to retry.

---

## Compliance Note for LLM Agents and Code-Completion Tools

Before generating or modifying code in this repository, an agent must confirm the following invariants hold for its proposed change:

1. Does it preserve the locked filenames in `app/database/` (Section 2.1)?
2. Does it avoid persisting raw audio or image bytes anywhere permanent (Section 2.2)?
3. Does it preserve the CPU-gate-before-GPU-model ordering (Section 3.3)?
4. Does it avoid introducing concurrent GPU model residency (Section 4.2)?
5. Does it avoid introducing LangChain/CrewAI-class orchestration overhead (Section 5.1)?
6. Does it preserve the stateless, disk-persisted 2-step lifecycle contract (Section 5.3)?

If the answer to any of the above is "no," the proposed change is out of specification and must not be merged without an explicit, recorded architectural decision superseding this document.
