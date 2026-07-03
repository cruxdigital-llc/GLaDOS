---
name: retrospect
kind: core
description: Review recent work to harvest observed standards, philosophies, and phase-fitness signals
reads: [intent.status, manifest.platform]
writes: [observations.pending]
emits: [progress, observation]
mutates: none
requires: []
---

# (GLaDOS) Retrospect

**Goal**: review a recent stretch of work and turn what it taught into durable
signal — observed standards and philosophies queued for promotion, and advisory
evidence about whether the project's declared settings still describe reality.
This core detects and records; it never applies an improvement itself.
Candidates land in `observations.pending` for the steward workflow to promote,
and configuration changes stay human decisions.

## Process

### 1. Scope
- Take the scope from the caller: a feature, a bugfix cycle, an epic, or
  "general". Interactively, ask the user what to retrospect on. Headless with
  no scope given, review the work landed since the last retrospect.

### 2. Gather evidence
Ground the review in artifacts, not recollection:
- the project status file (`intent.status`) — recent changes and milestones;
- merged and closed work in the window, via the project platform CLI (per
  `glados.yaml` `platform:`);
- escalations and review outcomes in the window, and what became of them.

Then answer two questions with specifics: **what went well** (successes worth
repeating) and **what went wrong** (bottlenecks, rework, surprises).

### 3. Harvest observations
Sweep the window for implicit standards and philosophies that guided the work
but are written nowhere:

| Trigger            | Looks like                                        |
|--------------------|---------------------------------------------------|
| User correction    | the user overrode an agent decision               |
| Repeated pattern   | the same unwritten choice recurred across changes |
| Explicit statement | "we always…", "never…", "our policy is…"          |

Classify each as a **standard** (specific, enforceable) or a **philosophy**
(directional, guiding), then append an entry to `observations.pending`:

```
### <date> — <short title>
- Kind: standard | philosophy
- Source: user correction | repeated pattern | explicit statement
- Context: what was happening when this was observed
- Proposal: the rule or principle, stated clearly
- Strength: must | should | may (standard) — core | preferred | aspirational (philosophy)
- Confidence: high | medium | low
- Status: pending
```

Each appended entry produces an `observation` outcome. Do not edit the
standards tree here — promotion is steward's job, and skipping the pending
queue skips the review that makes a standard legitimate.

### 4. Phase-fitness signals
The manifest declares intent; reality drifts. Check the window for signals
that the declaration and the evidence disagree:

| Signal                                                     | What it suggests                                                  |
|------------------------------------------------------------|-------------------------------------------------------------------|
| Bug reports arriving from people outside the team          | the project has users, whether or not the declared phase admits it |
| A sustained fix-only streak, no feature work landing       | the team is operating in a preserve mode it never declared         |
| Escalations routinely approved without substantive change  | decision rights are stricter than the team actually wants          |

Each detected signal is appended to `observations.pending` with its evidence
(counts, links, the window examined) and produces an `observation` outcome.
Detection is the whole job: this workflow never edits `glados.yaml` and never
initiates a phase change — it makes the evidence visible for the humans who
own the declaration.

### 5. Process improvements
Where a went-wrong finding implicates process rather than code, route the
proposal by what kind of change it is:
- **Live-tunable value** (channel bindings, decision keys, module params):
  name the concrete `glados.yaml` edit in this run's summary — these keys are
  read at run time, so a human's two-line MR changes behavior on the next run.
- **Review blind spot**: propose a persona addition — a file dropped in
  `personas/` plus one manifest line seats it at the next panel.
- **Defect in workflow text itself**: append it to `observations.pending` so
  it survives until steward's next pass.

### 6. Wrap up
- Summarize for the caller: went-well and went-wrong highlights, observations
  recorded, signals raised, and the proposed edits awaiting a human.
- This run produces a `progress` outcome carrying that summary.
