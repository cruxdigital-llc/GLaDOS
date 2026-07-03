# (GLaDOS) Run Epic

**Goal**: Drive an entire multi-ticket epic from initiative to a single,
human-reviewable **integration→main** MR — autonomously and unattended. Decompose
the epic into child tickets, then run the per-feature loop on each in dependency
order (`build-feature` → `review-mr` ⇄ `address-review` → merge) until the backlog
is exhausted. This is the epic-level wrapper around that loop; it adds the parts a
single feature doesn't have: sub-tickets, an integration branch, sequential merges,
and the conventions that make running it hands-off safe.

## Prerequisites
- [ ] `{{STATUS}}` exists (else bootstrap via
      `{{CMD}}autonomous-loop` first).
- [ ] An epic brief: a tracking issue, a roadmap block, or a user mandate.
- [ ] Project CLI authed (`glab`/`gh` per `CLAUDE.md`). **Read `CLAUDE.md` first** —
      git, CI, branch, and review conventions are project-specific and override the
      defaults below.

## Process

### 1. Initialize the Epic
-   Locate or create the **epic / tracking issue**; capture its goal + the
    epic-level **acceptance criteria** (how you'll know it worked).
-   **Decompose into child tickets** — one shippable slice each, ordered by
    dependency (shared/infra → backend → its frontend leg). File each as a sub-issue
    with a tight spec + acceptance criteria, cross-linked to the epic. Sequence the
    list so no ticket starts before its dependency merges.
-   Create the **integration branch** `feature/<epic-slug>` off the default branch
    and push it. **Every child MR targets this branch, never `main`** — so `main`
    stays releasable and the human reviews ONE consolidated diff at the end. (A
    frontend repo gets its own `feature/<epic-slug>` branch; its FE legs target it.)
-   Create a **durable progress file** in the scratchpad (outside the repo): the
    mandate, a ticket table (`id | depends-on | status`), the operating rules, and
    any env facts. **Update it as every ticket lands** — it is the resume anchor that
    survives context compression and lets a fresh session continue mid-epic.

### 2. Per-Ticket Loop (sequential, dependency order)
For each child ticket, on a `feat/<id>` branch off the integration branch:

1.  **Build** — `{{CMD}}build-feature` (plan → spec → implement → verify → open MR →
    self-review). For a large ticket, write a precise spec and **delegate the
    implementation to a subagent** (it leaves changes uncommitted); the orchestrator
    then reviews the diff, runs the **full** suite, commits, and opens the MR. This
    conserves orchestration context for the long haul. **MR targets the integration
    branch.**
2.  **Review** — `{{CMD}}review-mr`: spawn the parallel multi-persona panel
    (`{{MODULES}}/mr-review-panel.md` — UAT, Adversarial, Standards,
    Philosophy, Dead-code **+** the ticket's Active Personas). Each fresh subagent
    reviews a self-contained brief, **posts an MR comment**, and returns a verdict.
3.  **Address** — if any persona `REQUEST_CHANGES`, `{{CMD}}address-review`:
    consolidate + dedupe + rank findings, **fix the root cause from the main agent**
    (not subagents — they reviewed, you fix), add tests pinning each fix, re-run the
    gate, and **post a finding→resolution note**. Default to fixing **in-MR**, not
    deferring to a follow-up.
4.  **Re-review** — loop `review-mr` ⇄ `address-review` until **all** personas
    `APPROVE` (loop bound **5 cycles**; escalate if a resolved finding re-opens).
5.  **Merge** — when review-clean **and CI green**, merge to the integration branch.
    Respect `CLAUDE.md`'s no-author-self-approval + settle-time rules. Use a
    **merge-on-green watcher** (poll the pipeline; merge the instant it passes)
    instead of blocking, and **verify the state actually flipped** to `merged`.
    Update the progress file.
6.  Next ticket.

### 3. Close the Epic
-   When the backlog is exhausted, confirm the integration branch contains exactly
    the epic's tickets and run the full suite on it.
-   Open **one integration→main MR** with an epic-level `## Summary` + `## Test plan`
    for the human to review before deploy. **Do not merge it** — the human owns the
    deploy gate.
-   Annotate each child ticket ("landed on `feature/<epic-slug>`; closes on epic→main
    merge") — auto-close fires only on a default-branch merge.

> [!IMPORTANT]
> **Operating conventions — the autonomy enablers (skip these and unattended runs rot):**
> - **One durable progress file**, updated every ticket. The single resume anchor.
> - **Delegate implementation, keep review.** Subagents implement (uncommitted) and
>   review (panel); the orchestrator specs, reviews, commits, merges. Keeps context.
> - **Full-suite gate before EVERY commit** — targeted tests miss integration breaks.
>   A failing test is a real defect until proven otherwise; **never loosen assertions**
>   to make it pass (prefer real instances or strictly-typed test doubles over
>   permissive catch-all mocks; follow `CLAUDE.md`'s testing rules).
> - **Per-repo CI is the final gate, not local tests.** Reproduce its EXACT checks
>   locally before merging (lint / format-check / commit-message lint / typecheck /
>   build). They catch what targeted runs miss — formatting, conventional-commit
>   length, and env-default crashes that only surface on a clean boot.
> - **Fix in-MR, don't defer.** Only carry forward what is genuinely out-of-epic-scope,
>   and say so explicitly (with the owning ticket) rather than silently dropping it.
> - **Run review personas as adversaries.** The loop's value is catching real defects
>   (auth holes, tenant-isolation leaks, missing field maps, scoring flaws) — brief
>   each persona to try to break the change, not to rubber-stamp.
> - **No bylines, no self-approval, no chained `add`/`commit`/`push`** per `CLAUDE.md`.

### Exit
-   Stop when the backlog is exhausted (integration→main MR open for the human), or
    when a blocking decision genuinely needs the human (a product call, an
    irreversible action, a 5-cycle review stalemate). **Escalate with the open
    question — never loop indefinitely.**
