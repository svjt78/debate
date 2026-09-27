# Build Debate Lab from the finalized specification

Use the following prompt as the initial instruction to an AI coding agent. Give the agent access to this project directory and `DEBATE_LAB_SPEC.md`. This prompt commissions implementation when submitted to that agent; preparing this file does not itself run or install the app.

---

You are the implementation engineer for **Debate Lab**. Build and verify the complete local application described in the specification. Deliver working software, not just a plan, interface mockup, architecture explanation, or simulated debate.

## 1. Read the source of truth before making changes

Project directory:

```text
/Users/suvojitdutta/Documents/Rest/apps/apps/debate-lab/debate_lab
```

Authoritative specification:

```text
/Users/suvojitdutta/Documents/Rest/apps/apps/debate-lab/debate_lab/DEBATE_LAB_SPEC.md
```

Historical source, only if clarification is necessary:

```text
/Users/suvojitdutta/Documents/Rest/apps/apps/debate-lab/debate_lab/debate_lab.pdf
```

Read the entire specification and any applicable repository instructions. Inspect the existing project before scaffolding. Preserve existing work, the specification and the source PDF. If work already exists, assess it and continue from its actual state instead of replacing it wholesale.

**Scope clarification:** the specification says its original deliverable was “requirements and specification only.” That describes the previous task. This prompt now explicitly authorizes building and testing the application. All product requirements and protective constraints remain in force. Do not use the earlier delivery wording as a reason to stop at another specification.

Follow the host's governing instructions. Within this project's instructions, explicit user clarifications take precedence over this prompt, then use `DEBATE_LAB_SPEC.md`, with the PDF as historical context. Do not resurrect answered questions or infer the PDF's missing opening sentence. If you find a genuine product contradiction, explain it and ask a focused question rather than silently changing the requirements.

## 2. Working agreement

- Be brutally honest. Separate implemented behavior, tested behavior, inferred behavior and blocked/unverified behavior.
- Continue through implementation and meaningful verification. A successful build or a convincing screenshot alone does not demonstrate a functioning debate system.
- Make ordinary reversible engineering decisions yourself, document them, and proceed. Do not ask the user to select libraries or repeat settled product choices without a concrete reason.
- Ask only when missing information materially affects scope, user data, authorization, or a requirement that cannot be satisfied as written. Ask in normal chat with concise options and a recommendation. After asking, end the turn and wait; do not continue background work awaiting the answer.
- Give concise progress updates explaining results, uncertainties and the next meaningful check.
- Never silently downgrade a required feature to a placeholder or “future work.” If a required integration is blocked, implement the surrounding supported behavior, document the exact blocker and obtain the necessary decision. Do not declare the whole app complete while required behavior remains blocked.
- Use deterministic fake providers only in explicitly labeled tests/development fixtures. Production must not fall back to generated sample debates, fake transcripts, fabricated citations or invented verdicts.

## 3. Non-negotiable boundaries

The following directory is protected:

```text
/Users/suvojitdutta/Documents/local_models
```

Do not modify, delete, reorganize, overwrite, download into, or create configuration/cache files inside it. Do not modify model weights, manifests or runtime-wide configuration. Use existing models through their local API. Keep all application data, extracted media and optional auxiliary model caches outside that directory. Audit paths used by dependencies so default caches cannot accidentally land there.

Do not replace, reinstall, upgrade, restart or reconfigure the user's Ollama service to make the app work without an explicit user decision. Do not kill unrelated processes or unload another application's active model. This implementation task permits bounded inference tests through the existing API and normal app-owned request lifecycle operations; it does not permit destructive environment changes.

Install ordinary project dependencies in an isolated project environment when authorized by the host's permissions. Do not change global Python or Node packages. Before downloading an additional transcription model or making a system-level installation, identify the need, location and expected size when known, then ask if authorization is required. No auxiliary model download is authorized merely because the specification mentions MLX Whisper.

Keep inference and application storage local. Do not add a cloud inference fallback, paid service, telemetry, public hosting, remote fonts, account system or external database. Optional Ollama search is the agreed exception for external research, and remains disabled by default. Never buy credits or automatically upgrade a plan.

Use synthetic or expressly supplied test evidence. Do not scan unrelated personal folders for test material. Never print credentials, embed them in frontend bundles, commit them or include them in exports.

## 4. Build with this stack

