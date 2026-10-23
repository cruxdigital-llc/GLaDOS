# Pipelines: your project's own workflows

> Terms such as *core*, *manifest*, *run record*, *outcome* and *lane* are
> defined in [concepts.md](../concepts.md).

GLaDOS ships a fixed set of workflows. Its main feature path, build-feature,
runs four stages in a fixed order: plan, spec, implement, verify. A project
that wants a different process can declare its own workflows in
`glados.yaml`, without forking GLaDOS. These docs call them **project
workflows**. In config they live under `pipelines:`, because `workflows:` is
already a config key (it picks modules per workflow).

A pipeline is an ordered list of **steps**: GLaDOS's built-in steps and steps
your project writes. One built-in workflow, `run-pipeline`, runs any of them.
build-feature and fix-bug do not change, and stay available.

## Your team owns the shape, GLaDOS owns visibility

No step is mandatory, and no step has a fixed position. A refactor can skip
planning. A design pass can stop before any code. A team can write tests
before anything else. What GLaDOS protects is not a process shape but the
team's ability to see and trust what happened. These hold in every pipeline,
whatever its steps:

- **A run record from the first minute,** with a step table written before
  any step runs, finalized at the end and saved, with its step artifacts, to
  the `glados/ledger` branch (`glados.py ledger save`), never to the work's
  branch. The run-record guard hooks block a session end while any run in
  flight, outer runs included, has a record or step artifact the ledger
  lacks, while a run marker cannot be read or decoded or `.glados/runs/`
  cannot be listed, and while a directory, or a link to a directory or to
  nothing, stands where a record should be
  ([hooks/README.md](../../hooks/README.md)). The CI ledger check lists any
  record a merge request commits.
- **Outcomes reach a team-visible place,** and decision rights apply inside
  every step.
- **Before any step changes code,** the run claims a branch (never the
  default branch) and records the base commit and the SDA claim. The yield
  rule applies when someone else edits the branch.
- **Only declared steps run.** A missing step file escalates instead of
  being improvised, and a required step cannot be skipped.
- **One vocabulary.** Every finding is `blocking` or `advisory`, and every
  revise loop has a bound.

