# Debate Lab — requirements and technical specification

Date: 21 September 2026

Deliverable: requirements and specification only. No application implementation, model installation, inference benchmark, or model-directory changes are included in this task.

## 1. Product and scope

Build a single-user local browser application in which two AI debaters argue opposing positions, a judge evaluates the completed debate, and a separate ingestion role prepares shared evidence. The user watches public arguments stream live and controls the session throughout its lifecycle.

This specification consolidates `debate_lab.pdf` and the user's subsequent answers. Those answers take precedence over the PDF. The PDF's opening message is truncated after “One thing I…”; its missing requirement is unknown and has not been reconstructed. The originally referenced screenshot was unavailable, but local API inspection resolved the model identifiers.

User-confirmed requirements are the baseline. Implementation choices and provisional tuning values below are engineering recommendations, not claims that the user individually specified them. Performance and capability tests are future implementation acceptance work.

### Confirmed decisions

| Area | Requirement |
|---|---|
| Delivery | Detailed requirements and specification; no app implementation in this task |
| Platform | Local browser app on the user's Apple Silicon laptop with 48 GB unified memory |
| Inference and storage | Local; no cloud inference fallback |
| Roles | Alpha, Bravo, Judge, Charlie; independent instructions and histories |
| Models | Independently configurable before a new run; existing runs retain their original assignments |
| Memory management | Sequential model loading/unloading as needed |
| Debate setup | User supplies proposition and may edit the opposing positions |
| Format | Openings, alternating rebuttals, then closing statements |
| Evidence | Pasted text, PDF/text/Markdown files, images, audio, video, and user-supplied URLs |
| Charlie | Extract/transcribe, preserve references, flag uncertainty, and ask about material ambiguity; no silent relevance-based exclusion |
| Information requests | Either debater can request information; pause for the user to answer, decline, or continue without it |
| Evidence fairness | Same admitted evidence available to both; unsupported factual claims marked unverified |
| Intervention | Add shared evidence/instructions while paused; retain previous arguments unchanged |
| Judgment | Evidence quality, logic, relevance, and responses to objections; winner, tie, or inconclusive allowed |
| Surrender | Explicit concession of the overall position, with brief judge confirmation |
| User control | Stop argumentation at any point and request judgment; separate cancellation without judgment |
| Limits | Default 12 completed turns and 15 active minutes; configurable token cap, calibrated during implementation |
| Pause/recovery | Durable checkpoint; regenerate an interrupted turn from the last completed turn |
| History | Saved sessions, reopenable transcripts, Markdown/JSON exports, explicit deletion |
| Web | User-supplied URLs by default; optional Ollama free-account search, disabled by default |
| Visual style | Scholarly dark |

## 2. Verified local environment

Read-only inspection on 21 September 2026 found:

- Apple M5 Pro and 48 GB unified memory.
- Ollama-compatible API at `http://127.0.0.1:11434`; `/api/version` returned `0.33.3`.
- `/api/tags` listed the models below. `/api/ps` reported no loaded models at inspection time. Installed/available does not mean currently resident or benchmarked.
- The workspace initially contained only `debate_lab.pdf`.
- Model manifests were present under `/Users/suvojitdutta/Documents/local_models/manifests`.

| Role | Exact default API model ID | API-advertised capabilities relevant here |
|---|---|---|
| Alpha | `gpt-oss:20b` | Completion, tools, thinking |
| Bravo | `qwen3:30b-a3b-thinking-2507-q4_K_M` | Completion, tools, thinking |
| Judge | `gemma4:31b-mlx` | Completion, vision, tools, thinking |
| Charlie | `gemma4:31b-mlx` | Completion, vision, tools, thinking |

The Gemma entry reported `safetensors` format but omitted parameter-size and quantization metadata. Its name and declared capabilities are verified API metadata, not independent verification of its architecture, performance, or modality accuracy. No inference was performed. The three distinct default entries report approximately 51.8 GB of aggregate stored size; disk size is not a RAM measurement, but all three must not be assumed to fit simultaneously with runtime overhead on this laptop.

Never write to, reorganize, delete, pull models into, or alter configuration within `/Users/suvojitdutta/Documents/local_models` as part of this work. Future app data and optional tool caches must use a separate application-owned location.

