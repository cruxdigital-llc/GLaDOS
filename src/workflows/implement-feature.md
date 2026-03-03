# (GLaDOS) Implement Feature

**Goal**: Write code to satisfy the specification.

## Prerequisites
- [ ] `specs/[...]/spec.md` exists.

## Process

### 1. Resume Trace
-   Select the feature directory.
-   Read `spec.md`.
-   Log session resumption.

### 2. Capabilities Check
Invoke module: `{{MODULES}}/capabilities.md`
-   **Context**: checking for tools to speed up implementation (e.g. looking up docs via browser).

### 3. Task Breakdown
-   Create `specs/[...]/tasks.md` (Checklist of implementation steps).
-   Ask user to review the breakdown.

### 3. Implementation Loop
For each task in `tasks.md`:
1.  **Context**: Read relevant source files.
2.  **Code**: Write/Modify code in `src/`.
3.  **Test**: Write/Run unit tests for the specific change.
4.  **Log**: Mark task as done in `tasks.md`.
5.  **Trace**: Log modified files in `README.md`.

### 4. Observability Update
> [!IMPORTANT]
> **Trace**: Ensure all file changes are logged in `specs/[...]/README.md`.
> Invoke module: `{{MODULES}}/pattern-observer.md` — Log any implicit standards or philosophies observed during implementation.

### 5. Handoff
-   Suggest running `/glados/verify-feature` next.
