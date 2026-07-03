# (GLaDOS) Address Review

**Goal**: Resolve every open finding from a `{{CMD}}review-mr` pass in one
coherent fix pass — fixing from the **main agent** (not subagents), re-running
the test/lint gate, and posting a resolution note — then hand back to
`{{CMD}}review-mr` for the next pass. This is the fix half of the loop that runs
until the MR is approved by all personas.

## Prerequisites
- [ ] `{{CMD}}review-mr` has run and at least one persona returned
      `REQUEST_CHANGES`.

## Process

### 1. Resume Trace
-   Select the feature directory; read its `README.md` and the latest
    per-persona verdicts (Review Cycle N).

### 2. Consolidate Findings
-   Collect all open findings across personas from the MR comments + verdicts.
-   **Dedupe** (several personas often flag the same root cause) and **rank**
    `blocking` / `major` / `minor`.
-   For each, decide: **fix now**, or **reasoned exception** (a finding you
    deliberately decline — e.g. it conflicts with the in-tree house style, or is
    epic-scope by design). Every exception needs a one-line justification.

> [!IMPORTANT]
> Fix the **root cause**, not the symptom. Prefer making the bad state
> impossible (e.g. a DB constraint) over defensively tolerating it — this is the
> fail-fast philosophy. A failing review finding is a real defect until proven
> otherwise.

### 3. Fix (main agent)
-   Apply the fixes yourself, as one coherent edit set — do **not** fan out to
    subagents (they reviewed; you fix). Keep changes minimal and idiomatic;
    match the closest in-tree precedent.
-   Add or update tests that pin each fixed behaviour (esp. the blocking ones).

### 4. Re-run the Gate
-   Run project linters and the **full test suite** (regression check) before
    committing — distinguish any pre-existing/known-flaky failures from real
    regressions and say which is which.

### 5. Commit, Push, Report
-   Commit per `CLAUDE.md` conventions (conventional commit, no bylines,
    separate `add` / `commit` / `push`); push the branch.
-   **Post a resolution note** to the MR mapping **each finding → resolution**
    (fixed + how, or declined + why), citing the new commit.
-   **Trace**: log the fixes and the commit in `README.md`.

### 6. Handoff
-   Run `{{CMD}}review-mr` to re-review the new HEAD (loop continues until all
    personas approve, or the loop bound escalates).
