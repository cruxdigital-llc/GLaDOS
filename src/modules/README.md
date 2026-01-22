# Modules

Modules are reusable units of logic ("sub-routines") that are invoked by multiple workflows. They ensure consistency and adherence to GLaDOS standards.

## Core Modules

-   **`observability.md`**: Manages the "Trace" (Session Log) and "Status" (Project State). It ensures every workflow step is recorded in `specs/[YYYY-MM-DD]_...` and reflected in `PROJECT_STATUS.md`.
-   **`persona_review.md`**: Implements the dynamic review loop. It scans active personas and instructs the agent to adopt each role sequentially to critique the work.
-   **`capabilities.md`**: Introspects the agent's available tools (Browser, SQL, etc.) and maps them to the current task to enhance execution.
