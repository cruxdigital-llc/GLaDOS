# (GLaDOS) Review Codebase

**Goal**: Analyze an existing codebase to understand its structure and populate `PROJECT_STATUS.md`.

## Prerequisites
- [ ] `{{STATUS}}` exists (or will be confirmed created).

## Process

### 1. Initialize Trace
Create a directory: `specs/[YYYY-MM-DD]_review-codebase/`.
Create a `README.md` inside it.
Log the start of the session in `specs/[YYYY-MM-DD]_review-codebase/README.md`.

### 2. Exploration
1.  **Structure**: List files/directories to understand the high-level layout.
    -   *Tools*: `list_dir`, `find_by_name`.
2.  **Dependencies**: Check package files (`package.json`, `pyproject.toml`, etc.) to identify the tech stack.
3.  **Documentation**: Read `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, and other docs.

### 3. Deep Analysis
1.  **Patterns**: Identify key patterns (MVC, Hexagonal, etc.).
2.  **Dependency Graph**: Infer architectural patterns from dependencies (e.g., "Express + Prisma → REST API").
3.  **Convention Detection**: Auto-detect naming conventions, directory structure patterns, test frameworks.
4.  **Existing Docs Ingestion**: If project documentation exists, incorporate key findings into standards/philosophy candidates.
5.  **Standards Inference**: Infer existing standards (formatting, naming, error handling).
6.  **Debt**: Note obvious technical debt or "TODOs".
7.  **Health Check**:
    -   Test coverage: Is there a test framework? Coverage tool?
    -   Linting: Are linter configs present?
    -   CI/CD: Is there a pipeline definition?
    -   Type checking: Is static typing enforced?

### 4. Status Population
Update `{{STATUS}}` with:
-   **Architecture**: A summary of your findings (Tech Stack, Patterns).
-   **Mission**: Infer the mission if not explicitly stated (mark as "Inferred").
-   **Active Tasks**: Leave empty or add "Determine Roadmap".
-   **Known Issues**: Add any debt discovered.

### 5. Observability Update

> [!IMPORTANT]
> **Trace**: Log the findings and analysis in `specs/[YYYY-MM-DD]_codebase_review/README.md`.
> **Status**: Ensure `{{STATUS}}` is fully populated based on your findings.

### 6. Completion
Ask the user if they want to proceed to "Retrospect" or "Plan Feature".
