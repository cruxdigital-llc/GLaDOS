# Modules

Modules are reusable units of logic ("sub-routines") that are invoked by multiple workflows. They ensure consistency and adherence to GLaDOS standards.

## Core Modules

-   **`observability.md`**: Manages the "Trace" (Session Log) and "Status" (Project State). Ensures every workflow step is recorded in `specs/[YYYY-MM-DD]_...` and reflected in `PROJECT_STATUS.md`.
-   **`persona-context.md`**: The persona management system. Supports *review* personas (critique during gates), *operating* personas (session-level behavior), and *team manifests* for named combinations.
-   **`standards-gate.md`**: Enforces documented standards at pre- and post-implementation checkpoints. Uses 3-tier severity (`must`/`should`/`may`) and cross-checks `core` philosophies.
-   **`capabilities.md`**: Introspects the agent's available tools (Browser, SQL, etc.) and maps them to the current task to enhance execution.
-   **`interaction-proxy.md`**: Enables autonomous execution by having the agent answer its own interactive questions based on project context.
-   **`pattern-observer.md`**: *(Phase 2)* Passively detects and logs implicit standards and philosophies during normal workflow execution.

## Legacy

-   **`persona-review.md`**: Superseded by `persona-context.md`. Retained for backward compatibility but no longer referenced by workflows.
