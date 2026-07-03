# (GLaDOS) Review MR

**Goal**: Run one adversarial, multi-persona review pass over an open Merge
Request. Each persona posts a comment and returns a verdict. If **every** persona
approves, the MR is review-clean. Otherwise, hand off to `{{CMD}}address-review`
— forming the loop `review-mr` ⇄ `address-review` that runs until the MR is
**approved by all personas**.

## Prerequisites
- [ ] An open MR exists for the current feature branch.
- [ ] `product-knowledge/standards/` and `product-knowledge/philosophies/` exist.

## Process

### 1. Resume Trace
-   Select the feature directory; read its `README.md`.
-   Read/initialise the **Review Cycle** counter in `README.md` (cycle 1, 2, …).

### 2. Assemble the Review Brief
-   Gather: the MR id, the diff (`<base>...<head>`), the changed-file list, the
    `spec.md`, the test commands, and the **Active Personas** from `README.md`.
-   Make it self-contained — each panelist runs with no authoring context.

> [!IMPORTANT]
> **Re-review guard**: if the MR HEAD is unchanged since the last pass and the
> author has not responded, do not re-run — there is nothing new to review.

### 3. Spawn the Panel (parallel)
Invoke module: `{{MODULES}}/mr-review-panel.md`
-   **Context**: the panel = the standing lenses (UAT, Adversarial, Standards,
    Philosophy, Dead-code) **plus** the feature's Active Personas.
-   Spawn **one fresh agent per panelist, in parallel** (see
    `{{MODULES}}/evaluator-spawn.md`). Each reviews the brief,
    **posts an MR comment** headed with its persona + verdict, and returns the
    structured verdict object.

### 4. Tally Verdicts
-   Collect every panelist's `{ persona, verdict, blocking, major, minor }`.
-   **Trace**: record the per-persona verdicts and this cycle's outcome in
    `README.md`.

### 5. Decide
-   **All `APPROVE`** → the MR is review-clean.
    -   **Trace**: mark "Review-approved by all personas (cycle N)".
    -   Update `{{STATUS}}` to "approved / merge-ready".
    -   **Stop the loop.** Hand back to the human for merge (respect any
        author-self-approval / settle-time rules in `CLAUDE.md`; never merge
        unprompted).
-   **Any `REQUEST_CHANGES`** → Run `{{CMD}}address-review` to fix the findings.

> [!IMPORTANT]
> **Loop bound**: if approval is not reached within **5 cycles**, or a persona
> re-raises a finding already marked resolved, stop and escalate to the user
> with the open verdicts. Do not loop indefinitely.
