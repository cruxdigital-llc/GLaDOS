---
name: spec-feature
kind: core
description: Turn one feature's plan into finalized requirements and an implementable specification
reads: [run.active-personas, manifest.panel-personas]
writes: []
emits: [progress]
mutates: none
requires: [standards-gate]
---

# (GLaDOS) Spec Feature

**Goal**: turn the plan for one feature into a contract precise enough to
implement without further product decisions: finalized requirements plus a
technical specification. plan-feature decided *what* and *why*; this core
decides the contract; implement-feature writes the code. It touches no branch,
and its artifacts live in the run-record directory, beside this run's record
— never in a standalone spec directory.

## Process

### 1. Take the plan
- Take the feature's plan from the caller (build-feature or the user). Invoked
  standalone, work from the plan-feature run record for this feature in
  `.glados/runs/`.
- No plan is not a license to improvise one — run the plan-feature workflow
  first, then return here.

### 2. Finalize the requirements
- The plan labels invented requirements as assumptions. Confirm or kill each
  one: against the codebase, and with the user when one is present.
- Resolve the plan's open questions that block a contract; carry the rest
  forward as explicitly-open items in the spec, never as silent guesses.
- Write the result — goal, success criteria, non-goals, as settled rather
  than as planned — to a sibling file of this run's record, named after it
  (`<record-name>.requirements.md`).

### 3. Write the specification
Define, for everything the feature touches:
- **Data models** — schema changes, migrations, invariants.
- **API interface** — endpoints, payloads, contracts between components.
- **Edge cases** — error handling, failure modes, empty and limit states.

Build against the closest in-tree precedent named in the plan; where the spec
diverges from it, say why in the spec. Write the result to
`<record-name>.spec.md`, sibling to the requirements.

### 4. Persona pass
- Read the draft spec through each persona in `run.active-personas` (seated by
  plan-feature); when that key is absent, resolve the default roster from
  `params.review-panel.personas` in `glados.yaml`.
- Each persona presses the question the plan assigned it, plus its own
  mandate: what does this contract get wrong, leave undefined, or make
  expensive later?
- Fold fixes into the spec; note declined objections in the spec with a
  one-line reason. This pass shapes the artifact — it is not the adversarial
  review loop, which runs later against the diff.

### 5. Gate before implementation
This is the standards gate's pre-implementation checkpoint: the specification
is audited against the project's standards tree while a contract problem is
still a text edit, not a rewrite. Hand off only a spec that has cleared it.

### 6. Handoff
- The deliverable is the requirements + specification pair in the run-record
  directory.
- This run produces a `progress` outcome carrying their location and the
  spec's remaining open items.
- Suggest running the implement-feature workflow next.
