# Identify Bug

**Goal**: Reproduce and isolate a bug.

## Prerequisites
- [ ] `{{STATUS}}` exists.

## Process

### 1. Initialize Trace
-   Ask for a Bug Name/ID (e.g., "Login Timeout").
-   Create `specs/[YYYY-MM-DD]_bugfix_[slug]/`.
-   Create `README.md`.
-   Log session start.

### 2. Reproduction (QA Persona)
-   Ask: "How do we reproduce this?"
-   Create `repro_steps.md` or a reproduction script in the trace directory.
-   **Goal**: Create a failing test case.

### 3. Isolation (Architect Persona)
-   Analyze the stack trace or logs.
-   Identify the specific module/function causing the issue.
-   Log findings in `README.md`.

### 4. Observability Update
> [!IMPORTANT]
> **Trace**: Log the successful reproduction (or failure to reproduce) in `specs/[...]/README.md`.
> **Status**: Add to "Known Issues" in `{{STATUS}}`.

### 5. Handoff
-   Suggest running `/plan-fix` next.