Pipeline definitions are read live from `glados.yaml` (lane 2). That bends
the v2 rule that anything an agent must not skip is compiled, on purpose: the
Claude Code plugin is built once from GLaDOS's own example config, so it
cannot compile your pipelines. Every rule about how a step runs is compiled
into `run-pipeline` instead, and
[Keeping required steps honest](#keeping-required-steps-honest) lists what
makes a skipped step visible.

## Declaring steps

Declare your own steps under `steps:`:

```yaml
steps:
  architecture-review:
    description: Audit structure against our layering and dependency rules
    kind: gate
    stage: speccing
    audits: [shape, spec-feature]
```

| Key | Required | Meaning |
|---|---|---|
| `description` | yes | One line. |
| `kind` | yes | `produce` writes a file beside the run record. `gate` checks an earlier artifact. `change` edits code on the branch. |
| `stage` | yes | `planning`, `speccing`, `implementing` or `verifying`. Where the step sits for SDA and Wheatley. |
| `produces` | no | Only on `produce` steps: `plan`, `shape`, `spec` or `verification`. Lets the step stand in for the built-in that produces that kind. |
| `audits` | on gates | The steps (built-in or yours) the gate may audit. In a given pipeline it audits the most recent one that ran before it. |

Unknown keys are an error: these declarations drive gating, so a typo must
not pass quietly.

### Step bodies

Each step a pipeline runs has a body at `product-knowledge/steps/<id>.md`,
named exactly as the id (case included). It is plain markdown with **no
frontmatter**, because every declaration lives in `glados.yaml`. The body only says what to produce or check. Suggested
headings: *What to produce* (or *What to check*), *Personas to seat*,
*References*.

`product-knowledge/steps/architecture-review.md`:

```markdown
## What to check
- Dependencies point inward: handlers depend on services, services on
  domain types, never the reverse.
- Nothing in the web client imports from the job runner.
- Every new public function has exactly one owning layer.

## Personas to seat
architect, scalability-engineer

## References
product-knowledge/standards/layering.md
```

GLaDOS owns everything else about the step: the step table, the severity
scale, the revise bound, and where results go. A body cannot loosen a gate.

A step can consult the project's canon: name its id in a canon entry's
`applies-to`, or cite a principle (`canon:<name>#<principle-id>`) under
*References*, and the step, its review and its gate read that digest. See
[canon.md](canon.md).

## Declaring pipelines

```yaml
pipelines:
  backend-feature:
    description: A change to an endpoint, schema, migration or background job
    when: >-
      The change adds or alters an endpoint, a schema, a migration or a
      background job.
    sequence:
      - plan-feature
      - shape
      - architecture-review
      - spec-feature
      - implement-feature
      - verify-feature
      - open-mr
      - self-review
    step-options:
      architecture-review:
        review: fresh-agent
```

| Key | Required | Meaning |
|---|---|---|
| `description` | yes | One line, 250 characters or fewer (some runtimes truncate longer ones). It becomes the shortcut command's description. |
| `when` | yes | Prose the agent matches a brief against when nobody names a pipeline. |
| `sequence` | yes | The step ids in order, as a block list or a one-line flow list (`[a, b]`). Not empty, no repeats. |
| `step-options` | no | Settings per step, keyed by step id. Every key must be in the sequence. |

Each entry under `step-options` takes:

| Key | Values | Default |
|---|---|---|
| `modifier` | `required`, `optional`, `advisory` | `required` |
| `when` | Prose saying when the step applies; required with `modifier: optional`, and allowed only there | none |
| `review` | `none`, `in-context`, `fresh-agent` | `in-context` for gates and `shape`, `none` otherwise |
| `checkpoint` | `none`, `record`, `human` | `none` |

Two more keys tune every pipeline. A `glados.yaml` copied from
`glados.yaml.example` already has `decisions:` and `params:` (each with
these entries commented out): put the entries under those keys, or
uncomment them there, rather than pasting the block below as a second
`decisions:` or `params:`:

```yaml
decisions:
  pipeline-discretion: record   # agent | record | escalate | forbidden
params:
  pipeline:
    max-cycles: 8               # revise cycles per step before escalating
```

`pipeline-discretion` sets how much the agent may decide on its own: picking
a pipeline, skipping an optional step, switching pipelines once. The phase
presets set it to `agent` for nascent and evolving projects and `record` for
production and sunset, so in production every such choice is published as a
`decision`. Under `escalate`, the agent asks a person to name the pipeline
instead of picking one, and stops rather than switch. Under `forbidden`, it
never picks (a `default` pipeline or the fallback runs) and never switches.
Under either, optional steps always run. Setting it laxer than your phase
needs `relaxation-acknowledged:`, like any other decision. A value other
than those four classes, such as `agnet`, fails `validate`, install and
`check`, and run-pipeline stops on one before its first step.

A revise cycle is one revision of a step's artifact, for findings, for a
person's answers or for a refusal, and the check after it. `max-cycles`
counts them all, as it does for every other loop, and is only a runaway
guard. It must be a plain whole number of 1 or more (`8`, not `"8"`,
`true`, a list or `0`), whether `glados.yaml` sets it or the preset table
supplies it: `validate`, install and `check` refuse anything else, naming
the key and the layer it came from, and a run that finds no such bound
escalates instead of starting the loop. Progress is judged per check,
with no number to tune: a check is stalled when the revision before it
closed none of the blocking findings it was given, or when it raises an
earlier finding's defect (the same consequence) at another path, input or
place, a closed finding coming back included; when the run is unsure, it
counts as a recurrence. The first stalled check parks the step at once,
naming the open findings, their kind and how the author would remove it,
with a scenario, each option's cost and risk, and the author's
recommendation, confidence and evidence, and asking you to approve that,
rule a finding not a defect, waive findings by name, or stop. A finding is
closed only when nothing else in the artifact has the same defect, so
patching the one path a finding named while its twins remain is a stall,
not progress. The 2.5 candidates' `max-stalled-cycles` is retired:
install, `check` and `validate` warn when a manifest still sets it, and the
assembly report marks it read by nothing.

Each step that is checked keeps a cycle table in the run record, one row per
check, linking the check's own file (no check overwrites another's),
listing what it was given, closed and raised, and marking each raised
finding `new` or `recurs <n>`, so you can check the counting against what
each reviewer wrote. A fresh reviewer decides closure; for a gate audited
in-context or with `review: none`, the closure is the author's, and the row
says so.

`steps:` and `pipelines:` are yours alone: no phase preset can set them. An
edit to a sequence, a step option or a step body takes effect on the next
run, and never makes the compile stale. Adding, removing or renaming a
pipeline, or changing its description, changes the shortcut commands, so
script installs re-run install; until they do, `glados.py check` reports a
stale compile.

