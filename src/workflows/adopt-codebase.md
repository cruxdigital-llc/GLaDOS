---
name: adopt-codebase
kind: core
description: Onboard an existing codebase — scaffold GLaDOS state and the manifest, then extract its knowledge
reads: []
writes: [intent.status, work.base-sha]
emits: [progress]
mutates: branch
requires: []
---

# (GLaDOS) Adopt Codebase

**Goal**: brownfield onboarding — take a repo that already exists and give it
a working GLaDOS setup: the project manifest, the run-ledger home, and a
product-knowledge tree that reflects the code as it actually is. NOT a
greenfield workflow; with no codebase yet, start from the intent workflow.

## Process

### 1. Scaffold GLaDOS state
- Create `.glados/runs/` if absent — the run-ledger home every workflow's
  record lands in.
- If `glados.yaml` is absent at the repo root, copy `glados.yaml.example`
  there as `glados.yaml` and fill it **with the team** — every value is a team
  statement, never an agent guess:
  - `phase:` is REQUIRED and has no default. The team must pick one of the
    values the example manifest enumerates; the initial declaration describes
    present reality and is ungated. Do not proceed without it, and never fill
    it in yourself.
  - Walk the remaining keys with the team: `platform:`, `channels:`,
    `merge-authority:`, `decisions:`, `branching:`, and the per-workflow
    module lists.
- Once the manifest exists, run `glados.py install` so structural keys compile
  and the team reviews the assembly report.

### 2. Structural analysis
- Run the review-codebase workflow: layout, stack, conventions, health, drift
  against any declared status, and observed-standard candidates.
- Push past the base audit where adoption needs more:
  - **Dependency graph**: infer architecture patterns from the dependency set
    (e.g. a web framework plus an ORM implies a REST-service shape).
  - **Convention detection**: naming, directory layout, test framework — each
    inferred convention carries a confidence level (High/Medium/Low).
  - **Existing-docs ingestion**: fold `CONTRIBUTING.md`, `ARCHITECTURE.md`,
    and kin into the findings rather than rediscovering what they state.
  - **Health check**: test-coverage presence, linter configs, CI setup.

### 3. Standards extraction
- Run the steward workflow to promote the audit's observed-standard candidates
  into the standards tree — seed its focus from the Step 2 findings rather
  than asking the team cold.

### 4. Philosophy discovery
- Ask the team for the principles the code cannot reveal: the non-negotiable
  architectural decisions; the design principles the team follows; the
  trade-offs explicitly chosen (e.g. speed over correctness, or the reverse).
- Capture each stated principle as a file under
  `product-knowledge/philosophies/` with proper frontmatter. If the team has
  none to state, capture nothing — never invent principles for them.

### 5. Intent alignment
- Run the intent workflow: the mission file must exist and match the purpose
  the code actually serves. Where discovered purpose and stated mission
  diverge, the team resolves the difference — not the agent.

### 6. Validation checkpoint
**STOP — present a summary to the team before finalizing:**
- Architecture summary (from the Step 2 analysis).
- Discovered standards (as promoted in Step 3).
- Philosophies captured (if any).
- Inferred conventions, each with its confidence level.
- Identified gaps (areas not yet analyzed).

Ask: "Does this accurately represent your codebase? What should I correct?"
Fold corrections back into the artifacts above before moving on.

### 7. Finalize
- Update the project status file (`intent.status`) with adoption metadata:

  ```markdown
  ## Adoption Status
  **Adopted**: <date>
  **Coverage**: <which areas were analyzed>
  **Gaps**: <what remains unreviewed>

  ## Inferred Conventions
  - <convention> — Confidence: <High/Medium/Low>
  ```

- Commit the scaffolding and the knowledge tree:

<!-- glados:include vocabulary/git-conventions.md -->

### 8. Handoff
- This run produces a `progress` outcome carrying the coverage and gaps
  summary.
- Suggest the natural next step: run build-feature to start building, with
  periodic steward runs to keep the knowledge tree tight.
