# Debate Lab

A local, single-user debate workspace. React/TypeScript frontend, FastAPI backend, transactional SQLite state, sequential Ollama inference. **Implementation and verification remain in progress. Read `docs/VERIFICATION.md` before relying on any unverified integration.**

## Run locally

In Terminal, from any directory:

```sh
debate
```

This opens the browser when the app is ready and keeps the server in the foreground. Ctrl+C stops the server. If it is already running, the command opens that instance; stop it from its original terminal. The installed command at `~/.local/bin/debate` points to `scripts/debate` in this checkout.

From this directory:

```sh
./scripts/launch.sh
```

Open **http://127.0.0.1:8787**. The backend serves the compiled frontend and API. Stop it with Ctrl+C; active work is paused and saved. Do not run multiple workers. Do not start the launcher twice for the same data directory.

## Reproduce the environment

Python 3.12 and Node 22.12+ are recommended. Create an isolated environment; install locked dependencies; build the frontend:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
npm ci --prefix frontend
npm --prefix frontend run build
./scripts/launch.sh
```

The existing Ollama-compatible API must already be running at `http://127.0.0.1:11434`. Debate Lab never installs models or reconfigures the service. It checks model availability/digests at Start/Resume and pauses on mismatch. Default models: Alpha `gpt-oss:20b`; Bravo `qwen3:30b-a3b-thinking-2507-q4_K_M`; Charlie and Judge `gemma4:31b-mlx`. Role histories remain separate.

## Using the app

Create a proposition and optionally edit opposing positions. Choose four role assignments and limits. Add evidence in the draft chamber, or start without it. Pasted text, TXT/Markdown, PDF, images, audio/video and supplied URLs have a shared source inspector. Unsupported or blocked ingestion is visible; explicitly exclude a blocked source or resolve it before continuing.

- **Pause** interrupts app-owned processing, preserves completed history, and verifies request cleanup before reporting paused.
- **Resume** regenerates an interrupted operation from the saved semantic state, not the exact prior token stream.
- **Restart** preserves the old run and creates a new draft with the same pinned assignments, current evidence and instructions.
- **Stop & Judge** freezes completed arguments and admitted sources. Too little debate yields inconclusive, without a fabricated winner.
- **Cancel** stops without a new verdict. Delete is separate and removes only unshared artifacts.
- Change even turn totals (minimum four) in draft or while paused, until closing dispatch begins. Completed turns remain intact and two closings stay reserved. Time/token limits remain unchanged.
- Answer, decline or continue without requested information, then Resume when ready. Both sides see admitted additions. During source ambiguity, decline/continue explicitly excludes that source.

Only one session may actively process at once. Pause before switching. Optional search is automatic once enabled for that session, capped, and disclosed as external. The local Ollama inference API needs no key. Only the separate hosted web-search endpoint (`https://ollama.com/api/web_search`) requires an app-local credential or server environment variable `OLLAMA_API_KEY`; never put the key in frontend files, shared exports, or source control. The supplied key is stored in `.data/secrets/ollama-search-key` with owner-only permissions. To replace it without echoing it, run `.venv/bin/python scripts/configure_search_key.py`. The environment variable takes precedence if set. There is no paid fallback. Without a key, leave search disabled or use supplied URLs.

## Storage, recovery and export

Default data: `.data/debate.sqlite3` and `.data/artifacts/`. Set `DEBATE_DATA_DIR` to a different application-owned location if needed. The protected `Documents/local_models` path is rejected. HF/tool caches live under `.data`; no auxiliary model is downloaded automatically. Back up the complete data directory with the app stopped; copying only the main SQLite file during operation can miss its WAL.

Unclean restart loads a consistent checkpoint and requires manual Resume/Retry. Interrupted text is not accepted as a turn. Time since the last heartbeat may be uncertain; offline hours are never charged. Markdown/JSON exports include committed public records, IDs, provenance and limitations, but do not embed every original media file. Private thinking and credentials are excluded.

