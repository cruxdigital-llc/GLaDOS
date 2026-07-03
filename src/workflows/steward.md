---
name: steward
kind: core
description: Run the standing gardening pass — compact the run ledger, refresh stale docs, promote pending observations, sanity-check the test suite, and ship one cleanup MR
reads: [observations.pending, standards.index, intent.status, manifest.branching, manifest.merge-authority, manifest.platform]
writes: [observations.pending, standards.index, intent.status, work.base-sha]
emits: [progress, observation, bug]
mutates: branch
requires: []
---

# (GLaDOS) Steward

**Goal**: the standing housekeeping ceremony — cleanup over critique. Steward
keeps the project's memory honest: it compacts settled run records into a
digest, refreshes documentation that has drifted from the code, promotes
pending observations into standards and philosophies, and sanity-checks the
test suite. Everything it changes rides **one cleanup MR per pass**. The deep
codebase critique is the brunch ceremony, not this one; regenerating code from
intent is out of scope too — that belongs to a later regenerate-component core.

## Process

### 1. Cut the cleanup branch
- Create the working branch per the project's `branching` conventions in
  `glados.yaml`, named for the date and this workflow. The commit it is cut
  from is this run's base (`work.base-sha`, already recorded at run start).

### 2. Compact the run ledger
- Scan `.glados/runs/` for **settled** records: runs whose linked MR is merged
  or closed and whose outcomes need no further action. Leave in-flight and
  recent records alone.
- For each settled record, append one row to the ledger digest
  (`.glados/runs/DIGEST.md` — create it if absent), then delete the record:

  | Date | Workflow | Outcome | Links | One-line summary |
  |------|----------|---------|-------|------------------|

- The digest preserves the audit trail at one line per run; when in doubt
  whether a record is settled, keep it — compaction must never lose the only
  copy of an open thread.

### 3. Refresh documentation
- Bottom-up staleness pass: start at leaf-level docs (per-directory READMEs,
  sampled docstrings/inline docs) and work toward the root (top-level README,
  then the project status file, `intent.status` — its architecture and
  known-issues sections in particular).
- Update what is stale; do not rewrite what is accurate. Leave the mission
  document alone — deliberate updates to it belong to the intent core.

### 4. Promote observations
- Read the pending observations (`observations.pending`). For each one,
  decide: **promote** or **discard** — do not leave items pending across
  passes without a reason.
- Promotions become concise standards or philosophy files in the standards
  tree (`standards.index`): lead with the rule, explain why second, include a
  code example drawn from the codebase; then update the index. A promotion is
  only as strong as its evidence — cite where the pattern recurs.
- Discards get a one-line reason. Clear every processed item from the pending
  file, marked promoted or discarded.
- Each disposition produces an `observation` outcome — the promote/discard
  record is the calibration signal for whatever filed the observation.

### 5. Test sanity
- Run the project's full test suite. Capture the result for the MR's test
  plan, including new warnings and skips, not just failures.
- Breakage is not stewardship work: each distinct failure produces a `bug`
  outcome describing the breakage — **do not fix it inline**. A fix on a
  housekeeping branch muddies both the fix and the cleanup.
- A red suite does not block the pass: documentation, digest, and promotion
  changes still ship, with the breakage noted in the MR description.

### 6. Commit

<!-- glados:include vocabulary/git-conventions.md -->

### 7. Open the cleanup MR
- One MR for the whole pass, targeting `branching.default-target` from
  `glados.yaml`. Description carries `## Summary` (what was compacted,
  refreshed, promoted) and `## Test plan` (the suite result from step 5).
- Resolve `merge-authority` from `glados.yaml` for who may merge — this
  document states no authority, and this step never merges.
- If nothing changed — nothing settled, nothing stale, nothing pending — skip
  the MR rather than manufacture one.
- This run produces a `progress` outcome carrying the MR reference (or the
  no-op note) and a summary of what was compacted and promoted.
