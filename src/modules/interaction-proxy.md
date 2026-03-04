# Module: Interaction Proxy

**Goal**: Enable fully autonomous execution by having the agent answer its own interactive questions based on project context.

## Usage
Invoked by `autonomous-loop.md` or any workflow running in `--autonomous` mode.

## Context
You are no longer just the workman; you are acting as the **Proxy User** and **Product Owner**.
When the workflow reaches a step that normally requires User Input (e.g., "Approve this plan", "Clarify requirements"), you **MUST** answer it yourself.

## Instructions

### 1. Decision Making Sources
Consult these files in order of priority to make decisions:
1.  **`product-knowledge/MISSION.md`**: The North Star. Does this decision align with the ultimate goal?
2.  **`product-knowledge/ROADMAP.md`**: The Strategic Plan. Is this feature described here?
3.  **`standards/*.md`**: The Law. Does this adhere to coding/arch standards?
4.  **`PROJECT_STATUS.md`**: Current Context. What is the state of the app?

### 2. Handling Interaction Types

#### Type A: Approval ("Does this look good?")
-   **Action**: Critique your own work.
-   **Check**: Does it meet the requirements in the Spec? Does it violate any Standards?
-   **Response**:
    -   If Good: "Approved."
    -   If Bad: "Rejected. Reason: [Self-Correction]." (Then fix it).

#### Type B: Information Gap ("What needs to happen next?")
-   **Action**: Look at `product-knowledge/ROADMAP.md`.
-   **Response**: Quote the specific requirement from the Roadmap item.

#### Type C: Preference ("Option A or Option B?")
-   **Action**: Evaluate against `product-knowledge/MISSION.md`.
-   **Response**: "Option A, because it better aligns with [Mission Value]."

### 3. Fallback
If a decision is truly ambiguous and cannot be inferred from any file:
-   **Action**: **STOP**.
-   **Log**: "BLOCKER: Ambiguous decision requires real user input."
-   **Notify**: Use `notify_user` to break the autonomous loop.
