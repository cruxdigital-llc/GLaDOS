# Templates

Templates are static files that are copied to the user's project to bootstrap GLaDOS constructs.

## Files

-   **`PROJECT_STATUS.md`**: The source of truth for the project's high-level state. It tracks:
    -   Mission & Architecture.
    -   Active Tasks.
    -   Known Issues.
    -   Recent Changes.

This file is scaffolded into `product-knowledge/` at install (create-only) and kept current by the workflows that write the `intent.status` state key (`adopt-codebase`, `steward`).