## 3. Technology stack

These are the selected architectural recommendations for the specification. Exact dependency versions must be pinned and tested when implementation begins.

| Layer | Selection | Purpose |
|---|---|---|
| Browser interface | React + TypeScript + Vite | Typed interactive UI, live transcript, evidence inspector, setup and history screens |
| Styling | CSS variables and scoped CSS | Custom scholarly dark visual system, responsive layout, accessible controls, locally bundled fonts |
| Local backend | Python + FastAPI, served by Uvicorn | Session controller, typed HTTP API, persistence, evidence processing and inference coordination |
| Validation | Pydantic | Validate settings, commands, model outputs, evidence references and verdict structure |
| Live transport | Server-Sent Events (SSE) for output; HTTP POST for commands | Stream ordered public events and send reliable idempotent controls independently |
| Durable storage | SQLite + SQLAlchemy + schema migrations | Sessions, completed turns, evidence metadata, event history, checkpoints and usage |
| Artifact storage | Application-owned filesystem directory | Original evidence copies, extracted passages, audio transcripts and video frames |
| Inference | Ollama HTTP adapter using an asynchronous HTTP client | Configurable model IDs, streaming, capability checks, request cancellation and resource scheduling |
| PDF extraction | pypdf + pdfplumber | Text and page references; scanned pages routed through image rendering/OCR |
| Image preparation | Pillow and a PDF renderer | Normalize images and page images for Charlie; retain originals |
| Audio/video | FFmpeg/ffprobe + local MLX Whisper candidate | Extract timestamped audio/frames and produce local speech transcripts |
| Web retrieval | HTTP client + HTML content extractor | Retrieve supplied public URLs and retain source snapshots |
| Optional search | Ollama web-search API | Free-account search with an API key, opt-in per session and bounded requests |
| Verification | pytest for backend; browser automation such as Playwright for end-to-end checks | State transitions, crash recovery, actual cancellation, streaming and UI behavior |

The browser is a view/controller client, not the authoritative state store. The backend serves the compiled frontend and local API on loopback in the packaged local setup. An app-owned worker executes evidence and inference jobs, with one active heavy inference job at a time. A custom explicit state machine is preferable to introducing a general autonomous-agent framework for four tightly controlled roles.

SQLite should use transactions, foreign-key enforcement, WAL mode and a durability setting appropriate to committed checkpoints. WAL alone is not an application recovery design. Source files must be atomically written before their references become committed evidence records. App recovery checkpoints and SQLite's internal WAL checkpoints are distinct concepts.

No paid service or hosting is required for the core application. Optional search requires external network access and credentials. Audio transcription may require a separate local model download during a later implementation task; it is not assumed to be installed or authorized to download now.

## 4. Roles and model configuration

### Alpha and Bravo

Each receives its assigned position, the proposition, shared rules, completed public turns, current evidence version and shared user instructions. Each must address the opponent's material objections, distinguish factual claims from interpretations, cite source IDs where available, and explicitly identify any concessions or information requests.

Model-generated confidence is not evidence. Agreement between agents does not validate a factual claim. A citation can be structurally valid while failing to support the claim; the UI must distinguish reference existence from assessed support.

### Charlie

Charlie prepares a shared evidence packet for all participants. It preserves the user's proposition and original material, extracts or describes content, records uncertainty and asks for clarification when interpretation materially changes the debate. Charlie cannot silently remove a source because it appears irrelevant.

Deterministic extraction and specialized local media tools precede or support Charlie. A vision model is not assumed to provide native audio transcription. Video processing combines timestamped frames and a speech transcript; sample intervals and omitted visual periods must be disclosed. Charlie's descriptions are derived observations, not original quotations.

### Judge

The Judge has a separate instruction set and context from Charlie even when both use the same underlying model. It evaluates a frozen snapshot of completed arguments, admitted evidence and shared user instructions. It does not receive the debaters' private thinking output or Charlie's private history. It may inspect original admitted evidence through the same shared evidence tools, but does not introduce new sources after judgment begins.

### Configuration contract

