---
name: run-pipeline
kind: core
description: Run one of the project's own workflows, declared under pipelines in glados.yaml, step by step with every step tracked in the run record
reads: [intent.status, manifest.branching, manifest.merge-authority, manifest.platform, manifest.pipelines, manifest.steps, manifest.decisions, run.active-personas, manifest.panel-personas, epic.integration-branch, manifest.canon, canon.digests]
writes: [work.base-sha, observations.pending]
emits: [progress, verdict, escalation, decision, observation]
mutates: branch
requires: [standards-gate]
---

# (GLaDOS) Run Pipeline

**Goal**: take one piece of work through one of the project's own workflows,
declared under `pipelines:` in `glados.yaml` from GLaDOS's steps and the
project's own (`steps:`, with bodies in `product-knowledge/steps/`). The
pipeline sets which steps run and in what order. This core sets how each one
runs: one step table in the run record, bounded revise loops, outcomes the
team can see, and no step that was not declared.

## Process

### 1. Select the work and its pipeline
- Take the work from the caller (an epic ticket or a user brief), or else
  the top actionable item in the project status file (`intent.status`). If
  nothing is actionable, this run produces an `escalation` outcome and
  stops. A defect report goes to fix-bug: run the fix-bug workflow with it
  as a nested run, then end this run with no step table.
- **Resuming parked work.** A parked run leaves its work on its own branch
  and its record on the ledger, which the park's `escalation` and
  run-epic's ticket row name. When the caller, the brief or a prior record
  (preamble step 4) points at a park of this work, fetch that branch and
  check it out first, whatever branch this run started on, and read the
  record with the `parked` row. This run resumes it: take that record's
  pipeline, record `pipeline: <name> (selected by: resume)`, and check the
  approval or answer as **Resume** in step 4 sets out before step 2.
- Otherwise the first rule that applies picks the pipeline:

| # | Rule | Selected by |
|---|---|---|
| 1 | A person invoked this run, and the first word of their arguments names a pipeline: a declared one, or a kebab-case word close to a declared name | `invoker` |
| 2 | The ticket or brief names one, for example with a tracker label | `ticket` |
| 3 | run-epic's ticket row names one | `epic`, or `epic (agent)` for a row run-epic marked `(agent)` |
| 4 | The brief matches a pipeline's `when:`; of several, the one with stricter required steps | `agent` |
| 5 | A pipeline named `default` is declared | `default` |
| 6 | None: build-feature's stages, as plan-feature, spec-feature, implement-feature, verify-feature, open-mr, self-review | `fallback` |

- Record `pipeline: <name> (selected by: <rule>)` and, under rule 4, the
  alternatives considered. A pipeline named by rules 1 to 3 that is not
  declared (a stale shortcut, a typo such as `backend-featur`) means an
  `escalation` and a stop, never a silent fallback.
- Choosing by rule 4, skipping an optional step, and the one switch in step
  4 are discretion: apply `decisions.pipeline-discretion` as *Decision
  rights* sets out, `record` acts pooled as step 5 says. Under `escalate`,
  rule 4 stops with an `escalation` naming the pipelines that fit, so a
  person names one, and a misfit the re-check finds in a pipeline the agent
  chose stops the same way. Under `forbidden`, the agent makes none of
  these choices: rule 4 is passed over (rules 5 and 6 decide), and a misfit
  is recorded for the MR while the pipeline continues. Under either,
  optional steps run.

### 2. Validate before running anything

| Step | Runs | Needs | Produces | Stage | `review:` |
|---|---|---|---|---|---|
| `plan-feature` | nested workflow | brief | plan | planning | any; default `none` |
| `shape` | here, per *The shape step* | brief or plan | shape | speccing | any; default `in-context` |
| `spec-feature` | nested workflow | plan | spec | speccing | `none` or `fresh-agent` |
| `implement-feature` | nested workflow | spec | change | implementing | not allowed |
| `verify-feature` | nested workflow | spec and change | verification | verifying | not allowed |
| `open-mr` | here, per *Opening the merge request* | change | mr | verifying | not allowed |
| `self-review` | here, per *Self-review* | mr | a `verdict` on the MR | verifying | not allowed |

Project steps run here and take any `review:` (default `in-context` for a
gate, `none` otherwise). A `produce` step produces its declared `produces:`
kind, or only its own file; a `change` step produces `change`; a gate
produces nothing. A project step stands in for the built-in that produces
the same kind: a `produces: spec` step satisfies implement-feature, which
takes its spec from the caller.

