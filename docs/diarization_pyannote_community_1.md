# Governed pyannote Community-1 Speaker Diarization — implementation and setup record

**Status: ENGINEERING SCAFFOLD COMPLETE, INACTIVE BY DESIGN.** Speaker diarization is **implemented, governed and NOT ACTIVE**. It is not production speech, not live-validated and not a statement of diarization quality. Genuine execution of `pyannote/speaker-diarization-community-1` on real audio is **NOT VERIFIED**: the adapter is proven with a deterministic fixture engine, and no model weights exist in any environment used. The optional dependency group HAS been verified to install and import in an isolated `/tmp` environment (dependency tier, 2026-11-15; see §4). No model was downloaded, no paid call was made, no candidate audio was used or stored, and all existing authorization constants remain False. Owner decisions recorded 2026-11-15 as `OD-DIAR-01..04` in `docs/production/OWNER_DECISION_REGISTER.md`.

- Source decision record: `.kilo/plans/1794737231163-pyannote-community1-diarization-feasibility.md` (feasibility analysis, 2026-11-15).
- Predecessor pattern reused: `docs/capstone/speech/W12_4E_GOVERNED_SPEECH_PROVIDERS.md` (the governed Whisper STT / Kyutai TTS scaffold).

## 1. Summary of changes

| File | Change |
|---|---|
| `src/speech/policy.py` | New code constants `DIARIZATION_EXECUTION_AUTHORIZED = False` and `DIARIZATION_CLOUD_AUTHORIZED = False`; new `DIARIZATION_PROVIDER_IDS = ("pyannote_community_1",)` and `SELECTED_DIARIZATION_PROVIDER`; `GENUINE_MODEL_VALIDATION` gains `"pyannote_community_1": "NOT_VERIFIED"`; new verified-capability entry `DIARIZATION_CAPABILITY` (licence, size, requirements, HF gating, scope: "who spoke when" only, no speaker identification or voice-trait analysis) |
| `src/speech/diarization.py` (new) | The governed adapter: typed `DiarizationTurn` / `DiarizationResult`, a `DiarizationEngine` protocol, a deterministic `FixtureDiarizationEngine`, a `LocalPyannoteEngine` that lazy-imports `pyannote.audio`/`torch` and only ever loads an **operator-placed** model directory, and `PyannoteCommunityDiarizationService` (authorization gate, transient-audio lifecycle, byte/duration/speaker-count bounds, hard timeout, controlled `SpeechError` categories). Telemetry is force-disabled on import (`PYANNOTE_METRICS_ENABLED=0` plus `set_telemetry_metrics(False)`) |
| `src/speech/runtime.py` | `SpeechRuntime` accepts a `diarization_engine` (defaults to `LocalPyannoteEngine()`); `readiness()` reports a separate, **inactive** `diarization` state (`configured=False`, `operational=False`, explicit blockers) next to the existing `stt`/`tts` states |
| `pyproject.toml` | New **optional** dependency group `[diarization]` (`pyannote.audio`, `torch`, `torchcodec`, `torchvision`), not installed in base/dev/CI installs |
| `scripts/eval_diarization.py` (new) | Offline contract evaluator, mirroring `eval_speech_providers.py`: proves the authorization gate, the fixture contract, refusal-before-execution, "never downloads", and transient-audio cleanup |
| `tests/test_speech_w12_4e.py` | The exact-value assertion on `GENUINE_MODEL_VALIDATION` was extended to include the new provider registration (`"pyannote_community_1": "NOT_VERIFIED"`). The assertion remains an exact equality; no other test changed |

## 2. What was installed — and what deliberately was not

Nothing new was installed into the running environment. The deliverable is a **declared, optional, inactive** integration. This distinction matters for the honesty rules of this repository: a declared dependency group with a fixture-validated adapter is engineering completion, not operational capability.

### 2.1 Declared dependency group (NOT installed)

New optional group in `pyproject.toml`; install only with an explicit `pip install -e ".[diarization]"` in an isolated environment before any activation work:

