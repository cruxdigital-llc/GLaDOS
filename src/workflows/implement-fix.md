# (GLaDOS) Implement Fix

**Goal**: Apply the fix and verify passes the reproduction test.

## Prerequisites
-   Fix plan exists.

## Process

### 1. Resume Trace
-   Select bug directory.
-   Log resumption.

### 2. Implementation
-   Modify the code in `src/`.
-   Log specific file changes.

### 3. Local Verification
-   Run the reproduction script/test created in `Identify Bug`.
-   **Success**: The test passes.
-   **Failure**: Revisit the implementation.

### 4. Observability Update
> [!IMPORTANT]
> **Trace**: Log the code changes and test result in `specs/[...]/README.md`.

### 5. Handoff
-   Suggest running `/glados/verify-fix` next.
