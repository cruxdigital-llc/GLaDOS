---
description: Initialize GLaDOS in the current project — create the manifest and scaffold the product-knowledge structure
---

Bootstrap the GLaDOS framework in the current project directory.

## Process

1. **Create the manifest.** Copy `${CLAUDE_PLUGIN_ROOT}/glados.yaml.example`
   to `./glados.yaml` (skip if one already exists). Then ask the user which
   `phase:` describes the project — `nascent | evolving | production |
   sunset` — and set it in the new file. Phase is required, with no default;
   it states who gets hurt when the agent is wrong, not how proud the team is
   of the code: a repo with real users is `production`, whatever the code
   looks like. Point the user at `platform:` and the `channels:` bindings as
   the other load-bearing keys to review.

2. **Scaffold the `product-knowledge/` directory structure:**
   - `product-knowledge/PROJECT_STATUS.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/PROJECT_STATUS.md` (skip if present)
   - `product-knowledge/personas/` — create empty directory. Do **not** copy
     the library personas into it: every install vendors the shipped library
     into `.glados/personas/`; this directory is for the project's own
     personas and overrides (a project file of the same name wins).
   - `product-knowledge/standards/` — create empty directory
   - `product-knowledge/philosophies/` — create empty directory
   - `product-knowledge/observations/` — create directory with:
     - `observed-standards.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/OBSERVED_STANDARDS.md`
     - `observed-philosophies.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/OBSERVED_PHILOSOPHIES.md`

3. **SDA Conformance (Optional)**:
   Ask the user: "Would you like to enable SDA (Structured Development Artifacts) conformance? This adds a claims.md coordination file, an SDA-conformant ROADMAP template, and copies the SDA standard reference docs into your project."

   If the user says yes:
   - Create `claims.md` at the project root — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/CLAIMS.md` and replace `YYYY-MM-DD` with today's date
   - Create `product-knowledge/SPEC_LOG.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/SPEC_LOG.md` (skip if already exists)
   - Create `product-knowledge/ROADMAP.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/SDA_ROADMAP.md` and replace `YYYY-MM-DD` with today's date (skip if ROADMAP.md already exists — instead, prepend an `<!-- SDA: v1.0 -->` header if not already present)
   - If `product-knowledge/PROJECT_STATUS.md` exists and does not contain `SDA: v1.0`, prepend an `<!-- SDA: v1.0 -->` header
   - Copy `${CLAUDE_PLUGIN_ROOT}/docs/standards/sda-standard-v1.md` and `${CLAUDE_PLUGIN_ROOT}/docs/standards/sda-profile-glados-v1.md` into `product-knowledge/standards/`

4. Confirm to the user what was created and explain the directory structure.
   If SDA was enabled, mention the additional artifacts. Note that a full
   install — `python bin/glados.py install --mode claude --target
   /path/to/your/project`, run from a GLaDOS checkout — compiles the
   workflows against `glados.yaml` and vendors the persona library, guard
   hooks, and CI templates into `.glados/`.

5. Suggest running the `adopt-codebase` or `review-codebase` workflow as a next step.
