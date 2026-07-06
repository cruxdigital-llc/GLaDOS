---
name: fix-bug
kind: core
description: Take one bug from report through reproduction to a verified root-cause fix MR
reads: [manifest.branching, manifest.platform]
writes: [work.base-sha]
emits: [progress, bug, verdict, escalation]
mutates: branch
requires: [evaluator-spawn, standards-gate]
---

# (GLaDOS) Fix Bug

**Goal**: take one bug from report to a verified fix on a merge request. This
core runs the whole pipeline — reproduce → plan → implement → verify — in one
run. Two lines of philosophy govern every step: **fail fast** (a step that
cannot succeed stops the run loudly rather than limping forward), and **fix
root causes, not symptoms** (a fix that makes the symptom disappear without
explaining the failure is a band-aid, and a band-aid is a bug with better
camouflage). Closure is exactly two artifacts: the fix MR and a verified
verdict on it.

## Process

### 1. Reproduce
- Take the bug from the caller (an issue, an error report, or a user brief);
  derive a short slug from it.
- Build a reproduction: a failing test case wherever the defect can be
  captured by one; a reproduction script otherwise. The reproduction captures
  the exact steps, inputs, and observed-vs-expected behavior.
- **No reproduction, no fix**: if the bug cannot be reproduced, this run
  produces an `escalation` outcome describing what was tried, and stops —
  patching what you cannot reproduce is guessing.
- This step produces a `bug` outcome linking the reproduction (the failing
  test or script and the observed behavior), so the defect is on record
  independently of any fix.

### 2. Claim the branch
- Resolve `branching` from `glados.yaml`; create the working branch per its
  `feature` naming pattern. The commit the branch is cut from is this run's
  base (`work.base-sha`, already recorded at run start).

### 3. Plan the root-cause fix
- Isolate: follow the stack trace, logs, and the failing reproduction to the
  specific module and function at fault.
- Ask "why did this happen?" until the answer stops changing (5 Whys) — the
  first plausible frame is rarely the root cause.
- Band-aid check: does the proposed fix remove the cause, or only the symptom?
- Side-effect check: what else calls this path, and does the fix introduce
  new risks?
- Settle the strategy and its blast radius before editing anything.

### 4. Implement
- Apply the fix. The reproduction from step 1 must go red → green — that flip
  is the only accepted proof that the fix addresses the reproduced defect.
- If the fix does not turn the reproduction green, the root cause was
  misdiagnosed: return to step 3. Never stack a second patch on a first guess.
- Fold the reproduction test into the project's test suite permanently — it
  is the regression guard this bug pays forward.

### 5. Commit

<!-- glados:include vocabulary/git-conventions.md -->

### 6. Verify
- Verification is independent: a fresh evaluator with no implementation
  context confirms the reproduction no longer reproduces, runs the full test
  suite, and checks for side effects around the changed code.
- Each evaluation produces a `verdict` outcome. If the evaluator finds
  problems, fix them and re-verify; the cycle bound comes from
  `params.evaluator.max-cycles` in `glados.yaml`. If the bound is reached
  without a verified fix, this run produces an `escalation` outcome and
  stops — an unverified fix is worse than an open bug, because it closes the
  ticket without closing the defect.

### 7. Open the merge request
- Target branch: resolve `branching.default-target` from `glados.yaml`.
- Open the MR with the project platform CLI (per `glados.yaml` `platform:`).
- Description carries `## Summary` and `## Test plan` sections; bullet the key
  changes; link the `bug` outcome, the reproduction, and the verification
  result.

### 8. Handoff
- This run produces a `progress` outcome carrying the MR reference and the
  verification result.
- The bug is closed by the pair — the fix MR plus its verified verdict.
  Neither alone closes it.
