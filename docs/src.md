# Source Code

The `src/` directory contains the source definitions for the GLaDOS framework.

## Structure
-   **`workflows/`**: The core markdown files defining the agentic workflows (e.g., `plan-feature.md`).
-   **`modules/`**: Reusable logic blocks invoked by workflows (e.g., `observability.md`).
-   **`personas/`**: Definitions of roles adopted by the agent (e.g., `product-manager.md`).
-   **`templates/`**: Boilerplate files copied to the user's project (e.g., `PROJECT_STATUS.md`, `CLAIMS.md`, `SPEC_LOG.md`, `SDA_ROADMAP.md`).
-   **`overlays/`**: User-defined customizations that override default files during installation.

## Other Top-Level Directories

-   **`docs/`**: Reference documentation for modules, workflows, personas, overlays, and the SDA standard.
    -   **`docs/standards/`**: The SDA Standard v1.0 and GLaDOS Profile v1.0.
-   **`skills/`**: CLI-invokable skill wrappers (thin entrypoints that delegate to workflows).
-   **`bin/`**: Installation and update scripts (`glados-install.sh`, `glados-update.sh`).
