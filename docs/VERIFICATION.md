# Verification report — 21 September 2026

**Not all mandatory acceptance criteria are complete.** Core app behavior is implemented; the user-approved speech model is now installed and audio/video processing has passed live local tests; the supplied hosted-search credential is now configured and a live authenticated request plus result retrieval passed. Full laptop-reboot recovery and broad calibration remain unrun. Test doubles are never production fallbacks.

## Executed evidence

- 49 deterministic backend tests pass (`.venv/bin/python -m pytest -q`). Includes subprocess exit before/after SQLite commit, late result rejection, cancellation failure, role pinning/digest mismatch, source extraction, URL guards, search failures, information requests, and resource limits.
- Production frontend TypeScript/Vite build passes.
- Two real Chrome browser integration tests pass for library, setup, draft, text evidence, source inspector, even turn edits, JSON export, saved real-model verdict/citations/interrupted-attempt marker, and 390px layout. Actual screenshots inspected under `docs/screenshots/`.
- Real default models: completed four-turn debate with Charlie-prepared synthetic evidence and validated Judge output, ~182s (`live-smoke.json`).
- Real default models: Pause during visible Alpha output, interrupted attempt excluded, unknown usage labeled, shared instruction added, Resume, exactly four completed turns and validated verdict, ~171s (`live-lifecycle.json`).
- Native schema framing worked for Alpha/Bravo. Gemma explicitly rejected it; prompt JSON plus exact-fence handling and strict validation worked (`live-probes.json`).
- Request cancellation cleared `/api/ps` residency for each model in ~0.04–0.05s after stream close in the probes (`live-cancellation.json`). This is API-level evidence, not independent GPU instrumentation or a universal latency guarantee.
- Gemma vision correctly described red square and number 42 in a synthetic image (`live-vision.json`). This does not establish OCR/transcription accuracy on arbitrary evidence.
- DNS-pinned public HTTPS retrieval passed for example.com (`live-url.json`).

## Acceptance matrix

| AC | Implementation / evidence | Provider mode | Status and limits |
|---|---|---|---|
| 01 | Controller/pins/public JSON decoder; complete debate and lifecycle reports | Live Ollama + deterministic | Passed four-turn smoke; browser live SSE playback not yet separately stress-tested |
| 02 | Defaults endpoint; pinned assignment/digest checks; API and digest tests | Deterministic | Passed; live model replacement intentionally not performed |
| 03 | Controller cancellation, adapter cleanup; live lifecycle + per-model cancellation | Live Ollama + deterministic | Passed bounded probes; cessation evidence is API-level |
| 04 | Interrupted attempt regeneration and exact completed count | Live Ollama + deterministic | Passed |
| 05 | SQLAlchemy CAS transaction/event store; `test_actual_process_exit_at_transaction_boundary` | Real isolated SQLite subprocess | Passed before/after commit exit cases; not a full OS power-loss test |
| 06 | Restart creates preserved parent/new draft; late output invalidation | Deterministic | Passed; separate live restart race unrun |
| 07 | Frozen snapshot, insufficient-debate outcome, idempotent judge command | Deterministic | Passed no-turn and completed-history paths; broad live early-stop matrix unrun |
| 08 | Phase cancellation paths, no verdict on cancellation | Deterministic | Passed ingestion/debate/judgment; individual live adapter cancellation also passed |
| 09 | Versioned shared sources/instructions and immutable earlier turns | Live Ollama + deterministic | Live instruction addition passed; source addition covered deterministically |
| 10 | Saved requests, all three answers, same pending ordinal | Deterministic | Passed |
| 11 | Active-response deadline, finite reservations/output caps, separate judge reserve | Deterministic | Passed time/turn/reservation boundaries; long-session calibration incomplete |
| 12 | Unknown interrupted usage retains conservative charge | Live Ollama + deterministic | Passed; exact missing runtime usage cannot be reconstructed |
| 13 | Text/Markdown extraction, scanned PDF page rendering, image locators, local media worker | Deterministic extraction + live vision | Local audio/video extraction passed: spoken 40, 24 and 60 recovered correctly with valid timestamps; video frame + Charlie admission passed. Browser timestamp seek check recorded below. Accuracy on arbitrary media remains unproven. |
| 14 | Public IP validation, DNS-pinned HTTP/TLS, redirect loop checks, no discovered-link crawl | Live public URL + deterministic guards | HTTPS fixture passed; adversarial redirect/rebinding integration needs broader coverage |
| 15 | Session opt-in, query cap, source-sharing pipeline, explicit failure request | Deterministic | Missing-key and failure behavior passed. Live authentication and result retrieval passed (`live-search.json`); successful source-sharing and quota/failure behavior tested deterministically. A complete autonomous search-enabled debate has not yet been run. |
| 16 | React text-only rendering, validated action allowlist, source-as-data prompts, local network boundary | Deterministic + browser | Control boundaries tested; no claim that prompting alone eliminates semantic injection |
| 17 | Durable files, WAL/FULL transactions, recovery, manual resume | Deterministic recovery + browser | Browser reopen/recovery design exercised; actual laptop reboot **not run** |
| 18 | Idempotency keys, revision conflicts, file lease, SSE read-only replay | Deterministic | Duplicate commands passed; extended multi-tab stress test unrun |
| 19 | Missing/digest checks, memory headroom guard, blocked source status, disk commit atomicity | Deterministic | Digest/corrupt-source/atomicity tested; low-memory and full-disk UI fault injection **not run** |
| 20 | Markdown/JSON exports from committed state | Deterministic + browser | JSON export checked; comprehensive multimodal archive navigation is limited because media is not embedded |
| 21 | Pydantic verdict plus admitted/completed ID validation | Deterministic + live valid verdicts | Passed invalid-reference rejection; invalid outputs never become invented verdicts |
| 22 | Scholarly dark React UI, source dialog, keyboard Escape, responsive controls | Real Chrome | Desktop/narrow screenshots inspected; full keyboard audit and long streaming scroll stress test remain partial |

