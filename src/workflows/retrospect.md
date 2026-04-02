# (GLaDOS) Retrospect

**Goal**: Review recent work to improve processes and standards.

## Prerequisites
- [ ] `{{STATUS}}` exists.

## Process

### 1. Initialize Trace
Create a directory: `specs/[YYYY-MM-DD]_retrospect/`.
Create a `README.md` inside it.
Log the start of the session in `specs/[YYYY-MM-DD]_retrospect/README.md`.

### 2. Review
Ask the user what specifically they want to retrospect on (e.g., "The last feature", "The bugfix cycle", "General").
1.  **What went well?**: Identify successes.
2.  **What went wrong?**: Identify bottlenecks or failures.

### 3. Improvements
1.  **Process**: Do workflows need updating?
    -   *Action**: Propose changes to `src/workflows/*.md` (or the local copies).
2.  **Standards**: Do coding standards need updating?
    -   *Action**: Create or update `standards/`.

### 4. Observability Update

> [!IMPORTANT]
> **Trace**: Log the discussion and action items in `specs/[YYYY-MM-DD]_retrospective/README.md`.
> **Status**: Update `{{STATUS}}` "Recent Changes" to reflect the retrospective and any process updates.

### 5. Completion
Summarize the action items for the user.

> [!TIP]
> Consider running `{{CMD}}recombobulate` to systematically audit the codebase for standards drift, formalize observations, and clean up any accumulated vibe debt.