- Four independent model selectors, populated from the configured local runtime. Show exact model IDs and known capabilities.
- Save reusable default assignments; copy immutable assignments into every run.
- Pin model ID, digest when available, provider endpoint, generation settings and prompt-template version in the run record.
- Changing defaults affects future runs only. Resumed and restarted runs retain their pinned assignments; a separate “New debate” setup can copy settings and select different models.
- If a pinned model disappears or its digest changes, pause with an explicit explanation. Do not silently substitute another model. Offer restoring the original environment or creating a new run with a chosen replacement.
- Model installation/removal is outside the app's initial scope. Selecting an unavailable model must not automatically download it.
- Validate role compatibility. A Charlie replacement must have a configured route for every required modality; unsupported capabilities block the affected operation with an actionable message.
- Do not assume all providers support the same thinking options, context lengths or tool formats. Unsupported controls are disabled with an explanation.

## 5. Debate lifecycle and controls

Recommended authoritative states: `DRAFT`, `INGESTING`, `READY`, `RUNNING`, `PAUSING`, `PAUSED`, `AWAITING_USER`, `STOPPING`, `JUDGING`, `COMPLETED`, `CANCELED`, and `FAILED_RECOVERABLE`. Record a separate activity label for model loading, evidence processing, preparing a response and streaming.

| Control | Required behavior |
|---|---|
| Start | Validate setup, evidence readiness, models and limits; persist the initial checkpoint before dispatching work |
| Pause | Cancel current work, invalidate its generation ID, preserve committed state, mark any visible unfinished text interrupted, and stop the active clock |
| Resume | Reopen the saved run with unchanged assignments and completed history; regenerate an interrupted turn from its start |
| Restart | Stop the previous run, retain it separately, create a fresh run with the same proposition, current shared evidence, instructions and pinned settings |
| Stop & Judge | Stop argumentation immediately, exclude incomplete work, freeze a judgment snapshot and request a verdict; record user-ended-early status |
| Cancel | Stop ingestion, argumentation or judgment; keep the session marked canceled; do not generate a verdict |
| Delete | Separate explicit action removing the selected session and its unshared artifacts |

Pause/Resume should also preserve phase information during ingestion and judgment. Pausing judgment cancels an unfinished verdict; Resume regenerates it from the same frozen judgment snapshot. Repeated Stop & Judge during judgment must not launch duplicate judges.

Stop & Judge during initial ingestion can legitimately return “insufficient debate to judge.” Cancel remains available throughout. Restart must not dispatch its first job until old work has been terminated or the runtime is explicitly reported as unable to terminate it.

### Cancellation correctness

Closing a UI stream is insufficient. The controller must cancel the upstream request and any app-owned extraction processes, enforce a bounded cleanup timeout, and verify the adapter's cancellation behavior in integration tests. If work cannot be stopped, surface that failure and do not claim the session is fully paused or launch overlapping inference. Never terminate an unrelated Ollama process or another application's job.

Every job carries run ID, generation ID and expected state revision. Late output from invalidated jobs must never commit into the session, even if it arrives after cancellation. Commands have idempotency keys so retries cannot duplicate turns, restarts or judgments. Only one controller lease may advance a run.

## 6. Turn order, limits and information requests

Default schedule: Alpha opening, Bravo opening, eight alternating rebuttal turns, then Alpha and Bravo closings: 12 completed turns total. Starting with Alpha is an engineering default, not a claim of perfect judging neutrality. The saved schedule identifies speaker, phase and ordinal explicitly.

The first reached configured limit ends argumentation and triggers judgment. A hard time/token limit may prevent closings; the verdict must disclose that truncation rather than allow hidden overruns. Surrender or user Stop & Judge also ends argumentation early.

- Default active debate time: 15 minutes. Begin at dispatch of the first debate turn; include model loading, inference and app work while the debate is active. Exclude explicit pauses, waiting for the user, initial pre-debate ingestion and judgment. Show wall-clock duration separately.
- Default completed-turn limit: 12, including openings and closings. An interrupted, failed or information-request-only attempt is not a completed argumentative turn.
- Token cap: configurable before starting. Account for input/output separately and by role; include failed/interrupted attempts when usage is known. Expose separate ingestion, debate and judgment budgets so a debate cap cannot consume the reserved judgment allowance.
- The default numeric token budgets and per-response limits require local calibration. No tested value can honestly be inferred from model names or RAM alone. They remain explicitly uncalibrated implementation parameters, not missing user product decisions.
- Do not display false exactness: aborted requests may lack final usage counts. Preserve known usage, label estimates and unknown portions, and use conservative reservations when enforcing a cap. Never reset consumed tokens on Pause/Resume.
- Context-window capacity, generated-token allowance and cumulative session usage are different controls.