## Source-spec traceability

| Specification section | Implementation |
|---|---|
| 1 Product and scope | Full-stack app; user amendments recorded in PROGRESS.md |
| 2 Environment protection | Store path guard; isolated dependencies/cache paths; read/API-only existing models |
| 3 Stack | requirements.lock, frontend/package-lock.json, FastAPI/React/SQLite/SSE |
| 4 Roles/configuration | domain.py, provider.py, controller.pin, prompts/ |
| 5 Lifecycle | domain.TRANSITIONS, controller.command/_stop/run |
| 6 Turns/limits/requests | schedule/change_turns, inference reservations/deadlines, respond |
| 7 Evidence/provenance | evidence.py, cancellable extract.py, source inspector |
| 8 Web | public_get, Evidence.search, session search settings |
| 9 Judgment | frozen snapshot, Verdict validation, Judge panel |
| 10 Persistence/recovery | storage.py, transactional events, Store.recover, exports |
| 11 Interface | frontend/src/main.tsx and style.css |
| 12 APIs/workers | app.py, provider/extractor interfaces |
| 13 Resources/context | single controller, keep_alive=0, context_versions, local retrieval, memory guard |
| 14 Acceptance | Matrix above, backend/tests, frontend/tests, scripts/live_*.py |
| 15 Validation | Explicit blockers/calibration notes below |
| 16 References | Original spec; runtime API behavior checked in live reports |

## Provisional calibration and limitations

The successful four-turn run used 16,384 context and 3,072 generated-token allowance. Judge output used ~1,900 tokens, motivating the increased generation default. Current defaults are 60,000 ingestion, 120,000 debate and 32,000 judgment tokens, with 12 turns/15 active minutes. These are finite provisional operating values, **not a fully calibrated 12-turn guarantee**. Model memory samples during short 4k-context probes showed ~9 GB available after Gemma generation, but did not measure peak memory under every modality/context length.

Context records preserve source IDs, claims and concessions. Oversized context can use disclosed excerpts/Charlie summaries; full originals stay available through local retrieval. A source index that still cannot fit causes a recoverable stop. This is a real operational limit, not a claim of unlimited-document support.

Audio/video libraries are installed in the project venv. The user approved mlx-community/whisper-small-mlx (~481 MB repository); revision 45f3915 is installed under `.data/auxiliary-models/whisper-small-mlx`, and the three selected downloaded files passed Hugging Face checksum verification. Unselected .gitattributes and local downloader metadata account for the verifier inventory warnings. Optional search credentials are read from the server environment or the private credential file, never from exports or frontend code. No model service or protected model-directory changes were made.

## Final handoff state
Normal app is running at http://127.0.0.1:8787 with an empty user library. Completed synthetic real-model runs remain isolated in .data/live-verification, not mixed into user history. The temporary port-8788 preview was stopped after review. No inference or verification task remains running.

Final UI replay fix: replayed events are coalesced into one refresh and revision guards reject stale responses. Rebuilt frontend and reran the standard browser scenario successfully; the optional saved-verdict test was skipped on this last run because its already-reviewed preview server had been stopped. Its preceding run passed.

## Approved speech-model installation and verification
The user explicitly approved option 1A. No Ollama API key was needed for model download or local transcription. The normal launcher now detects the installed local Whisper directory and runs with Hub offline mode. The existing protected model directory remains untouched.

`live-media.json`: synthetic audio transcription passed (~19.8s first invocation); the same speech in a video passed (~1.3s warm system/filesystem state). Both recovered 40 visitors, 24 requests and $60, with valid segment timestamps. Video sampling now always includes the first frame, including clips shorter than the 30-second interval. Low-confidence segments are explicitly flagged when reported probabilities warrant it.

`live-media-admission.json`: real Whisper transcription, real Charlie vision and summary, and admission into the shared evidence record passed in ~50.2s. Transcript segments and the sampled frame retain timestamps; derived visual description is labeled. Transcription provenance records engine/version, local model path and weight SHA-256.

