# Questions park; stalled cycles count

> Design rationale for two 2.5 changes to run-pipeline's revise loop. The
> rules are in `src/vocabulary/questions.md` (*Questions for a person*),
> `src/workflows/run-pipeline.md` (**Bound**, **Resume** and **Questions**
> in step 4), `src/vocabulary/design-review.md` and
> `src/vocabulary/loop-bounds.md`; the new bound's baseline is in
> `src/kernel/presets/phases.yaml`. Companion to
> [review-inputs.md](review-inputs.md).

**Status:** part of 2.5.0, still a release candidate. **Baseline:** the
2.5.0 candidate with *What a fresh reviewer is given*. **Revised by**
[v3.md](v3.md): `max-stalled-cycles` is gone (one stalled check parks the
step), and materiality now turns on named outcomes.

## The problem

Two trial runs of a plain-first project pipeline on one ticket each spent
about six hours in design without reaching code. The fresh-agent design gate
did its job: most of its blocking findings were real defects, caught before
any code. The loop around it ended badly in two ways.

- **Progress counted as failure.** Every revise cycle counted against
  `params.pipeline.max-cycles` (3 in the baseline, never tuned). A cycle
  that closed every finding it was given and then found a new, real one
  used up the bound like a cycle that fixed nothing. The second run closed
  both of its first findings in its second cycle and still reached its last
  allowed cycle.
- **A question had nowhere to go but a finding.** The first run's third
  cycle failed on an outcome the plan claimed was met. Whether it was met
  depended on what the ticket's author meant by their words, which no
  reading of the code could settle. The only way to raise it was a blocking
  finding, which used up the last cycle and ended the run in an escalation.
  A run could park for a person only at a `human` checkpoint the pipeline
  had declared in advance.

## Why core, not project

A project chooses its steps, its gates, its checkpoints and the numbers in
`params.pipeline`. It cannot change what a cycle is, what counts against a
bound, when a finding is closed, what a fresh reviewer may write besides
findings, or when run-pipeline parks. Those are compiled into run-pipeline
and its design review. A project `checkpoint: human` parks after a step on
every run, question or not, and cannot park in the middle of a revise loop
for a question the reviewer raised.

## What changed

| Rule | Where it lives |
|---|---|
| A question for a person is what someone meant by their words, where the readings differ materially: one adds, drops or changes a unit, a stored record, a failure path or an outcome, or needs a choice classed `escalate`. It quotes the words, lists the readings (plainest first, each an outcome, never a mechanism) and what each would change. It never stands in for a finding: what the code, the files, a standard, a stated outcome or the blocking definition settles is a finding, and a doubt that changes nothing material is an advisory. An artifact that goes on under an assumption whose readings differ materially has a blocking finding. | New fragment `vocabulary/questions.md`, included by design-review and copied into every design-review brief |
| Every question parks the step as at a `human` checkpoint, one park per check, answered by the same people. The run routes questions from the readings as their finder wrote them. A reading that needs a `forbidden` choice is refused, never asked; an `agent` or `record` choice is made under its class. The answer is recorded verbatim as the answerer's words, the question and readings as their finder's, and the run resumes inside the step. | run-pipeline, **Questions** and **Resume**; run-epic, the parked ticket |
| A revise cycle is any revision of a step's artifact (for findings, answers or a refusal) and the check after it. `max-cycles` counts them all, as in every other loop; the new `max-stalled-cycles` counts those given findings that close none. The bounds are checked before a park: a step at a bound escalates with its questions. | run-pipeline, **Bound**; *Loop bounds*; baseline in `phases.yaml` |
| A finding is closed only when nothing else in the artifact has the same defect. A later check may also find an open finding not a defect, which counts as closed. A closed finding raised again (same path, input and consequence) re-opens it and stops the run, as before. | design-review, the reviewer's prompt; run-pipeline, **Bound** |
| Each check writes its own numbered files and is one row of the step's cycle table, which links them: what it was given, closed (copied from its file) and raised (each `new` or `re-opens <n>`), its questions, and whether it stalled. A check done here (a gate in-context or with `review: none`) numbers its findings and reports closure the same way, marked as the author's. An ask at a `human` checkpoint is a row too, and a refusal is the finding it raises. A resumed run copies the tables. | run-pipeline, **Bound**, **Checkpoint** and step 3; design-review |

The review-mr loop, the evaluator and the standards gate keep their bounds
and their counting. No new severity tier, verdict word or step status:
`parked` already existed.

## Choices made during implementation

- **`max-cycles` keeps its meaning.** It counts every revise cycle, as
  `max-cycles` does in every other namespace, and a project that already
  sets it keeps what it asked for. The stalled count is the new key. A
  stale presets file without the new key still bounds the loop through
  `max-cycles`.
- **`max-cycles: 8` and `max-stalled-cycles: 3`, set in the baseline
  only.** The total is there to end a loop that keeps closing one finding
  and raising another. In the trial runs the gate raised one or two
  blocking findings per check and the next revision closed them, so a
  design that converges fits well inside 8; a step still revising after 8
  is not converging, and a person should look at it. No phase preset
  changes either.
- **The first check is not a revise cycle.** The old text did not say
  whether it was, and the trial runs counted it, so 3 meant three checks. A
  project that wants the old strictness sets `max-cycles: 2`.
- **Closure is the next check's, and it is per kind.** A fresh reviewer is
  given the open findings by number, copied verbatim, and reports each as
  closed, not closed or not a defect. Closing one path of a kind while
  another path of the same kind remains leaves the finding open, so a
  revision that patches only the named instance stalls instead of counting
  as progress. The run copies the reviewer's call into the table; it
  decides only whether a raised finding re-opens a closed one, and marks
  it, so a reader can check that call against the two files.
- **The brief copies open findings; it does not point at earlier
  reviews.** An earlier review file also holds that pass's checks and
  result, which *What a fresh reviewer is given* keeps out of a brief. The
  kept, numbered files are what make the copy checkable afterwards.
- **Every question parks.** Routing is mechanical, from the readings as
  written, so neither the author nor its own in-context audit can turn a
  material question into an assumption or a defect into a question without
  that showing. The earlier draft's third route, going on with the plainest
  reading and listing the question in the MR description, was dropped: a
  question that changes nothing material is an advisory, under the rules
  advisories already have.
- **An answer costs a revise cycle, never a stalled one.** The revision
  for it and the check after it count toward `max-cycles`, so a loop of
  checks that only ask questions still ends.
- **Who answers an unattended question.** The same people who may approve a
  park (a maintainer, or a CODEOWNER of `glados.yaml` or
  `product-knowledge/steps/`), because the park works exactly as a
  checkpoint does. The record notes when the answerer is not the person
  whose words the question turns on.
- **After the MR opens, a question does not park.** It goes on the MR with
  the step's verdict, because a step after open-mr does not edit the
  branch.
- **A run without a branch cuts one before it parks,** because a park
  commits and pushes the record.

## Left out

- The evaluator and the MR review panel do not raise questions yet. Their
  loops were outside this change.
- Naming unclear outcomes as questions at the start of planning, and
  requiring a revision to cover a whole class of failure paths rather than
  only the one a finding names. Both are being tried in project step text
  first; the closure test that makes a patched instance a stall is core.
- Checking at install that a bound is a positive integer, and that
  `max-stalled-cycles` does not exceed `max-cycles`. A bound that is not a
  number installs today for every loop; that check belongs with all of
  them.
  (Since done for every loop: install, check and validate refuse a bound
  that is not a whole number of 1 or more, and a workflow escalates on one
  at run time. `max-stalled-cycles` was retired.)