- React, TypeScript and Vite for the browser interface.
- Custom scholarly dark styling using CSS variables and scoped CSS.
- Python, FastAPI, Uvicorn and Pydantic for the local backend and validation.
- SQLite with SQLAlchemy and versioned migrations for durable state.
- A separate application-owned artifact directory for original evidence and derived files.
- Server-Sent Events for live output; idempotent HTTP commands for controls.
- An asynchronous Ollama HTTP adapter and an explicit backend session state machine.
- pypdf/pdfplumber, Pillow and a suitable local PDF renderer for document/image processing.
- FFmpeg/ffprobe and a verified local speech-transcription route, with MLX Whisper the specified candidate.
- Local URL retrieval/content extraction and optional Ollama free-account web search.
- pytest and browser end-to-end testing, preferably Playwright.

Choose compatible stable versions, pin dependencies and include lockfiles. Consult current official documentation when API behavior or compatibility is uncertain. Record a justified deviation if a selected component cannot meet the requirements; ask before changing a product-level choice. Avoid adding a general autonomous-agent framework, cloud queue, vector service or other infrastructure unless a demonstrated requirement needs it.

The backend owns state. React state and browser local storage must never be the sole source of truth. Serve the built frontend and API locally on loopback through a documented launch command. Provide a development workflow as well as a normal local-use workflow.

## 5. Agent configuration and runtime verification

Default roles and exact model IDs from prior read-only inspection:

| Role | Default model |
|---|---|
| Alpha | `gpt-oss:20b` |
| Bravo | `qwen3:30b-a3b-thinking-2507-q4_K_M` |
| Judge | `gemma4:31b-mlx` |
| Charlie | `gemma4:31b-mlx` |

Previously observed endpoint: `http://127.0.0.1:11434`. Previously observed hardware: Apple M5 Pro, 48 GB unified memory. Recheck availability and capabilities; these are prior observations, not guarantees about the current environment.

All four roles need independent model selectors. Charlie and Judge may share weights but must not share conversational histories or private role state. Store exact model IDs and available digests, generation settings, endpoint, role prompt versions and capability metadata with every run.

Changing model defaults affects new debates only. Resume and Restart retain pinned assignments. To use a different assignment, create a new debate, optionally copying settings. A missing model or changed digest must produce an explicit recoverable condition, never automatic substitution or downloading.

Perform bounded live capability probes before relying on tool calls, vision, structured output, thinking settings, cancellation or unloading. Do not assume an advertised capability has been proven functional. Do not assume a vision model transcribes audio. Do not expose raw private thinking in UI, transcripts, logs or exports.

Schedule only one app-owned heavy inference job at a time. Coordinate Charlie's ingestion work with debate and judgment work rather than running three large models concurrently. Measure memory and loading behavior at conservative context lengths before increasing them. Do not attempt to occupy all 48 GB or assume stored model size equals working memory.

## 6. Critical behavior that must survive real use

Implement every requirement in the specification. Pay particular attention to these failure-prone areas:

### Durable session controller

Implement an explicit transition table with legal commands, prerequisites and effects for every state and phase. Separate an authoritative state from an activity label. Persist a job-start intent before launching work and use run ID, job/generation ID and expected state revision to reject stale results.

Commit completed turn, evidence version, usage, next-speaker pointer and recovery checkpoint atomically. Emit durable completion only after that transaction succeeds. Use idempotency keys and one effective controller lease so duplicate commands, multiple browser tabs or reconnects cannot launch duplicate inference.

Pause must interrupt actual inference and app-owned processing, not just suppress output. Resume restores the saved semantic state and regenerates an interrupted turn from its beginning; it does not pretend to resume the exact internal token state. Restart creates a separate fresh run and preserves the previous run. Old output must never leak into the new run.

A cancellation failure is a real failure: report it, keep the new work from starting, and do not label the run fully paused while old inference is still active. Verify provider behavior rather than assuming that closing a browser connection cancels the model.

Support Pause/Resume in ingestion and judgment as specified. Stop & Judge freezes completed arguments and admitted evidence and excludes unfinished work. Cancel works during ingestion, debate and judgment without producing a new verdict. Preserve terminal session history until explicit deletion.

### Recovery and resource limits

Checkpoint after every completed turn, evidence/instruction addition and control action. Recover across browser closure, backend failure and application restart without relying on a live model cache. On unclean recovery, require manual Resume/Retry rather than automatically continuing unattended.

Maintain the selected default of 12 completed turns and 15 active minutes. Calibrate and expose finite token allowances for ingestion, debate and judgment, keeping the judgment reserve separate. Distinguish context size, per-request generation limits and cumulative usage. Record an explained provisional tuning choice if measurements remain incomplete; never call it calibrated without evidence.

Count active time according to the spec. Pause/wait/offline time must not be charged as debate time. Preserve tokens consumed by failed or interrupted attempts when known; display uncertainty when final usage is missing. Do not replace unknown usage with zero. Use conservative reservations and disclose enforcement limitations if the runtime cannot provide exact interrupted-token accounting.

