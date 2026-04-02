# (GLaDOS) Plan Fix

**Goal**: Design a fix that resolves the bug without side effects.

## Prerequisites
-   Bug directory exists (`specs/[...]_bugfix_[slug]/`).
-   Bug is reproduced.

## Process

### 1. Resume Trace
-   Select bug directory.
-   Log resumption.

### 2. Root Cause Analysis
-   Confirm the root cause identified in the previous step.
-   Ask: "Why did this happen?" (5 Whys).

### 3. Fix Strategy (Architect Persona)
-   Propose a fix.
-   Check: "Does this introduce new risks?"
-   Check: "Is this a band-aid or a real fix?"
-   Create `specs/[...]/plan.md`.

### 4. Observability Update
> [!IMPORTANT]
> **Trace**: Log the chosen strategy in `specs/[...]/README.md`.

### 5. Handoff
-   Suggest running `{{CMD}}implement-fix` next.