- Run `glados.py validate --target .` from the GLaDOS that compiled this
  document (`.glados/glados.py` in a script install, `bin/glados.py` under
  the plugin root in the Claude Code plugin) and record its warnings.
  Without Python, check by hand:
  1. ids are kebab-case, and none reuses a built-in step, a GLaDOS workflow
     or alias, `run-pipeline`, `init`, or another step or pipeline;
  2. the sequence is not empty, repeats nothing, and lists only built-in or
     declared steps, none of them a workflow `disabled-workflows` turns off;
  3. each step's needs come from an earlier step, and a step that always
     runs (`required` or `advisory`) never relies on a kind whose only
     earlier producers are `optional`;
  4. each gate's `audits` names a step that runs before it in this
     sequence, and the gate audits the latest such step; a gate that always
     runs needs one that always runs;
  5. a step takes only `description`, `kind` and `stage` (all required),
     `produces` (only on a `produce` step) and `audits` (required on a gate,
     only there); a pipeline takes only `description`, `when` and
     `sequence` (all required) and `step-options`, whose entries name steps
     in the sequence and take only `modifier`, `when`, `review` and
     `checkpoint`. Values: `kind` is `produce | gate | change`; `stage` is
     `planning | speccing | implementing | verifying`; `produces` is
     `plan | shape | spec | verification`; `modifier` is
     `required | optional | advisory`; `review` is
     `none | in-context | fresh-agent`, and only where the table allows it;
     `checkpoint` is `none | record | human`. `when:` appears exactly when
     `modifier: optional`;
  6. each project step the pipeline runs has a body at
     `product-knowledge/steps/<id>.md`, named exactly as the id (case
     included), with no YAML frontmatter;
  7. each pipeline's description is 250 characters or fewer;
  8. `params.pipeline.max-cycles`, and every other `max-cycles` under
     `params:`, resolves (`glados.yaml` over the preset table) to a whole
     number of 1 or more: not text, `true` or `false`, a list, or 0 or
     less.
- An error or a missing step body means an `escalation` naming it and a
  stop; never improvise around it. Warnings do not stop the run: an MR with
  no verification step before it, or a declared step no pipeline uses.

### 3. Write the step table and pin the inputs
- Before any step runs, write the step table into the run record, one row
  per sequence entry, every status `pending`:

  `# | step | kind | modifier | review | checkpoint | status | artifact | result | note`

- `kind` is `core`, `library` or the project step's kind. Status is one of
  `pending | done | skipped | waived | parked | failed`, as a word: no
  markdown checkboxes, which SDA reads as an implementing signal.
- Every artifact path goes in its row, nested runs' records included. A
  step's own file is `<record>.<id>.md`, where `<record>` is this run's
  record path without `.md`.
- **The record is an index**: under its header, `## Now` (the step in
  progress, what it waits on, the next action), kept current; a reader
  reads it and the rows its step needs. Findings stay in their check's
  files, and how the revision before check n answered them in
  `<record>.<id>.revision-<n>.md`, which no brief names.