Test hard time/token limits during an active response, not merely between turns. Use bounded cleanup, loading and processing timeouts. Do not allow an unbounded retry loop or repeated information request to bypass limits.

### Evidence and Charlie

Implement every agreed input type: pasted text, PDF/text/Markdown files, images, audio, video and public user-supplied URLs. Preserve originals, hashes, source IDs, locators, extraction versions and uncertainty. Distinguish verbatim source content, extracted text, transcription and Charlie's interpretation.

Image references must open the relevant image; PDF citations must identify the correct page/passage; media citations must seek to the relevant timestamp. Disclose sampling gaps in video processing. A blocked, ambiguous, partial or unsupported source must remain visible and cannot be mislabeled fully processed.

Both debaters have access to the same admitted evidence. While paused, the user may add evidence or shared instructions; keep prior turns unchanged and record the new versions. Charlie cannot silently rewrite the proposition or discard evidence based on relevance.

Either debater may request information. Save the request, pause, and offer the user three paths: answer with material, decline, or continue without it. Process any supplied material into the shared record before resuming the pending turn. Implement ambiguity handling without endless re-asking of declined questions.

### Honest judgment

Implement explicit overall surrender with brief judge confirmation; conceding one point is not surrender. Support Alpha wins, Bravo wins, tie and inconclusive, including insufficient completed debate. Do not manufacture a winner to satisfy a schema.

Judge a frozen snapshot with the specified rubric: evidence, logic, relevance and engagement with objections. Include concise public reasons, scores, turn/source references and limitations. Validate both output structure and referenced identifiers before committing a verdict. Scores are not probabilities or factual proof.

Keep model/source claims separate from verified facts. A reference resolving successfully does not establish that it supports the attached claim. Unsupported factual claims must remain identifiable; describe the limits of any automated support assessment.

### Network and evidence boundaries

Default mode fetches only supplied URLs and permitted redirects; it must not autonomously search or follow discovered links. Optional Ollama search requires explicit session enablement and a server-side API key. Bound search calls, handle unavailable credentials/quota/network errors and share resulting evidence with both sides. Do not bypass paywalls or site restrictions.

Restrict supplied URL retrieval to public HTTP(S) resources. Validate redirects and resolved destinations, block local/private-network targets and non-web schemes, and bound response size/time. Keep the trusted loopback Ollama connection separate from untrusted evidence URL handling. Sanitize rendered Markdown/HTML and treat source content as data, never executable instructions.

## 7. UI quality bar

Build a polished scholarly dark application, not a generic chatbot page. Follow the specification's visual direction: charcoal surfaces, restrained warm accents, serif headings, readable body typography and a calm reading experience. Bundle any fonts/assets locally and respect their licenses.

Required views and interactions:

- Session library with saved, completed, canceled and recoverable sessions.
- New-debate setup with proposition, opposing positions, four model selectors, evidence, limits and search mode.
- Live debate chamber with labeled speakers, phases, activity, progress, usage and checkpoint status.
- Evidence inspector with original and derived content, citation navigation and media timestamps.
- Claims/concessions panel and a distinct Judge panel.
- Information-request and paused-input workflows.
- Clearly distinct Pause, Resume, Restart, Stop & Judge and Cancel actions.
- Markdown/JSON exports and explicit deletion.
- Visible, actionable loading/error/recovery/unsupported-capability states.

Preserve reading position during streaming and provide “Follow live.” Support keyboard use, focus visibility, readable contrast and narrow layouts. Do not convey role/state only through color. Inspect actual rendered screens with the browser tool; do not claim visual QA from source code alone.

## 8. Execution plan — continue through all stages

Create a concise implementation plan and a requirements-to-verification checklist, then proceed. Keep a small progress document with decisions, completed work, blockers and the next resumable step so another agent can continue without restarting discovery.

### Stage 1: Inspect and establish contracts

Inspect files, applicable instructions, runtime availability and dependency tooling. Recheck model IDs without altering the model directory. Define state transitions, persistence schemas, event contracts, role-output schemas and adapter interfaces. Create a traceability table for all specification sections and AC-01 through AC-22. Identify integration probes and any prerequisite requiring user input.

### Stage 2: Implement durable orchestration

Build migrations, storage, event sequencing, the controller, worker ownership, cancellation, clock/usage accounting and recovery. Use a controllable fake provider in tests to force slow streams, late output, cancellation failure, malformed output and crash boundaries. Establish atomic completion and duplicate-command behavior before relying on the UI.

### Stage 3: Connect real inference

