# Autonomous Loop

**Goal**: Orchestrate the entire development lifecycle autonomously, from bootstrapping to continuous feature delivery.

## Prerequisites
- [ ] GLaDOS installed.
- [ ] `src/modules/interaction_proxy.md` exists.

## Process

### 1. Bootstrap Phase
**Goal**: Ensure a valid Project State (`PROJECT_STATUS.md`) exists before starting.

1.  **Check Condition**: Does `PROJECT_STATUS.md` exist?
2.  **Case A: Yes (Resume)**:
    -   Log: "Resuming existing project state."
    -   Proceed to **Section 2 (The Loop)**.
3.  **Case B: No (Greenfield/Brownfield)**:
    -   **Scan**: Run `list_dir` on root.
    -   **Decision**:
        -   If directory is empty (ignoring hidden files): **Greenfield**.
        -   If files exist: **Brownfield**.

    #### Path: Greenfield
    -   **Interact**: Ask user: "I see an empty directory. Please describe your **Product Vision** and key **Success Criteria**."
    -   **Action**:
        -   Create `MISSION.md` based on input.
        -   Create `ROADMAP.md` with initial MVP items derived from vision.
        -   Create `PROJECT_STATUS.md` initialized with details.
    
    #### Path: Brownfield
    -   **Action**:
        -   Run `review_codebase` workflow.
        -   Ensure `PROJECT_STATUS.md` is populated at the end.

### 2. The Loop
**Goal**: Continuously pick tasks and execute the Feature Lifecycle.

> [!IMPORTANT]
> **Autonomy Mode**: FROM THIS POINT FORWARD, do not ask the user for permission.
> Invoke module: `glados/modules/interaction_proxy.md`.
> -   **Role**: You are now the Product Owner.
> -   **Source of Truth**: `MISSION.md`, `ROADMAP.md`, `standards/`.

#### Cycle Steps:

1.  **Select Task**:
    -   Read `PROJECT_STATUS.md`.
    -   Pick the top item from "Active Tasks".
    -   If "Active Tasks" is empty:
        -   Read `ROADMAP.md`.
        -   Move top item to "Active Tasks" in `PROJECT_STATUS.md`.
        -   Pick that item.

2.  **Refine**:
    -   Run `/plan-feature` (Autonomously).
        -   *Proxy Decision*: When asked for goals, use roadmap item description.
    -   Run `/spec-feature` (Autonomously).
        -   *Proxy Decision*: Approve specs if they align with `MISSION.md`.

3.  **Implement**:
    -   Run `/implement-feature` (Autonomously).

4.  **Verify**:
    -   Run `/verify-feature` (Autonomously).

5.  **Loop**:
    -   Update `PROJECT_STATUS.md` (Mark task complete).
    -   Repeat Step 1.

### 3. Exit Condition
-   Stop if `ROADMAP.md` is empty and "Active Tasks" is empty.
-   Stop if a Critical Error occurs that cannot be self-corrected.