## Built-in steps

| Step | Runs as | Needs | Produces | Stage |
|---|---|---|---|---|
| `plan-feature` | a nested workflow | a brief | plan | planning |
| `shape` | a library step in the pipeline run | a brief or plan | shape | speccing |
| `spec-feature` | a nested workflow | plan | spec | speccing |
| `implement-feature` | a nested workflow | spec | change | implementing |
| `verify-feature` | a nested workflow | spec and change | verification | verifying |
| `open-mr` | a library step in the pipeline run | change | MR | verifying |
| `self-review` | a library step in the pipeline run | MR | a verdict on the MR | verifying |

**Shape** sketches the new code's signatures, in the project's own language
and without bodies, before the spec is written: the units with their paths
and signatures, changed signatures, dependency direction, the unit that reads
each new field, the precedent each unit follows, and what is left to the
spec. It never writes stub files to the branch. implement-feature writes the
stubs as its first task, and none survive to the MR. verify-feature's
evaluator checks the public units the diff adds or drops against it. Shape
decides names, types, placement and direction; the spec decides semantics,
invariants, payloads and errors.

**open-mr** commits and pushes the work, saves the record and step
artifacts so far to the `glados/ledger` branch, opens the MR with the step
table and a link to each artifact's ledger copy (`glados.py ledger link`),
and delivers outcomes that were waiting for an MR.
**self-review** is build-feature's self-review step: the agent critiques its
own diff and posts a verdict. Once the last step is done, the run hands the
MR to review-mr, together with the blocking findings and one-way questions
of any step after `open-mr`.

## How steps connect

Order is checked through inputs, not positions. Each step needs some kinds
of artifact and produces one. The kinds are a closed set: plan, shape, spec,
change, verification and MR. Validation checks that every step's needs come
from an earlier step.

- **A project step can stand in for a built-in.** It declares what it
  produces. A refactor's `target-structure` step that `produces: spec`
  satisfies implement-feature, which already accepts a spec handed to it by
  its caller.
- **A `produce` step without `produces:`** still writes its own file, and a
  later gate can audit it.
- **A step that always runs (required or advisory) whose only earlier
  producers are optional** is an error: the run could reach it with nothing
  to work on. The same goes for a gate that always runs and can audit only
  optional steps.
- **Opening the MR is a step too.** A pipeline without `open-mr`, or whose
  optional `open-mr` was skipped, ends with its artifacts beside the run
  record on the `glados/ledger` branch, which suits a spike, an RFC or a
  design pass. When it worked on a branch of its own, it commits and pushes
  that branch's work for a person; the record and its artifacts are on the
  ledger, not on the branch.
- **Verification before an MR is your call.** build-feature keeps its
  verified-before-MR gate. A pipeline that opens an MR with no verification
  step before it gets a warning from `validate`, and the MR description says
  "No verification step ran in this pipeline."

## Modifiers

| Modifier | Runs | Findings | What the agent may do |
|---|---|---|---|
| `required` (default) | Always | A blocking finding stops the pipeline. The audited artifact is revised and checked again: a stalled check parks the step for a person, and after `params.pipeline.max-cycles` revise cycles the run escalates. | Nothing. Only a human waiver, recorded with who gave it, lifts it. |
| `optional` | When the agent judges the step's `when:` holds (an optional step must have one) | Same as required, if it runs | Skip it, recording the `when:` evaluation and a one-line reason. |
| `advisory` | Always | Recorded at advisory severity and carried to the MR description. Never stops the run. | Treat a finding as blocking anyway. |

A modifier governs the findings of the step's own result, review or gate. It
never softens a stop: a nested workflow that escalates, or the standards gate
reaching its bound inside spec-feature or shape, ends the run whatever the
modifier. An optional step left with nothing to work on, because the steps
it needs or audits were all skipped, is skipped too.

"Dynamic" means `optional` plus `when:`. The agent cannot insert a step the
sequence does not list. A step it might want goes in the sequence as
optional.

## Review and checkpoints

Two separate settings per step.

**`review`** is who critiques the step's artifact. For a gate, it is how the
audit itself is done.

- `none`: no review.
- `in-context`: the persona pass. The running agent reads the artifact
  through the seated review personas (the plan's roster, or without a plan
  the default panel, plus any the step body names), folds fixes in, and notes
  declined objections with a reason. For a gate with no persona seated, the
  agent does the audit itself against the step body, and says so.
