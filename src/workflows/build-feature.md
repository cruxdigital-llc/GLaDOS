# (GLaDOS) Build Feature

**Goal**: Take one feature from idea to a review-ready Merge Request — the full
plan → spec → implement → verify pipeline, then open the MR and self-review it.
This is the entry point of the review loop
(`build-feature` → `review-mr` ⇄ `address-review`).

## Prerequisites
- [ ] `{{STATUS}}` exists.
- [ ] A feature is selected (an "Active Tasks" / roadmap item, or a user brief).

## Process

### 1. Select & Trace
-   Identify the feature (top "Active Tasks" item, or ask the user).
-   The feature directory `specs/[YYYY-MM-DD]_feature_[slug]/` is created/owned
    by `plan-feature`; all steps below log to its `README.md`.

### 2. Refine
-   Run `{{CMD}}plan-feature` — establishes goals, Active Personas, plan.
-   Run `{{CMD}}spec-feature` — produces `requirements.md` + `spec.md`.

> [!IMPORTANT]
> **Validation**: never create a `plans/` directory or numbered plan files. All
> working traces live under `specs/[YYYY-MM-DD]_...`.

### 3. Build
-   Run `{{CMD}}implement-feature`.
-   Run `{{CMD}}verify-feature` — fresh-evaluator gate + test/lint regression.

> [!IMPORTANT]
> Do not proceed to the MR until `verify-feature` passes. A verified feature is
> the precondition for review.

### 4. Open the Merge Request
-   Commit per the project's git conventions (read `CLAUDE.md`): conventional
    commit, no bylines, separate `add` / `commit` / `push`.
-   Open the MR **against the feature's integration branch** (not `main` if the
    project uses an epic/feature branch — confirm the target from
    `{{STATUS}}`), using the project's CLI (`glab` / `gh` per `CLAUDE.md`).
-   Description carries `## Summary` and `## Test plan`; bullet the key changes.

### 5. Self-Review
-   Critically review your own diff against the codebase conventions and the
    closest in-tree precedent. Find real issues; record strengths to keep.
-   **Post the self-review as an MR comment.** Queue any findings for the
    consolidated fix pass rather than editing immediately (keep review line
    references stable).

### 6. Handoff
-   **Trace**: log the MR URL + self-review in `specs/[...]/README.md`; move the
    task status to "MR open / in review" in `{{STATUS}}`.
-   Run `{{CMD}}review-mr` to begin the adversarial review loop.
