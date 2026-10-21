<!-- claude-plugin bootstrap guard — this artifact was compiled from
     glados.yaml.example, not from the repo it runs in. -->
**Bootstrap guard.** This workflow was compiled from `glados.yaml.example`,
not this repo's manifest. Before step 1: if this repo has a `glados.yaml`,
read it now — its `phase:`, decision rights, channels, merge authority,
params, any project workflows and steps (`pipelines:`, `steps:`) and
any canon (`canon:`) govern this run wherever they differ from the text
below. If it has no `glados.yaml`, copy `glados.yaml.example` to
`glados.yaml` (or run `/glados:init`) and set `phase:` before doing
consequential work — do not guess a phase.

**Plugin paths.** This repo may have no `.glados/` directory. Three
read-only files then come from the plugin's own copy at the plugin root
(two levels above this file, the directory that holds
`compiled/claude-plugin/`): when `.glados/presets.yaml` is missing, the
preset table is `src/kernel/presets/phases.yaml` there; when
`.glados/personas/` is missing, the library personas are `src/personas/`
there; and when `.glados/glados.py` is missing, the toolchain is
`bin/glados.py` there. Project personas in `product-knowledge/personas/`
still win a name collision. Run records and the `.glados/runs/` markers
always live in this repo: create them here, never in the plugin.

Optimize for doing no harm; when the consequences of a choice are unclear, stop and ask rather than guess.

## Before doing anything else (mandatory)

1. **Create the run record now** at
   `.glados/runs/<YYYY-MM-DD>-<workflow>-<slug>.md` — before any other work.
   Note the workflow, start time, and goal. Then set the in-flight markers
   the run-record guard hooks key on. `.glados/runs/current` holds the
   filename of the innermost run in flight; `.glados/runs/stack` lists every
   run in flight, one filename per line, outermost first, and its last line
   always equals `current`.
   - **Nested run.** This run is nested only when a workflow you are
     running in this session started it as one of its own steps
     (plan-feature from build-feature's stage table, a stage from
     run-pipeline's step table, a ticket's build from run-epic's per-ticket
     loop) and `current` names that workflow's record. If `stack` does not
     exist yet, create it holding the parent's filename. Append this run's
     filename to `stack` and write it into `current`. Note in this record
     that the run is nested and name the parent record, and list this
     record's path in the parent's record under `## Nested runs`.
   - **Fresh run.** Otherwise write this run's filename into `current` and
     write `stack` holding just this filename. Any other `current` or
     `stack` is stale, whatever its record says (a run that crashed, or an
     earlier session that ended mid-run): replace it, and note the stale
     filename(s) in this record. A run that resumes earlier work (run-epic
     picking up its ticket table) is fresh too; it builds on the earlier
     record as step 4 says.

   Both markers are transient run state: never commit them (the epilogue
   pops them). A run that dies early with a record beats one that succeeded
   invisibly; the epilogue finalizes this file, but it must exist from the
   first minute.
2. **Record `work.base-sha`** — the current base commit — in the record
   before mutating anything (branch, board, or shared files). The end-of-run
   yield check compares against it; without it, an external edit is
   undetectable and unrecoverable.
3. **Record your SDA claim (when `glados.yaml` sets `sda: true`)**: if this
   run mutates shared state, append your claim to `claims.md` at the repo
   root before the first mutation — workflow, scope, holder, timestamp. An
   existing uncleared claim on the same scope is contention: coordinate with
   its holder — build on their run or wait — do not clobber. The epilogue
   clears the entry. A nested run (step 1) adds no claim of its own and does
   not treat the claim of a run enclosing it (any record on `stack`) as
   contention: it works under that claim, which the outermost run clears.
   One exception: a ticket's build inside run-epic is a unit of work of its
   own (its own branch and MR), so it records and clears its own claim as
   an outermost run would; the epic's claim is still not contention, and
   runs nested inside that build work under the ticket's claim.
4. **Read prior run records first**, where this workflow revisits a subject
   (an MR, an epic, a component): scan `.glados/runs/` for records touching
   the same subject before redoing work. If a prior run already reviewed the
   current HEAD, produced the artifact, or holds the claim, build on that
   record instead of repeating the work — and say so in this run's record.

## Reading glados.yaml

When this workflow resolves a key from `glados.yaml` and the manifest does
not set it, take its default from the preset table, `.glados/presets.yaml`.
Layer it in this order, later layers winning: the table's `baseline`, then
the preset named by the manifest's `phase:`, then the keys the manifest sets
explicitly.

## Decision rights

Before making any decision listed under `decisions:` in `glados.yaml`,
resolve its class from the manifest and apply it:

| Class | What you do |
|---|---|
| `agent` | Decide, note the decision and its rationale in the run record, continue. |
| `record` | Decide, AND emit a `decision` outcome: what was decided, why, and how reversible it is. |
| `escalate` | Stop. Emit an `escalation` outcome and wait for a human — do not proceed on a guess. |
| `forbidden` | Refuse. Emit an `escalation` outcome and record the refusal in the run record — even if asked to proceed mid-run. |

Judge a decision against the target branch. A table, migration, interface
or format this branch adds is one decision, made once under its class;
reworking it before it reaches the target is part of that decision, not a
further schema migration or API break. That holds unless the project
deploys or publishes from a branch other than the target.

For judgment calls not listed in `decisions:`, apply the optimize-for line at
the top of this file, and record the consequential ones in the run record.

<!-- GLaDOS v2 compiled artifact — generated by glados.py; edit the source, not this file.
     workflow: run-pipeline
     glados-version: 2.5.0
     manifest-sha256: d23f47f077c49c8ea87c6c32bd5a5db2ffd9f7575be6895d939ea6e02ba8e73c
     modules-inlined: standards-gate
     compile-source: src/workflows/run-pipeline.md
