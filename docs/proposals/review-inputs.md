# What fresh reviewers are given

> Design rationale for a 2.5 change to what a fresh reviewer is told to treat
> as settled. The rules are in `src/vocabulary/review-inputs.md` (*What a
> fresh reviewer is given*) and the files that include it; this page records
> why they are core, what changed, and what was left to projects.

**Status:** part of 2.5.0, still a release candidate. **Baseline:** the
2.5.0 candidate before this change. **Revised by** [v3.md](v3.md): an
author's deferral no longer excuses a criterion the work received, and
words bind as firmly as they were said.

## The problem

GLaDOS gets independence from fresh agents: an evaluator, a design reviewer,
a review panel, each with no memory of writing the change. But the agent
that did the work writes the brief, and core text told the fresh agent to
treat parts of that brief as settled. On one merge request every reviewer
was disarmed this way. The author's spec, copied into a contract file, took
precedence over the reviewer's judgement. A mechanism the author named as a
success criterion became a criterion that blocked its own removal. The MR
description's scope, earlier PASS tables and "X is not a defect" notes rode
into the brief. Code from the MR's own first revision counted as
pre-existing. Nothing in the review was wrong by the rules it was given.

## Why core, not project

Most of what went wrong is fixable in a project's own pipeline: a project
step can stand in for any built-in that produces the same kind, and the
class names under `decisions:` are open. Those fixes belong in the project
and are not part of this change.

What a project cannot reach is the text compiled into review-mr,
verify-feature and every fresh-agent step review:

| Core text | What it did |
|---|---|
| mr-review-panel, standing order 3 | Scope the MR description states was "a decision already made". The author writes the description. |
| mr-review-panel, *Assemble the brief* | Listed what the brief carries but forbade nothing else, so prior verdicts and the author's dispositions rode along. |
| evaluator-spawn, *What was agreed* and the evaluator prompt | A contract file took precedence, whoever wrote it, and PASS needed every criterion, the author's own included. The diff ran from the run's base commit, so earlier revisions of a continued branch were out of it. |
| evaluator-spawn and design-review, *Out of scope* | Anything the spec, plan or description deferred was settled. |
| verdicts | "Breaks an acceptance criterion" blocked, whoever set the criterion. Pre-existing was measured from where the run started. The reader rule accepted tests and copies as readers, and covered only types, fields and parameters. |
| review-mr | The brief carried the whole MR description, with its step table of gate results and the findings it lists. Cycle 2 and later always briefed the delta, so a re-plan mid-MR was never judged whole. |
| implement-feature, verify-feature | Never mentioned the shape, although *The shape step* promised implement-feature lays it down first. |
| preamble, *Decision rights* | Said nothing on what is a schema migration or an API break, so a table and an interface that existed only on the branch were treated as deployed and public. |

## What changed

| Rule | Where it lives |
|---|---|
| A brief carries only the inputs its workflow lists. It says who wrote each one: the author (whoever wrote the change, agent or person) or a person, quoted with where they were said; a go-ahead on the author's proposal approves the direction, not the proposal. A scope statement excuses an absence, never a presence, and deferring a unit's consumer does not excuse the unit. | New fragment `vocabulary/review-inputs.md`, included by design-review, evaluator-spawn and mr-review-panel. |
| Each acceptance criterion carries its source. A contract file outranks the plan and spec only for what a person's words name. The evaluator's PASS needs only the criteria the work received; a failed criterion of the author's is an issue at the tier its consequence earns. | evaluator-spawn, *What was agreed* and the evaluator prompt |
| A deferral is labelled with who deferred it and excuses an absence. | evaluator-spawn and design-review, *Out of scope* |
| The panel reads the MR description without its step table or the findings it lists. Its stated scope says what the change leaves out; it never makes what the change puts in correct. | review-mr, step 4; mr-review-panel, standing order 3 |
| The reviewed diff runs from the merge-base with the target when the run's base commit is not on the target, so earlier revisions of a continued branch are in it. | evaluator-spawn, *What changed*; design-review, *What to review* |
| Blocking covers an acceptance criterion the work received, not the author's own. Pre-existing means on the target branch. A reader acts on the value in production code, and passing a value out counts only when the receiver acts on it; a check that only rejects a value reads it only when production code can produce what it rejects. Public methods name a production caller (or the export, for a published API); exception types name a handler and what it decides, and a framework default is not one. | verdicts; root-cause synthesis uses "the work received" too |
| Each requirement names its source: the ticket, a person's words with where they were said, or "assumption". | plan-feature, *Requirements* |
| A plan, shape or spec record that changed since the reviewed head makes the next cycle brief the whole change. | review-mr, step 4 |
| implement-feature lays the shape down first and states each departure. The evaluator lists every public unit the diff adds that the shape does not list, and every shape unit it drops; stating a departure does not excuse a unit it adds. | implement-feature; evaluator-spawn; *The shape step* |
| A table, migration, interface or format the branch adds is one decision, made once; reworking it before it reaches the target is not a further migration or API break, unless the project deploys or publishes from other branches. | preamble, *Decision rights* |

No new severity tier and no new verdict word. Each rule is said once: the
three review documents include one fragment rather than restating it.

## Choices made during implementation

- The evaluator and the design reviewer get the fragment verbatim, beside
  *Verdicts and finding severities*. Their prompts have no standing order
  like the panel's third, so the brief is the only way they learn that the
  author's inputs are under review.
- Panel standing order 5 now names public methods and exception types, and
  units the change leaves without a production caller, so a panelist's own
  orders match the reader rule it is handed.
- *Root-cause synthesis* no longer calls declared work "a decision already
  made". What the description declares left out is a deferral, as before;
  what it declares put in is not settled by saying so.
- *The shape step* passes the shape to verify-feature as well as
  implement-feature, so "when the run has a shape" has a way to be true.
- "Public" is defined once, in *Verdicts and finding severities*, which
  every core carries.

## Left to projects

- A plain-design requirement (no mechanism the criteria do not need) is
  being trialled in a project pipeline first.
- Moving a success criterion that names a code construct (a lock, a lease, a
  table) under Approach. A project plan step can stand in for plan-feature
  to do it, and the source label already keeps an author's mechanism from
  blocking: a criterion only blocks when the work received it.
- The pipeline-level fixes: project steps that stand in for built-ins, and
  project decision classes.
