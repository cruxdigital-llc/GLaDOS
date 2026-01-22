# Review Codebase

**Goal**: Analyze an existing codebase to understand its structure and populate `PROJECT_STATUS.md`.

## Prerequisites
- [ ] `glados/PROJECT_STATUS.md` exists (or will be confirmed created).

## Process

### 1. Initialize Trace
Create a directory: `specs/[YYYY-MM-DD]_review_codebase/`.
Create a `README.md` inside it.
Log the start of the session in `specs/[YYYY-MM-DD]_review_codebase/README.md`.

### 2. Exploration
1.  **Structure**: List files/directories to understand the high-level layout.
    -   *Tools*: `list_dir`, `find_by_name`.
2.  **Dependencies**: Check package files (`package.json`, `pyproject.toml`, etc.) to identify the tech stack.
3.  **Documentation**: specific `README.md` or other docs.

### 3. Analysis
1.  **Patterns**: Identify key patterns (MVC, Hexagonal, etc.).
2.  **Standards**: Infer existing standards (formatting, naming).
3.  **Debt**: Note obvious technical debt or "TODOs".

### 4. Status Population
Update `glados/PROJECT_STATUS.md` with:
-   **Architecture**: A summary of your findings (Tech Stack, Patterns).
-   **Mission**: Infer the mission if not explicitly stated (mark as "Inferred").
-   **Active Tasks**: Leave empty or add "Determine Roadmap".
-   **Known Issues**: Add any debt discovered.

### 5. Observability Update

> [!IMPORTANT]
> **Trace**: Log the findings and analysis in `specs/[YYYY-MM-DD]_codebase_review/README.md`.
> **Status**: Ensure `glados/PROJECT_STATUS.md` is fully populated based on your findings.

### 6. Completion
Ask the user if they want to proceed to "Retrospect" or "Plan Feature".