A pre-existing resident model blocks inference to avoid disturbing another application's work. Wait for that application's request/residency to finish. If cancellation cannot be confirmed, new app inference stays blocked. The app never kills the model service.

## Audio/video prerequisites

`imageio-ffmpeg` supplies an isolated executable; `DEBATE_FFMPEG` may point to an already-installed FFmpeg. MLX Whisper code is installed as a project dependency. **The user-approved Whisper Small MLX model is installed** at `.data/auxiliary-models/whisper-small-mlx` (repository revision `45f3915`; downloaded files checksum-verified). The normal launcher selects this existing directory automatically. To use another explicitly installed model, set `DEBATE_WHISPER_MODEL` to its local directory outside the protected model store. Transcription uses that path with Hub offline mode, not a repository ID. Timestamped transcription is automatic and may be inaccurate. Video samples one frame per 30 seconds; visual gaps are disclosed.

Deployment tuning environment variables: `DEBATE_MAX_SOURCE_MIB` (25), `DEBATE_MAX_MEDIA_SECONDS` (600), `DEBATE_MAX_PDF_PAGES` (100), `DEBATE_PROCESS_SECONDS` (180). Limits are reported by `/api/health` and shown before evidence upload. They are provisional, not accuracy guarantees.

## Limits and measurement

Default: complete 12 turns (six per party), then judgment. Completion mode automatically grows separate ingestion/debate/judgment budgets as bounded requests are reserved. Fixed mode retains the legacy time and token caps. Each completion-mode inference attempt has a ten-minute deadline, three-minute stream inactivity limit and 4 GiB available-memory floor. Action and retry limits still prevent runaway work. Context capacity, generated tokens and cumulative charged usage are distinct. Reservations use conservative byte-based bounds, not an exact tokenizer. Interrupted unknown usage remains accounted conservatively and labeled.

The installed Gemma endpoint rejects native schema formatting. Its adapter uses prompt JSON plus strict application validation; exact JSON code fences are accepted. Other models use native schema framing. Prompt and capability choices are stored in run configuration. Do not treat an advertised capability as proof of accuracy.

Long context may use recorded Charlie summaries and disclosed public excerpts; full originals remain on disk and local retrieval is available by source/turn ID. If even the source index cannot fit the safe allowance, the run stops visibly rather than silently discarding evidence. Automated claim support is only a model assessment.

## Develop and test

```sh
# Backend (same launch command, no automatic reload during debates)
./scripts/launch.sh
# Frontend dev server in another terminal
npm --prefix frontend run dev
# Deterministic backend tests; no model inference
.venv/bin/python -m pytest -q
# Real browser integration (requires running backend and Chrome)
npm --prefix frontend run test:e2e
```

Live tests are explicit opt-in commands, use synthetic material and isolated data: `scripts/probe_models.py`, `scripts/live_smoke.py`, `scripts/live_cancel.py`, and `scripts/live_vision.py`. Run only one at a time while no other app is using Ollama. They do not download models. The browser test creates and deletes only its uniquely named synthetic draft. An additional saved-verdict browser test runs when `./scripts/preview_verification.sh` is serving the isolated completed live-test records at port 8788; otherwise that test is skipped.

Progress: `PROGRESS.md`. Contracts: `docs/ARCHITECTURE.md`. Measured evidence and screenshots: `docs/`.


## Automatic context and usage

The starting context remains 16,384; the default maximum automatic context is 131,072, capped in practice by the matching model's locally tested tiers. The controller tries full history at the smallest fitting locally tested capacity, then creates recorded local Charlie summaries when necessary. Models without a matching calibration profile retain conservative sizing and cannot automatically expand. Calibration is tied to model digest, endpoint and reported runtime version. Run `.venv/bin/python scripts/calibrate_context.py` with the app idle to refresh profiles; this runs inference but does not change the Ollama service.

Text sizing uses a sample-calibrated estimate only for predominantly ASCII requests within the tested byte range, counting non-ASCII bytes conservatively. Other inputs retain the conservative byte bound. This is not exact tokenization or proof against every provider truncation behavior. Estimates that are exceeded by reported prompt counts are invalidated. Neither calibration nor summary coverage checks prove semantic fidelity.