- `fresh-agent`: a new agent with no memory of writing the artifact reviews
  it from a self-contained brief, under the same isolation rules as the
  verify-feature evaluator. The brief carries inputs, never the author's
  conclusions: the artifact, what to check (the step body, or the built-in
  step's own contract), what a person asked, quoted verbatim with where it
  was said, the seated personas, the standards and canon digests that apply,
  what was deferred and by whom, and the findings still open, but no earlier
  verdict, approval or gate result and no disposition the author gave a
  finding. Everything the author wrote is labelled as the author's and is
  under review like the code. The reviewer runs no tests and edits nothing,
  and each check gets a new one. The author reviewing its own work is the
  weak case, so use `fresh-agent` for gates that matter.

`review` may be set on your own steps, `shape` and `plan-feature`.
`spec-feature` takes only `none` or `fresh-agent`, because it already runs a
persona pass. `implement-feature`, `verify-feature`, `open-mr` and
`self-review` take no `review`.

**`checkpoint`** is whether a person must approve before the run moves on.

- `none`: continue.
- `record`: continue, and publish the step's result in the run's `decision`
  outcome.
- `human`: the run saves its record and artifacts to the `glados/ledger`
  branch, commits any uncommitted code on its branch, and pushes the
  branch. It then asks in the session when
  a person started it, with the step marked `parked` until they answer, so
  a session that ends first leaves work a later run can resume; a "no" is a
  blocking finding, so the artifact is revised and the question asked
  again. Unattended (in run-epic, or headless), it **parks**: the branch and
  the SDA claim are kept, outcomes waiting for an MR stay waiting, and one
  escalation is filed naming the branch, the run record and the artifacts
  by their ledger links (`glados.py ledger link`), and the approval needed.
  A later run on the same work restores the parked record from the ledger
  (every run starts with `glados.py ledger restore`), checks out that
  branch, and resumes once a maintainer, or a CODEOWNER of `glados.yaml` or
  `product-knowledge/steps/`, approves on that escalation. It takes the
  parked run's pipeline, step table and cycle tables, quotes the approval
  into its record, and escalates if `glados.yaml`, a step body, or the
  configuration `glados.py effective-config` reports (the preset table
  included) differs on the branch the work targets from what the parked run
  pinned. With no approval yet, it says so and ends, and the work stays
  parked.

**A person's words.** Every step and review reads a person's words (the
ticket, an instruction in the session or on the MR, an answer) as firmly as
they were said. A *Directive* ("must", "never", or a plain statement of what
is wanted) binds. A *Preference* ("should", "I'd like", "I think we need")
sets a default that evidence may override. A *Hunch* ("I think", "maybe", a
stated problem) is a belief the artifact tests against the code and reports
on. An *Assent* ("seems fine", "go with that", choosing a question's
reading) approves only the direction of what the person was shown, not its
mechanism or wording. Where the code suggests their words miss what they
want, the artifact says so in the open: "your words say X; the code shows Y;
I propose Z". Against a Directive, or where it is material, that is a
question for them; otherwise the work follows Z, and the run's `decision`
outcome lists the challenge. Any other departure from a person's words,
including one under too soft a tag, breaks a criterion the work received.

**Questions for a person.** Some things no reading of the code settles:
what a person meant by their words. When the readings differ materially
(one changes an outcome the ticket or a person names, or needs a choice
classed `escalate` under `decisions:`), the author, a review or a gate's
audit raises a question for a person. It gives the decision in one line, a
concrete scenario through today's code, the readings plainest first (each
an outcome you might want, with what users would see, its cost, risk and
reversibility), the finder's recommendation with its confidence and
evidence, the door and its default, and the words it turns on, quoted with
where they were said. Readings that differ otherwise (a unit, a stored
record, a failure path) are not material: the artifact takes the one your
standards or nearest in-tree precedent follows, else the plainest, labelled
as an assumption. The evaluator checks that a test pins each labelled
assumption, as it does each answer. A question never stands in for a
finding: what the code, the files, a standard or a stated outcome settles
is a finding, and a doubt that changes nothing material is an advisory. A
reviewer also checks each assumption the artifact labels: going on under
one whose readings differ materially is a blocking finding.

