# SDA Profile: GLaDOS v2.1

*Maps the Structured Development Artifacts (SDA) Standard v1.0 onto GLaDOS v2
conventions, including project workflows (`run-pipeline`) and nested runs.*

---

## 1. Overview

This profile is the [GLaDOS Profile v2.0](sda-profile-glados-v2.md) with the
amendments below. Every section of v2.0 that this document does not amend
applies unchanged, and v2.0 itself is not edited: it stays the accurate
mapping for installs before GLaDOS 2.5.0. The [standard](sda-standard-v1.md)
is unchanged.

Conformance Level: Full, with the same **one declared divergence** as v2.0
(work units are single run-record files, not directories) and the same
declared scope-token extension for claims.

What changed, in one line each:

- The workflow name set gains `run-pipeline` (section 2).
- Files beside a run record (step artifacts, and spec-feature's and the
  evaluator's files) are named and ignored by record-name parsing
  (section 3).
- A `run-pipeline` record reports its phase from its step table (section 4).
- One unit of work gets one claim and one work-unit row, owned by its
  outermost run; nested runs add neither (section 5).
- A run parked at a checkpoint keeps its claim and appends no row until the
  work resumes and ends (section 5).

## 2. Workflow names (amends v2.0 section 4.2)

The `WORKFLOW` segment of a record name is one of the sixteen v2 core names:

    intent, adopt-codebase, plan-feature, spec-feature, implement-feature,
    verify-feature, build-feature, run-pipeline, review-mr, address-review,
    run-epic, fix-bug, review-codebase, retrospect, steward, brunch

Parsers still disambiguate by the longest known workflow name after the date.
A project's own pipelines are not workflow names: every pipeline runs as
`run-pipeline`, so its records are named
`.glados/runs/{YYYY-MM-DD}-run-pipeline-{KEBAB_SLUG}.md`, and the pipeline's
name is inside the record (`pipeline: <name> (selected by: <rule>)`).

## 3. Step artifacts (amends v2.0 sections 4.2 and 4.4)

A run record can have sibling files that extend it, named after the record
with one more dot-separated segment before `.md`. v2.0 section 4.4 places the
Specification in spec-feature's record; it lives in that record's sibling
files instead (`<record>.requirements.md` and `<record>.spec.md`, which the
record links), and the evaluator's brief and evaluation are siblings of the
verify-feature record the same way:

| File | Written by |
|---|---|
| `<record>.<step-id>.md` | a project step of a `run-pipeline` run (its result, its change notes, or a gate's findings) |
| `<record>.shape.md` | the `shape` step |
| `<record>.<step-id>.review-brief.md`, `<record>.<step-id>.review.md` | a fresh-agent design review of a step |
| `<record>.requirements.md`, `<record>.spec.md` | `spec-feature` |
| `<record>.evaluation-brief.md`, `<record>.evaluation.md` | the evaluator |

`<record>` is the record's path without `.md`. These files are artifacts of
the work unit their record names, never work units of their own. The v2.0
pattern already excludes them, because `KEBAB_SLUG` contains no dot; this
profile states it so that parsers do not loosen the pattern to admit them.

## 4. Phase of a run-pipeline record (amends v2.0 section 5)

A `run-pipeline` record carries a step table, one row per step of the
pipeline, written before any step runs:

    # | step | kind | modifier | review | checkpoint | status | artifact | result | note

Status is a word, one of `pending | done | skipped | waived | parked |
failed`. It is never a markdown checkbox, so v2.0's checkbox signal (rule 2)
is never read from a step table.

Each row has a stage, one of `planning | speccing | implementing |
verifying`:

| Step | Stage |
|---|---|
| `plan-feature` | planning |
| `shape`, `spec-feature` | speccing |
| `implement-feature` | implementing |
| `verify-feature`, `open-mr`, `self-review` | verifying |
| a project step | its `stage:` under `steps:` in `glados.yaml`, as of the blob SHA the record pins |

For a subject with a `run-pipeline` record, this rule is evaluated after
the log-marker clause of v2.0's rule 1 (the subject's work-unit row is
present) and before rules 2 to 5. Rule 1's other clause, a passing
verification record, does not apply to such a subject: a pipeline runs
verify-feature as one of its steps, and rows after it (open-mr, a
checkpoint) can still be unfinished.

| Priority | Phase | Condition |
|---|---|---|
| 1a | the row's stage | the stage of the first row whose status is not `done`, `skipped` or `waived`. A `parked` row is awaiting a human approval at that stage; a `failed` row stopped there and escalated. |

When every row is finished, the record reports the stage of its last row
until the log marker appears: the outermost run appends the work-unit row
when it ends (section 5), so a finished pipeline is `done` by the log marker.
Rules 1 to 5 apply unchanged to subjects with no `run-pipeline` record; the
stage cores a pipeline runs leave their own records too, and for a subject
that has a `run-pipeline` record, rule 1a takes precedence over them.

Phase flow is unchanged: unclaimed → planning → speccing → implementing →
verifying → done. A pipeline may skip phases (a refactor with no planning
step) or end early (a design pipeline with no code), and a board shows it in
whatever column its current row reports.

## 5. Units of work: claims and the work-unit log (amends v2.0 sections 2, 6, 7 and 8)

v2.0 said every mutating run claims and every run appends a row. From this
profile on,
**one unit of work gets one claim and one row, both owned by its outermost
run**:

- **Nested runs append no row.** A run started by another workflow running in
  the same session, as one of its own steps (plan-feature inside
  build-feature, a stage inside `run-pipeline`), is nested: it is listed on
  `.glados/runs/stack` and under `## Nested runs` in the outer record. It
  appends no `SPEC_LOG.md` row, so rule 1's "work-unit row present" means the
  whole unit finished, never a nested stage.
- **Nested runs claim nothing.** Only the outermost run records and clears a
  `claims.md` claim. A nested run works under it and never treats a claim of
  a run enclosing it as contention.
- **run-epic tickets are units of their own.** Each ticket's build inside
  `run-epic` (build-feature, or `run-pipeline` with the ticket's pipeline)
  has its own branch and MR, so it claims and appends its own row as an
  outermost run would. The epic's claim is not contention for it, and the
  runs nested inside the ticket's build do neither.
- **A `run-pipeline` run is the outermost run of its pipeline.** The stage
  cores it runs follow the nested-run rules.
- **A parked run has not finished.** A `run-pipeline` run that parks at an
  unattended `human` checkpoint keeps its claim and appends no row. The run
  that resumes the work after the approval builds on that claim (it is not
  contention) and clears it, with the row, when the unit ends.
- **Nesting is decided by who started the run.** A leftover marker or an
  unfinished-looking record from another session never makes a run nested: it
  is stale, and a fresh run replaces it.

Amended text: v2.0 section 2's "every run appends its work-unit row",
section 6's "one row per run" (the Work Unit Log row of its table) and
section 7's "one row per run" read "one row per unit of work, appended by its
outermost run"; section 8's claiming and clearing are done by the outermost
run. Section 8's "Direction (v2.1, not shipped)" paragraph about a lease
module is a GLaDOS roadmap note, not part of this profile: profile v2.1 adds
no leases.

## 6. Repository layout (amends v2.0 section 3)

    <repo-root>/
    └── product-knowledge/
        ├── steps/                  # bodies of the project's own pipeline steps
        └── canon/                  # digests of the works declared under canon:

`product-knowledge/steps/`, `product-knowledge/canon/` and the `pipelines:`,
`steps:` and `canon:` blocks of `glados.yaml` are GLaDOS extensions (v2.0
section 10). SDA consumers ignore them; the step table in a `run-pipeline`
record is what section 4 reads.

## 7. Conformance checklist (amends v2.0 section 11)

Replace the v2.0 item "`product-knowledge/SPEC_LOG.md` gains one row per run,
newest first" with:

- [ ] `product-knowledge/SPEC_LOG.md` gains one row per unit of work,
      appended by its outermost run, newest first
- [ ] `claims.md` entries are recorded and cleared by the outermost run of a
      unit of work only
- [ ] `run-pipeline` records carry a step table whose statuses are words
      from the set in section 4, never checkboxes

## 8. Version History

| Version | Date | Notes |
|---|---|---|
| 2.1 | 2026-10-17 | Additive to v2.0: `run-pipeline` joins the workflow names; step artifacts and spec-feature's and the evaluator's sibling files named and excluded from record-name parsing; phase of a `run-pipeline` record from its step table (a passing nested verification does not mark it done); one claim and one work-unit row per unit of work, owned by the outermost run (nested runs add neither; run-epic tickets are units of their own; parked runs keep their claim) |
| 2.0 | 2026-07-03 | See [sda-profile-glados-v2.md](sda-profile-glados-v2.md), unchanged |
| 1.0 | 2026-04-01 | See [sda-profile-glados-v1.md](sda-profile-glados-v1.md), unchanged and historical |
