---
name: implement-feature
kind: core
description: Write the code and tests that satisfy an approved specification
reads: [manifest.branching]
writes: [work.base-sha]
emits: [progress]
mutates: branch
requires: [standards-gate]
---

# (GLaDOS) Implement Feature

**Goal**: turn an approved specification into a working diff with tests. This
core is the Implement stage of the build pipeline (plan → spec → **implement**
→ verify). It changes code and nothing else — no MR, no verdict, no merge;
those belong to the workflows around it.

## Process

### 1. Take the spec
- The spec comes from the caller: the spec-feature stage's output, or a spec
  the user hands over directly.
- No spec, no implementation — do not improvise requirements from a feature
  title. Return to the caller for spec-feature first.
- Read the spec in full before touching code. Its acceptance criteria are the
  definition of done for the loop below.
- When the caller passes a shape with the spec, take it too. Its units are
  the first task of the breakdown: lay their signatures down before any
  body.

### 2. Claim the branch
- When the caller already put this run on a working branch, stay on it.
  Otherwise resolve `branching` from `glados.yaml` and create one per its
  `feature` naming pattern — never implement directly on the default target.
- The commit the work starts from is this run's base (`work.base-sha`,
  already recorded at run start).

### 3. Break down the work
- Split the spec into an ordered checklist of implementation tasks, each small
  enough that its tests can pass on their own.
- Order by dependency: shared types and interfaces before their consumers,
  migrations before the code that assumes them.
- A finding the caller passes to fix (a gate's or an evaluator's) is a task
  covering its kind: list in the checklist every place where the change has
  the same defect (each other path, input or place of its kind; a breach
  that predates the change is not one), then fix each or name, per place,
  the input that shows it does not hold there. Fixing only the place it
  names leaves it open.
- When a human invoked this workflow directly, offer the breakdown for review
  before writing code; inside a pipeline run, proceed.

### 4. Implementation loop
Work the checklist top to bottom. For each task:

| Step    | Do                                                                |
|---------|-------------------------------------------------------------------|
| Context | read the source the task touches and the closest in-tree precedent |
| Code    | write or modify the code, matching the surrounding conventions     |
| Test    | write or extend tests for this change; run them until they pass    |
| Mark    | check the task off; move to the next                               |

- One task at a time — do not fold tasks together or code ahead of the
  checklist.
- If the spec proves wrong or incomplete mid-loop, stop and surface the
  mismatch to the caller; do not silently diverge from what was specified.

### 5. Verify the whole
- With the checklist complete, run the tests of every area the diff touches
  and the project's unit suite — not just the tests written above. A green
  per-task loop with a red suite is unfinished work. The full suite runs
  once per fix loop, in verify-feature's evaluator.
- Re-read the spec's acceptance criteria against the final diff; anything
  unmet goes back on the checklist.
- With a shape, compare the final diff with it. Any public unit the diff
  adds that the shape does not list, or a shape unit the diff drops, is a
  departure, and the handoff states it.

### 6. Handoff
- Leave the working diff on the branch for the caller's verify and commit
  steps.
- This run produces a `progress` outcome carrying the checklist state, a
  summary of the diff, the test result, and each departure from the shape
  with its reason.
- Run the verify-feature workflow next (the calling pipeline does this
  automatically).
