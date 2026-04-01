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

2. **SDA Conformance (Optional)**:
   Ask the user: "Would you like to enable SDA (Structured Development Artifacts) conformance? This adds a claims.md coordination file, an SDA-conformant ROADMAP template, and copies the SDA standard reference docs into your project."

   If the user says yes:
   - Create `claims.md` at the project root — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/CLAIMS.md` and replace `YYYY-MM-DD` with today's date
   - Create `product-knowledge/SPEC_LOG.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/SPEC_LOG.md` (skip if already exists)
   - Create `product-knowledge/ROADMAP.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/SDA_ROADMAP.md` and replace `YYYY-MM-DD` with today's date (skip if ROADMAP.md already exists — instead, prepend an `<!-- SDA: v1.0 -->` header if not already present)
   - If `product-knowledge/PROJECT_STATUS.md` exists and does not contain `SDA: v1.0`, prepend an `<!-- SDA: v1.0 -->` header
   - Copy `${CLAUDE_PLUGIN_ROOT}/docs/standards/sda-standard-v1.md` and `${CLAUDE_PLUGIN_ROOT}/docs/standards/sda-profile-glados-v1.md` into `product-knowledge/standards/`

3. Confirm to the user that GLaDOS has been initialized and explain the directory structure. If SDA was enabled, mention the additional artifacts created.

4. Suggest running the `adopt-codebase` or `review-codebase` workflow as a next step.
