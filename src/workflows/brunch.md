---
name: brunch
kind: core
description: Run the codebase critique roundtable and ship one surgical fix MR
reads: [run.active-personas, manifest.panel-personas, manifest.branching, manifest.merge-authority, manifest.platform]
writes: [observations.pending, work.base-sha]
emits: [progress, verdict, bug, observation, escalation]
mutates: branch
requires: []
---

# (GLaDOS) Brunch

**Goal**: a ruthless, multi-perspective critique of the codebase that ships
**one surgical merge request** fixing the top 1–2 findings. The MR is the
deliverable, not a stack of tickets — meet every finding with "can we fix this
right now?" before "should we track this for later?"

## Process

### 1. Set the review window
- From prior run records of this workflow: default the window to "since the
  last brunch's reviewed ref"; with no prior record, review the full codebase.
- Review the default MR target branch, in a clean tree. The reviewed ref is
  this run's base (`work.base-sha`, already recorded at run start).

### 2. Evidence pre-flight — run the thing
A review by reading alone is shallow. Run every check the project supports; the
captured outputs are the **evidence bundle** every reviewer receives.

| Check | Capture |
|-------|---------|
| Static checks | linters and formatters in check mode, type checker |
| Full test suite | results, flakes, skips, slow tests, coverage |
| Build | package / container / frontend artifacts and their warnings |
| Boot | bring the full stack up; health checks; startup logs |
| UAT (if a UI exists) | walk the golden path and several unhappy paths; screenshots, console and network logs |
| Data layer (if a DB exists) | recent migrations, schema, query plans on the heaviest queries |
| Dependency scan | vulnerability audit output |
| CI signal | recent pipeline runs via the project platform CLI (per `glados.yaml` `platform:`) — flakes, failures |

- A check that fails or cannot be run **is itself a finding** — attribute it
  to the relevant persona and continue.
- If no evidence can be gathered at all (the stack will not run in any form),
  this run produces an `escalation` outcome and stops — a roundtable without
  evidence is not a brunch.

### 3. Reviewer rounds — parallel persona subagents
Seat one reviewer subagent per persona: every `type: review` persona definition
in the persona directories — the project's `product-knowledge/personas/` plus
the vendored library in `.glados/personas/` (a project file wins a name
collision) — plus each persona named in `params.review-panel.personas` from
`glados.yaml` (and in `run.active-personas` when present). Never seat a
`type: moderator` persona as a reviewer. A named persona whose definition file
is missing from both directories is a malformed panelist — handle it per the
composition rules below, never by silently dropping the seat.

Each reviewer, independently and in parallel:
- loads its persona file as its role, with the persona's Tool Bias in force;
- receives the same evidence bundle and review window;
- writes findings in its persona's Finding Format, severities per below;
- may disagree with the others — reviewers never coordinate; the moderator
  resolves conflicts.

<!-- glados:include vocabulary/verdicts.md -->

This step produces a `verdict` outcome.

### 4. Moderation
Spawn the `type: moderator` persona from the persona directories
(`product-knowledge/personas/` first, then `.glados/personas/`) with every
findings file and the evidence bundle. Its persona file owns the classification table, the
Fix Now selection rules, and the ticket-hygiene waterfall
(Fix > Amend > Discard > Track) — follow it exactly.

- The moderator selects the **top 1–2 Fix Now findings**; they become the MR.
- Each finding the waterfall routes to the tracker produces a `bug` outcome,
  carrying whether it amends an existing issue or warrants a new one.
- The discard-classification breakdown (sub-category counts with one-line
  reasons) is persona-calibration signal: append it to the pending
  observations (`observations.pending`); this produces an `observation` outcome.

### 5. Execute the fix
- Resolve `branching.feature` from `glados.yaml`; cut the fix branch from the
  reviewed ref.
- Implement the selected fix(es) surgically — fix the finding, not the
  neighborhood. If the moderator directed a partial fix, do the best partial
  fix possible and record what remains.
- Full test suite green before pushing; targeted UAT for anything
  user-visible.

<!-- glados:include vocabulary/git-conventions.md -->

### 6. Open the merge request
- Open the MR with the project platform CLI (per `glados.yaml` `platform:`),
  targeting `branching.default-target`.
- Description carries `## Summary`, `## Findings addressed` (persona and
  severity per finding), and `## Test plan`.
- Resolve `merge-authority` from `glados.yaml` for who may merge — this
  document states no authority, and this step never merges.
- This run produces a `progress` outcome carrying the MR reference, the fixed
  findings, any tickets touched, and the discard breakdown counts.
