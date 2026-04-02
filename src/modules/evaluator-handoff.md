# GLaDOS Evaluator Handoff Module

**Goal**: Assemble a self-contained evaluation brief so a fresh agent can verify work without inheriting any implementation context.

## Usage
Invoked at the end of implementation, before spawning the evaluator agent.

## Instructions

### 1. Identify the Trace
-   **Target**: The active `specs/[YYYY-MM-DD]_[type]_[name]/` directory.

### 2. Assemble the Brief
Create `specs/[trace-dir]/evaluation-brief.md` with the following sections:

#### Section A: What Was Requested
-   Copy the full contents of `requirements.md` from the trace directory.
-   If this is a bug fix, copy `repro_steps.md` instead.

#### Section B: What Was Agreed To
-   Copy the acceptance criteria from `spec.md` (or `plan.md` for bug fixes).
-   If a `contract.md` exists in the trace directory, include it — it takes precedence.

#### Section C: What Changed
-   Run `git diff` against the branch point (or last commit before this trace began) to produce the list of files changed.
-   Include only the file list and a summary-level diff (not the full diff — the evaluator should read files directly).

#### Section D: How to Verify
-   **Test commands**: Extract from project standards or `README.md` (e.g., `npm test`, `pytest`).
-   **Lint commands**: Same source.
-   **App entry points**: If browser tools are available, list URLs or commands to start the app.
-   **Repro steps**: For bug fixes, include the reproduction steps so the evaluator can confirm the fix.

#### Section E: Standards to Enforce
-   List the applicable standards from `product-knowledge/standards/` (use the same filtering logic as `standards-gate.md` — match by scope and keywords).
-   Include file paths so the evaluator can read them directly.

#### Section F: Personas to Consult
-   List the review personas from `{{PERSONAS}}/` that apply to this work.
-   Include file paths so the evaluator can load them directly.

### 3. Log
-   Record "Evaluation brief assembled" in the trace `README.md`.
