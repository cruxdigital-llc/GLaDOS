---
name: intent
kind: core
description: Establish or refresh the product mission and roadmap
reads: [intent.mission, intent.roadmap, intent.status]
writes: [intent.mission, intent.roadmap]
emits: [progress, decision]
mutates: none
requires: []
---

# (GLaDOS) Intent

**Goal**: keep the product's stated intent true. This core owns the mission
(`product-knowledge/MISSION.md`, state key `intent.mission`) and the roadmap
(`product-knowledge/ROADMAP.md`, state key `intent.roadmap`). Planning
workflows read these files as
ground truth, so a stale mission misleads every downstream run. The core has
two modes: **establish** (no mission exists yet) and **refresh** (the stated
intent has drifted from what the product has become).

## Process

### 1. Read what exists
- Read `intent.mission` and the roadmap if present, and `intent.status` for
  what has actually shipped.
- Pick the mode: no mission file, or a placeholder → **establish**; otherwise
  **refresh**. Never overwrite an existing mission from a blank page — read
  the current state first and change only what the evidence supports.

### 2. Gather intent

**Establish** — interview the owner; each answer becomes a mission section:

| Question | Pins down |
|----------|-----------|
| What specific problem or pain does this address? | Problem |
| Who are the primary users? | Audience |
| What is the core solution, and what makes it distinct? | Solution |
| What is this product deliberately *not*? | Non-goals |

If no human is reachable, draft answers from repo evidence (README, tests,
shipped features), mark each one `(inferred — confirm)`, and leave the marks
in place until the owner confirms.

**Refresh** — diff stated intent against observed reality: shipped work absent
from the roadmap, roadmap items untouched across many runs, mission claims the
product no longer honors. Propose amendments; do not silently rewrite the
problem or audience — those changes are record-class (step 5).

### 3. Write the mission
- Create or update `product-knowledge/MISSION.md` with sections **Problem**,
  **Audience**, **Solution**, **Non-goals**. Keep it to a page — a mission
  that must be skimmed will be skipped.
- Head the file with the managed-document banner (GLaDOS-managed, last-updated
  date, "edit directly; GLaDOS reads current state before future updates").

### 4. Write the roadmap
- Create or update `product-knowledge/ROADMAP.md` under the same banner, with
  three horizons: **Now**, **Next**, **Later**.
- Each *Now* item is scoped tightly enough for the plan-feature workflow to
  take it directly; *Later* items may stay coarse.
- Order by the mission, not by recency of request. Prune shipped items — the
  project status file records history; the roadmap states intent.

### 5. Record what changed
- A material change to Problem, Audience, or Solution, or a reordering of the
  roadmap's *Now* horizon, produces a `decision` outcome: what changed, why,
  and how reversible it is.

### 6. Handoff
- This run produces a `progress` outcome naming the mode, the files touched,
  and any decisions recorded.
- Ask the owner to review the two files; incorporate corrections in this run
  rather than leaving them for the next.

> **Component intent (later release).** Per-component intent files will live
> under `product-knowledge/intent/` — the durable statement of what each
> component is *for*, kept beside the mission. This core is their eventual
> home; do not create that directory yet.
