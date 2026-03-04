# (GLaDOS) Plan Feature

**Goal**: Analyze requirements and create a high-level plan for a new feature.

## Prerequisites
- [ ] `{{STATUS}}` exists.

## Process

### 1. Initialize Trace
-   Ask user for the Feature Name (e.g., "User Authentication").
-   Convert the name to kebab-case (e.g., `user-authentication`).
-   **CRITICAL**: Create a directory: `specs/[YYYY-MM-DD]_feature_[kebab-case-name]/`.
    -   The naming convention is `YYYY-MM-DD_prefix_user-name` — the last `_` separates the system prefix from the user-provided kebab-case name.
    -   **DO NOT** create a `plans/` directory.
    -   **DO NOT** create numbered files like `001_plan.md` in the root or `plans/`.
    -   ALL work must happen inside the timestamped `specs/` directory.
-   Create `README.md` (The Trace Log).
-   Log session start.

### 2. Context & Persona Selection
Invoke module: `{{MODULES}}/capabilities.md`
-   **Context**: Determine what tools can assist with this feature (e.g., Browser for UI).

-   **Scan**: Check the installed personas directory at `{{PERSONAS}}/`.
-   **Present**: List all available personas to the user.
-   **Select**: Ask: "Which Personas should assist with this feature?" (e.g., Security Expert, Accessibility Lead).
-   **Log**: Record the list of **Active Personas** in `specs/[...]/README.md`.

### 3. Requirements Analysis
-   Ask: "What is the goal of this feature?"
-   Ask: "What are the success criteria?"
-   Create `specs/[...]/requirements.md`.

### 4. High-Level Plan
-   Draft a plan: "How will we approach this?"
-   Create `specs/[...]/plan.md`.

### 5. Observability Update
> [!IMPORTANT]
> Invoke module: `{{MODULES}}/observability.md`
> -   **Context**: Log decisions in trace, add feature to "Active Tasks" in status.

### 6. Handoff
-   Suggest running `/glados/spec-feature` next.