Implement the local Ollama adapter, model discovery, pinned assignments and sequential scheduling. Run short, bounded live tests with the specified models. Implement streaming public text and validated structured actions without leaking thinking output. Choose a tested framing strategy for mixing live public arguments with machine-readable claims/concessions/requests; do not expose raw JSON as the debate experience or make brittle text matching the sole controller authority.

### Stage 4: Complete evidence and web integrations

Implement local ingestion, provenance, Charlie, shared evidence versions, user information requests and all required modalities. Add user-supplied URL retrieval and optional free-account search. If an auxiliary model or search credential is unavailable, complete the integration and deterministic tests, but explicitly mark the unexecuted live check. Ask for the prerequisite when needed; do not erase the requirement.

### Stage 5: Build and integrate the complete interface

Wire the UI to real backend state and streamed events. Complete the library, setup, chamber, evidence/claims panels, judge view, model configuration, pause-input flow, exports and recovery experience. Inspect browser rendering at laptop and narrow sizes and fix observed problems.

### Stage 6: Verify, calibrate and package

Run the acceptance matrix, real-model smoke tests, controlled failure/recovery checks and browser end-to-end workflows. Calibrate conservative operating defaults and document actual measured limitations. Provide a reproducible install/build/launch workflow, clean shutdown and recovery instructions. Inspect the final app rather than relying on an earlier build.

Do not stop after the first attractive screen or first successful debate. Stages are implementation order, not permission to defer the rest of the agreed scope.

## 9. Verification evidence required

Keep a verification report mapping **every AC-01 through AC-22** to:

- Implementation location or feature.
- Test name or reproducible manual steps.
- Provider mode: deterministic fake, live Ollama, live external search, or browser integration.
- Actual result: passed, failed, blocked, or not run.
- Relevant evidence location and precise limitations.

Do not mark a live integration passed because a mock test passed. Do not mark recovery passed because a UI refresh worked. Do not claim cancellation stops computation without evidence from the real adapter/runtime behavior.

At minimum, verify:

1. A real short debate with Alpha and Bravo, Charlie-prepared supplied evidence and a real Judge verdict.
2. Live Pause mid-response, persisted state, Resume from the last complete turn and exclusion of the interrupted text from judgment.
3. App-owned backend termination around checkpoint boundaries in an isolated test instance, followed by recovery with no duplicated or half-committed turns. Do not restart the user's laptop to test this; describe any actual reboot check as unperformed unless explicitly done by the user.
4. Restart and late-output rejection; cancel during each processing phase; repeated Stop & Judge and duplicate commands.
5. Evidence/instruction additions and information-request answer/decline/continue paths.
6. Turn/time/token boundaries, separate judgment allowance and interrupted-usage uncertainty.
7. Representative text, scanned-PDF, image, audio and video fixtures with source navigation and limitations.
8. Default URL-only behavior, optional search mode and credential/quota/network-failure handling. A missing API key blocks the live search check, not deterministic integration tests or the rest of the application.
9. Model default changes, pinned-model persistence, missing-model and changed-digest behavior.
10. UI streaming/scroll behavior, keyboard controls, evidence navigation, verdict, session recovery and exports in a real browser.

Use isolated test databases/artifact directories. Tests must never delete the user's saved sessions or touch protected model files. Match tests to meaningful invariants and failures; avoid large suites that simply mirror implementation details. Once relevant checks pass, rerun them only when changes or failures justify it.

## 10. Deliverables and completion criteria

Deliver:

- Complete frontend/backend source and versioned role prompts.
- Database migrations, reproducible dependencies and lockfiles.
- Configuration examples without secrets, including model assignments and optional search settings.
- A documented normal local launch command and development commands.
- A README covering prerequisites, startup, storage paths, shutdown, resume/recovery, model configuration, modality dependencies and search setup.
- Meaningful automated tests and representative non-sensitive fixtures.
- Requirements traceability and verification report for AC-01 through AC-22.
- Browser screenshots or equivalent reviewable visual evidence from the actual final app.
- A short record of implementation decisions, measured resource defaults, remaining limitations and any blockers.

Do not edit the original specification to make missing implementation appear compliant. Record proposed deviations separately and obtain a decision when they change product behavior. Do not publish, deploy publicly, push changes or create a pull request unless separately requested.

Your final response must state:

1. What was built and where it is saved.
2. The exact command the user can run to launch it.
3. What was verified with real local models versus test doubles.
4. Whether all mandatory acceptance criteria passed; list any failed, blocked or unrun criteria.
5. Known limitations and the specific next action required from the user, if any.

Never call the app complete or production-ready merely because compilation succeeds. If a prerequisite blocks complete verification, deliver the completed work with the precise limitation and do not overstate readiness.

Begin by reading the specification and inspecting the project. Then implement and verify the application through completion within the boundaries above.