Each question is a door. Its default is the reading a person's Directive or
chosen reading takes, else its finder's recommendation. A **one-way door**
(no default, because a person's words take two readings, or a default that
needs an `escalate` choice or leaves unmet an outcome another reading meets;
when unsure, one-way) parks the step exactly as at a `human` checkpoint, all
of a check's one-way questions in one park, with the questions in place of
the approval and answered by the same people. A project step's body may
instead name a later step, before any step that writes code or opens the
MR, at whose end (or skip) its questions park, so a run asks once. A
**two-way door** parks nothing: the author takes the default and goes on,
the run's `decision` outcome lists it, and the question joins the next
park, or goes on the MR, for you to confirm or overturn; unanswered, the
answer stands. An advisory the author declines is noted in its step row;
once two fresh reviewers or evaluators of the run have raised it, it is a
question for you, asked once: whether you want it. It is never made
blocking. A reading that needs a `forbidden` choice is refused, never
asked; a choice your classes leave to the agent is made, not asked. The
answer is recorded verbatim as the answerer's words, the question and
readings as their finder's, and the run resumes inside the step: the author
revises, and the check runs again. That revision is a revise cycle, and the
bound is checked first: a step already at it escalates with its questions
instead of parking.

Gates and reviews before the MR publish no verdict, because no MR exists yet.
Their results go into the step table, the run's `progress` outcome and the MR
description. A step after `open-mr` (self-review, or a gate of your own)
reviews work already under review, so its findings start no revise loop.
Its verdict, with any questions it raised, is posted on the MR when the
step ends, and the run hands its blocking findings and one-way questions to
review-mr as still open: the panel's first pass closes each finding or
keeps it, and address-review works through any that stand.

## How a pipeline is chosen

`run-pipeline` picks a pipeline by the first rule that applies, and records
which rule chose it:

1. The person running it names one: `/glados:run-pipeline backend-feature
   <brief>`.
2. The ticket or brief names one, for example with a tracker label.
3. `run-epic` assigned one when it broke the epic into tickets.
4. The agent matches the brief against each pipeline's `when:`, and records
   the alternatives it considered. When two match, it takes the one with the
   stricter required steps.
5. A pipeline named `default`, if you declare one.
6. Otherwise build-feature's stages (plan, spec, implement, verify, open-mr,
   self-review), recorded as a fallback.

After the first step that produces a plan or spec, the run checks the choice
again against what that artifact says the work touches. A pipeline the agent
chose (rules 4 to 6, or a run-epic row marked `(agent)`) that no longer fits
is switched once, reusing the work so far. This stops the agent from
settling on the lightest pipeline. A pipeline a person or ticket named, or a
run-epic row a person set, keeps running, with the mismatch recorded. A
named pipeline that is not declared escalates, typos included; it never
falls back silently. A bug report goes to fix-bug, which runs instead of a
pipeline.

## Running a pipeline

| Install | Run a pipeline | Shortcut per pipeline | Config checked |
|---|---|---|---|
| Claude Code plugin | `/glados:run-pipeline <name> <brief>` | None. The plugin is built once from GLaDOS's own example config, so it cannot add commands per project. | At run start |
| Claude Code script install, Gemini CLI | `/glados:run-pipeline <name> <brief>` | `/glados:<name> <brief>` | At install, in `check`, and at run start |
| Antigravity, pi | `/glados-run-pipeline <name> <brief>` | `/glados-<name> <brief>` | At install, in `check`, and at run start |
| Direct | Read and follow `product-knowledge/glados/run-pipeline.md` | A pointer file, `product-knowledge/glados/<name>.md` | At install, in `check`, and at run start |
| Google AI Studio | Not supported: it cannot run code or touch the repo | | |