An information request includes the question, why it matters and the requesting role. The controller saves it and enters `AWAITING_USER`. The user may provide text/files/URLs, decline, or continue without answering. Charlie processes new material into the shared record before the next argument. Preserve already completed arguments and resume the pending speaker's turn. Do not repeatedly ask a declined question without materially new grounds; another request still requires user interaction and cannot form an autonomous loop.

## 7. Evidence ingestion and provenance

Each source has a stable ID, original name or URL, content hash, local snapshot, ingestion status and version. Derived items include extractor/model identity, creation time, uncertainty notes and a locator back to the original.

| Input | Required treatment |
|---|---|
| Pasted text | Preserve exact submitted text; add paragraph or line locators |
| PDF | Preserve page numbers, extract text, render scanned/ambiguous pages for local visual processing |
| Text/Markdown | Preserve original content and line/section references |
| Images | Keep original image; Charlie describes visible content and flags uncertain text or interpretation |
| Audio | Local transcription with timestamps; flag unintelligible segments and inferred speaker labels |
| Video | Timestamped audio transcript plus sampled frames; clearly disclose sampling and processing limits |
| Supplied URL | Retrieve public content, preserve requested/final URL and retrieval time, keep a snapshot and passage locators |

Unsupported, corrupt, oversized, blocked or partially processed sources remain visible with their status. Missing capability must not be disguised as a completed ingestion. Configurable file-size, media-duration and processing-time limits must be visible before submission; initial thresholds are deployment tuning values.

“Admitted” means supplied material was successfully processed into the shared record, not that its contents have been proven true. Sources with blocking ambiguity remain pending until the user resolves or explicitly excludes them. Both debaters receive notification of each new admitted evidence version. Retrieval may select different passages for different questions, but neither side has private evidence access; all retrieval results are recorded and available to both.

Adding instructions or evidence while paused creates a new version and event. Earlier turns retain their original evidence/instruction versions. Stop & Judge during unfinished ingestion uses only previously admitted material and states what was excluded. Newly admitted evidence that a side has not yet addressed must be disclosed in an early verdict.

Evidence text is untrusted source material, not app instructions. It cannot change roles, invoke shell commands, override the user, or alter verdict rules. Sanitize rendered content and restrict web fetching to public HTTP(S) targets, including redirect checks; do not allow a supplied URL to read local files or private services.

## 8. Web access and free-search extension

The default mode fetches only URLs supplied by the user. It does not autonomously search or follow discovered links. Failed retrieval prompts for a file or pasted content; do not bypass authentication, paywalls or access restrictions.

Optional mode: the user enables Ollama web search for a session and supplies a free-account API key. Local debaters can request searches through the app's bounded tool interface; returned source material is fetched, processed by Charlie and shared before argumentation continues. The app, not the model weights, provides network access.

Show the provider and disclose that queries/URLs leave the laptop. Do not send whole private source documents as search queries automatically. Log queries, result provenance and errors without logging the API key. Use a per-session search-request limit and a timeout; on quota exhaustion or provider failure, pause and offer user-supplied evidence or continuing without it. Never purchase credits, upgrade a plan or switch to paid services automatically.

Ollama documents free-account/API-key access; its published launch announcement describes free and higher-limit subscription access. This is not a promise of unlimited searches or a stable quota. A live authenticated integration test remains necessary.

Alternative considered: self-hosted SearXNG. It avoids a required paid search subscription but adds installation/maintenance and depends on upstream search availability. Public instances often disable structured results. It is an alternative architecture note, not an additional initial implementation requirement.

## 9. Judgment, concessions and user authority

