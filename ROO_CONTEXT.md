# ROO_CONTEXT.md — VocalPay System Anchoring File

**Document Status:** Permanent System Constraints Registry  
**Created:** 2026-08-08  
**Purpose:** This file permanently preserves the strict hardware boundaries, inference execution rules, and architectural constraints for all future Claude sessions and development work on the VocalPay codebase.

---

## 1. Target Machine Hardware Constraints (NON-NEGOTIABLE)

### 1.1 Physical Hardware Ceiling

| Component | Specification | Constraint Level |
|-----------|--------------|------------------|
| **GPU** | NVIDIA RTX 2050 Laptop GPU | Fixed |
| **VRAM** | **4 GB (hard ceiling)** | **NON-NEGOTIABLE** |
| **System RAM** | 16 GB | Fixed |
| **CPU** | Intel/AMD laptop-class | Variable |

**CRITICAL BOUNDARY:** The 4 GB VRAM ceiling is an immutable constraint. Every architectural decision, model selection, precision choice, and inference scheduling pattern is derived backward from this hard limit. Any code change that increases peak VRAM residency, introduces concurrent GPU model loading, or assumes elastic cloud resources is **architecturally non-compliant by design**.

### 1.2 Consequence: Zero Cross-Model VRAM Concurrency

At any given instant, **at most one deep-learning model** may hold CUDA-resident weights and activations. GPU-bound models must be **time-sliced sequentially**, never parallelized against each other. This constraint is enforced at the application layer through a global asyncio Lock in `app/core/inference_coordinator.py`.

---

## 2. Inference Isolation Guardrails

### 2.1 Sequential Serialization Lock

**Implementation:** `app/core/inference_coordinator.py::isolate_model_inference(stage: str)`

All deep-learning model inference operations **MUST** execute within the global `isolate_model_inference()` async context manager. This lock ensures:

1. **Thread-safe serialization** across concurrent incoming requests
2. **No overlapping GPU model residency** between InsightFace, Faster-Whisper, and any future CUDA models
3. **Deterministic memory pressure** by preventing unpredictable CPU+GPU overlap spikes on 16 GB system RAM

**Enforcement Rule:** Any code path that invokes a deep-learning model (biometric providers, ASR services, LLM agents) without wrapping the call in `isolate_model_inference()` is a compliance violation.

### 2.2 Model-to-Device Mapping (Locked Configuration)

| Model | Device | Precision | Justification |
|-------|--------|-----------|---------------|
| **SpeechBrain** (`speechbrain/spkrec-ecapa-voxceleb`) | **CPU** | Default | Voiceprint extraction is CPU-bound to free VRAM for other models |
| **InsightFace** (`buffalo_l`) | **CUDA** | Default ONNX | Facial embedding extraction requires CUDA via `onnxruntime-gpu` with `CUDAExecutionProvider` |
| **Faster-Whisper** (`small.en`) | **CUDA** | **FP16** | FP16 precision halves VRAM footprint vs. FP32; only loaded during HIGH-risk Step 2 verification |
| **Ollama** (`llama3.2:3b`) | **Mixed** | Default | Local inference server manages its own memory; invoked as external HTTP service |

**Precision Lock:** Faster-Whisper's FP16 precision is a deliberate VRAM optimization and must not be silently upgraded to FP32 without re-validating peak memory usage against the 4 GB ceiling.

---

## 3. Conversational Transaction Ingestion Rules

### 3.1 Voice-Driven `/initiate` Endpoint Contract

**Endpoint:** `POST /api/v1/transactions/initiate`

**Input:** Audio file ONLY (no explicit user_id, no separate amount parameter)

**Automated Resolution Workflow:**

1. **Amount Extraction:** The transaction amount is automatically extracted from the spoken audio via:
   - Faster-Whisper transcription (CUDA, FP16)
   - NLP-based amount parser (`_extract_transaction_amount()`) supporting:
     - Numeric literals: `₹250`, `$1,234.56`
     - Verbal number words: `"five hundred rupees"`, `"two thousand dollars"`
     - Indian numbering: `"one lakh"`, `"fifty thousand"`

2. **User Identity Resolution:** The user's identity is automatically resolved via:
   - Global database voiceprint sweep across all enrolled users
   - SpeechBrain (CPU) speaker embedding extraction from live audio
   - Cosine similarity scoring against every `User.speaker_embedding` in the database
   - Best match selected if score >= `SPEAKER_PASS_THRESHOLD` (default: 0.75)

3. **Risk-Based Branching:**
   - **Amount >= 500.00:** Immediate mandatory step-up (HTTP 403), regardless of biometric scores
   - **Amount < 500.00:** Ollama agent evaluates biometric telemetry and assigns risk tier

### 3.2 Hard Safety Gate: Mandatory Step-Up at ₹500 Threshold

**Rule:** If the extracted amount >= 500.00, the system **MUST** forcefully trigger an HTTP 403 step-up response, freezing the transaction as `PENDING_CHALLENGE` and requiring secondary verification (OTP or facial biometric).

**Rationale:** High-value transactions demand explicit user confirmation beyond passive voiceprint matching to prevent accidental authorization of large transfers.

**Implementation:** `app/api/v1/endpoints/transaction.py::initiate_transaction()`, lines 202-228

---

## 4. CPU DSP Gatekeeper (Pre-Inference Replay Detection)

### 4.1 Ordering Guarantee

**Locked Execution Order:** DSP Gate → (pass) → Biometric Pipeline

The CPU-bound digital signal processing (DSP) replay detection gate (`app/core/audio_dsp.py::detect_replay_attack()`) executes **before any deep-learning model is loaded**. This is the primary VRAM-protection mechanism at the ingestion boundary.

