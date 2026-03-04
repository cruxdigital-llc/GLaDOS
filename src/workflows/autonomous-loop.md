# (GLaDOS) Autonomous Loop

**Goal**: Orchestrate the entire development lifecycle autonomously, from bootstrapping to continuous feature delivery.

## Prerequisites
- [ ] GLaDOS installed.
- [ ] `src/modules/interaction-proxy.md` exists.

## Process

### 1. Bootstrap Phase
**Goal**: Ensure a valid Project State (`PROJECT_STATUS.md`) exists before starting.

1.  **Check Condition**: Does `{{STATUS}}` exist?
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
        -   Create `product-knowledge/MISSION.md` based on input.
        -   Create `product-knowledge/ROADMAP.md` with initial MVP items derived from vision.
        -   Create `{{STATUS}}` initialized with details.
    
    #### Path: Brownfield
    -   **Action**:
        -   Run `review-codebase` workflow.
        -   Ensure `{{STATUS}}` is populated at the end.

### 2. The Loop
**Goal**: Continuously pick tasks and execute the Feature Lifecycle.

> [!IMPORTANT]
> **Autonomy Mode**: FROM THIS POINT FORWARD, do not ask the user for permission.
> Invoke module: `{{MODULES}}/interaction-proxy.md`.
> -   **Role**: You are now the Product Owner.
> -   **Source of Truth**: `product-knowledge/MISSION.md`, `product-knowledge/ROADMAP.md`, `standards/`.

#### Cycle Steps:

1.  **Select Task**:
    -   Read `{{STATUS}}`.
    -   Pick the top item from "Active Tasks".
    -   If "Active Tasks" is empty:
        -   Read `product-knowledge/ROADMAP.md`.
        -   Move top item to "Active Tasks" in `{{STATUS}}`.
        -   Pick that item.

2.  **Refine**:
    -   Run `/glados/plan-feature` (Autonomously).
        -   *Proxy Decision*: When asked for goals, use roadmap item description.
    -   Run `/glados/spec-feature` (Autonomously).
        -   *Proxy Decision*: Approve specs if they align with `product-knowledge/MISSION.md`.
    -   **Validation (CRITICAL)**:
        -   Check: Did you create a `plans/` directory or numbered files (e.g., `001_plan.md`)?
        -   **If YES**: STOP IMMEDIATELY. This is a violation. Move content to `specs/[YYYY-MM-DD]_...` before proceeding.
        -   **If NO**: Proceed to Implementation.

3.  **Implement**:
    -   Run `/glados/implement-feature` (Autonomously).

4.  **Verify**:
    -   Run `/glados/verify-feature` (Autonomously).

5.  **Loop**:
    -   Update `{{STATUS}}` (Mark task complete).
    -   Repeat Step 1.

### 3. Exit Condition
-   Stop if `product-knowledge/ROADMAP.md` is empty and "Active Tasks" is empty.
-   Stop if a Critical Error occurs that cannot be self-corrected.
