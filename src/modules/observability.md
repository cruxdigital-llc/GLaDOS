# GLaDOS Observability Module

**Goal**: ensure every action is faithfully traced and the project status is kept in sync.

## Instructions

### 1. Update Trace
-   **Target**: The active `specs/[YYYY-MM-DD]_[name]/README.md`.
-   **Action**: Log the following:
    -   Key decisions made.
    -   Files created or modified (with links) — includes DSPy artifacts (`requirements_data.json`, `plan_data.json`, `spec_data.json`, `tasks_data.json`).
    -   Test results (if applicable).
    -   Persona feedback (if applicable).

### 2. Update Status
-   **Target**: `{{STATUS}}` (previously in project root).
-   **Action**: Update the following sections if changed:
    -   **Architecture**: If tech stack or major patterns changed.
    -   **Current Focus** (CRITICAL):
        -   **Hierarchy**: Maintain `Epic` -> `Feature` -> `Task` structure.
        -   **Specificity**: Do not use generic terms like "Coding". Use "Implementing Auth Middleware in auth.ts".
        -   **State**: move completed items to "Recent Changes".
    -   **Known Issues**: Add discovered bugs or debt.
    -   **Recent Changes**: summarize completed workflows.
