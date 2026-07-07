# Ticket lifecycle: mirror the run's stage onto the tracker

> New v2 terms used here (*lane*, *stage*, *outcome*, *sink*) are defined in
> [concepts.md](../concepts.md).

A GLaDOS run knows what phase the work is in — it just claimed a branch, it just
opened an MR — but by default the *tracker* doesn't: the issue sits in whatever
column it started in for the whole run. The `lifecycle:` block closes that gap.
It maps each **canonical stage** the run crosses to a **state value** in your
tracker, and the agent moves the ticket there as it goes, using the project's
own CLI (`glab`/`gh`/MCP). GLaDOS declares the intent; it never calls the
platform API itself — the same contract as the `label` sink.

It is **opt-in**: with no `lifecycle:` block, or `driver: none`, nothing
changes.

## Configuration

Lane-2 (live) — editing it changes the next run's behavior, no reinstall:

```yaml
lifecycle:
  driver: gitlab-scoped-label     # how the state is set on-platform
  field:  "Workflow"              # scoped-label prefix (GitLab), or status field
  transitions:                    # canonical stage -> your tracker's state value
    claim-branch: "In Progress"
    open-mr:      "In Review"
  policy: advance-only            # advance-only (default) | free
```

## Canonical stages

The `transitions` keys are **GLaDOS canonical stages**, not per-workflow step
names — so one mapping covers `build-feature`, `fix-bug`, and any future
ticket-owning core.

| Stage | Fires when | Fired by a run? |
|-------|-----------|-----------------|
| `claim-branch` | the run creates its working branch | yes |
| `open-mr` | the run opens the merge request | yes |
| `escalated` | the run emits an `escalation` | yes |
| `merged` | the MR merges | **no — see below** |

`merged` is a valid key, but a GLaDOS run does not move it: most runs don't
perform the merge (`merge-authority: human`), so there is no run present at
merge time. Realize `Done` **platform-side** instead — `Closes #<id>` in the MR
description auto-closes the issue on merge, or a board rule moves the card. Map
`merged: "Done"` only if you also rely on that platform-native mechanism.

## Drivers

`driver` is the platform-specific bit GLaDOS refuses to hardcode:

| Driver | Status | How it sets state |
|--------|--------|-------------------|
| `gitlab-scoped-label` | shipped | replaces the `<field>::*` scoped label (they're mutually exclusive) via `glab` |
| `github-label` | shipped | removes other lifecycle labels, adds the mapped one via `gh` |
| `gitlab-work-item-status` | deferred | Work Items **Status** field — recognized, not yet implemented |
| `github-projects-status` | deferred | Projects v2 status — recognized, not yet implemented |
| `none` | — | inert (the default) |

Configuring a deferred driver is an install error naming it as deferred — so you
find out at install, not mid-run. The two shipped drivers are pure-CLI (no
GraphQL project plumbing), which is why they land first.

## The three semantics that make it safe

1. **Transition, not emission.** Unlike a sink (which *appends* a comment or a
   label), a lifecycle move *replaces* the previous state — the ticket is in
   exactly one lifecycle state at a time. It's idempotent: already there → no-op.
2. **`advance-only` (default).** A retried or resumed run can't drag a ticket
   backward, and a state a human set *outside* your `transitions` values is
   never overwritten — a manually parked ticket stays parked. `policy: free`
   lifts both guards.
3. **Best-effort, never a gate.** A failed transition does not abort the run: it
   records the failure and emits an `escalation`, then carries on. A flaky
   tracker API must not block an otherwise-good MR the way a failed `verify`
   legitimately does.

## What the compiler checks

Install-time, with the same rigor as `channels:`:

- `driver` is in the closed set (typo → error); a deferred driver → a clear
  "not yet implemented" error.
- every `transitions` key is a canonical stage (typo → error).
- an active driver must map at least one stage (a set driver with empty
  transitions is a half-config).
- `policy` is `advance-only` or `free`.

The resolved `lifecycle` mapping appears in the assembly report with its
provenance, like every other key. Everything about *how* the state is set is the
agent's to execute; the compiler only validates the declaration.
