# GLaDOS Persona Review Module

**Goal**: Ensure the work satisfies the specific concerns of all active stakeholders.

## Instructions

### 1. Identify Personas
-   **Source**: Scan the `{{PERSONAS}}/` directory to find all available persona files.
-   **Filter**: Use ALL found personas by default.
    -   *Optional*: If the trace `README.md` explicitly lists "Active Personas", you may limit the review to that subset.

### 2. Review Loop
For *each* active persona:
1.  **Load Context**: Read the definition in `{{PERSONAS}}/[persona_name].md`.
2.  **Adopt Role**: "Acting as [Persona Name]..."
3.  **Audit**: Review the current work (Plan, Spec, or Code) against the persona's:
    -   **Responsibilities**: Is the core job being done?
    -   **Key Questions**: Have they been answered?
4.  **Log Feedback**: Record specific critique, questions, or approval in the trace `README.md`.
    -   *Format*: `**[Persona Name]**: [Feedback]`

### 3. Synthesis
-   If *any* persona blocks the work (raises critical issues):
    -   **Stop**: Do not proceed to the next phase.
    -   **Action**: Ask user to resolve the issue.
-   If all approve:
    -   **Proceed**.
