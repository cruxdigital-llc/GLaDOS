---
description: Initialize GLaDOS in the current project — scaffold product-knowledge structure
---

Bootstrap the GLaDOS framework in the current project directory.

## Process

1. Create the `product-knowledge/` directory structure:
   - `product-knowledge/PROJECT_STATUS.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/PROJECT_STATUS.md`
   - `product-knowledge/personas/` — copy all files from `${CLAUDE_PLUGIN_ROOT}/src/personas/`
   - `product-knowledge/standards/` — create empty directory
   - `product-knowledge/philosophies/` — create empty directory
   - `product-knowledge/overlays/` — create empty directory
   - `product-knowledge/observations/` — create directory with:
     - `observed-standards.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/OBSERVED_STANDARDS.md`
     - `observed-philosophies.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/OBSERVED_PHILOSOPHIES.md`

2. Confirm to the user that GLaDOS has been initialized and explain the directory structure.

3. Suggest running `/adopt-codebase` or `/review-codebase` as a next step.
