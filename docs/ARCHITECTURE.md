# Implementation contracts

## State and ownership
`domain.TRANSITIONS` defines legal commands. Authority is the SQLite run snapshot. Each mutation compare-and-swaps a revision and writes a sequenced durable event in the same transaction. Completed turn, usage, evidence version and next turn (derived from completed count plus saved schedule) commit together. HTTP commands have durable idempotency keys. One controller task runs globally per data directory; an OS advisory lock excludes another backend process. Use exactly one Uvicorn worker.

Draft -> ingestion -> running -> judging -> completed. Pause interrupts any working phase and retains its phase. Resume regenerates the interrupted operation. Awaiting-user resumes only after a response. Cancel never creates a verdict. Restart preserves the prior run and creates a fresh draft with pinned models and current shared evidence/instructions. Repeated Stop & Judge in judgment is a no-op. Recovery requires a manual action.

SSE completion events replay from SQLite sequence IDs. Public text snapshots are transient and do not resume work. Browser state is never authoritative. Source artifacts are atomically moved into place before records reference them. SQLite schema migration 1 is in `storage.Store`; schema_versions prevents opening a newer schema accidentally.

## Inference
One heavy request at a time, including Charlie and Judge. The adapter refuses pre-existing residency rather than unloading another application's model. Each request uses keep_alive=0. Closing a stream is followed by a bounded `/api/ps` emptiness check. This is API-level evidence; it is not independent GPU instrumentation. If cessation cannot be confirmed, the controller blocks new work and reports the limitation.

Alpha/Bravo use native JSON-schema framing. The installed Gemma endpoint explicitly rejected it in the live probe, so Gemma uses prompt JSON plus the same Pydantic validation. Exact JSON fences are tolerated; explanatory text or invalid structure is rejected. Public-text deltas are decoded separately. Private thinking fields are discarded without persistence or logging.

Every run pins model IDs/digests, endpoint, capabilities, options and prompt version. Resume checks drift. Thinking uses provider default, is not exposed as an unverified configurable control. Token reservations are conservative bounds, not tokenizer measurements. Failed/interrupted requests retain reservations unless final usage is known. No exact interrupted-token accounting is claimed.

## Sources and network
App-owned extractor subprocesses can be terminated independently of Ollama. Text/Markdown, PDFs, images, media and supplied URLs retain originals and locators. MLX Whisper is offline-only and requires an explicitly installed local model directory. No implicit Hugging Face model download is allowed. Source size, duration and processing limits are provisional.

URL fetching resolves each redirect, rejects all non-global IPs and connects directly to a validated IP while preserving Host/TLS SNI. Environment proxies are disabled. No discovered links are followed in default mode. Optional search is session opt-in, capped, with a server-only environment credential. Result URLs enter the same shared source pipeline. Queries and result metadata are saved; API keys are not.

## UI and product decisions
Plain React text rendering prevents source HTML execution. No remote fonts, telemetry or external asset requests. Four selectors, shared inspector, claim statuses, public verdict and exports use committed backend state. Confirmed user changes: evidence optional; enabled searches automatic; even turns >=4, editable in draft/paused before closing dispatch; one active session. Time/token limits do not change when turn totals change.

## Current verification scope
See VERIFICATION.md and generated JSON reports. Unrun integrations must remain explicitly unverified. The original specification is preserved.

## Charlie preparation extension

`POST /api/sessions` defaults new API-created sessions to guided preparation. `preparation_mode` accepts `guided` or `prepared`; guided creation permits an empty proposition. Internal legacy `NewSession` calls and saved sessions lacking `preparation` retain the existing lifecycle. No destructive database migration is required: preparation records extend the versioned JSON session body.

`POST /api/sessions/{id}/preparation` takes `action`, `expected_revision`, optional `text`, optional structured `brief`, and `accept_limitations`. Actions are `analyze`, `message`, `research`, `edit`, `approve`, and `fork`. Revisions prevent stale writes. A preparation record retains messages, brief history, latest structured output, integrated source IDs, prompt text, approval version/hash, and explicitly accepted limitations. Approval requires a nonempty question and both positions. It never starts a debate; unapproved Start/Stop & Judge requests are rejected. A fork links a new draft and preserves prior debate content.

Preparation uses `PREPARING`, with `phase=preparation`, and returns to `DRAFT` for user review. Pause, cancellation, single-controller ownership, model pinning, recovery, memory monitoring, and bounded inference deadlines apply. A manual Resume after interruption returns to preparation until approval. Charlie is pinned first; remaining roles are checked before debate. A separate `preparation` usage bucket grows to reserve each bounded inference and is excluded from debate attempt accounting and active-time charges. The approved brief and acceptance record are supplied to both debaters and the frozen Judge snapshot.

`POST /api/sessions/{id}/evidence/path` takes an explicit absolute local `path`, expands `~`, validates a regular file, applies the shared byte limit, and snapshots its bytes. It does not scan directories. Hash and import provenance are saved. New preparation sources use a cancellable subprocess per extraction unit, with committed source cursors and stable passage IDs; image and text interpretation have separate committed cursors. Original passages, derived visual observations, intermediate summary notes, and coverage warnings remain stored. Extraction or model failure cannot silently admit a source.

PDF pages are rendered as well as text-extracted. DOCX is inspected as bounded ZIP/XML content without executing macros or external relationships. Public URLs retain the existing DNS-pinned fetch boundary and dispatch supported document/image MIME types to their extractors. Webpage HTML is text-only; known hosted-video pages and unsupported MIME types are rejected. Summaries are compact derived context, not proof of complete semantic preservation. Oversized final preparation context stops recoverably rather than silently deleting messages or source coverage.
