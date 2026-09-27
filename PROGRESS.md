# Debate Lab implementation

Status: functioning core app implemented; verification partially complete. Speech model installation was approved and completed. The user supplied the hosted-search credential; it is stored privately and authenticated search plus result retrieval passed. Search remains opt-in per session. See docs/VERIFICATION.md for exact coverage.

## Confirmed clarifications (override original spec)
- Evidence optional; unsupported facts labeled unverified.
- Session-enabled search runs automatically within its limit.
- Even turn totals >=4; editable in draft or while paused until first closing dispatch. Preserve completed history and reserve both closings. Time/token limits unchanged.
- One active session globally. Pause before switching.

## Execution checklist
1. Establish persistence, transition and provider contracts; dependency isolation.
2. Durable controller and deterministic failure/recovery tests.
3. Real Ollama adapter and bounded capability checks.
4. Evidence modalities, provenance, safe URL retrieval and optional search.
5. React chamber/library/setup, controls, inspectors and exports.
6. Browser checks, real-model verification, limits calibration, launch documentation.

## Environment
Only BUILD_PROMPT.md and DEBATE_LAB_SPEC.md existed. Historical PDF absent.
Existing local API was read successfully after sandbox network approval; all three default model IDs are available. No inference tested yet. System Python is 3.9; use isolated Python 3.12 environment. FFmpeg/ffprobe not on current PATH. Historical initial state: no model downloads were authorized. User subsequently approved Whisper Small MLX only.

## Defaults and decisions
Original specification remains unchanged. Role prompts are versioned in prompts/. Runtime data defaults to .data/ in the project, excluded from source control; protected local_models path is rejected. Single backend process uses an OS advisory lock plus transactional revision checks. No cloud inference or fake fallback.

## Completed work
- React/TypeScript/Vite scholarly dark interface with real backend wiring and responsive inspector.
- FastAPI/SQLite controller, snapshots/events, command idempotency, model pinning, cancellation, recovery and exports.
- All source modality routes; isolated extraction, URL boundary, optional search adapter; media code installed without model weights.
- 35 backend tests passed, including real subprocess crash boundaries. Production frontend builds.
- Real four-turn smoke passed in ~182 seconds; real Pause/add instruction/Resume completed in ~171 seconds without duplicate turns.
- Live request cancellation passed for each default model; API-level cessation evidence only.
- Live Gemma vision identified red square and 42; public HTTPS fetch passed.
- Desktop/narrow browser checks passed; final transcript/inspector verification passed (2 browser tests total).

## Integration discoveries
- Installed Gemma endpoint rejects native structured format. Use prompt JSON, enforce top-level values, tolerate exact JSON fences, validate in Pydantic. No automatic model substitution.
- 16k context and 3072 generation allowance worked on a four-turn fixture. Judge used ~1900 generated tokens. Defaults adjusted but broad 12-turn calibration is still provisional.
- Speech model is now installed; real offline audio/video extraction passed. Search credential is now configured; one authenticated hosted-search request and its first public result fetch passed. Search remains disabled by default.

## Next resumable step
1. DONE: user approved Whisper Small MLX (~481 MB); downloaded revision 45f3915 into .data/auxiliary-models/whisper-small-mlx and checked selected-file checksums.
2. Normal launcher now detects the approved local speech model. Offline audio/video transcription and timestamps passed; Real Charlie vision/summary and shared video admission passed (~50s); browser timestamp navigation passed. All three current browser tests passed; no speech-model prerequisite remains.
3. DONE: supplied key stored in .data/secrets/ollama-search-key (0600, parent 0700); authenticated hosted search passed (three results) and first result retrieved using DNS/IP boundary checks. Successful shared evidence and quota/error behavior are tested deterministically.
4. Finish remaining acceptance matrix coverage and broaden calibration without overstating current readiness.

Launch: ./scripts/launch.sh ; http://127.0.0.1:8787.
Normal app data .data/. Isolated real tests .data/live-verification/; preview ./scripts/preview_verification.sh at port 8788.


User clarification: local Ollama inference requires no API key. The key question concerned only Ollama hosted web search; keep it disabled pending user decision.

Search-key update: no secret is stored in frontend bundles, run records, exports, or verification reports. The local credential file is ignored with .data/. No inference moved to a hosted model.


## Context recovery work — 22 September
- Automatic tested-tier expansion, model/runtime-specific sizing estimates, recorded local summaries and recovery ceiling edits implemented.
- 49 backend tests pass; updated frontend build and Chrome settings/390px layout check pass.
- Capacity probes: Alpha/Bravo up to 32K; Charlie/Judge up to 24K. Higher Gemma probe timed out and is not enabled automatically.
- Current seven-turn session passed the new context guard but remains failed on Bravo's separate generated-token limit. Completed turns unchanged; see docs/context-long-recovery.json. Do not describe it as recovered to a verdict.
- Live context scenarios and limitations: docs/context-scenarios.json and docs/VERIFICATION.md.

- Forced-summary live fixture passed: six Charlie summaries, unchanged eight original turns, completed verdict at 16K. Evidence-backed 12-turn fixture still failed at turn eight on the separate generated-token cap; full 12-turn completion under current defaults is not verified.