Older turns are summarized from originals; their structured claims and concessions remain verbatim. The latest turn from each side and shared instructions stay intact. Originals, summary versions, coverage IDs and per-attempt capacity remain in exports. The context guard still pauses if mandatory material cannot fit; arbitrary 100-turn or very large-source sessions are not guaranteed to complete.

In Run settings & allowances, change Maximum automatic context in draft, paused or recoverable failure. Resume uses the saved checkpoint. Reported session tokens, current reservation, retained uncertain estimates and per-request context are displayed separately. History preparation counts against the relevant debate or judgment budget.

Completion-mode responses start at 8,192 generated tokens, including reasoning. A confirmed length stop receives one retry at 16,384 after input is resized. Existing sessions keep their original policy until **Upgrade and Resume** is selected; the upgrade is recorded and completed arguments are preserved. Live verification on 22 September 2026 completed a 12-turn no-source debate plus judgment and recovered an isolated copy of the saved seven-turn session to 12 turns plus judgment without altering its original arguments. An evidence-backed test initially stopped safely for low memory; its checkpoint resume then completed all 12 turns and judgment with the same models and safeguards. The cross-app verification report is in the Ollama Local UI project at `docs/CONTEXT_VERIFICATION.md`. Completion remains dependent on memory, valid model output and service availability.

## Charlie preparation

New debates now default to **Prepare with Charlie**. Start with a subject or leave it blank, then combine pasted text, images, Markdown, DOCX, PDFs, and public URLs in the shared evidence panel. **Path** imports an explicitly selected absolute local file path (including `~/…`) into saved application storage; **File** uploads a copy. Neither changes the original file.

Select **Analyze inputs with Charlie** to interpret the material. Charlie proposes possible debate questions when needed, asks up to three related clarification questions at a time, and prepares an editable brief. The brief includes background, scope, definitions, assumptions, the intended resolution, evidence coverage, and suggested Alpha/Bravo positions. Positions can represent opposing claims, explanations, or alternative actions.

Charlie explains evidence gaps and where to obtain useful evidence. Public-web research runs only when you enter a query and select **Search public sources**; it uses the existing configured search integration. You can supply evidence, narrow the question, or explicitly accept unresolved limitations. **Approve debate brief** records your decision; **Start** begins the debate separately. Editing the inputs, shared instructions, or brief invalidates approval. **I already have a prepared subject** skips the Charlie conversation and goes directly to manual brief review.

Document extraction and interpretation save checkpoints per unit. Pause/Resume retains completed units; after an extraction error, **Review inputs again** retries blocked sources. Upload and path imports share the same limits, including the configurable 25 MiB file and 100 PDF-page defaults. The processing timeout applies per extraction batch. Sources exceeding a hard limit remain visibly blocked, with no silent truncation. Accepting incomplete coverage excludes unfinished sources from the debate record; originals and partial processing remain available.

Images and rendered PDF pages receive visual interpretation, including pages with extractable text. DOCX processing reads paragraphs, tables, headers/footers, notes, embedded raster images, and cached chart values. Native DOCX chart layout, floating shapes, unsupported image formats, and some rendering details may require a PDF or screenshot; those coverage limitations are disclosed. Webpage interpretation is text-only. Audio, video, and hosted-video pages are deferred for this preparation workflow. Historical media remains accessible in existing sessions.

After debate starts, **Revise subject in a new draft** creates a linked draft without changing completed arguments or results. Existing saved sessions retain their original lifecycle. Preparation usage is separate from debate usage and does not consume active debate minutes. Exports include the brief, conversation, approval, and accepted limitations.

Verification and current limits: [Charlie preparation verification](docs/CHARLIE_VERIFICATION.md). The implementation plan is [CHARLIE_INGESTION_PLAN.md](CHARLIE_INGESTION_PLAN.md). Restart a running backend to load the new routes and controller behavior.
