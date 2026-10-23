# Templates

Templates are static files that are copied to the user's project to bootstrap GLaDOS constructs.

## Files

-   **`PROJECT_STATUS.md`**: The source of truth for the project's high-level state. It tracks:
    -   Mission & Architecture.
    -   Active Tasks.
    -   Known Issues.
    -   Recent Changes.

This file is scaffolded into `product-knowledge/` at install (create-only) and kept current by the workflows that write the `intent.status` state key (`adopt-codebase`, `steward`).

-   **`CANON.md`**: The template for a canon digest: the team's own summary of one reference work declared under `canon:` in `glados.yaml`, with frontmatter (`canon`, `version`, `retrieved`, `source-sha256`, `drafted-from`) and one `## <principle-id>` section per principle. Install creates an empty `product-knowledge/canon/` (create-only); the team copies this template there for each work. It is never scaffolded with content: which works count is the team's call. See `docs/guides/canon.md`.
