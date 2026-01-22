# Plan Feature

**Goal**: Analyze requirements and create a high-level plan for a new feature.

## Prerequisites
- [ ] `PROJECT_STATUS.md` exists.

## Process

### 1. Initialize Trace
-   Ask user for the Feature Name (e.g., "User Authentication").
-   Convert to camelCase (e.g., `userAuth`).
-   Create a directory: `specs/[YYYY-MM-DD]_feature_[camelCaseName]/`.
-   Create `README.md` (The Trace Log).
-   Log session start.

### 2. Context & Persona Selection
Invoke module: `glados/modules/capabilities.md`
-   **Context**: Determine what tools can assist with this feature (e.g., Browser for UI).

-   **Scan**: Check the installed `personas/` directory (e.g., `.agent/personas/` or `glados/personas/`).
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
> Invoke module: `glados/modules/observability.md`
> -   **Context**: Log decisions in trace, add feature to "Active Tasks" in status.

### 6. Handoff
-   Suggest running `/spec-feature` next.
