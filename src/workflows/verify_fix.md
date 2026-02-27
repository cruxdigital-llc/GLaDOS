# Verify Fix

**Goal**: Ensure no regressions and close the bug.

## Prerequisites
-   Fix is implemented and passes repro test.

## Process

### 1. Resume Trace
-   Select bug directory.
-   Log resumption.

### 2. Regression Testing (QA Persona)
-   Run the full test suite.
-   Check for side effects in related modules.

### 3. Code Review (Architect Persona)
-   Ensure the fix adheres to standards.
-   Check if any new technical debt was added.

### 4. Cleanup
-   Merge the reproduction test into the main test suite (if appropriate) to prevent regression.

### 5. Completion
1.  **Status**: Update `{{STATUS}}`:
    -   Remove from "Known Issues".
    -   Add to "Recent Changes".
2.  **Trace**: Mark `specs/[...]/README.md` as CLOSED.