- Pin the gating inputs: record the git blob SHA (`git hash-object`) of
  `glados.yaml` and of each step body used. Re-check them before each step
  and before finishing. A change means an `escalation` ("gating inputs
  changed mid-run") and a stop.
- A resumed run (step 1) copies the parked run's step and cycle tables
  instead, finished rows and their artifacts kept, and compares its fresh
  pins with the parked run's, taking the fresh pins from the branch the
  work targets (`git rev-parse <target>:<path>` after a fetch), not the
  parked branch. Any difference, including a sequence edited while the
  work was parked, is "gating inputs changed mid-run".

### 4. Run the sequence
Run the rows in order. Never fold steps together, skip ahead, or run a step
the sequence does not list.

- **Branch.** A pipeline whose sequence has a step that produces `change`
  (implement-feature or a `change` step), or a `human` checkpoint, works on
  its own branch from before its first step. When the caller already put
  this run on a working branch (run-epic does), stay on it; a resumed run
  stays on the parked branch (step 1). Otherwise resolve `branching` from
  `glados.yaml` and create one per its `feature` pattern, cut from
  `epic.integration-branch` inside an epic, else from
  `branching.default-target`. Never work on the default target. Any other
  pipeline claims no branch until it parks and cuts one. A run on its own
  branch that ends with no MR, a park included, leaves its work there for
  a human: it commits any working diff, pushes, and says so in the record.
- **Commits.** When a row ends or parks, its process files (artifact,
  briefs, check results, record) go to the ledger in one save (*Before
  ending this run*, step 4).
- **Nested workflows** run as build-feature runs them ("run the spec-feature
  workflow"). Pass the artifacts that meet their needs, by path from the
  step table, and the run's answers and the tags of *What a fresh reviewer
  is given* as caller context. Those artifacts bind, and a stage states any
  departure in its own artifact. Its "run X next" line gives way to this
  sequence.
- **Project steps.** The body says what to produce or check; this document
  says how. `produce`: write the result to `<record>.<id>.md`. `change`:
  edit code on the branch and record what changed in `<record>.<id>.md`.
  `gate`: audit the latest artifact from a step its `audits` names, against
  the body, and write findings on the *Verdicts and finding severities*
  scale to its audit's file (**Bound**). A gate passes with no `blocking`
  finding.
- **Modifiers** (`modifier:`, default `required`):

| Modifier | Runs | On a `blocking` finding | Row ends |
|---|---|---|---|
| `required` | always | do not advance: revise the audited artifact (re-run its producer with the findings, or revise in place for a step run here), then check again | `done` with its artifact, or `waived` by a named person |
| `optional` | when the agent judges its `when:` holds | as `required` | as `required`, or `skipped` with the `when:` evaluation and a one-line reason |
| `advisory` | always | record it at `advisory` for the MR description and go on; the agent may still treat it as blocking (noted) | `done` |

- **What a modifier governs**: the blocking findings of the step's own
  result, review or gate. It never softens a stop. A nested workflow that
  ends in `escalation`, and the standards gate stopping at its bound (inside
  spec-feature or the shape step), end this run under any modifier. A
  nested workflow still publishes its own outcomes, such as verify-feature's
  `verdict`.
- **Nothing to work on.** An optional step is skipped too, its row saying
  why, when every earlier producer of a kind it needs was skipped, or (for a
  gate) every step its `audits` names was.
- **Bound.** A revise cycle is one revision of a step's artifact, whatever
  it answers (open blocking findings, a person's answers, a refusal), and
  the check after it. A checked step has a cycle table below the step
  table, one row per check (a review, a gate's audit, or an ask at a
  `human` checkpoint):

  `check | file | given | closed | raised | questions | stalled`

  - `check` is the row's number n. Each check's files carry it, so none
    overwrites another; a gate's audit done here is
    `<record>.<id>.audit-<n>.md`. `file` links them, or quotes the answer
    to an ask.
  - A finding is named by its check and number (`2.1`). `given`: what
    earlier rows left open. `closed`: those its file reports closed or not a
    defect, naming whose call it was; a check done here reports as step 5 of
    the reviewer's prompt sets out. `raised`: its new blocking findings,
    each `new`, or `recurs <n>` when its file shows earlier finding n's
    defect (the same consequence) at another path, input or place, a
    re-open included, saying why; when unsure, `recurs`. `questions`: those
    it asked (**Questions**).
  - `stalled`: `yes` when it raises a `recurs`, or ends a revise cycle
    given findings that closes none of them; `—` for a check after no
    revision; else `no`.

  A stalled check parks the step at once, naming the open findings, their
  kind and how the author would remove it, for the person to approve that,
  rule a finding not a defect, waive findings by name, or stop, with a
  scenario, each option's cost and risk, and the author's recommendation,
  confidence and evidence. At the bound, mark the row `failed`.
- **Review** (`review:`) of the step's artifact; for a gate, it is how the
  audit is done. `none`: this agent alone. `in-context`: a *Persona pass*.
  `fresh-agent`: a *Fresh-agent design review*.
- **Checkpoint** (`checkpoint:`, default `none`), once the step is done.
  `record`: add the step's result to the pooled `decision` outcome and go
  on. `human`: save first (**Commits**), commit any working diff a step
  left uncommitted, and push the branch. If a person invoked the run, mark
  the row `parked` in that save, ask them in the session, record who
  answered what, and set the row as the answer decides; a session that ends
  before the answer leaves a park that a later run resumes. A refusal, with
  the person's reasons, is a blocking finding the ask raises: revise the
  artifact as `required` does, whatever the modifier, and ask again within
  the step's bounds; a person who says stop ends the run.
  Unattended (run-epic, headless), park: mark the row `parked`, keep the
  branch, emit one `escalation` naming the branch, this run's record, the
  artifact paths and the approval needed, and end the run, which has not
  finished its unit of work (*Before ending this run*, steps 3 and 5).
- **Resume.** A run resuming parked work (step 1) continues after the
  checkpoint, or inside the step for answers, once a maintainer, or a
  CODEOWNER of `glados.yaml` or `product-knowledge/steps/`, has approved
  or answered on the park's escalation. Check that person's role with the
  platform CLI and quote the approval or answers in the
  new record. A park left by a session that ended before its in-session
  answer has no escalation: a person who invoked this run answers as at the
  checkpoint, and an unattended run parks it as above. A claim the parked
  run left is the one this run resumes, not contention. With no approval
  or answer yet, say so in the record and end the run there, running no
  step and copying no table: it ends as a park does, with no new
  escalation.
- **Questions.** The run records each question for a person, a nested
  plan's open ones included, and how it went:
  - A reading that needs a choice classed `forbidden` is refused as
    *Decision rights* sets out, never asked.
  - **A one-way door parks the step** once its check is done (with no
    check, once its artifact is written), or at the end or skip of a later
    step its body names, none up to it producing `change` or `mr`: one park
    for all of them, as at a `human` checkpoint, the questions standing
    where the approval would. At a bound, the run stops instead, its
    escalation carrying the questions too.
  - **A two-way door parks nothing.** The author answers it by its
    default (*Doors*). The question joins the next park, else the MR, for
    the person to confirm or overturn; unanswered, the answer stands.
  - **A declined advisory** (a fresh agent's, left undone when its row
    ends) is noted in that row by file and number. Once two fresh reviewers
    or evaluators in this run have raised it (the same defect at the same
    unit), it is a question for the person, asked once whatever
    *Materially* says: whether they want it, readings "wanted" and "not
    wanted", the two findings quoted as its words and recommendation,
    beside the author's reasons for declining. It is never made blocking.
  - **Answers.** Record each verbatim, with who gave it and where, noting
    when that is not the person whose words the question turns on; the
    question and its readings stay their finder's. The author then revises
    for the answers, in each artifact they reach, and any finding still
    open (**Bound**).
  - A step after open-mr parks for no question: its questions go on the MR
    with its `verdict`.
- **Selection re-check.** After the first step that produces a plan or spec,
  re-test `when:` against what that artifact says the work touches. A
  pipeline the agent chose (rules 4 to 6, or a rule 3 row marked `(agent)`)
  that no longer fits (for the fallback: once a declared pipeline fits)
  switches once, as discretion: validate the new one, rewrite the step table
  keeping finished artifacts, and record why, so run-epic can update the
  ticket's row. One a person named (rules 1 and 2, or a rule 3 row with no
  mark) continues, the mismatch recorded for the MR.
- **No verdict before the MR.** Gates and reviews that run before open-mr
  publish no `verdict` outcome. Their results ride the step table into
  `progress` and the MR description.
- **After the MR opens.** A step later in the sequence than open-mr reviews
  work already under review: its blocking findings start no revise loop
  and the branch is not edited for them. They go into a `verdict` on the
  MR, as *Publishing a verdict* sets out, delivered to its bound sinks when
  the step ends, not at the end of the run, and marked delivered so the
  epilogue does not post it again. The row ends `done` once it is posted,
  and step 5 hands its blocking findings to review-mr. self-review is such
  a step.

### 5. Finish
- Bring the step table up to date.
- When there is anything to list, emit one pooled `decision` outcome: every
  `record` checkpoint, every two-way door the author answered
  (**Questions**), every challenge the work followed and, when
  `decisions.pipeline-discretion` is `record`, every discretionary act.
  This holds on every way the run ends: here, at a
  park, and at a stop on an `escalation`, each listing the acts made so far.
- When this run, or the parked run it resumed, opened an MR, hand it to
  review after the last step: run the review-mr workflow, handing it the
  blocking findings and one-way questions of every verdict a step after
  open-mr posted, each named, as still open.
- When no MR was opened, the artifacts in the record are the deliverable
  (**Branch** in step 4).
- This run produces a `progress` outcome carrying the pipeline, the step
  table, and the MR reference if there is one.

The shared rules for findings, loops and canon, then the steps and reviews
this run performs itself:

<!-- glados:include vocabulary/verdicts.md -->

<!-- glados:include vocabulary/loop-bounds.md -->

<!-- glados:include vocabulary/canon.md -->

<!-- glados:include vocabulary/shape.md -->

<!-- glados:include vocabulary/persona-pass.md -->

<!-- glados:include vocabulary/design-review.md -->

<!-- glados:include vocabulary/open-mr.md -->

<!-- glados:include vocabulary/self-review.md -->
