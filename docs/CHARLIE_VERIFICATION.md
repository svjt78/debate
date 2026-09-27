# Charlie preparation verification

Date: 2026-09-24.

## Implemented

- Default guided preparation and prepared-subject shortcut; combined text, image, document, URL, upload and path inputs.
- Saved clarification conversation, structured evidence requests and collection guidance, manually requested research, editable question and positions, approval before debate, and linked revised drafts.
- Separate preparation state, model/prompt pinning, usage accounting, pause/resume, and backend recovery.
- Incremental extraction and interpretation with retained originals, passage locators, coverage warnings, and resumable checkpoints.
- Brief, approval, and accepted limitations included in debate/Judge context and exports; old saved sessions retain their lifecycle.

## Deterministic verification

- Backend suite: **69 passed**. Includes the original 55 tests and 14 preparation tests covering approval, invalidation, preservation, image-only input, interrupted processing, search authorization/failure, unsupported content, local-path copies, DOCX extraction, multipage PDFs, URL dispatch, backend restart, and concurrent-session guards.
- Frontend TypeScript/Vite build: passed.
- Browser checks: **3 passed** (two new preparation checks and the existing library/source-inspector/export/layout regression), covering guided preparation through synthetic debate and fork, prepared shortcut, upload, path control, edit invalidation, and a 390-pixel viewport.
- Desktop and mobile preparation screenshots were inspected. No horizontal overflow was observed in the tested narrow layout.
- Browser model output is deterministic test data. These tests verify the application workflow, not model understanding or evidence quality.

## Real-model checks

Both probes used the existing `gemma4:31b-mlx` model and a separate `.data/preparation-verification` database. They did not start a debate, change model assignments, lower memory safeguards, or modify existing debate records.

- Image-only preparation: extraction completed; inference stopped with **“Memory headroom below 4 GiB during generation.”** The session remained `FAILED_RECOVERABLE`, with no debate turns or approval. See [image probe record](live-preparation.json).
- Text-only preparation: inference stopped with the same memory safeguard. No debate turns or approval were produced. See [text probe record](live-preparation-text.json).
- Consequently, real-model interpretation quality and complete real-model preparation are **not verified** in this run. Live public search was not exercised; requested-only behavior and failure handling were tested deterministically.

## Coverage limits

- Audio, video and hosted-video interpretation are deferred. Webpages use text only.
- DOCX text, tables, embedded raster images, and cached chart values are extracted. Native chart layout, floating shapes, and unsupported visual formats can require a PDF/screenshot. Warnings remain visible and require explicit acceptance before approval.
- File/page limits remain configurable; batching is resumable, not unlimited. Unreadable content and context overflow are disclosed, not silently discarded.
- Full originals and intermediate notes are retained, but compact summaries can omit nuance. Charlie's judgments are model assessments rather than factual verification.

## Reproduction

```sh
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
npm run build --prefix frontend
```

The isolated browser fixture is `backend/tests/preparation_preview.py`, requires `PREPARATION_PREVIEW_DATA`, and must only be launched with a disposable data directory and `PYTHONPATH=backend:backend/tests`. Run `frontend/tests/preparation.spec.ts` against that fixture, not the production server: its expectations depend on synthetic responses.

Explicit live probes: `.venv/bin/python scripts/live_preparation.py` and `.venv/bin/python scripts/live_preparation.py --text`. They require an idle model service and sufficient memory.