Use four criteria: evidence quality, logical validity, relevance to the proposition, and engagement with opposing objections. Engineering default: equal weighting, with each criterion scored 0–5 using explicit rubric descriptions. Scores aid explanation; they are not calibrated probabilities or proof of correctness.

Verdict structure:

- Outcome: Alpha wins, Bravo wins, tie, or inconclusive; use `insufficient_debate` as a reason when too little completed material exists.
- Concise public justification, criterion scores and citations to completed turn/source IDs.
- Key supported and unsupported claims, decisive objections, concessions and remaining uncertainty.
- Ending reason: normal limit, explicit surrender, user Stop & Judge, or other recorded termination.
- Evidence/instruction versions and limitations, including uneven opportunities to respond after an early stop.

Recommended minimum for a comparative verdict: one substantive completed contribution from each side, unless a completed explicit overall surrender can be confirmed. Beyond that minimum the judge may still return inconclusive. Validate the verdict schema and referenced IDs before committing it; malformed output is a recoverable error, not a fabricated winner.

Conceding a subclaim does not surrender the debate. Overall surrender requires explicit structured intent or unambiguous public concession, which the judge confirms. If confirmation is ambiguous, pause for the user rather than resume argumentation after an announced stop or assign a speculative winner.

The user can stop argumentation at any time and request judgment. Overriding or reopening a completed verdict is not part of the selected scope. The user may start a new run instead. Canceled runs do not receive a new verdict.

## 10. Persistence, checkpoints and recovery

Persist a checkpoint after every completed turn, evidence/instruction addition and control action. Also persist a job-start intent before dispatch, so recovery can detect work that was in flight. A checkpoint is sufficient to reconstruct semantic session state without a surviving browser tab, Python process, model KV cache or loaded model.

Minimum stored data:

| Record | Required content |
|---|---|
| Session/run | IDs, parent/restart relationship, proposition, positions, status, phase, next speaker, state revision |
| Configuration snapshot | Model IDs/digests, endpoint, prompt versions, generation settings, limits and rubric |
| Turn/attempt | Speaker, phase, ordinal, attempt ID, completed/interrupted/failed status, public text, timestamps, evidence version |
| Evidence/instructions | Originals, immutable versions, derived artifacts, locators, hashes, admission status |
| Claim/concession | Text, proposing turn, references, challenged/accepted/unresolved status and uncertainty |
| Information request | Question, requester, response or decline, pending/resolved state |
| Usage/clock | Per-attempt known/estimated usage, reservations, accumulated active time and active interval metadata |
| Checkpoint/event | Monotonic sequence, transaction revision, committed state and reason |
| Job | Generation ID, cancellation status, controller lease, last durable heartbeat |
| Judgment | Frozen input snapshot, validated verdict or interrupted/error status |

Commit the completed turn, its evidence version, usage, next-speaker pointer and checkpoint in one transaction. Publish the durable completion event only after commit. A disk error stops progression; the UI must not display “saved” for uncommitted state.

On recovery, load the last consistent checkpoint and reconcile any job lacking completion. Mark interrupted inference as incomplete; do not replay it as accepted debate history. Show the recovered phase and require manual Resume or Retry. Resume regenerates the affected turn or judgment using the saved inputs. Exact token continuation and identical regenerated wording are not guaranteed.

Save bounded clock/usage heartbeats while active to limit crash uncertainty. On an unclean shutdown, report any unknown interval rather than counting offline hours or inventing precise consumption. Reconnection replays durable events using sequence IDs without dispatching new inference. Continuous disk persistence of partial response text is not required by the selected checkpoint policy; visible fragments are marked interrupted and may not survive a crash.

Keep local session history until explicit deletion. Markdown export presents readable public arguments, source references, verdict and limitations. JSON export contains a versioned structured snapshot, including configuration and provenance; secrets and private thinking are excluded. These exports are not a promise of a self-contained archive of every media file. PDF export and side-by-side run comparison are outside the initial scope.

## 11. User interface

### Setup and library

Session library shows title, outcome/state, last activity and recovery status. New-debate setup contains proposition, editable opposing positions, four model assignments, evidence inputs, limits and optional search mode. Model availability and ingestion readiness are visible before Start.

### Debate chamber

