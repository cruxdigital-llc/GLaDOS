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
   looks like. The copy's `decisions:` block, and the
   `relaxation-acknowledged: [delete-code]` line after it, are written for
   `evolving`: for `production` or `sunset`, delete both, so the phase's
   preset governs (`validate`, which `run-pipeline` runs first, refuses each
   value laxer than the preset's). For `sunset`, delete
   `disabled-workflows: []` as well: it would re-enable `build-feature` and
   `run-pipeline`, which that phase turns off. Under `nascent` both may
   stay (the block's stricter values, such as `schema-migration: record`,
   apply); delete both to take nascent's own. Point the user at `platform:`
   and the `channels:` bindings as the other load-bearing keys to review.

2. **Scaffold the `product-knowledge/` directory structure:**
   - `product-knowledge/PROJECT_STATUS.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/PROJECT_STATUS.md` (skip if present)
   - `product-knowledge/personas/` — create empty directory. Do **not** copy
     the library personas into it: every install vendors the shipped library
     into `.glados/personas/`; this directory is for the project's own
     personas and overrides (a project file of the same name wins).
   - `product-knowledge/standards/` — create empty directory
   - `product-knowledge/philosophies/` — create empty directory
   - `product-knowledge/steps/` — create empty directory. It holds the body
     of each project step a pipeline runs (`<step-id>.md`, plain markdown
     with no frontmatter); the steps and pipelines themselves are declared
     under `steps:` and `pipelines:` in `glados.yaml` (commented examples in
     the template; see `${CLAUDE_PLUGIN_ROOT}/docs/guides/pipelines.md`)
   - `product-knowledge/canon/` — create empty directory. It holds the
     digest of each reference work the team declares under `canon:` in
     `glados.yaml`: the team's own summary, written from
     `${CLAUDE_PLUGIN_ROOT}/src/templates/CANON.md` (commented example in the
     template; see `${CLAUDE_PLUGIN_ROOT}/docs/guides/canon.md`)
   - `product-knowledge/observations/` — create directory with:
     - `observed-standards.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/OBSERVED_STANDARDS.md`
     - `observed-philosophies.md` — copy from `${CLAUDE_PLUGIN_ROOT}/src/templates/OBSERVED_PHILOSOPHIES.md`

3. **SDA Conformance (Optional)**:
   Ask the user: "Would you like to enable SDA (Structured Development Artifacts) conformance? Each unit of work that mutates shared state will then record a claim in claims.md, and each unit of work will append one work-unit row to product-knowledge/SPEC_LOG.md, both from its outermost run (runs nested inside it add neither)."

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
   - Copy every `${CLAUDE_PLUGIN_ROOT}/docs/standards/sda-*.md` file (the standard, `sda-standard-v1.md`, and the GLaDOS profiles `sda-profile-glados-v1.md`, `sda-profile-glados-v2.md` and `sda-profile-glados-v2.1.md`) into `product-knowledge/standards/`

4. Confirm to the user what was created and explain the directory structure.
   If SDA was enabled, mention the additional artifacts. If the user wants
   their own workflows, point them at the commented `steps:` and
   `pipelines:` blocks in `glados.yaml`, and at checking them with
   `python ${CLAUDE_PLUGIN_ROOT}/bin/glados.py validate --target .`; the
   plugin runs one with `/glados:run-pipeline <name> <brief>`. If the team
   follows reference works (a book, a paper, a post), point them at the
   commented `canon:` block; the same validate command checks it. Note that a full
   install — `python bin/glados.py install --mode claude --target
   /path/to/your/project`, run from a GLaDOS checkout — compiles the
   workflows against `glados.yaml` and vendors the persona library, guard
   hooks, and CI templates into `.glados/`.

5. Suggest running the `adopt-codebase` or `review-codebase` workflow as a next step.
