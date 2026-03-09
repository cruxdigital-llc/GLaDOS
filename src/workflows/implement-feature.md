# (GLaDOS) Implement Feature

**Goal**: Write code to satisfy the specification.

## Prerequisites
- [ ] `specs/[...]/spec_data.json` exists.

## Process

### 1. Resume Trace
-   Select the feature directory.
-   Read `spec_data.json` (or run `python3 {{GLADOS_DSPY}} show --input-dir specs/[...]/ --artifact spec`).
-   Log session resumption.

### 2. Capabilities Check
Invoke module: `{{MODULES}}/capabilities.md`
-   **Context**: checking for tools to speed up implementation (e.g. looking up docs via browser).

### 3. Task Breakdown
-   Run the DSPy engine to generate the task breakdown:
    ```
    python3 {{GLADOS_DSPY}} tasks \
      --input-dir specs/[...feature dir]/ \
      --context-dir product-knowledge/ \
      --output-dir specs/[...feature dir]/
    ```
-   Review the generated `tasks_data.json` with the user.

### 4. Implementation Loop
For each task in `tasks_data.json`:
1.  **Context**: Read relevant source files.
2.  **Code**: Write/Modify code in `src/`.
3.  **Test**: Write/Run unit tests for the specific change.
4.  **Log**: Update `tasks_data.json` — set the task's `status` to `"done"`.
5.  **Trace**: Log modified files in `README.md`.

### 5. Observability Update
> [!IMPORTANT]
> **Trace**: Ensure all file changes are logged in `specs/[...]/README.md`.
> Invoke module: `{{MODULES}}/pattern-observer.md` — Log any implicit standards or philosophies observed during implementation.

### 6. Handoff
-   Suggest running `/glados/verify-feature` next.