Optional search clarification: the local API at localhost:11434 is unauthenticated. Only the distinct hosted `https://ollama.com/api/web_search` integration needs OLLAMA_API_KEY. It stays disabled by default; live authentication and result retrieval subsequently passed as recorded below. Official reference: https://docs.ollama.com/capabilities/web-search .

Final media browser verification: all three browser tests passed. The app reports transcription configured; the admitted video opens in the source inspector and clicking the second transcript locator seeks playback to 7.5 seconds. Screenshot: docs/screenshots/media-inspector.png. Backend regression suite remains 35 passed. Temporary preview stopped after verification; main app remains on port 8787.

## Hosted-search credential and live test
The user supplied a credential for this integration. It is stored only in .data/secrets/ollama-search-key (0600; directory 0700), excluded from exports/source control. Environment credentials take precedence. Extractor subprocesses do not inherit search credentials.

`live-search.json`: one query to Ollama hosted search succeeded, returned three results, and the first official-documentation result was fetched through the DNS-pinned public URL adapter. No paid fallback, cloud inference, or service reconfiguration was used. Deterministic tests separately verify successful search material is admitted and supplied to both debaters, and 401/403/429 responses pause/fail without exposing credentials. Live quota exhaustion was intentionally not induced.

The per-debate setup checkbox “Allow optional Ollama web search” controls automatic hosted search on/off and defaults to off. The backend rejects model search requests when disabled. Saving a credential does not enable search. Explicitly supplied URL retrieval is separate from this switch.

## First-run judgment context regression
The four-day-workweek example reached all four turns but was rejected by the application byte-bound context guard before Judge inference. Compact JSON and removal of schema display titles and turn bookkeeping reduce wire overhead without changing schema validation, claims, concessions, or stored originals. The guard now also reserves 512 units for framing. The configured context and output limits remain unchanged. Added boundary and schema-field regression tests; all 42 backend tests pass. A copy of the saved run passes context construction using the deterministic provider; see context-recovery.json for the separate real-provider recovery result.

Live recovery succeeded: the saved four-day-workweek session completed with a real Judge verdict (Bravo wins), no error, and identical hashes for all four completed turns before and after recovery. Recorded in context-recovery.json.


## Context policy implementation — 22 September 2026

Implemented automatic per-request expansion to the smallest matching tested tier, with a configurable ceiling (default 32,768), followed by recorded Charlie summaries if needed. The latest contribution from each side, current instructions, all structured claims/concessions and original records are preserved. Summary coverage validation checks identifiers and indices, not semantic fidelity. Retrieval is subject to the same sizing guard. History preparation is charged to the relevant bucket, and actual attempt options/provenance are exported.

No matching preflight tokenizer has been validated. Predominantly ASCII requests within the probe range use a sample-derived model coefficient with a 50% margin plus 512 framing units; non-ASCII bytes are counted conservatively. Other inputs retain the byte bound. A measured underestimate invalidates the coefficient. These are estimates, not proof that every runtime avoids truncation.

Live calibration: Alpha and Bravo passed 16,384 / 24,576 / 32,768 probes. Charlie/Judge passed 16,384 / 24,576; the 32,768 probe hit the provider timeout and was not registered. Boundary markers, structured output, sampled available memory and cancellation/residency were checked. Initial Qwen/Gemma probes exhausted their short 256-token output allowance; repeats used the normal 3,072 allowance. `context-calibration.json` retains results.

Current saved religious-philosophy session: resumed past the context guard, then Bravo exhausted its 3,072 generated-token allowance at turn eight. The original seven turns are identical. It remains FAILED_RECOVERABLE, not complete (`context-long-recovery.json`). A new 12-turn no-source fixture also stopped at a generated-token limit. These failures are distinct from context sizing, and generated-token defaults remain insufficiently calibrated.

The evidence-heavy four-turn fixture completed with a verdict. An initial eight-turn fixture fit without summarization and completed, so it does not count as summary-path validation. Further scenario results are recorded in `context-scenarios.json`.

The browser check passed the context-ceiling update, revision-safe persistence, reported usage/reservation labels and narrow layout. Screenshots were inspected; mobile metric lines were separated after the first visual review.

Forced-summary live verification passed: eight synthetic original turns, six recorded Charlie summaries, a completed Judge verdict, unchanged originals, all inference at 16,384 context; 318 seconds. The earlier smaller fixture fit without summarization and is separately retained in the report.


Final 12-turn evidence-backed attempt stopped after seven completed turns on Bravo's generated-token allowance, not the context guard (`long_evidence` in context-scenarios.json). No automatic reply-limit increase or repeated retry was applied. Thus full 12-turn completion with the current default output allowance is **not verified**. The context changes are implemented and tested, but this separate generation-budget limitation remains unresolved. The real user session likewise remains at seven completed turns.

Final checks: 49 backend tests passed, including interruption during summarization followed by successful resume with unchanged originals. Frontend production build passed. Chrome settings and narrow-layout test passed after the metric layout adjustment; the final mobile screenshot was inspected.
