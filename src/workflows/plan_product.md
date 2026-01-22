## Prerequisites
- [ ] Mission is defined (`MISSION.md`).
- [ ] `glados/PROJECT_STATUS.md` is up to date.

## Process

### 1. Initialize Trace
Create a directory: `specs/[YYYY-MM-DD]_plan_product/`.
Create a `README.md` inside it.
Log the start of the session in `specs/[YYYY-MM-DD]_plan_product/README.md`.

### 2. Roadmap Definition
Discuss with the user:
-   **MVP Features**: What must be in the first release?
-   **Future Horizons**: What comes later?

Create/Update `ROADMAP.md` in the project root.
**Include Header**:
```markdown
<!--
GLaDOS-MANAGED DOCUMENT
Last Updated: [Date]
To modify: Edit directly.
-->
```

### 3. Tech Stack Definition
Check for existing standards in `standards/tech-stack.md`.
If none, ask the user to define:
-   Frontend
-   Backend
-   Database/Storage
-   Infrastructure

Create/Update `TECH_STACK.md` in the project root.
**Include Header**:
```markdown
<!--
GLaDOS-MANAGED DOCUMENT
Last Updated: [Date]
To modify: Edit directly.
-->
```

### 4. Observability Update

> [!IMPORTANT]
> **Trace**: Log the decisions made and file paths in `specs/[YYYY-MM-DD]_plan_product/README.md`.
> **Status**: Update `glados/PROJECT_STATUS.md`:
> -   "Architecture": Summarize the Tech Stack.
> -   "Active Tasks": Add the top items from the MVP roadmap.

### 5. User Verification
Request review of the generated files.
