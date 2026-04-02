# GLaDOS Capabilities Module

**Goal**: Discover and leverage available Tools, Skills, and MCPs to enhance the workflow.

## Instructions

### 1. Discovery
-   **Introspect**: Check your available tools and skills.
-   **Identify**: Look for specialized capabilities relevant to the current task:
    -   **Web/UI**: `browser_action`, `screenshot`.
    -   **Data**: `sql_query`, `read_resource` (MCP).
    -   **External**: `jira`, `github`, `slack`.
    -   **Subagent/Subprocess**: Any mechanism for spawning a fresh agent with a clean context window (e.g., subagent tools, background agents, CLI subprocess).

### 2. Adaptation
-   If **Browser/UI** tools are present:
    -   *Action*: Add "UI Verification" or "Visual Regression" steps to the Plan/Verify phase.
-   If **Database** tools are present:
    -   *Action*: Verify schema changes directly against the DB.
-   If **Project Management** tools (Linear/Jira) are present:
    -   *Action*: Read ticket details directly or update ticket status.
-   If **Subagent/Subprocess** capability is present:
    -   *Action*: Enable context-isolated evaluation in Verify workflows (see `evaluator-spawn.md`).

### 3. Log
-   Record "Active Capabilities" in the trace `README.md`.
