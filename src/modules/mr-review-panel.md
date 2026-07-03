# GLaDOS MR Review Panel Module

**Goal**: Run one adversarial, parallel, multi-persona review panel over an open
Merge Request. Every panelist is a fresh agent with no authoring context; each
posts an MR comment and returns a structured verdict for the caller to tally.

> For sequential in-context persona passes during build phases (feedback logged
> to the trace `README.md`), see `persona-review.md`. This module is the
> parallel fresh-agent panel for MR review.

## Contract
This module inherits the **context isolation** invariant of
`evaluator-spawn.md` — each panelist starts with a clean context window, no
knowledge of the implementation journey, only the self-contained review brief —
and adds an invariant of its own:

-   **Adversarial stance**: panelists are briefed to try to **break** the
    change, not to rubber-stamp it. Approval must be earned.

Unlike `evaluator-spawn.md`, communication is **not** filesystem-only: each
panelist posts an MR comment and returns a structured verdict object to the
caller, rather than writing `evaluation.md`. The MR itself is the shared
artifact.

## Panel Composition
The panel = the **standing lenses** + the feature's **Active Personas**.

Standing lenses (always present):
| Lens | Mandate |
|------|---------|
| **UAT** | Does the change actually do what the spec/ticket promises? Exercise it as a user would; verify each acceptance criterion. |
| **Adversarial** | Attack the change: edge cases, error paths, race conditions, auth/tenancy holes, injection, data loss. |
| **Standards** | Audit against `product-knowledge/standards/` — every applicable standard, cited by name. |
| **Philosophy** | Audit against `product-knowledge/philosophies/` — fail-fast, root-cause-not-symptom, and the project's stated values. |
| **Dead-code** | Hunt leftovers: unused symbols, orphaned files, stale comments/docs, debug artifacts, commented-out code. |

Active Personas: read the feature trace `README.md` for the "Active Personas"
list; load each definition from `{{PERSONAS}}/[persona_name].md` and add it to
the panel with its Responsibilities and Key Questions as its mandate.

## Instructions

### 1. Assemble the Brief
The caller (e.g. `review-mr`) supplies a self-contained review brief: MR id,
diff (`<base>...<head>`), changed-file list, `spec.md`, test commands, and the
panel roster. If anything is missing, assemble it before spawning — panelists
cannot ask questions.

### 2. Spawn the Panel (parallel)
Spawn **one fresh agent per panelist, all in parallel**. Each panelist's prompt
contains: the review brief, its persona mandate, and these standing orders:

```
You are the [Persona] reviewer on an adversarial MR review panel.
You have no knowledge of how this change was written — only the brief.
Your job is to find real problems, not to confirm success.

1. Read the brief, the spec, and the diff. Read surrounding source as needed.
2. Review strictly through your persona's lens. Cite file + line for findings.
3. Classify each finding: blocking / major / minor.
4. Post ONE MR comment via the project CLI, headed:
   `## [Persona] review — [APPROVE | REQUEST_CHANGES]`
   followed by your findings (or an explicit "no findings" note).
5. Return the structured verdict object:
   { persona, verdict: APPROVE | REQUEST_CHANGES, blocking: [...], major: [...], minor: [...] }

Verdict rule: any blocking or major finding ⇒ REQUEST_CHANGES.
Minor-only findings MAY approve with notes.
```

### 3. Collect Verdicts
-   Gather every panelist's verdict object; confirm every panelist both posted
    its MR comment and returned a verdict (respawn any that silently died —
    never let a missing verdict count as approval).
-   Return the full verdict list to the caller — tallying and the
    approve/loop decision belong to the calling workflow, not this module.