Use a dark charcoal background, restrained warm highlights, serif display headings and highly readable body text. Distinguish Alpha, Bravo, Charlie and Judge by explicit labels and subtle accents rather than color alone. Avoid decorative motion and dense terminal styling.

- Header: topic, state/activity, completed-turn counter, active time, token usage with uncertainty labels, checkpoint status.
- Primary reading area: chronological streaming transcript with named speakers, phase labels, citations and clear interruption markers.
- Evidence inspector: source list, original/derived distinction, source passage or image/media timestamp, uncertainty and ingestion status.
- Claims panel: challenged, accepted and unresolved claims, with links to the relevant turns.
- Persistent controls: Pause/Resume, Restart, Stop & Judge, Cancel. Disabled controls explain their current state.
- Distinct Judge panel: verdict, criterion assessment, decisive references and limitations.
- Information-request panel: question, source submission, decline and continue-without-answer controls.

Keep long text to readable line lengths and preserve the user's scroll position while streaming; provide “Follow live” to rejoin the latest output. All actions must work by keyboard with visible focus and readable contrast. On a narrow viewport, use evidence/claims drawers rather than compressing the transcript into unusable columns. Announce state changes accessibly without reading every streamed token.

Show public arguments and processing activity, not raw private thinking. “Preparing response” can indicate model activity without exposing internal reasoning. Store only the public argument and concise structured claim/concession metadata required by the product.

## 12. API and worker outline

Recommended local API surface:

| Endpoint | Purpose |
|---|---|
| `GET /api/models` | List exact available models and capability metadata |
| `POST /api/sessions` | Create draft with validated immutable-on-start configuration |
| `GET /api/sessions/{id}` | Read authoritative state and latest checkpoint |
| `POST /api/sessions/{id}/commands` | Start, pause, resume, restart, stop-and-judge, cancel; includes expected revision and idempotency key |
| `GET /api/sessions/{id}/events` | SSE stream with sequence-based reconnection |
| `POST /api/sessions/{id}/evidence` | Stage source additions for shared processing |
| `POST /api/sessions/{id}/instructions` | Record shared instructions in permitted states |
| `POST /api/sessions/{id}/information-requests/{request_id}/response` | Answer, decline or continue without information |
| `GET /api/sessions/{id}/export?format=markdown|json` | Export committed public data |
| `DELETE /api/sessions/{id}` | Explicit deletion after safely stopping active jobs |

Conflict responses return current revision/state. SSE events include activity, public text deltas, committed turn, evidence-ready, request-for-information, checkpoint-saved, usage update, state change, verdict and recoverable error. Only committed events are guaranteed replayable; token deltas are transient.

Worker interfaces should separate model inference, file extraction, speech transcription, URL retrieval and search. Each receives a cancellation token and job identity. Ollama's current API documents streaming chat, per-request model selection and returned usage fields; actual abort behavior and incomplete-response usage must be verified against the installed server.

## 13. Context and resource management

Use a single app-owned heavy-inference queue. Load the requested role's model only when needed; unload app-owned residency as supported when changing models. Reuse the same resident Gemma weights for Charlie and Judge without sharing role histories. Do not change Ollama's global configuration or kill unrelated jobs.

Context assembly preserves proposition, role instructions, current shared instructions, concessions, unresolved claims and relevant source passages. Keep originals on disk and retrieve passages with stable IDs. If summaries are needed for long sessions, record their versions, retain links to full turns and disclose that summaries are derived. Never silently drop contrary evidence or treat an agent summary as a source quotation.

Calibrate usable context length, maximum output, thinking settings, loading latency, memory headroom and audio/video chunk sizes on the target machine. Advertised maximum context is not a promise of feasible memory use. A 15-minute setting is a user limit, not a promise that 12 turns will finish within it.

## 14. Implementation acceptance criteria

These are required future tests, not tests already performed in this specification task.

