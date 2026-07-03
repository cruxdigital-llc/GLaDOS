---
name: verify-feature
kind: core
description: Verify the implemented feature with a fresh evaluator that has no implementation context
reads: [standards.index]
writes: []
emits: [progress, verdict, escalation]
mutates: none
requires: [evaluator-spawn]
---

# (GLaDOS) Verify Feature

**Goal**: independently verify an implemented feature before it becomes a
merge request. The agent that wrote the code is predisposed to approve it, so
judgment comes from a fresh evaluator with no implementation context — this
core assembles the evaluator's world, runs the verify/fix loop, and audits the
standards documents for staleness. It mutates nothing itself: every fix it
surfaces is applied by the implementing context, then re-verified.

## Process

### 1. Assemble the evaluation brief
Build a self-contained brief for an agent that knows nothing about how the
code was written: what was requested, what was agreed (acceptance criteria in
the spec's own words), the changed-file list, the commands to test, lint, and
run the app, the applicable standards documents (paths, not summaries), and
the review personas to consult. The brief plus the repo is the evaluator's
entire world — anything the verdict should rest on must be in one of them.

### 2. Spawn the fresh evaluator
The evaluator starts with a clean context — no conversation history, no
knowledge of implementation decisions — and communicates through filesystem
artifacts only. It must:

- run the test suite and linters named in the brief;
- exercise the running app where tools allow — never judge behavior from
  code reading alone;
- judge each acceptance criterion on observed evidence;
- check the diff against each standard listed in the brief;
- critique from each persona listed in the brief;
- verify the tests reflect the final implementation:

| Test-synchronization check | Looking for |
|----------------------------|-------------|
| Stale references | imports or references to deleted / renamed modules |
| Fake alignment | test doubles whose behavior diverges from the real implementation's semantics (dedup, validation, filtering) |
| New-method coverage | a public method introduced by this feature with no corresponding test |
| Sibling comparison | behavioral tests present in the closest architecturally similar component's suite but absent here |

<!-- glados:include vocabulary/verdicts.md -->

The evaluator's verdict is emitted as a `verdict` outcome.

### 3. The verify/fix loop
On blocking findings, hand them to the implementing context for fixes — this
core edits nothing. After the fixes land, reassemble the brief and spawn a
**new** evaluator; never reuse or continue the previous one, since an
evaluator that has watched the fixes happen is no longer fresh.

<!-- glados:include vocabulary/loop-bounds.md -->

### 4. Standards-stale audit
After the verdict clears the gate, sweep the project's standards documents
(`product-knowledge/standards/`): do any contain code examples, pattern
descriptions, or references invalidated by this change — code modified,
renamed, or removed? A standard that documents deleted code misleads every
later reader. Hand each needed correction to the implementing context to fold
into the working branch, and carry what was found in the verification result.

### 5. Handoff
This run produces a `progress` outcome carrying the verification result: the
final verdict, the cycle count, and the standards-audit findings. The
caller's verified-before-MR gate keys off this result.
