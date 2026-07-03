---
name: plan-feature
kind: core
description: Analyze requirements and produce a high-level plan and review-persona roster for one feature
reads: [intent.mission, intent.roadmap, intent.status, manifest.panel-personas, manifest.decisions]
writes: [run.active-personas]
emits: [progress, decision]
mutates: none
requires: []
---

# (GLaDOS) Plan Feature

**Goal**: turn one feature brief into a plan the downstream stages can execute:
goals, success criteria, an approach, and the persona roster that will review
the work. This core decides *what* and *why*; spec-feature decides the
contract, implement-feature the code. It touches no branch.

## Process

### 1. Frame the feature
- Take the brief from the caller (build-feature, an epic ticket, or the user).
- Read the mission (`intent.mission`), the roadmap (`intent.roadmap`) when
  one exists, and the project status file (`intent.status`): does this
  feature serve the stated intent, where does it sit on the roadmap, is
  related work already in flight, what does it depend on?
- If the brief conflicts with the mission or duplicates in-flight work, do not
  plan around it silently — state the tension at the top of the plan so the
  caller decides with it in view.

### 2. Requirements
- Establish, from the brief and the user when one is present:
  - **Goal** — what the feature does and for whom.
  - **Success criteria** — observable checks that would prove it works.
  - **Non-goals** — what this feature deliberately does not do.
- Requirements you invented rather than received are assumptions: label them
  as such so spec-feature can confirm or kill them.

### 3. Approach
- Draft the high-level plan: components touched, sequencing, notable risks,
  and the closest in-tree precedent to build against.
- Resolve `decisions:` from `glados.yaml` and classify every decision-shaped
  choice the approach makes (a new dependency, a schema migration, …):
  - A choice whose decision-rights class is `record` is made here and
    produces a `decision` outcome.
  - A choice classed `escalate` or `forbidden` is not made here — leave it as
    a named open question in the plan for the caller to resolve.

### 4. Seat the review panel
- Scan the persona directories for available reviewer lenses: the project's
  `product-knowledge/personas/`, then the library vendored in
  `.glados/personas/` (a project file wins a name collision).
- Start from the default roster in `params.review-panel.personas`
  (`glados.yaml`), then tailor it to what this feature actually touches — add
  lenses the surface demands, drop lenses with nothing to look at.
- Record the selected roster as `run.active-personas` — this core is its
  writer. Downstream review passes read it and fall back to
  `params.review-panel.personas` only when it is absent.
- For each seated persona, note in the plan the one question it should press
  hardest on for this feature.

### 5. Handoff
- The deliverable is the plan itself: goal, success criteria, non-goals,
  approach, open questions, and the seated roster with per-persona focus.
- This run produces a `progress` outcome carrying that plan.
- Suggest running the spec-feature workflow next.