| ID | Scenario and required result |
|---|---|
| AC-01 | Start a debate: correct pinned models receive their roles and the same evidence version; public text streams before completion |
| AC-02 | Change default Alpha model: a new run uses it; an existing paused run retains its original model and digest |
| AC-03 | Pause mid-response: upstream work terminates, completed state persists, partial argument is excluded and active time stops |
| AC-04 | Resume: same next speaker and shared state return; interrupted turn regenerates without duplicating completed turns |
| AC-05 | Force backend termination around a turn commit: recovery contains either the complete committed transaction or the previous checkpoint, never a half-accepted turn |
| AC-06 | Restart during generation: old run remains in history; late old output cannot enter the new run and heavy jobs do not overlap |
| AC-07 | Stop & Judge at any stage: only completed turns/admitted evidence are used; insufficient material returns an explicit non-verdict |
| AC-08 | Cancel during ingestion, debate and judging: work stops and session remains canceled without a new verdict |
| AC-09 | Add paused evidence/instructions: both sides see the new version; earlier turns remain unchanged and traceable |
| AC-10 | Information request: checkpoint persists, time pauses, all three response choices work and the correct turn resumes |
| AC-11 | Hit time/turn/token boundary: no further argumentative turn is launched; judgment uses its separate allowance |
| AC-12 | Abort without usage totals: known consumption is retained, missing usage is labeled and never shown as zero |
| AC-13 | Process text, scanned PDF, image, audio and video fixtures: locators resolve; extraction gaps and unsupported capabilities are explicit |
| AC-14 | Supply a URL in default mode: only permitted supplied targets/redirects are fetched; no search is issued |
| AC-15 | Enable optional free search: requests are bounded and shared; missing credentials, quota and network failure never trigger paid fallback |
| AC-16 | Model/source output contains instructions or unsafe HTML: it cannot override controller rules or execute in the browser |
| AC-17 | Close/reopen browser or restart laptop: completed state and source copies survive; offline time is not charged as active debate |
| AC-18 | Duplicate command/reconnect/multiple browser tabs: no duplicate inference or state transitions occur |
| AC-19 | Missing model, changed digest, low memory, unreadable evidence or disk failure: actionable recoverable state; no silent substitution or data loss claim |
| AC-20 | Export: Markdown/JSON match committed history and outcome, resolve source IDs, disclose limits and omit credentials/private thinking |
| AC-21 | Judge output references nonexistent turns or has invalid structure: validation fails visibly; no invented verdict is committed |
| AC-22 | Complete UI walkthrough: scholarly dark layout, keyboard controls, readable streaming, citations and recovery indicators work at laptop and narrow viewport sizes |

## 15. Remaining implementation validation

Product decisions are settled. The following technical parameters cannot be honestly finalized without implementation-time tests: exact dependency versions, model cancellation latency, reliable model unloading, actual vision/tool/structured-output support, local transcription installation and accuracy, memory/context limits, calibrated token budgets, media-size limits and free-search quota/access.

Do not claim these have passed based on metadata inspection. If testing reveals that a confirmed requirement cannot be met locally, report the concrete limitation and propose an explicit revision instead of silently narrowing the feature.

## 16. References

Local source: `debate_lab.pdf`, five pages, plus the user's clarification messages in this task. Local environment observations came from read-only hardware metadata, model manifest names and Ollama `/api/version`, `/api/tags`, `/api/ps` responses on 21 September 2026.

Official references checked for architectural recommendations:

- [Vite guide](https://vite.dev/guide/): React/TypeScript setup and frontend build tooling.
- [FastAPI](https://fastapi.tiangolo.com/): Python API framework.
- [SQLite WAL](https://www.sqlite.org/wal.html): concurrency and transaction-log behavior.
- [Ollama API introduction](https://docs.ollama.com/api/introduction) and [chat endpoint](https://docs.ollama.com/api/chat): local inference interface, streaming and request/response fields.
- [Ollama FAQ](https://docs.ollama.com/faq): context settings and model residency considerations.
- [MLX Whisper example](https://github.com/ml-explore/mlx-examples/tree/main/whisper): candidate local Apple Silicon transcription route.
- [FFmpeg](https://ffmpeg.org/): local media processing.
- [Ollama web search documentation](https://docs.ollama.com/capabilities/web-search) and [web search announcement](https://ollama.com/blog/web-search): external search API, free-account access and rate-limit caveats.
- [SearXNG search API](https://docs.searxng.org/dev/search_api.html): alternative search interface and public-instance limitations.