### 4.2 Detection Parameters

| Parameter | Threshold | Interpretation |
|-----------|-----------|----------------|
| **Spectral Roll-off** | >= 4800 Hz | Frequency below which 85% of spectral energy is contained. Replayed audio through consumer speakers compresses high-frequency content. |
| **Spectral Centroid** | >= 2700 Hz | The "center of mass" of the spectrum. Electronic playback through second-stage microphones brightens the spectral signature. |

**Detection Rule:** If `(mean_rolloff >= 4800 Hz) AND (mean_centroid >= 2700 Hz)`, classify as **CRITICAL replay attack**.

### 4.3 CRITICAL Short-Circuit Behavior

On CRITICAL classification:
- HTTP 401 response immediately returned
- **NO deep-learning models are invoked** (InsightFace, SpeechBrain, Faster-Whisper, Ollama)
- `FraudEvent` row written with `event_type = "REPLAY_ATTACK"`, `blocked = True`
- No `PendingTransaction` freeze occurs (CRITICAL is terminal)

---

## 5. Post-Response Memory Cleaning Protocol

### 5.1 Global Background Task Hook

**Implementation:** `app/main.py::schedule_memory_optimization()` middleware (lines 68-80)

Every HTTP request automatically schedules a `optimize_hardware_memory()` background task **after response delivery**. This ensures that:

1. Python garbage collection runs (`gc.collect()`)
2. CUDA cache is purged (`torch.cuda.empty_cache()`)
3. VRAM telemetry is logged for monitoring

### 5.2 Memory Optimization Function

**Implementation:** `app/core/memory_manager.py::optimize_hardware_memory()`

Returns telemetry including:
- `ram_usage_percent`
- `vram_allocated_mb`, `vram_peak_mb`, `vram_total_mb`, `vram_available_mb`
- `collected_blocks` (Python GC)

**Rationale:** On a 4 GB VRAM constraint, aggressive post-request cleanup prevents memory fragmentation and ensures the next request starts with maximum available memory headroom.

---

## 6. Database & State Persistence Layer

### 6.1 Async SQLite Configuration

**Engine:** SQLAlchemy 2.0 + aiosqlite  
**Location:** `app/database/database.py`

All database operations are **fully asynchronous**. No synchronous ORM sessions are permitted in the request path.

### 6.2 Biometric Privacy Constraint (Zero Raw Media Retention)

**Rule:** User biometric identity is stored **exclusively as JSON-serialized numerical embedding vectors**. No raw audio clips, waveform buffers, or facial imagery are persisted at rest.

**Locked Storage Schema:**
- `User.speaker_embedding`: JSON list of 192 floats (SpeechBrain ECAPA-TDNN)
- `User.face_embedding`: JSON list of N floats (InsightFace buffalo_l normalized embedding)

Any code path that writes raw audio bytes or image bytes to the `users` table or any permanent-storage table is a **privacy-architecture violation**.

### 6.3 Stateless 2-Step Transaction Lifecycle

The system exposes exactly two endpoints:

1. **Step 1:** `POST /api/v1/transactions/initiate` — Ingest audio, resolve identity, assign risk, freeze if MEDIUM/HIGH
2. **Step 2:** `POST /api/v1/transactions/verify` — Consume OTP or biometric challenge exactly once

**Stateless Guarantee:** No in-memory session state is held between steps. All resumable context is persisted to and rehydrated from SQLite via `app/database/crud.py`.

**Transaction Freeze Table:** `PendingTransaction` (transient, 5-minute `expires_at` window)  
**Permanent Audit Ledger:** `Transaction` (immutable financial record)

---

## 7. Agentic Risk Reasoning Constraints

### 7.1 Local Agent Framework

**Model:** Ollama `llama3.2:3b`  
**Integration:** Direct HTTP client (no LangChain, no CrewAI, no multi-agent frameworks)

**Rationale:** Orchestration frameworks carry non-trivial Python-process memory overhead that works against system RAM discipline. The agent is invoked as a single, direct call against the local Ollama server per transaction.

### 7.2 Native JSON Structured Output

The agent uses Ollama's `format="json"` parameter to constrain output to well-formed JSON:

```json
{
  "risk_tier": "LOW|MEDIUM|HIGH|CRITICAL",
  "explainable_ai_rationale": "concise evidence-based explanation"
}
```

No post-hoc text parsing of free-form generation is performed.

---

## 8. Compliance Checklist for Future Code Changes

Before generating or modifying code, confirm:

1. ✅ Preserves locked filenames in `app/database/` (database.py, models.py, schemas.py, crud.py)
2. ✅ Avoids persisting raw audio or image bytes anywhere permanent
3. ✅ Preserves CPU-gate-before-GPU-model ordering (DSP first, then biometrics)
4. ✅ Avoids introducing concurrent GPU model residency (no `asyncio.gather` on GPU models)
5. ✅ Avoids introducing LangChain/CrewAI-class orchestration overhead
6. ✅ Preserves stateless, disk-persisted 2-step lifecycle contract
7. ✅ Respects the 4 GB VRAM ceiling in all model selection and precision choices

---

## 9. Future Session Continuity Protocol

**For Claude/Cline AI Sessions:**

1. **Always read this file first** when resuming work on VocalPay codebase
2. Cross-reference architectural decisions against Section 8 compliance checklist
3. When proposing model upgrades or precision changes, explicitly validate peak VRAM usage
4. When proposing concurrency patterns, confirm compatibility with `isolate_model_inference()` serialization lock
5. When modifying transaction endpoints, preserve the stateless 2-step freeze/verify contract

---

**End of ROO_CONTEXT.md**
