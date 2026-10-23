---
name: steward
kind: core
description: Run the standing gardening pass — compact the run ledger, refresh stale docs and canon digests, promote pending observations, sanity-check the test suite, and ship one cleanup MR
reads: [observations.pending, standards.index, intent.status, manifest.branching, manifest.merge-authority, manifest.platform, manifest.canon, canon.digests]
writes: [observations.pending, standards.index, intent.status, work.base-sha, canon.digests]
emits: [progress, observation, bug]
mutates: branch
requires: []
---

# (GLaDOS) Steward

**Goal**: the standing housekeeping ceremony — cleanup over critique. Steward
keeps the project's memory honest: it compacts settled run records into a
digest, refreshes documentation that has drifted from the code, promotes
pending observations into standards and philosophies, and sanity-checks the
test suite. Everything it changes on its branch rides **one cleanup MR per
pass**. The deep codebase critique is the brunch ceremony, not this one;
regenerating code from intent is out of scope too — that belongs to a later
regenerate-component core.

## Process

### 1. Cut the cleanup branch
- Create the working branch per the project's `branching` conventions in
  `glados.yaml`, named for the date and this workflow. The commit it is cut
  from is this run's base (`work.base-sha`, already recorded at run start).

### 2. Compact the run ledger
- Scan `.glados/runs/` for **settled** records: runs whose linked MR is merged
  or closed and whose outcomes need no further action. Leave in-flight and
  recent records alone, and any this branch tracks.
- For each settled record, append one row to the ledger digest
  (`.glados/runs/DIGEST.md` — create it if absent), then delete the record
  and its step artifacts:

  | Date | Workflow | Outcome | Links | One-line summary |
  |------|----------|---------|-------|------------------|

- Save the digest and every deleted path to the ledger
  (`.glados/glados.py ledger save <paths>`).
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

### 4. Refresh canon digests
- Skip this step when `glados.yaml` has no `canon:` block. This is the one
  workflow that fetches a canon source; every other workflow reads only the
  digest at each entry's `digest:` path.
- For each entry with a `url`, fetch the source when this harness can, and
  hash the response body, byte for byte as fetched, with SHA-256 (the
  definition in the CANON.md template). Compare it with the digest's
  `source-sha256`:
  - **Unchanged:** leave the digest alone, unless `retrieved` is more than
    180 days old (when `glados doctor` flags it); then set it to today.
  - **Changed, or no hash recorded yet:** read the work and set it beside
    the digest. If a principle the digest summarizes changed, update the
    digest to match, in the team's words: the principles the change
    affects, `version`, `retrieved` and `source-sha256`. Keep each **Here,
    specifically:** as the team wrote it, and flag in the MR any the change
    may have made wrong. If none changed (often only the page around the
    work did: navigation, ads, a timestamp), treat it as unchanged, and
    write the new `source-sha256` only when none was recorded or when
    `retrieved` moves too, so a page that differs on every fetch does not
    edit the digest on every pass.
  - **Not fetched** (no fetch tool, a paywall, an error): treat it as a
    book, and say why.
- For a book, or any source not fetched, report the digest's age from
  `retrieved`. Never edit a digest from memory.
- List each digest whose frontmatter says `drafted-from: recall` as awaiting
  confirmation: a person checks it against the source and sets
  `drafted-from: source`. Never make that change yourself.
- List each declared digest that is missing.
- A refreshed digest keeps the template's rules: the team's words, at most
  one quoted sentence, under about 1,000 words. Digest edits ride this
  pass's cleanup MR, where a person reviews them like any other change.

### 5. Promote observations
- Read the pending observations (`observations.pending`). For each one,
  decide: **promote** or **discard** — do not leave items pending across
  passes without a reason.
- Promotions become concise standards or philosophy files in the standards
  tree (`standards.index`): lead with the rule, explain why second, include a
  code example drawn from the codebase; then update the index. A promotion is
  only as strong as its evidence — cite where the pattern recurs.
- An observation that canon conflicts with a recorded decision, a standard
  or a philosophy is settled the same way: change the standard or
  philosophy, or write the project's exception into that principle's
  **Here, specifically:** in the canon digest, so the conflict stops
  recurring.
- Discards get a one-line reason. Clear every processed item from the pending
  file, marked promoted or discarded.
- Each disposition produces an `observation` outcome — the promote/discard
  record is the calibration signal for whatever filed the observation.

### 6. Test sanity
- Run the project's full test suite. Capture the result for the MR's test
  plan, including new warnings and skips, not just failures.
- Breakage is not stewardship work: each distinct failure produces a `bug`
  outcome describing the breakage — **do not fix it inline**. A fix on a
  housekeeping branch muddies both the fix and the cleanup.
- A red suite does not block the pass: documentation, digest, and promotion
  changes still ship, with the breakage noted in the MR description.

### 7. Commit

<!-- glados:include vocabulary/git-conventions.md -->

### 8. Open the cleanup MR
- One MR for the whole pass, targeting `branching.default-target` from
  `glados.yaml`. Description carries `## Summary` (what was compacted,
  refreshed, promoted, and the canon report from step 4) and `## Test plan`
  (the suite result from step 6).
- Resolve `merge-authority` from `glados.yaml` for who may merge — this
  document states no authority, and this step never merges.
- If nothing changed — nothing stale, nothing pending — skip
  the MR rather than manufacture one. The canon report (digest ages, recall
  drafts awaiting confirmation, missing digests) then goes in this run's
  `progress` outcome instead.
- This run produces a `progress` outcome carrying the MR reference (or the
  no-op note) and a summary of what was compacted and promoted.