-->

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
- **Resuming parked work.** A parked run's record is committed on its own
  branch, which the park's `escalation` and run-epic's ticket row name.
  When the caller, the brief or a prior record (preamble step 4) points at
  a park of this work, fetch that branch and check it out first, whatever
  branch this run started on, and read the record with the `parked` row
  there. This run resumes it: take that record's pipeline, record
  `pipeline: <name> (selected by: resume)`, and check the approval or
  answer as **Resume** in step 4 sets out before step 2. The rules are not
  applied again.
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
  rights* sets out, except that `record` pools every act into one `decision`
  outcome for the run. Under `escalate`, rule 4 stops with an `escalation`
  naming the pipelines that fit, so a person names one, and a misfit the
  re-check finds in a pipeline the agent chose stops the same way. Under
  `forbidden`, the agent makes none of these choices: rule 4 is passed over
  (rules 5 and 6 decide), and a misfit is recorded for the MR while the
  pipeline continues. Under either, optional steps run.

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
  7. each pipeline's description is 250 characters or fewer.
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
- Pin the gating inputs: record the git blob SHA (`git hash-object`) of
  `glados.yaml` and of each step body used. Re-check them before each step
  and before finishing. A change means an `escalation` ("gating inputs
  changed mid-run") and a stop.
- A resumed run (step 1) copies the parked run's step and cycle tables
  instead, finished rows and their artifacts kept, and compares its fresh
  pins with the parked run's. It takes the fresh pins from the branch the work
  targets (`git rev-parse <target>:<path>` after a fetch), since the parked
  branch still holds the copies pinned at the park. Any difference,
  including a sequence edited while the work was parked, is "gating inputs
  changed mid-run".

### 4. Run the sequence
Run the rows in order. Never fold steps together, skip ahead, or run a step
the sequence does not list.

- **Branch.** A pipeline whose sequence has a step that produces `change`
  (implement-feature or a `change` step), or a `human` checkpoint, works on
  its own branch from before its first step, so every commit this run and
  its nested runs make lands there. When the caller already put this run on
  a working branch (run-epic does), stay on it; a resumed run stays on the
  parked branch (step 1). Otherwise resolve
  `branching` from `glados.yaml` and create one per its `feature` pattern,
  cut from `epic.integration-branch` inside an epic, else from
  `branching.default-target`. Never work on the default target.
  `work.base-sha` is already recorded and the SDA claim follows the
  preamble. Any other pipeline claims no branch.
- **Nested workflows** run as build-feature runs them ("run the spec-feature
  workflow"). Pass the artifacts that meet their needs as caller context, by
  path from the step table. Those artifacts bind, and a stage states any
  departure in its own artifact. Its "run X next" line gives way to this
  sequence. A nested run that ends in `escalation` ends this run too,
  whatever the step's modifier.
- **Project steps.** The body says what to produce or check; this document
  says how. `produce`: write the result to `<record>.<id>.md`. `change`:
  edit code on the branch and record what changed in `<record>.<id>.md`.
  `gate`: audit the latest artifact from a step its `audits` names, against
  the body, and write findings on the *Verdicts and finding severities*
  scale to its audit's file (**Bound**). A gate passes with no `blocking`
  finding.
  While a project step runs, with its review and its gate, the consult point
  for *Consulting canon* is the step's id.
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
    each `new`, or `re-opens <n>` when the table shows it closed (same path,
    input and consequence), which stops the run (*Loop bounds*).
    `questions`: those it asked (**Questions**).
  - `stalled`: `yes` for a revise cycle given findings that closes none,
    `—` for a check after no revision, else `no`.

  At either bound in *Loop bounds*, mark the row `failed`.
- **Review** (`review:`) of the step's artifact; for a gate, it is how the
  audit is done. `none`: this agent alone. `in-context`: a *Persona pass*.
  `fresh-agent`: a *Fresh-agent design review*.
- **Checkpoint** (`checkpoint:`, default `none`), once the step is done.
  `record`: add the step's result to the pooled `decision` outcome and go
  on. `human`: commit the run record and step artifacts first, with any
  working diff a step left uncommitted, on the run's branch, and push the
  branch (the Stop hook blocks ending a turn on an uncommitted record). If
  a person invoked the run, mark the row `parked` in that commit, ask them
  in the session, record who answered what, and set the row as the answer
  decides; a session that ends before the answer leaves a park that a later
  run resumes. A refusal, with the person's reasons, is a blocking finding
  the ask raises: revise the artifact as `required` does, whatever the
  modifier, and ask again within the step's bounds; a person who says stop
  ends the run.
  Unattended (run-epic, headless), park: mark the row `parked`, keep the
  branch, emit one `escalation` naming the branch, this run's record, the
  artifact paths and the approval needed, and end the run. Push the branch
  again once the epilogue has committed the record and before it publishes
  the escalation, so every path the escalation names resolves for the
  approver and for a run in another session. A parked run has not finished
  its unit of work, so its SDA claim and work-unit row follow the
  parked-run rule in step 3 of *Before ending this run*, and its pending MR
  items stay pending (step 5 there).
- **Resume.** A run resuming parked work (step 1) continues after the
  checkpoint, or inside the step for answers, once a maintainer, or a
  CODEOWNER of `glados.yaml` or `product-knowledge/steps/`, has approved
  or answered on the park's escalation. Check that person's role with the
  platform CLI and quote the approval or answers in the
  new record. A park left by a session that ended before its in-session
  answer has no escalation: a person who invoked this run answers as at the
  checkpoint, and an unattended run parks it as above. Build on the parked
  record and its tables (step 3); a claim the parked run left is the one
  this run resumes, not contention. With no approval or answer yet, say so
  in the record and end the run there, running no step and copying no
  table.
  It ends as a park does, with no new escalation: the claim stays, no
  work-unit row is appended, pending MR items stay pending, and the branch
  is pushed again once the epilogue has committed the record.
- **Questions.** The run records each question for a person, a nested
  plan's open ones included, and how it went, routing each from the
  readings as their finder wrote them, never reworded:
  - A reading that needs a choice classed `forbidden` is refused as
    *Decision rights* sets out, never asked; one classed `agent` or
    `record` is made under its class and by itself asks nothing. A
    question left with no reading materially different from the plainest
    is an advisory finding.
  - **Every other question parks the step** once its check is done (with
    no check, once its artifact is written): one park for all of them, as
    at a `human` checkpoint, the questions standing where the approval
    would. A run with no branch of its own cuts one before parking, as
    **Branch** does. At a bound, the run stops instead, its escalation
    carrying the questions too.
  - **Answers.** Record each verbatim, with who gave it and where, noting
    when that is not the person whose words the question turns on; the
    question and its readings stay their finder's. The author then revises
    for the answers and any finding still open (**Bound**).
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
  work that is already under review, so its blocking findings start no
  revise loop and the branch is not edited for them. They go into a
  `verdict` on the MR, as *Publishing a verdict* sets out, delivered to its
  bound sinks when the step ends, not at the end of the run, and marked
  delivered in the record so the epilogue does not post it again. The row
  ends `done` once it is posted, and step 5 hands its blocking findings to
  review-mr. self-review is such a step.

### 5. Finish
- Bring the step table up to date: it indexes every artifact of the run.
- When there is anything to list, emit one pooled `decision` outcome: every
  `record` checkpoint and, when `decisions.pipeline-discretion` is `record`,
  every discretionary act. This holds on every way the run ends: here, at a
  park, and at a stop on an `escalation`, each listing the acts made so far.
- When this run, or the parked run it resumed, opened an MR, hand it to
  review after the last step: run the review-mr workflow to begin the
  adversarial review loop, handing it the blocking findings of every
  verdict a step after open-mr posted, each named, as findings still open.
- When no MR was opened, the artifacts in the record are the deliverable.
  A run on a branch of its own (step 4) leaves its work there for a human:
  commit any working diff on it, push it, and say so in the record. Push it
  again once the epilogue has committed the record, as at a park, so the
  record reaches the remote too.
- This run produces a `progress` outcome carrying the pipeline, the step
  table, and the MR reference if there is one.
- Known gap: build-feature can still be run directly, outside any pipeline.
  Its MR carries no step table, which is how the bypass shows.

The shared rules for findings, loops and canon, then the steps and reviews
this run performs itself:

## Verdicts and finding severities

There is exactly one severity scale and one verdict vocabulary. No reviewer,
panelist, or evaluator may introduce another tier or another verdict word.

**Finding severities — two tiers only:**

| Severity | Meaning |
|----------|---------|
| `blocking` | The change must not merge as-is: it breaks behaviour, breaks an acceptance criterion the work received (one the ticket or someone other than the author set; the author's own are design under review), opens a security, tenancy or data-loss hole, crosses a boundary the project's architecture standards draw, or leaves a test gap that hides one of these. |
| `advisory` | Worth one line, not worth blocking: style, naming, simplification, prose, a standard whose breach changes no behaviour and crosses no boundary, any suggestion the author may decline. |

Code is the truth and prose points at it. A finding about a comment, a
docstring, a README, a commit message or a merge-request description is
`advisory`, always: prose cannot break the build, and a review that blocks on
it teaches the team to skim the next one. Fix prose you pass through when the
fix is cheap; otherwise say it in one line.

Unsure whether a finding blocks? Then it is `advisory`, written as the
question it is. A wrong `blocking` finding costs more than a missed one: it
sends the author to refactor around a defect that does not exist.

**A finding is about code the change introduced.** Most codebases predate the
standards they are now held to, so a lens reading a touched file finds
breaches the author never wrote. Those are not this review's findings. A
breach that already existed in a file the change touches is noted, not
blocking, and the whole set of them is worth **one line** pointing at
wherever the project tracks bringing existing code up to standard — never one
finding per instance. Listing them buries the three findings the author can
act on among the fifteen they cannot, and an author who has skimmed one
review skims the next one, which is how a real finding gets missed.

Pre-existing means already on the target branch. Commits this branch already
carries (an earlier revision, an earlier run's work) are part of the change
and are not precedent. This settles what counts as pre-existing, not what a
delta pass re-reads.

Two things are not pre-existing, whatever their line numbers say: a breach
the change makes worse, and one the change now depends on. Both are findings
about this change and land at whatever tier they earn.

**For every type, field, parameter, public method or function, and
exception type a change adds, name the line that reads, calls or handles
it.** No reader, no field. Say which line, not that one probably
exists — a reader you cannot point at is the finding. A reader acts on the
value in production code: it branches on it, computes with it, or passes it
out of the change to a receiver that acts on it. A test, a copy into
another field, a check of the value against itself or its twin, and a
serializer whose output no receiver acts on are not readers; a check that
only rejects the value reads it only when some production code can produce
the value it rejects. A unit is public when code outside its own module can reach it.
For a public method or function the change adds, or keeps while removing its
last production caller, name its production caller; for one the project
publishes as its API, name that export instead. For an exception type the
change adds, name the handler that decides what happens next and what it
decides for this failure; the framework's default is not a handler.

This cuts the opposite way from the observation it is usually confused with.
"This value is computed and then dropped" is a true sentence that sounds like
a request to carry the value further, and carrying it is the expensive answer:
a field, a shape to hold it, a caller to thread it, and a test for each. The
cheap answer is almost always that nobody wanted the value, and the fix is to
stop computing it. Ask which before asking for plumbing. The same applies to a
value carried across a step boundary that the later step never acts on: that
is not information, it is coupling, and the step that stores a result does not
need to know why the step before it kept one.

A review can establish that nothing reads a field. It cannot establish that
nothing *should* — a reader someone is about to write is invisible here, and
"a later ticket will use it" is a real answer that only the people who know
what the system is for can weigh. So this is stated as the fact and never as
a demand: "nothing reads `x`" is the finding; "delete `x`" is a suggestion
the author may decline like any other. It is `advisory` unless the unread or
uncalled thing also breaks something.

**A finding is a claim and its evidence, and they are not the same length.**
The claim is what breaks, where, and what to do about it — a few lines, in
plain sentences. The evidence is the reproduction, the measurement, the walk
through the mechanism, the reason the obvious fix is the wrong one. Both are
owed. Only the claim is owed *on the first screen*.

Wherever a verdict is published, write it so that a reader who expands
nothing still learns every blocking thing they have to do. Evidence goes
beneath its claim, folded where the platform can fold it and last where it
cannot. This is what keeps two rules from fighting: a review may never drop a
finding, and a review nobody finishes reading has dropped all of them. A
comment gets shorter by putting its proof one click down, never by leaving
the proof out — and a finding that cannot state its ask in one line at the
top has not been understood well enough to post.

**An advisory earns its line by naming a consequence.** The two tiers say
how much a finding is worth acting on. Neither says whether it was worth
writing down, so `advisory` becomes where each lens files everything it
noticed, and the list fills with items whose only effect is that the code
would read differently to the person who raised them.

Before publishing one, name what acting on it changes. One of:

- **behaviour**, under some input;
- **whether a defect would be caught**, where the finding is about a test;
- **what someone has to work with when it fails**, where it is about a
  message, a log or a record that somebody actually reads.

A finding with none of the three is not being dropped, because it was
never a finding — it is a preference. Fix it in passing if you are already
in the file; otherwise let it go. Where you cannot tell whether a
consequence exists, it stays: the rule for an uncertain finding is
unchanged, and this is not a licence to argue yourself out of one.

This does not exempt naming, interfaces or structure. A name that makes a
reader believe something false about what the thing does has a
consequence, and so does a boundary the architecture draws and the code
crosses. What disqualifies a finding is that a different choice would
merely be tidier — so the test is whether you can NAME the consequence,
never which category the finding falls into.

**And price what you ask for.** A finding states a problem; a reader turns
it into work, and the size of that work is often invisible from the line
that asked. "This message should carry the index" is one clause and can
be a restructure. Where the fix is not obviously small, say what you think
it costs — and if you have not looked, say that instead of implying it is
cheap. A reviewer who has not priced the work has not finished the
finding, and an advisory whose fix is large is either worth stating as
that trade or not worth stating.

**Say each thing once.** The claim/evidence split makes a review shorter
by moving proof out of the way; it does nothing about the same POINT
appearing twice on the surface, which in practice is the larger cost. A
summary bullet and the finding's opening sentence say the same thing. So
does a line reporting a fix landed and the finding beneath it that closed.
So does a scope statement and the advisory that implies it. Each pair
reads as two facts and is one, and the second telling is always the weaker
one, because by then it is competing with the detail around it.

Where a review publishes a summary of what it is asking for, that summary
is the ONLY place those asks are written, and each finding is presented
under the line that summarises it rather than restating it. Before
publishing, read only what a reader sees without expanding anything and
count how many times the author is told the same thing: every count above
one is length that bought nothing, and cutting it removes no finding.

**Verdicts:** `APPROVE | REQUEST_CHANGES | ESCALATE`.

**Composition rules (applied at the tally, not left to individual reviewers):**

- Any `blocking` finding ⇒ `REQUEST_CHANGES`.
- A missing or malformed panelist verdict ⇒ `ESCALATE` — never approval.
  Silence is not consent; respawn or escalate, do not count it as a pass.
- Advisory-only findings ⇒ `APPROVE`. Advisories are offered, not owed: the
  author may fix, decline or ignore them, and approval waits on none of them.


## Loop bounds

Every retry loop is bounded, and the bound is a manifest value — never a number
written into workflow text. Resolve bounds from `glados.yaml` at run time:

| Loop | Bound |
|------|-------|
| review-mr ⇄ address-review cycles per MR | `params.review-panel.max-cycles` |
| evaluator verify/fix cycles per feature | `params.evaluator.max-cycles` |
| standards-gate re-runs per gated artifact | `params.standards-gate.max-cycles` |
| revise cycles per pipeline step (run-pipeline) | `params.pipeline.max-cycles` |
| stalled revise cycles per pipeline step (run-pipeline) | `params.pipeline.max-stalled-cycles` |

Rules:

- Count cycles in the run record and check the bound **before** starting the
  next cycle.
- On hitting a bound: stop, emit an `escalation` outcome carrying the open
  findings and the cycle history, and end the run. Never loop indefinitely.
- If a finding previously recorded as resolved **re-opens**, that is a
  stalemate regardless of the counter: stop and emit an `escalation`
  immediately rather than spending remaining cycles on it.
- An escalated loop is a finished run, not a failed one — the record states
  where it stopped and why.


## Consulting canon

Canon is the reference works the project declares under `canon:` in
`glados.yaml`. If it has no `canon:` block, skip this section.

- **Which entries apply.** The consult point is the workflow you are running
  or, inside run-pipeline, the current step (`shape`, or a project step's
  id); a step's review and standards gate belong to that step. An entry
  applies when its `applies-to` names the consult point. With no
  `applies-to`, it applies at `plan-feature`, `shape`, `spec-feature`,
  `verify-feature` and `review-mr`. A canon id cited in a project step's
  body applies there too.
- **Read the digest, never the URL.** Read the file at the `digest:` path
  of each entry that applies. Never fetch its `url` during a run. If a
  digest is missing or unreadable, say so in the record or report and go
  on without it. Never fill a principle in from memory.
- **Seats.** An entry's `seats` (default `philosophy`) names the standing
  lenses or personas that apply it. Working in context, press each principle
  from the seat it names. A fresh agent (panelist, evaluator, design
  reviewer) gets the digest paths for its seats, never a summary, and the
  Weight, Recall drafts, Cite and Conflicts rules here, copied verbatim.
  An evaluator or a lone reviewer holds every seat. An entry whose seats
  are not on the panel goes to the Philosophy lens, or to every reviewer
  where there is none.
- **Weight.** Precedence, highest first: a decision the project recorded,
  its standards, its philosophies, canon. A departure from canon is an
  `advisory` finding unless a `must` standard or a `core` philosophy adopts
  the principle by citing its canon id; then it is a breach of that
  document, and the finding cites both. Either way the finding names its
  consequence: what changes in behaviour, which defect goes uncaught, or
  what someone has to work with when it fails.
- **Recall drafts.** A digest marked `drafted-from: recall` is cited with
  "(drafted from recall)" and never raises a finding above `advisory` on
  its own.
- **Cite** a principle as `canon:<name>#<principle-id>` with the digest
  path. Principle ids are the digest's `## <principle-id>` headings. Never
  paste digest text into an artifact, record or comment. An artifact you
  produce names each principle it relies on or departs from, with the
  reason for a departure.
- **Conflicts.** When canon disagrees with a higher-ranked source, the
  higher one governs, and the disagreement is an observation, not a
  finding: add an entry to the pending observations (`observations.pending`)
  naming the canon id and what overrides it, and emit an `observation`
  outcome. A run that commits its record to `glados/ledger` carries it in
  the outcome only. A fresh agent lists each conflict under **Canon
  conflicts** in its output instead, and the workflow that spawned it
  files it.


## The shape step

Shape sketches the code a change will add or alter as signatures without
bodies, so the structure is reviewed while changing it is still a text edit.
It works from the plan when an earlier step produced one, and from the brief
otherwise. It writes one file beside the run record, `<record>.shape.md`,
and nothing else.

| Section | What it holds |
|---|---|
| Units | Each new or changed module, type, function or handler: its path, its signature in the project's own language in a code block, and a one-line purpose. No bodies. |
| Changed signatures | Each existing signature that changes: `path:line`, the current form and the proposed one. |
| Dependency direction | Which unit depends on which, and the layer each one sits in. |
| Readers | For every new field, parameter, public method or function, and exception type, the unit that reads, calls or handles it, as *Verdicts and finding severities* defines them. |
| Precedent | The unit on the target branch each new one follows. |
| Left to spec | Semantics, invariants and error behavior: named here, decided in the spec. |

One unit, for example:

~~~markdown
### `src/billing/invoices.py` (new)
```python
def issue_invoice(order: Order, due_in_days: int) -> Invoice: ...
```
Issues one invoice for a paid order. Follows `src/billing/receipts.py`.
~~~

- **Readers is the cheapest place to drop a field.** *Verdicts and finding
  severities* asks a review to name the line that reads each new field; at
  shape time, name the unit. A field with no reader is dropped now, or its
  reader is named, before a spec, a test and a caller are built around it.
- **A change with no new or changed signatures** writes one line: "no new or
  changed signatures".
- **Never write stub files to the branch.** The shape lives only in its
  file. When implement-feature or verify-feature runs after a shape, pass it
  the shape with the spec: implement-feature's first task lays the
  signatures down as stubs, and no stub survives to the MR.
- **Shape and spec split the decisions.** Shape decides names, types,
  placement and dependency direction. The spec decides semantics,
  invariants, payloads and errors. When spec-feature runs after a shape, pass
  it the shape with the plan: the spec builds on the shape and states any
  departure, and its persona pass does not reopen settled shape decisions.
- **Check the shape against canon.** The consult point is `shape`: read the
  canon that applies, as *Consulting canon* sets out, and name in
  Dependency direction, by canon id, each principle the shape relies on or
  departs from.
- **Gate the shape.** After the review its `review:` setting asks for, this is
  the standards gate's shape checkpoint: audit the shape against the
  project's standards tree, as *Standards gate* sets out, and hand on only a
  shape that has cleared it.


## Persona pass

An in-context review: the agent that produced an artifact reads it again
through each seated review persona. The pass shapes the artifact. It is not
the adversarial review loop, which runs later against the diff.

- **Seat the personas.** Read `run.active-personas` (seated by
  plan-feature); when that key is absent, resolve the default roster from
  `params.review-panel.personas` in `glados.yaml`. Add any persona the step's
  body names under "Personas to seat". Resolve each name in the project's
  `product-knowledge/personas/` first, then in the library vendored in
  `.glados/personas/`. A name found in neither is said in the record, never
  dropped silently. With no persona seated, say so in one line: the pass was
  empty, not skipped.
- **Press.** Each persona presses the question the plan assigned it, when
  there is a plan, plus its own mandate: what does this artifact get wrong,
  leave undefined, or make expensive later? The pass also presses each
  principle of the canon that applies at this step, from the seat it names,
  as *Consulting canon* sets out.
- **Fold.** Fold fixes into the artifact. Note each declined objection in the
  artifact with a one-line reason.
- **For a gate, the pass is the audit.** The personas check what the gate's
  body says to check. Each problem is a finding, on the *Verdicts and finding
  severities* scale, in the gate's own file; the audited artifact changes
  only through the gate's revise loop. With no persona seated, this agent
  does the audit itself against the body, as under `review: none`, and the
  gate's file says so: an empty pass never passes a gate.


## Fresh-agent design review

A review of a step's artifact by a new agent that did not write it. It
keeps the evaluator's two invariants:

1. **Context isolation.** The reviewer starts with a clean context window.
   It inherits no conversation history, reasoning or decisions from this run.
2. **Filesystem-only communication.** The run and the reviewer exchange
   exactly two files beside the run record, numbered n by the check
   (**Bound** in step 4): `<record>.<id>.review-brief-<n>.md` (input) and
   `<record>.<id>.review-<n>.md` (output). Nothing else is shared.

### Assemble the review brief

Write the brief self-contained:

| Section | Contents |
|---|---|
| What to review | The artifact path or paths: the step's own file, or for a gate, the artifact it audits. For code, the changed files and the base commit (`work.base-sha`, or the branch's merge-base with the target branch when that commit is not on the target). |
| What to check | For a project step, its body: `product-knowledge/steps/<id>.md`. For a built-in step, what its artifact must contain, copied from the document that defines it (this one for shape, the stage's own workflow for plan-feature and spec-feature), and the plan or brief it answers. |
| Personas to seat | Each persona's name and definition file path, resolved as *Persona pass* resolves them |
| Standards and canon | The applicable files under `product-knowledge/standards/` (philosophies included) and, when `glados.yaml` declares `canon:`, the digest of each entry that applies at the reviewed step, as *Consulting canon* sets out (a lone reviewer holds every seat), and the rules that section gives a fresh agent, copied verbatim. Paths, never summaries. |
| What is deliberately out of scope | Anything the plan, the spec or an earlier step deferred, each labelled with who deferred it: the author, or a person quoted. A deferral excuses an absence, as *What a fresh reviewer is given* sets out. Raise one only where living with it breaks something, and then say what breaks |
| Findings still open | Those the cycle table leaves open, by number, copied verbatim from where they were raised |
| Answers | Each question this run asked, with its readings and answer, copied verbatim from the run record |
| Vocabulary | The rules in *Verdicts and finding severities*, *What a fresh reviewer is given* and *Questions for a person*, copied verbatim |

## What a fresh reviewer is given

A fresh reviewer is only as independent as its brief, and the agent that did
the work writes the brief. So a brief carries inputs, never the author's
conclusions about them.

- **Only the listed inputs.** A brief carries what the workflow that writes
  it lists for it and nothing else: no verdict, approval or gate result from
  an earlier pass, no disposition the author gave a finding, no instruction
  about what is or is not a defect. A finding still open from an earlier
  pass may be named, as open.
- **Say who wrote each input.** The author is whoever wrote the change,
  agent or person. Everything the author wrote (plan, shape, spec, a
  contract file, the MR description) is labelled as the author's, and is
  under review like the code. A person's words, meaning anyone's but the
  author's (the ticket, an instruction given in the session or on the MR),
  are quoted verbatim with where they were said (a file path or an MR note)
  and labelled as theirs. A person set only what their quoted words name: a
  go-ahead on the author's proposal approves the direction, and the
  proposal stays the author's.
- **A scope statement excuses an absence, never a presence.** "Deferred to
  <item>" or "not in this MR" means the reviewer does not report that thing
  as missing. No scope statement, the author's or a person's, makes what the
  change does add correct: what it adds is reviewed on its merits. Deferring
  a unit's consumer does not excuse the unit: that nothing calls it is still
  a finding.


## Questions for a person

No code or file settles what a person meant. Whoever finds an artifact
resting on words whose readings differ materially, or on an `escalate`
choice no one's words reach, raises a question: the author, a reviewer or
a gate's audit. An artifact that assumes an answer instead has a blocking
finding.

- **Materially**: one reading adds, drops or changes a unit, a stored
  record, a failure path or an outcome, or needs a choice `decisions:`
  classes `escalate`.
- **Form**: numbered, under *Questions for a person* in its finder's file:
  the question; the words it turns on, quoted with where said, or the
  `escalate` class it needs; the readings, plainest first, each an outcome
  the person might want, never a mechanism; and what each changes.
- **A question never replaces a finding** and fails nothing. What code,
  files, a standard, a stated outcome or the blocking definition settles is
  a finding at its tier, even where a person's words are silent. A question
  goes beside it only if the answer changes its fix. Any other doubt is an
  advisory written as a question.


*(See **Verdicts and finding severities**, earlier in this document.)*

### Spawn the reviewer

Spawn a fresh agent with this prompt:

```
You are a design reviewer. Your job is to find problems, not to approve.
You have no knowledge of how this artifact was made, only what it should be
and what it is.

1. Read the review brief at <record>.<id>.review-brief-<n>.md. It is your
   only context; do not ask for more.
2. Read every file the brief names, directly.
3. Check the artifact against what the brief says to check, through each
   persona it seats, against each standard it lists, and against the
   principles in each canon digest it lists, at the weight the brief gives.
4. Run no tests and edit nothing.
5. Report each finding the brief names as open: closed, only when nothing
   else in the artifact has the same defect (no other path, input or place
   of its kind); not closed, and where it still holds; or not a defect,
   and why. One not closed is still blocking.
6. List every other issue: what is wrong, where (file, and section or
   line), its severity per the vocabulary in the brief, and what would fix
   it.
7. Check each assumption the artifact labels, and raise questions for a
   person, as the vocabulary in the brief sets out.

Write your review to <record>.<id>.review-<n>.md with sections: Checks
(item | met/not met | notes), Open findings (number | status | where or
why), Issues (numbered; location, severity, what would fix it), Questions
for a person, Canon conflicts when the brief lists canon digests (canon
id | what overrides it), and Result, exactly one of:
PASS: no blocking issue.
FAIL: list the blocking issues, open findings not closed included.
```

### Use the result

- FAIL is a `blocking` finding for the step, handled by its modifier: revise
  the artifact, then review again. PASS with advisory issues records them in
  the step's row.
- Each check spawns a **new** reviewer from a freshly written brief. Never
  reuse, continue or negotiate with an earlier one: fix the artifact, not the
  review.
- File each canon conflict the review lists, as *Consulting canon* sets
  out. A conflict is never a finding and never fails the review.
- Record the latest brief and review paths in the step's row. The result
  feeds the step table and, for a gate, its pass or fail. It never becomes
  a `verdict` outcome.


## Opening the merge request

The open-mr step commits the work on the branch and opens one merge request
for it. It never merges.

### Commit

Commit the work on the branch together with this run's record and step
artifacts so far, then push the branch, so every link the description
carries resolves for whoever reviews the MR.

## Git conventions

**Read the project's `CLAUDE.md` (or equivalent agent instructions) before any
git operation.** Its git, CI, branch, and review conventions are authoritative
and override every default below.

Defaults, where the project states nothing:

- **Conventional commits**: `fix:`, `feat:`, `refactor:`, `docs:`, `test:`,
  `chore:` — subject in the imperative, scoped where the project scopes.
- **Wrap at 80 characters** — subject line and every body line. Tighten a long
  subject (drop adjectives) rather than wrapping it.
- **No bylines, no attribution trailers** — no `Co-Authored-By:`, no
  "generated by" lines, no attribution footers on commits, MR bodies,
  issues, or comments.
- **Separate `git add`, `git commit`, `git push`** — never chained, so each
  result is visible on its own.
- Run the project's full test suite before committing; reproduce the project's
  exact CI checks locally before pushing.
- Never force-push over work you did not write.


### Open the MR

- Target branch: when this run is inside an epic, read
  `epic.integration-branch`; otherwise resolve `branching.default-target`
  from `glados.yaml`.
- Open the MR with the project platform CLI (per `glados.yaml` `platform:`).
- The description carries:
  - `## Summary` and `## Test plan` sections, with the key changes bulleted;
  - the pipeline, the rule that selected it, and any selection mismatch the
    run recorded;
  - the step table as it stands, with a link to every artifact it names;
  - every finding an advisory step recorded;
  - when no step in this pipeline produced `verification`, this sentence in
    the Summary: "No verification step ran in this pipeline."
- Resolve `merge-authority` from `glados.yaml` for who may merge. This step
  states no authority, and it never merges.

### Deliver what waited for the MR

With the MR open, and before anything reviews it, post the outcomes that
were waiting for it: the `## Pending MR delivery` items of this run's record,
of the runs nested inside it, and of a parked run this run resumed (with the
runs nested inside that one), as *No MR yet is not a failed delivery* (step 5
of *Before ending this run*) sets out for the run that opens the MR.


## Self-review

The self-review step reviews the MR's diff as a critic, before the review
panel runs.

- Review the diff against the spec (or the project step that stood in for
  it), the shape when there is one, and the closest in-tree precedent. Hunt
  for real defects and note strengths worth keeping. A contentless "looks
  good" self-review is a skipped step, not a passed one.
- Classify each finding on the *Verdicts and finding severities* scale. This
  step produces a `verdict` outcome, which lands on the MR as *Publishing a
  verdict* sets out.
- Its verdict follows **After the MR opens** in run-pipeline's step 4: it is
  posted when the step ends, and its findings start no revise loop,
  whatever the step's modifier.
- Do not edit the branch while findings are open; queue fixes so review line
  references stay stable.

## Publishing a verdict

How a `verdict` reads when it lands on a merge request. This is the default
shape: a project that configures its `mr-comment` sink overrides whichever
part of it that config speaks to, and a project that configures nothing gets
exactly this.

**Everything here governs wording and order, never content.** A finding that
reaches this step has already survived the tally — and, where it blocks,
refutation — so it goes on the comment whatever shape it arrives in. Nothing
in this section decides whether something is a finding, lowers a severity, or
moves a finding between tiers; that was settled upstream, where the reasoning
could be recorded. A rule here that seems to call for leaving something out
is being misread. If a finding resists every attempt to state it well, post
it badly worded and say so.

### Order

1. **The verdict line.** The composed verdict, the count of blocking
   findings, the cycle number and the SHA reviewed, on one line.
2. **What has to change**, on a comment carrying a blocking finding. One line
   per blocking finding: what has to change, and where. No evidence, no
   mechanism, no measurement. This list is the only place the asks are
   written — each finding below sits under its own line rather than
   restating it — so an author who reads only this far can start work and
   cannot mistake what is being asked. Every blocking finding gets its line;
   if the list runs long, that is the synthesis's cue to look again for a
   shared cause, never a reason to leave one out.

   A comment with no blocking finding has no such list. Its verdict line is
   the summary, followed by one sentence naming the cause the change was up
   against and whether the diff removed it — on a clean pass, that sentence
   is the only thing the review has to say.
3. **What the last cycle's work closed**, from the second cycle on. One line
   per finding the previous pass left open: closed, or still open. It goes
   above the findings because it is the first thing an author looks for —
   the only part that tells them the work they just did landed.
4. **The blocking findings**, each as one collapsed block whose summary is its
   line from item 2, word for word:

       <details><summary>1. the line from item 2, verbatim</summary>

       The claim — what breaks, file:line, what to do — in a few plain
       sentences. Then the evidence: the reproduction, the measurement, the
       walk through the mechanism, why the obvious fix is the wrong one.

       </details>

   A consolidated finding — several members dissolved by one design change —
   is posted as the one finding it is, its members listed inside as evidence.
5. **Advisories**, one line each.
6. **Breaches that predate the change**, if the panel found any: one line,
   pointing at wherever the project tracks bringing existing code up to
   standard. The tally has already pooled them; if more than one line of them
   reaches here, it still gets one line.
7. **The lens roll-call**, one collapsed line (`UAT ✓ · Adversarial ✗ · …`).
   Which lens raised a finding is bookkeeping, never a section header.

An `ESCALATE` adds one sentence saying why — the cycle bound reached, a
contradiction the panel could not settle, a seat that never returned. A
composed escalation can carry no blocking finding at all, so that sentence may
be the only thing the author has to act on.

A verdict that came from an evaluator rather than a panel has no roll-call and
no consolidation to report; skip what it cannot fill rather than inventing it,
and say in one line which pipeline produced it.

Nothing else crosses from the run record: not the refuted findings, not the
diff the pass read, not the process by which the verdict was reached.

### Voice

- Write to a senior engineer who is busy and skeptical and will not read past
  the first screen. Plain English, not model prose.
- Lead with the verdict. No preamble, and no recap of what the change does —
  the author wrote it.
- Open each finding with the plain sentence you would say out loud. The rule
  or standard it rests on goes underneath as evidence, never in place of the
  sentence.
- Name a concrete failure — "this drops the tenant filter, so a broker in firm
  A sees firm B's reports" — not "consider whether this may impact isolation".
- Leave out praise, emoji headers, restatements of the severity scale or the
  review process, and commentary about the panel.
- *Verdicts and finding severities* asks that each thing be said once and
  that each ask be priced. Both apply to the comment as written: the surface
  is where a point made twice costs the most.

### Length

- The visible text — everything outside the folds — aims at one screen, about
  three hundred words. It is a check, not a cap. Past it, look for proof
  sitting on the surface that belongs inside a fold, and for findings that
  should have been consolidated; a comment gets shorter by moving its proof
  one click down, never by dropping it.
- **A fold is cheap, not free.** In a web view the reader pays for folded
  evidence only when they open it. `glab`, plain-text mail and most terminals
  render the tags literally, so there the evidence is last rather than hidden.
  That is the other reason the surface has to stand on its own: if a sentence
  only makes sense once the block beneath it is open, it is in the wrong half.
- **Never fold an ask.** A reader who expands nothing must still learn every
  blocking thing they have to do — which item 2 guarantees, and which is what
  makes folding the rest safe.

### Evidence

- Cite a line number only from a read of the file at the head under review,
  never from memory of the diff; re-open the cited file before the finding
  goes out. A wrong line number is a wrong finding, and an author who meets
  three bad citations stops reading the fourth comment.
- A finding the refutation stage marked unconfirmed says so inside itself and
  keeps its tier: "blocking — unconfirmed: is `x` reachable with …?" The
  author answers a question instead of chasing a defect.

## Standards gate

Before advancing past this point, audit the artifact the preceding step
produced — the spec when this gate runs before implementation, the working
diff when it runs before declaring the work done — against the project's
documented standards. The standards tree lives at
`product-knowledge/standards/` and that is the **only** standards root: a bare
`standards/` directory at the repo root is not read, not even as a fallback.

### Discover applicable standards

- Read `product-knowledge/standards/index.yml` for the registered standards.
  If the tree or its index is absent, say so in the gate report and pass the
  gate vacuously — an empty standards tree gates nothing, but skipping the
  gate silently is not the same thing.
- Each standard file carries YAML frontmatter:

  ```yaml
  ---
  scope: [api, backend]         # areas this standard applies to
  severity: must | should | may # RFC 2119
  keywords: [error, response]   # aids matching
  ---
  ```

- Filter to the standards that apply to the artifact at hand: `scope` tags
  against the areas and file types touched; `keywords` against the content of
  the spec or the changed files.
- A standard without frontmatter is `severity: should`, `scope: [all]`.
- Philosophy documents registered in the index participate like any other
  standard; treat `weight: core` as `severity: must`.

### Audit

*(See **Verdicts and finding severities**, earlier in this document.)*

For each applicable standard, read its full content and compare the artifact
against it. A standard the artifact adheres to produces no finding. A breached
standard produces exactly one finding, classified on the single severity scale
above by the standard's declared severity:

| Standard severity  | Finding    |
|--------------------|------------|
| `must`             | `blocking` |
| `should` / `may`   | `advisory` |
| canon, not adopted | `advisory` |

A standard's `must`/`should`/`may` is authoring metadata about the standard;
findings themselves take only the two tiers — no third tier exists at the
gate.

### Gate decision

- **Any `blocking` finding**: stop. Do not advance to the next step until the
  artifact is brought into compliance, then re-run the gate on the corrected
  artifact. If the standard itself appears wrong or outdated, do not weaken or
  bypass it inline — record the conflict in the gate report as a candidate for
  the standards owner to review, and either comply anyway or halt the work
  here with the conflict stated.
- **Only `advisory` findings**: proceed. State each advisory finding's
  disposition as the severity scale requires — fixed, or declined with a
  one-line reason.

Each re-run of the gate on a corrected artifact is one gate cycle. Count
the cycles in the run record. At `params.standards-gate.max-cycles`, do not
re-run again: stop, emit an `escalation` carrying the open blocking findings
and the cycle history, and end the run. A run enclosing this one (preamble
step 1) stops too, rather than advancing on an artifact the gate did not
pass. Gate cycles are bounded as *Loop bounds* sets out:

*(See **Loop bounds**, earlier in this document.)*

### Report

Close the gate with a summary table; the surrounding workflow carries it in
its findings and outcomes:

```markdown
## Standards Gate
| Standard            | Scope   | Severity | Finding  |
|---------------------|---------|----------|----------|
| API Response Format | api     | must     | none     |
| Error Logging       | backend | should   | advisory |
```

## Before ending this run (mandatory)

A run without a committed run record and a published outcome is an incomplete
run — finish these steps even if the work above was cut short, and say so in
the record rather than omitting it.

1. **Finalize the run record** at `.glados/runs/<YYYY-MM-DD>-<workflow>-<slug>.md`:
   outcome, key decisions (with their decision-rights class), verdicts if any,
   links (MR, issues, commits), and any state keys this run wrote
   (`review.reviewed-head`, `epic.progress` updates, …). If this run was cut
   short, record how far it got — a partial record beats a missing one. A
   record is a screen, not an essay: reasoning that already lives in the
   published comment or in the diff is not repeated in it.
2. **Yield check**: compare the recorded `work.base-sha` against the current
   base. If an external edit moved it, emit `yielded (external_edit)` in the
   record, then rebase or release — never force-push over someone else's work.
3. **SDA work-unit log (when `glados.yaml` sets `sda: true`)**: a run that is
   not nested (preamble step 1) appends the single work-unit row for the
   whole unit of work to `product-knowledge/SPEC_LOG.md` — date, workflow,
   scope, outcome, links — and clears its entry in `claims.md`, so both ride
   the record commit below. A nested run does neither: it holds no claim of
   its own, and a work-unit row marks its subject done, so a nested plan's
   row would mark the whole feature done early. Its record path is already
   listed in the parent's record, and the outermost run's row covers it.
   The exception is the one the preamble names: a ticket's build inside
   run-epic is a unit of work of its own, so it appends the ticket's row
   and clears the ticket's claim; the runs nested inside it do neither.
   A run that ends with its unit of work still waiting on an approval has
   not finished it: run-pipeline parking at a `human` checkpoint or
   resuming a park that has no approval yet, and run-epic stopping with
   only parked tickets left. It keeps its claim and appends no row, and the
   run that resumes the work does both when the unit ends.
4. **Commit the record** on the current working branch:
   `chore(glados): record <workflow> run`. Runs that act on a merge request
   under review — review-mr, address-review — commit their record to the
   `glados/ledger` branch instead, never to the author's branch: the MR
   carries the change and the comment, and the ledger carries the trail.
5. **Publish outcomes**: read `glados.yaml` → `channels:` (which sinks each
   outcome type goes to) and `sinks:` (how each sink behaves). For every
   outcome type this run emitted, deliver it to each bound sink using the
   project's own platform CLI/tooling (glab/gh/MCP), **rendering per that
   sink's declared config** — interpret its keys sensibly for the sink's
   medium and this team's conventions, and record in the run record which keys
   you honored and which you did not recognise, so a typo surfaces as a line
   in the record instead of as silence. Built-in sinks are `mr-comment`,
   `issue`, `issue-comment`, `label`, and `ledger`; a project may declare
   others (e.g. `slack`). `progress` always lands in the ledger at minimum.
   - **`grouping:`** decides how many comments one outcome becomes:
     `aggregate` — one comment carrying the whole outcome, and the reading to
     take when the key is absent; `per-persona` — one per seated persona;
     `per-finding` — one per finding. `threads: resolvable` posts each of
     those as its own resolvable thread where the platform supports it.
   - **`summary:`** applies only where `grouping:` splits an outcome across
     several comments, and controls whether an additional composed-verdict
     comment joins them. Under `aggregate` the single comment already **is**
     the composed verdict, so `summary: false` suppresses nothing: an outcome
     bound to a sink always produces at least one comment there. A reading of
     any sink config that ends in posting nothing is a misreading.
   - **Delivery is verified, not assumed.** Every sink bound to an outcome
     type must actually receive it. If a bound sink is unreachable or the post
     fails, record the failure in the run record and emit an `escalation`.
     Delivery to a different sink does not cover the one that failed: a
     verdict that never reached the MR leaves the change looking unreviewed,
     however many other sinks got a copy. Never silently drop an outcome.
   - **No MR yet is not a failed delivery.** When an outcome is bound to
     `mr-comment` and no MR exists yet for the work it is about (a verdict
     from verify-feature inside build-feature, a `decision` from a nested
     plan-feature, run-epic's backlog selection), deliver it to its other
     bound sinks and record it in the run record under `## Pending MR
     delivery`. This does not escalate. The run that opens the MR posts
     every pending MR item from its own record, from the records of the
     runs nested inside it, and from a parked run it resumed (with the runs
     nested inside that one) as soon as the MR is open, before handing the
     MR to review (build-feature right after it opens the MR in its step 5,
     before its self-review; a pipeline's open-mr step), then marks each
     item delivered in the record that holds it. Any item still pending
     when this step runs, with its MR open, is posted now. When the
     outermost run ends and no MR exists for the work an item is about
     (run-epic's backlog selection, a standalone plan), mark that item "no
     MR for this work; mr-comment delivery not applicable" instead of
     escalating, even if nested runs opened MRs for their own work. A run
     that ends with its unit still waiting on an approval (step 3) has not
     ended it: its items stay pending for the run that resumes the work and
     opens the MR. Once
     the MR exists, a post that fails is a failed delivery as above. These
     record updates (this run's record, and any nested record you marked
     delivered) ride the step 4 commit when made before it; any made in
     this step go in one more `chore(glados): record <workflow> run` commit
     before step 6.
   - Reaching only the ledger is not itself a failure. `progress`, `decision`,
     and `observation` may be bound ledger-only by design, as may any outcome
     type in a project whose manifest confesses `visibility-acknowledged:
     ledger-only`. Escalate on a sink that failed, never on a binding the
     manifest deliberately declared.
   - **One escalation per run, and it is never itself escalated.** Collect
     every failed delivery from this run into a single `escalation` naming all
     of them, rather than emitting one per failed post. If that escalation
     also fails to deliver, record both failures in the run record and stop —
     do not raise a further escalation for it. Without this floor a single
     unreachable platform produces an unbounded chain, every link failing for
     exactly the reason that produced it, and the run manufactures noise at
     the moment the team can least act on it.
6. **Release** anything held: leases (when enabled) and other in-flight
   markers. Then pop this run off the marker stack: remove this run's line
   from `.glados/runs/stack`; if lines remain, write the last remaining line
   into `.glados/runs/current` (the enclosing run is in flight again);
   otherwise delete both `current` and `stack`. With no `stack` file, delete
   `current`. Never leave a marker naming this finished run: a leftover
   marker makes the run-record guard hooks block the next session.