| Package | Version bound | Why it is in the set |
|---|---|---|
| `pyannote.audio` | `>=4.0.7,<4.1` | The toolkit that ships the `community-1` pretrained diarization pipeline. Floor 4.0.7 picks up batch-inference and `subfolder` loading fixes; the cap below 4.1 pins the reviewed 4.0 line (the "next" line drops Python 3.10 and changes the dependency surface) |
| `torch` | `>=2.5,<3.0` | The PyTorch runtime the pipeline executes on. Bounded so a verified compatible set can be pinned per environment before activation |
| `torchcodec` | `>=0.3,<2.0` | pyannote.audio 4.0 switched audio I/O from torchaudio to torchcodec; torchcodec requires the system `ffmpeg` binary. The 4.0.x line had to pin torch/torchcodec/torchaudio jointly to avoid a known segmentation fault (torchcodec issue #995), which is why the group is bounded and version-set verification is an activation prerequisite, not an afterthought |
| `torchvision` | (as resolved) | Part of the torch stack that is resolved together with the group so a single install produces a consistent, reviewed set instead of relying on transitive drift |

### 2.2 System requirements (activation-time, not installed now)

| Tool | Role | Rationale |
|---|---|---|
| `ffmpeg` (system binary) | Decoding backend for torchcodec; resamples arbitrary input to mono 16 kHz | pyannote.audio 4.0 removed the `soundfile`/`sox` backends — only `ffmpeg` or in-memory audio are supported |
| `git-lfs` (operator workstation) | One-time clone of the gated Hugging Face model repository to the operator model directory | `MODEL_DOWNLOADS_AUTHORIZED` stays False: weights are **placed by an operator after a resource decision**, never downloaded by the application |
| `SPEECH_DIARIZATION_MODEL_DIR` (operator environment) | Local path to the cloned `pyannote/speaker-diarization-community-1` repository | Keeps the app free of any Hugging Face token; `LocalPyannoteEngine.model_available()` checks the directory and never creates, mutates or downloads it |

### 2.3 The model itself (referenced, not downloaded)

| Item | Fact |
|---|---|
| Model | `pyannote/speaker-diarization-community-1` (revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee`) |
| Licence | Weights **CC-BY-4.0** ("will always remain freely accessible"); pyannote code MIT → self-hosting permitted with attribution |
| Size | ~34 MB total (segmentation 5.9 MB, embedding 26.6 MB, PLDA transforms ~0.3 MB) |
| Access | Gated (auto-approval): one operator accepts the user conditions once; the app never holds a token |
| Output | Regular speaker diarization **plus** `exclusive_speaker_diarization` (single speaker per instant — designed to reconcile STT word timestamps) |
| Scope | Diarization only. No voiceprinting, no speaker identification, no voice-trait analysis (those begin with the premium `precision-2/3` lines, which are out of scope) |

### 2.4 Development tooling used for validation (already present)

Tooling used to verify the scaffold, all existing dev tooling, installed only in the isolated runner (`uv run --project . --extra dev`): pytest 8.4.2, ruff, uv. No runtime dependency changed.

## 3. Rationale for the key design choices

1. **Optional `[diarization]` extra, lazily imported.** The torch stack is a ~2–3 GB footprint; the base application, CI and dev installs never import it (same pattern as `[speech]`, `[ocr]`, `[live]`). The base app's behaviour is byte-identical whether or not the extra is installed.
2. **A separate `DIARIZATION_EXECUTION_AUTHORIZED` code constant.** Existing tests assert the exact meaning of `SERVER_SPEECH_PROVIDERS_AUTHORIZED`, `WHISPER_API_TRANSPORT_AUTHORIZED`, `MODEL_DOWNLOADS_AUTHORIZED` and `VOICE_CLONING_ENABLED`; a distinct constant keeps those gates untouched while still making activation an owner-approved, reviewed code change that no Admin action, setting, request or environment variable can perform. `MODEL_DOWNLOADS_AUTHORIZED` remains False and the operator-placed-weights rule is preserved via the offline `Pipeline.from_pretrained(local_dir)` mode.
3. **Fixture engine + `BoundedRunner(1)`.** Contract tests run deterministically with no model, no weights and no network (CI-safe). One concurrent diarization at a time, with a hard wall-clock timeout, because the pipeline is CPU-heavy; over-bound requests are refused as `busy`, never queued silently.
4. **Transient-audio lifecycle reuse.** Candidate audio is validated, wrapped in `TransientAudio` (zeroed on discard), handed to the engine through `secure_tempfile` (0700 dir / 0600 file, overwritten and removed in `finally`), and discarded in all paths. The engine's `secure_tempfile` usage matches how the local Whisper engine consumes bytes; the observable `LIVE_TEMP_FILES` counter lets tests prove nothing is left behind.
5. **Telemetry force-disabled.** `pyannote.audio` reports pipeline origin and **file durations** when telemetry is enabled. The adapter sets `PYANNOTE_METRICS_ENABLED=0` on import and calls `set_telemetry_metrics(False, save_choice_as_default=True)` before loading the pipeline — fail-closed: no usage metadata about candidate sessions can leave the process.
6. **Bounded inputs.** 25 MB default byte bound, 2 h default duration bound, speaker counts validated to 1–10 with `min ≤ num ≤ max`. A duration is taken from the WAV header when parseable (the existing `audio_duration_seconds` helper); all other formats are bounded by size until a real decode happens inside the engine.
7. **Controlled error categories only.** Every failure surfaces as a `SpeechError` category (`not_authorized`, `empty`, `unsupported_mime`, `too_large`, `too_long`, `invalid_bounds`, `busy`, `timeout`, `model_unavailable`, `provider_error`); raw exception text (which could carry content) never reaches a user or a log line with content.
8. **No `return_embeddings`, no identifiers that trip the privacy gates.** The service never requests segment vectors from the pipeline; turns carry only start/end/speaker labels. Module vocabulary (`DiarizationTurn`, `speaker`) deliberately avoids the `voiceprint`/`speaker_embedding` identifiers that the project's privacy evaluators forbid.

## 4. Verification evidence (what was actually run)

| Check | Command (via `uv run --project . --extra dev`) | Result |
|---|---|---|
| Lint | `ruff check .` | All checks passed |
| Existing speech + scope tests | `pytest tests/test_speech_w12_4e.py tests/test_r1_scope_exclusions.py` (with `--extra db` for the migration test) | 74 passed |
| New contract evaluator | `python scripts/eval_diarization.py` | 5/5 checks PASS (authorization constant False, fixture contract, not-authorized runs nothing, local engine never downloads, transient-audio cleanup) |
| Import isolation | `SpeechRuntime()` readiness keys | `['diarization', 'stt', 'tts']`; the diarization state reports inactive with explicit blockers |
| Isolated-env dependency verification (OD-DIAR-01, dependency tier, 2026-11-15) | `uv venv --python 3.11 /tmp/kilo/dia-verify` + `uv pip install "pyannote.audio>=4.0.7,<4.1" "torch>=2.5,<3.0" "torchcodec>=0.3,<2.0" torchvision` | **PASS** — resolved `pyannote.audio 4.0.7`, `torch 2.15.0+cu132`, `torchcodec 0.17.0`, `torchvision 0.29.2`, `torchaudio 2.11.1` (Python 3.11.15; 5.8 GB with CUDA wheels — a CPU-only PyTorch index is the lean operator option); system `ffmpeg 6.1.1` present. Adapter checks with the real stack installed: `dependency_available() → True`; missing/empty `SPEECH_DIARIZATION_MODEL_DIR` → `model_available() → False`, directory never created, load refused as `ModelUnavailable` (no download attempted); telemetry helper callable, `PYANNOTE_METRICS_ENABLED` disabled; `DIARIZATION_EXECUTION_AUTHORIZED` False; genuine stays `NOT_VERIFIED` |

Not claimed: genuine pyannote execution, real-audio DER, inference latency, or readiness. `GENUINE_MODEL_VALIDATION["pyannote_community_1"]` stays `NOT_VERIFIED` until owner-authorised activation produces real evidence on the target host with synthetic data.

## 5. Expected impact

**Functionality — none today, capability later.** No candidate-facing surface changes: diarization is inactive, the Admin speech page and `/speech` routes are unchanged, and the runtime only exposes a read-only readiness state. After the owner decides to activate (flip the constant, place weights, add consent/disclosure surfaces and the recording-analysis feature), the product gains "who spoke when" attribution for uploaded practice recordings, with `exclusive_speaker_diarization` mapping naturally onto transcription timestamps.

**Performance — zero when inactive, understood when active.** Inactive: the runtime engine object does no work beyond a directory-existence check; lazy imports keep torch out of the process. When activated, published characteristics to plan capacity against (to be re-measured, never assumed): CPU real-time factor ≈ 0.9 (a 10-minute recording ≈ 8–9 CPU minutes — batch/async only), ~1–2 s of GPU-h100-class time per audio-hour, ~0.9 GB peak memory. `BoundedRunner(1)` bounds concurrency so a burst of requests cannot exhaust the host; the 2 h default bound caps worst-case wall time per call.

**Maintainability — the main win.** The new capability lives in one module beside the existing governed providers, reusing the proven `policy → engine → service → runtime` pattern, `TransientAudio`/`secure_tempfile`, `BoundedRunner` and the controlled-category error model instead of inventing a new one. A 5-check offline evaluator gate (`scripts/eval_diarization.py`) makes the invariants testable in CI without torch. The licence/attribution facts (CC-BY-4.0 + MIT, citations Plaquet & Bredin 2023, Wang et al. 2023, Landini et al. 2022) are recorded in `policy.DIARIZATION_CAPABILITY.notes` so a legal-review packet can be assembled without re-research.

## 6. Remaining owner decisions before any activation

1. **Proceed?** Activation is a reviewed code change flipping `DIARIZATION_EXECUTION_AUTHORIZED` (Admin cannot flip it; DI-E-014 pattern).
2. **First feature.** Recommended: async analysis of uploaded mock-interview recordings; not realtime, not dictation.
3. **Where weights live.** Operator model-directory decision (the resource decision that accompanies the weights placement rule).
4. **Legal/consent.** Voice-data processing disclosure and consent surfaces, in all seven language packs, before any candidate-facing use — plus legal review of the diarization scope statement above.
