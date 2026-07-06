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
   Ask the user: "Would you like to enable SDA (Structured Development Artifacts) conformance? Every mutating run will then record a claim in claims.md and every run will append its work-unit row to product-knowledge/SPEC_LOG.md."

   If the user says yes, set `sda: true` in `glados.yaml` and re-run the
   install (`python bin/glados.py install --mode <mode> --target
   /path/to/your/project`, from a GLaDOS checkout) — the installer scaffolds
   the SDA artifacts create-only (claims.md, SPEC_LOG.md, `SDA: v1.0`
   headers, standards docs) and lists them in the assembly report. The
   compiled workflows key on the manifest value at run time.

   **Fallback — plugin-only setups that never run the installer.** Perform
   the equivalent steps by hand:
   - Set `sda: true` in `glados.yaml` (the workflows' runtime SDA steps key on it)
   - Create `claims.md` at the project root — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/CLAIMS.md` and replace `YYYY-MM-DD` with today's date
   - Create `product-knowledge/SPEC_LOG.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/SPEC_LOG.md` and replace `YYYY-MM-DD` with today's date (skip if already exists)
   - If `product-knowledge/ROADMAP.md` exists and does not contain `SDA: v1.0`, prepend an `<!-- SDA: v1.0 -->` header. Do **not** create a roadmap — the installer never invents one; a missing roadmap is the team's call (the `intent` workflow establishes it). If the user asks for a starter, offer `${CLAUDE_PLUGIN_ROOT}/src/templates/SDA_ROADMAP.md` (replace `YYYY-MM-DD` with today's date)
   - If `product-knowledge/PROJECT_STATUS.md` exists and does not contain `SDA: v1.0`, prepend an `<!-- SDA: v1.0 -->` header
   - Copy `${CLAUDE_PLUGIN_ROOT}/docs/standards/sda-standard-v1.md`, `${CLAUDE_PLUGIN_ROOT}/docs/standards/sda-profile-glados-v1.md`, and `${CLAUDE_PLUGIN_ROOT}/docs/standards/sda-profile-glados-v2.md` into `product-knowledge/standards/`

4. Confirm to the user what was created and explain the directory structure.
   If SDA was enabled, mention the additional artifacts. Note that a full
   install — `python bin/glados.py install --mode claude --target
   /path/to/your/project`, run from a GLaDOS checkout — compiles the
   workflows against `glados.yaml` and vendors the persona library, guard
   hooks, and CI templates into `.glados/`.

5. Suggest running the `adopt-codebase` or `review-codebase` workflow as a next step.
