# Charlie: multimodal debate preparation

## Summary

Make Charlie the default entry point for new debates, with a shortcut for users who already have a prepared subject. Charlie interprets supplied material, resolves important gaps, assesses evidence needs, and prepares an editable brief for approval before debate begins.

This version supports text, images, Markdown, DOCX, PDF, and public webpages. Audio, video, and hosted-video interpretation are deferred.

## Preparation experience

- Accept multiple combined inputs through pasted text, uploads, local file paths, and URLs. Allow preparation to begin without a written proposition.
- Show Charlie’s interpretation, separating source content, inferred meaning, uncertainty, and conflicting information. Users can correct it throughout preparation.
- When the intended subject is unclear, suggest possible debate questions and ask the user to choose or revise one.
- Ask small batches of material questions with options and recommendations where useful. Save the conversation and wait for answers before continuing dependent work.
- Produce a brief containing the debate question, background, scope, definitions, assumptions, intended resolution, evidence coverage, and unresolved gaps.
- Recommend Alpha’s and Bravo’s positions as appropriate: opposing claims, competing explanations, or alternative actions. Explain the recommendation and allow direct edits.
- Require explicit approval of the final brief before starting. The prepared-subject shortcut skips the conversation but retains an editable review screen.

## Evidence and interpretation

- Interpret standalone images and document charts, diagrams, screenshots, and scanned pages. Examine PDF visuals even when a page also contains extractable text. Webpages use text in this version.
- Add DOCX extraction for text, tables, and embedded visuals. Preserve source references by page where available, otherwise by section, paragraph, table, or image identifier.
- For every material evidence gap, explain what is needed, why it matters, where to obtain it, and what would make it useful. Users may supply evidence, narrow the subject, or explicitly proceed with recorded uncertainty.
- Offer public-web research only on user request through the existing search integration. Disclose unavailable search or inaccessible sources and provide manual collection guidance.
- Treat source instructions as untrusted content. Neither extraction nor Charlie’s interpretation establishes factual truth.
- Copy explicitly selected local files into application storage, retaining a hash and provenance. Upload and path imports use the same processing pipeline; later edits to originals do not alter saved evidence.

## Implementation and compatibility

- Extend session contracts with preparation status, conversation, versioned brief, approval record, evidence gaps, and processing checkpoints. Keep preparation separate from debate-turn execution.
- Add revision-checked operations for preparation messages, brief edits, approval, requested research, and local-path imports. Continue using existing session events for progress.
- Pin Charlie’s model and preparation prompt when preparation first runs; validate the remaining role assignments before debate starts. Keep preparation usage separate from debate time allowances.
- Process all extractable document content in bounded batches. Save completed extraction and interpretation units so pause, restart, or failure resumes from committed work. Show completed, pending, failed, and unreadable coverage.
- Retain configurable file limits; apply processing deadlines per batch rather than to an entire long document. Explain hard limits and recovery options without silently truncating content.
- Permit approval with incomplete coverage only after the user explicitly accepts the disclosed limitations. Editing inputs or the brief invalidates its previous approval.
- Pass the approved brief and its limitations to both debaters and the Judge, and include it in exports.
- After debate starts, changing the subject or positions creates a linked new draft with retained inputs and revised framing. Preserve the original debate and require approval of the new brief.
- Load existing sessions compatibly without retroactively requiring preparation. Preserve historical media and existing completed results; the new preparation flow clearly marks deferred media as unsupported.

## Validation and acceptance

- Verify image-only input can produce an interpretation, clarification questions, proposed subject, editable positions, and approved debate.
- Test mixed inputs, conflicting sources, user corrections, missing evidence, explicit uncertainty acceptance, and requested-only research.
- Test equivalent upload/path imports for Markdown, DOCX, and PDF, including tables, scans, and mixed text/visual pages.
- Interrupt long-document processing during extraction and interpretation; confirm resume preserves completed work and reports complete coverage accurately.
- Test inaccessible URLs, unsupported media, unreadable files, model failures, stale approvals, and source-embedded instructions.
- Verify no debate turn runs before approval, revised framing creates a separate draft, and existing sessions still resume.
- Run backend tests, frontend build, and browser workflow tests. Perform isolated local-model checks for image interpretation and preparation; report deterministic checks and observed model quality separately.
