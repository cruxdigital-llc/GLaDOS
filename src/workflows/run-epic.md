---
name: run-epic
kind: core
description: Drive a multi-ticket epic or the backlog to one human-reviewable integration MR
reads: [intent.status, manifest.branching, manifest.merge-authority, manifest.platform, epic.progress]
writes: [epic.progress, epic.integration-branch, work.base-sha]
emits: [progress, escalation, decision]
mutates: board
requires: [mr-review-panel, standards-gate]
---

# (GLaDOS) Run Epic

**Goal**: drive a multi-ticket effort unattended: establish the ticket queue,
run the per-feature loop (build-feature → review-mr ⇄ address-review → merge)
on each ticket in dependency order, and finish with one consolidated diff for
a human. This core adds what a single feature lacks — sub-tickets, an
integration branch, sequential merges, and epic state durable enough that any
fresh session can pick up mid-epic.

## Process

### 0. Resume or initialize
- `git pull`, then read `epic.progress` from the run ledger. If a record for
  this epic exists, resume from its ticket table at the first unfinished row
  and skip step 1.

### 1. Initialize the epic
- **Ticket source** — two modes:
  - *Default (epic mode)*: locate or create the epic tracking issue; capture
    its goal and acceptance criteria. Decompose into child tickets — one
    shippable slice each, in dependency order (shared/infra → backend → its
    frontend leg) — filed as cross-linked sub-issues with tight specs, using
    the project platform CLI (per `glados.yaml` `platform:`). No ticket
    starts before its dependency merges.
  - *`--backlog` mode*: the queue is the actionable backlog in the project
    status file (`intent.status`), taken top-down. Each item is already a
    ticket — no decomposition, no integration branch; MRs target
    `branching.default-target`.
- The decomposition (or backlog selection order) is a scoping call: this step
  produces a `decision` outcome recording the ticket breakdown.
- **Integration branch** (epic mode): resolve `branching.epic-integration`
  from `glados.yaml`, cut it from `branching.default-target`, push it, and
  record it as `epic.integration-branch`. Every child MR targets it, keeping
  the default branch releasable. The commit it is cut from is this run's base
  (`work.base-sha`, recorded at run start).
- **Write `epic.progress`** to the ledger: the mandate, the ticket table
  (`id | depends-on | holder | status`), the integration branch, operating
  rules, and any environment facts a resuming session needs.

### 2. Per-ticket loop (sequential, dependency order)
For each ticket, on a working branch off the integration branch (named per
`branching.feature`):

1. **Build** — run the build-feature workflow; its MR targets the integration
   branch.
2. **Review** — run the review-mr workflow.
3. **Address** — while the panel's verdict demands changes, run the
   address-review workflow, then re-review. Bounds and stalemate handling:

<!-- glados:include vocabulary/loop-bounds.md -->

4. **Merge** — when the review is clean and CI is green, resolve
   `merge-authority` from `glados.yaml` and act only as the resolved value
   permits for a child→integration merge. Poll the pipeline and merge the
   moment it passes rather than blocking; verify the MR state actually
   flipped to merged.
5. **Record** — update the ticket's row in `epic.progress` and commit the
   update before starting the next ticket: resume durability is per ticket,
   not per run. Each landed ticket produces a `progress` outcome.

### 3. Close the epic
- Queue exhausted (epic mode): confirm the integration branch contains exactly
  the epic's tickets; run the full test suite on it.
- Open one integration→`branching.default-target` MR via the project platform
  CLI, with an epic-level `## Summary` and `## Test plan`. Resolve
  `merge-authority` for that scope; where the resolved value does not permit
  the merge, opening this MR is the run's final mutating act.
- Annotate each child ticket ("landed on the integration branch; closes when
  the epic MR merges") — platform auto-close fires only on a default-branch
  merge.
- Mark the epic complete in `epic.progress`; this produces a `progress`
  outcome. In `--backlog` mode there is no consolidated MR — the run ends when
  the backlog is exhausted, `epic.progress` marking where the queue stands.

### Operating conventions — the autonomy enablers
- **Delegate implementation, keep review.** Subagents implement (leaving
  changes uncommitted) and review; the orchestrator specs, reviews the diff,
  runs the full suite, commits, and merges — conserving orchestration context
  for the long haul.
- **One durable progress record** — `epic.progress` in the ledger, updated as
  every ticket lands. Never a second copy, never a machine-local file.
- **A failing test is a real defect until proven otherwise.** Targeted runs
  miss integration breaks — gate every commit on the full suite; never loosen
  an assertion or a test double to make it pass.
- **Fix in-MR, don't defer.** Carry forward only what is genuinely outside
  the epic's scope, and say so explicitly with the owning ticket — never
  silently drop a finding.

<!-- glados:include vocabulary/git-conventions.md -->

### Exit
- Stop when the ticket queue is exhausted, or when a blocking call genuinely
  needs a human — a product decision, an irreversible action, a review
  stalemate per the bounds above; the latter produces an `escalation` outcome
  carrying the open question.