The brief can be left out when a ticket or the project status file supplies
the work. A pipeline or step name that collides with a GLaDOS workflow, an
alias, a built-in step, `run-pipeline` or `init` fails validation. A removed
pipeline's shortcut is cleaned up at the next install. The sunset phase
preset disables run-pipeline along with build-feature; each pipeline's
shortcut then says so instead of running anything. A `disabled-workflows:`
list you write yourself replaces the preset's, so name run-pipeline in it
when it should stay off ([MIGRATION.md](../../MIGRATION.md#upgrading-a-v2-install-to-25)
has the upgrade notes).

In `run-epic`, each ticket gets a pipeline when the epic is broken down (only
pipelines whose `open-mr` always runs, since an epic integrates MRs), and the
ticket table shows it, marking the agent's choices `(agent)`. With
run-pipeline disabled, every ticket gets `build-feature`. A person can
change a ticket's pipeline, and the run never overwrites that choice. A
ticket parked at a checkpoint waits, with its dependents; independent tickets
carry on (a ticket parked on a question waits the same way, for its answer).
Its row reads `awaiting-approval:<step>` with the parked branch and
record noted, it resumes on that branch, and the epic closes only once no
row is parked. When only parked tickets are left, the run-epic run ends
with a `progress` outcome listing what each one waits for, and the next
run-epic run picks them up. With no `pipelines:` declared, run-epic behaves
as before.

## Checking your config: `validate`

```bash
# a script install
python .glados/glados.py validate --target .

# a plugin-only repo, using the GLaDOS checkout the plugin runs from
python /path/to/GLaDOS/bin/glados.py validate --target .
```

`validate` loads the project's `glados.yaml`, runs every check that install
runs, prints errors and warnings, and writes nothing. It exits 1 on any
error. It needs no install, so a plugin-only repo can run it in CI against a
pinned GLaDOS release (`--source` points it at another GLaDOS checkout).
`install` and `check` run the same checks, and `run-pipeline` runs
`validate` before its first step. Without Python, it applies a compiled
checklist instead. `install` also records each pipeline's resolved step
table, defaults filled in, in the `## Pipelines` section of
`.glados/assembly-report.md`.

`validate` resolves `glados.yaml` over the preset table of the GLaDOS that
runs it. A run reads its defaults from `.glados/presets.yaml` (in a
plugin-only repo, the plugin's own table), so run-pipeline also runs
`glados.py effective-config --target .` at its start, and you can too. It
resolves `glados.yaml` over that table and fails, exiting 1, when a bound a
workflow uses is absent, null or not a whole number of 1 or more, or a
decision class or merge authority is misspelt; otherwise it prints the
digest of the configuration the run obeys, which the run pins (see
[Run records](#run-records-sda-and-wheatley)). `--ref <commit>` reads
`glados.yaml` and a tracked preset table as that commit has them.

Errors:

- ids that are not kebab-case, or names that collide (see the previous
  section);
- a sequence that is empty, repeats a step, or names a step that is neither
  built in nor declared;
- a step whose needs no earlier step produces, or a step that always runs
  whose only earlier producers are optional;
- a gate whose `audits` names no earlier step in the sequence, or (when the
  gate always runs) only optional ones;
- unknown keys, values outside their sets, missing required keys,
  `produces:` on a step that is not `produce`, `audits:` on a step that is
  not a gate, `when:` without `modifier: optional` (or `modifier: optional`
  without `when:`), `step-options` for a step not in the sequence, or a
  `review` value the step does not take;
- a step a pipeline runs with no body file (or one whose name differs from
  the id only in case), or a body file with frontmatter;
- a nested workflow the sequence uses that `disabled-workflows` turns off;
- a description over 250 characters;
- a loop bound under `params:` (`params.pipeline.max-cycles`, and every
  other `max-cycles`), set in `glados.yaml` or inherited from the preset
  table, that is not a whole number of 1 or more: `0`, a negative number,
  `true`, a quoted `"8"` or a list; or a `params:` namespace written as a
  value (`pipeline: 5`) instead of a mapping;
- a `decisions:` value other than `agent`, `record`, `escalate` or
  `forbidden` (`pipeline-discretion` included), or a `merge-authority:`
  other than `human`, `agent-integration-only` or `agent`;
- YAML that GLaDOS's parser would read differently from a YAML reader,
  named by its line: for example an anchor, tag or merge key, `: ` inside
  an unquoted value, or a line after a `when: >-` block that is indented
  less than the text but deeper than `when:` itself
  ([MIGRATION.md](../../MIGRATION.md#upgrading-a-v2-install-to-25) lists
  every case).

Warnings, which never fail:

- a pipeline that opens an MR with no verification step before it;
- a declared step that no pipeline uses;
- pipelines declared while `disabled-workflows` turns off run-pipeline;
- a top-level key GLaDOS does not read (usually a typo);
- a `params` key nothing reads (`max_cycles`, or a `run-pipeline:`
  namespace), which leaves the inherited value in force, or a retired one
  such as `params.pipeline.max-stalled-cycles`.

## Run records, SDA and Wheatley

- **One record per pipeline run,** named
  `.glados/runs/<date>-run-pipeline-<slug>.md`. It holds the step table,
  with every row `pending` before the first step runs:

  ```
  # | step | kind | modifier | review | checkpoint | status | artifact | result | note
  ```

  Statuses are `pending`, `done`, `skipped`, `waived`, `parked` and
  `failed`, written as words, not checkboxes.
- **`## Now` first.** Under its header, the record holds the step in
  progress, what it waits on and the next action, kept current; a reader
  reads that and the rows its step needs. What a check found stays in that
  check's files, and how a revision answered it in
  `<record>.<id>.revision-<n>.md`, which no reviewer's brief names. A row's
  process files are saved to the `glados/ledger` branch together when the
  row ends or parks; none of them is committed to the work's branch, so the
  MR's diff is the change. A pipeline with no branch of its own claims none
  until it parks and cuts one. The run saves them with `glados.py ledger
  save` (the clone's git exclude file keeps `.glados/runs/` out of every
  branch's commits). To read a run in another clone, `glados.py ledger
  restore <record>` copies the record and its step artifacts into
  `.glados/runs/`, and `ledger link <path>` prints a file's web link on the
  ledger, the form the MR description and escalations use. A project in a
  subdirectory of its repository keeps its records under that
  subdirectory's path on the ledger.
- **The step table is the index.** A step's own file sits beside the record
  as `<record>.<id>.md` (shape writes `<record>.shape.md`). Each check of a
  step writes files of its own, numbered by its row in the step's cycle
  table: a fresh-agent review `<record>.<id>.review-brief-<n>.md` and
  `<record>.<id>.review-<n>.md`, a gate audited here
  `<record>.<id>.audit-<n>.md`.
  Built-in stages run as nested workflows with their own records, as under
  build-feature, and their rows link them.
- **Pinned inputs.** The record holds the git blob hashes of `glados.yaml`
  and each step body used, and the digest `glados.py effective-config`
  prints of the configuration in effect: `glados.yaml` layered over the
  preset table the run reads (`.glados/presets.yaml`, or in a plugin-only
  repo the plugin's own), so a bound or decision right the manifest
  inherits is pinned too. Without Python, the run pins the preset table's
  blob hash instead. If any of them changes mid-run, the run escalates, so
  an agent cannot loosen its own gates. A resumed run takes the fresh pins
  from the branch the work targets (`effective-config --ref <target>`).
  `effective-config` refuses a configuration that leaves a bound a workflow
  uses absent, null or not a whole number of 1 or more, or that misspells a
  decision class or merge authority, and that refusal stops the run too.
- **SDA.** The
  [v2.1 profile](../standards/sda-profile-glados-v2.1.md) reports a
  pipeline's phase as the `stage` of its first row that is not done, skipped
  or waived, until its `SPEC_LOG.md` row marks it done. Step files are
  ignored by record-name parsing, and only the outermost run of a unit of
  work appends its `SPEC_LOG.md` row. See [sda.md](sda.md).
- **Wheatley.** The columns stay the six SDA phases. Showing a card's
  pipeline name, current step and an awaiting-approval badge needs
  Wheatley to read the `glados/ledger` branch, which is direction, not
  shipped. See [wheatley.md](wheatley.md).

## Keeping required steps honest

- **Step table.** Written before any work, with every row pending. A
  required row can end only as done (with its artifact) or waived (by a
  named person).
- **Pinned inputs.** A change to `glados.yaml`, a step body, or a bound or
  decision right the preset table supplies, mid-run or while the work is
  parked, escalates.
- **MR description.** The step table goes into the MR, where the team reads
  it. review-mr's panelists get the description without the step table or
  the findings it lists: a fresh reviewer is given inputs, never the
  author's conclusions, so a skipped or waived row is for people to see, not
  something the panel takes on trust.
- **Ownership.** CODEOWNERS should cover `product-knowledge/steps/` as well
  as `glados.yaml`. `glados.py doctor` reports when it does not.
- **Known gap.** Anyone can still run build-feature directly and bypass the
  project's pipelines, because build-feature stays fixed. The bypass shows:
  that MR carries no step table.

## Examples

Four generic pipelines, one per kind of work. Each one's `when:` tells the
agent when to pick it.

**`frontend-feature`**: the change stays in the web client.

`plan-feature` → `ux-flows` (optional) → `shape` (optional) →
`spec-feature` → `implement-feature` → `accessibility-check` (advisory) →
`verify-feature` → `open-mr` → `self-review`

**`backend-feature`**: the change adds or alters an endpoint, schema,
migration or background job.

`plan-feature` → `shape` → `architecture-review` → `spec-feature` →
`implement-feature` → `verify-feature` → `open-mr` → `self-review`

**`refactor`**: the goal is structural and no user-visible behavior may
change. There is no plan or spec stage: the target structure is the spec.

`target-structure` → `architecture-review` → `characterization-tests` →
`implement-feature` → `verify-feature` → `open-mr`

**`design-rfc`**: the team wants an agreed design before building. No code
and no MR: the result is the RFC, a step file beside the run record on the
ledger, approved by a person.

`plan-feature` → `shape` → `architecture-review` → `rfc`

The block declares all four. Merge it into your `glados.yaml` rather than
pasting it whole: a copy of `glados.yaml.example` already has `decisions:`,
so add the last line under it, and if you uncommented the example's
`steps:` and `pipelines:`, add these entries under those keys, keeping one
`architecture-review` step and one `backend-feature` pipeline (these).

```yaml
steps:
  ux-flows:
    description: Sketch the screens and user flows the change adds or alters
    kind: produce
    stage: planning
  accessibility-check:
    description: Check new and changed UI against our accessibility standard
    kind: gate
    stage: verifying
    audits: [implement-feature]
  architecture-review:
    description: Audit structure against our layering and dependency rules
    kind: gate
    stage: speccing
    audits: [shape, target-structure, spec-feature]
  target-structure:
    description: Describe the structure the refactor ends in, and what must not change
    kind: produce
    produces: spec
    stage: speccing
  characterization-tests:
    description: Write tests that pin current behavior before anything moves
    kind: change
    stage: implementing
  rfc:
    description: Write the design proposal for the team to approve
    kind: produce
    stage: speccing

pipelines:
  frontend-feature:
    description: A change that stays in the web client
    when: >-
      The change stays in the web client. Any new endpoint, schema,
      migration or background job rules it out.
    sequence:
      - plan-feature
      - ux-flows
      - shape
      - spec-feature
      - implement-feature
      - accessibility-check
      - verify-feature
      - open-mr
      - self-review
    step-options:
      ux-flows:
        modifier: optional
        when: The change adds a screen or alters a user flow
      shape:
        modifier: optional
        when: The change adds components or hooks shared across pages
      accessibility-check:
        modifier: advisory

  backend-feature:
    description: A change to an endpoint, schema, migration or background job
    when: >-
      The change adds or alters an endpoint, a schema, a migration or a
      background job.
    sequence:
      - plan-feature
      - shape
      - architecture-review
      - spec-feature
      - implement-feature
      - verify-feature
      - open-mr
      - self-review
    step-options:
      architecture-review:
        review: fresh-agent

  refactor:
    description: Behavior-preserving restructuring
    when: >-
      The goal is structural (move, split, rename, re-layer) and no
      user-visible behavior may change.
    sequence:
      - target-structure
      - architecture-review
      - characterization-tests
      - implement-feature
      - verify-feature
      - open-mr
    step-options:
      architecture-review:
        review: fresh-agent       # a new agent with no memory of writing it
        checkpoint: human         # a person approves the target before code moves

  design-rfc:
    description: An agreed design before anyone builds it, with no code change
    when: >-
      The team wants an agreed design before committing to build, or the
      brief asks for an RFC.
    sequence: [plan-feature, shape, architecture-review, rfc]
    step-options:
      architecture-review:
        review: fresh-agent
      rfc:
        checkpoint: human

decisions:
  pipeline-discretion: record     # every choice the agent makes is published
```

Each declared step needs its body in `product-knowledge/steps/`, for example
`product-knowledge/steps/target-structure.md`:

```markdown
## What to produce
- The module layout after the refactor: what moves where, and what is
  renamed or split.
- The public interfaces that must not change, by path.
- Behavior that must not change, stated as checks a test can make.

## Personas to seat
architect

## References
product-knowledge/standards/layering.md
```

The refactor pipeline needs no plan: `target-structure` produces the spec
that implement-feature and verify-feature need. It changes code, so the run
works on its own branch from its first step. The design-rfc pipeline never
changes code and opens no MR. Its human checkpoint on `rfc` gives it a
branch of its own and holds the run until a person approves it. The RFC
itself is saved with the record to the `glados/ledger` branch, and the
park's escalation links the approver to it (or, when a person started the
run, the question in the session does).
