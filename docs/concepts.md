# Concepts

GLaDOS is a library of engineering workflows for AI coding agents. You install
it into a project; it compiles a set of slash commands (such as
`/glados:build-feature`) tailored to that project's configuration. When your
agent runs one, it follows a disciplined, team-visible process — reviews get
posted, decisions get recorded, every run leaves a record on the project's
run ledger (the `glados/ledger` branch) — instead of improvising.

This page defines the vocabulary the rest of the docs use, in dependency
order. Each section is skimmable on its own; follow the links when you want
the full detail. The design rationale behind everything here lives in
[V2_STRATEGY.md](V2_STRATEGY.md).

## The workspace install and the compiler

GLaDOS is not a service or a daemon — it is markdown workflow text plus one
Python file, `bin/glados.py`, the **compiler**. "Installing" means running the
compiler against your project's configuration file: it assembles each workflow
from shared fragments, checks the result for contradictions, and writes
ready-to-run slash commands into your project for your agent runtime:

```bash
cp glados.yaml.example /path/to/your/project/glados.yaml
python bin/glados.py install --mode claude --target /path/to/your/project
```

`--mode` picks the runtime the commands are emitted for: `claude` /
`claude-plugin` (Claude Code), `direct` (plain files in the repo), `gemini`
(Gemini CLI, Google's open-source terminal agent), `antigravity` (Google
Antigravity, Google's agentic IDE — CLI `agy`; antigravity.google), `pi`
(pi, the minimal terminal coding agent — emitted as `glados-*` prompt
templates in `.pi/prompts/`), or `aistudio` (Google AI Studio,
aistudio.google.com — emitted as paste-ready bundles, since AI Studio has no
tools of its own). One compiled output feeds every mode. The source tree the
compiler assembles from is described in [src.md](src.md).

## The manifest: `glados.yaml`

The **manifest** is one YAML file at your project root — the single place your
team states policy. Its load-bearing keys:

- **`channels:`** — where results get posted. Each result type is bound to
  one or more destinations, e.g. `verdict: [mr-comment]` means review
  verdicts land as merge-request (pull-request) comments.
- **`decisions:`** — what the agent may decide alone. Each named decision
  gets one of `agent` (just do it), `record` (do it, but write a decision
  record), `escalate` (ask a human), `forbidden`. Example:
  `new-dependency: agent`, `destructive-data-op: escalate`. Any other value
  fails install, `check` and `validate`.
- **`merge-authority:`** — who may merge: `human`, `agent-integration-only`,
  or `agent`; any other value fails the same way.
- **`sda:`** — explicit-only, default `false`: opts the project into SDA
  (Structured Development Artifacts) conformance. Install scaffolds the
  artifacts (`claims.md`, the work-unit log), and every run that is not
  nested inside another then records a claim before mutating and appends
  the work-unit row when its unit of work ends; both are committed with the
  work, on its branch. A nested run, such as plan-feature inside
  build-feature, works under the outer run's claim and row; a ticket's build
  inside run-epic counts as a unit of work of its own; review-mr and
  address-review, which act on another's merge request, do neither; and a
  run that ends still waiting on a person (a parked pipeline step) keeps its
  claim and appends no row until the run that resumes it ends the unit. No
  phase preset may set it — see [guides/sda.md](guides/sda.md).
- **`pipelines:` and `steps:`** — explicit-only, optional: the project's
  own workflows, ordered lists of GLaDOS's steps and steps the project
  writes, run by the `run-pipeline` workflow. See
  [guides/pipelines.md](guides/pipelines.md).
- **`canon:`** — explicit-only, optional: the reference works the team
  holds as authoritative (a book, a paper, a post), each with a digest the
  team writes in `product-knowledge/canon/`. Planning, speccing,
  verification and review read the digests and cite principles as
  `canon:<name>#<principle-id>`; a departure is advisory unless a standard
  adopts the principle. See [guides/canon.md](guides/canon.md).

Workflow text never states any of these; it reads the keys at run time. Two
workflows therefore cannot contradict each other about who merges — the
sentence that could contradict does not exist. Start from the commented
template, [glados.yaml.example](../glados.yaml.example).

The toolchain reads the manifest with its own YAML subset, and refuses,
naming the line, any YAML it would not read the way the agent does: an
anchor, an alias, a tag or a merge key, for example.

## Phase

**`phase:`** is a required manifest key — one word, no default — declaring
honestly who gets hurt when the agent is wrong:

| Phase | Users | A bad merge costs |
|---|---|---|
| `nascent` | The builders themselves | An hour of your own time |
| `evolving` | Early adopters who opted in | A design partner's afternoon |
| `production` | People who don't forgive | An incident, maybe churn |
| `sunset` | People who depend on current behavior | Harm on the way out |

The phase expands into defaults for other manifest keys (precedence:
baseline < phase preset < your explicit keys), so `nascent` runs loose and
`production` runs strict without you tuning twenty knobs. Two hard rules: a
phase may never reduce visibility (you can be fast, not invisible), and only
a human-merged change to `glados.yaml` can change it. Full design:
[V2_STRATEGY.md, decision 8](V2_STRATEGY.md).

## The run ledger

Every workflow run writes one markdown **run record** — what was attempted,
what was decided, how it ended — into `.glados/runs/`, beside its step
artifacts. Example: `.glados/runs/2026-07-03-fix-bug-login-timeout.md`. The
run saves them to the repo's `glados/ledger` branch (`glados.py ledger save`),
never to the work's branch: a merge request's diff is the change, and the
ledger carries the trail. That branch is the run ledger: a fresh session, a
teammate, or a CI job resumes an epic or audits a decision from it alone
(`glados.py ledger restore`), with no access to anyone's chat transcript.
Each run starts by copying the ledger's records in (`ledger restore`), and
links a record by its ledger copy (`glados.py ledger link`). What a run
writes outside `.glados/runs/` (pending observations and, with `sda: true`,
the claim and the work-unit row) is committed with the work, on its branch.

Install, migrate, `ledger save` and `ledger restore` add `/.glados/runs/*`
to the clone's git exclude file, which keeps records out of every branch's
commits; a plugin-only repo, which never installs, gets the line from the
`ledger restore` its first run starts with. A project in a subdirectory of
its repository (a monorepo package) keeps its own `.glados/runs/`: its
exclude line is `/<dir>/.glados/runs/*`, and its records go on the ledger
under `<dir>/.glados/runs/`, so two projects in one repository never share
a path.

On enforcement: at run start the workflow writes in-flight marker files
(never committed). `.glados/runs/current` names the run in flight and
`.glados/runs/stack` lists every run in flight, because runs nest:
build-feature runs plan-feature inside itself, and the inner run must not
erase the outer run's marker. The epilogue pops its own entry when the record
is finalized. Small guard scripts vendored into `.glados/hooks/` block the
agent session from ending while any run on the stack, the current one or
any run enclosing it, has a record or step artifact not saved to the
ledger as it is on disk (a directory where a record should be, or a link
to a directory or to nothing, counts as no record), or while a marker, or `.glados/runs/` itself, exists
but cannot be read. A CI check (`glados.py verify-ledger`) is the backstop
on runtimes without hooks — wiring recipes in
[hooks/README.md](../hooks/README.md).

## Cores, modules, and vocabulary

A **workflow core** is the short instruction file for one workflow's
distinctive work — there are 16, e.g. `review-mr`, `fix-bug` (catalog:
[workflows.md](workflows.md)). A **module** is an optional add-on the
manifest switches on per workflow — there are three: `mr-review-panel`,
`evaluator-spawn`, `standards-gate` ([modules.md](modules.md)). **Vocabulary**
files are shared rule text that exists exactly once in `src/vocabulary/` and
is stamped into every workflow that uses it at install time. Example: the
verdict words `APPROVE | REQUEST_CHANGES | ESCALATE` are defined in one file,
so no two workflows can drift into different severity scales — the previous
version of GLaDOS had six verdict vocabularies, and that is why constants
exist once.

## The three lanes

The lanes answer one practical question: what needs a reinstall, and what
changes instantly?

- **Lane 1 — compiled.** Structure: which modules a workflow includes, the
  mandatory run-record ending, the verdict words. Changing these means
  editing the manifest and rerunning `install` — deliberately a small
  ceremony, because the compiler re-checks everything and prints what changed.
- **Lane 2 — live-read.** Policy values: `channels`, `merge-authority`,
  `decisions`, panel roster, loop bounds. Compiled text tells the agent to
  read these from `glados.yaml` at run time, so a two-line edit changes
  behavior on the very next run. Example: rerouting bug reports from issues
  to MR comments is a lane-2 edit — no reinstall.
- **Lane 3 — referenced on demand.** Bulky optional files: personas,
  standards documents, canon digests. Drop a file in the right directory, name it in the
  manifest, and the next run picks it up.

**Project workflows are lane 2 by design, a deliberate exception.** The v2
rule is that anything an agent must not skip is compiled. A project's own
workflows (`pipelines:` and `steps:` in the manifest, with step bodies in
`product-knowledge/steps/`) are read live by the `run-pipeline` core
instead, because the Claude Code plugin is compiled once from GLaDOS's own
template and could never compile them. What keeps a skipped step visible is
compiled into `run-pipeline`: the step table written before any step runs,
the pinned hashes of `glados.yaml`, the step bodies and the configuration
they resolve to with the presets (`glados.py effective-config`), the
bounded revise loops, and the step table in the MR. The compiler checks
both blocks at install, at `check`, and in `glados.py validate`. Only each
pipeline's name and description are structural, because they name a
shortcut command. See
[guides/pipelines.md](guides/pipelines.md).

**Canon is lane 2 too, with lane-3 digests.** The `canon:` block is read
live at each consult point, and the digests it names are files the agent
reads on demand, never fetched from the web during a run. What is compiled is
only how to consult them: read the digest, route it to its seats, weigh it
below the project's own decisions, standards and philosophies. The compiler
checks the block wherever it runs, and nothing from it or a digest enters a
compiled file. See [guides/canon.md](guides/canon.md).

Only the structural keys feed the manifest hash stamped into compiled output:
`phase`, `optimize-for`, `default-modules`, `workflows`, `disabled-workflows`,
`sda`, and the names and descriptions of `pipelines:`. `glados.py check`
reports a stale compile when one of them changed after the last install,
i.e. when a recompile is due; a lane-2 edit (a pipeline's sequence or step
options, or the `canon:` block, included) never makes the compile stale, and
comments or reformatting change nothing.
`check` still type-checks every value, lane 2 included, so a lane-2 edit
fails it only when the new value is itself invalid: an undeclared sink, a
relaxation nobody confessed, a misspelt decision class or merge authority,
a loop bound (`params.<name>.max-cycles`) that is not a whole number of 1
or more. A bound that reaches a run as no such number never starts its
loop: the workflow escalates, naming the key. `python
bin/glados.py doctor --target /path/to/your/project` reports the same, and
also notes when the vendored assembly report predates later edits. When the
report is the only thing that differs, the note is informational: the report
records the last install, and an older report makes nothing stale. When the
installed files differ too (a newer GLaDOS checkout, for example), doctor
says so and tells you to re-run install.

When a key the agent resolves from `glados.yaml` is absent, its default comes
from the preset table vendored at `.glados/presets.yaml` (in a plugin-only
repo, the plugin's own `src/kernel/presets/phases.yaml`): `baseline`, then
the preset for your `phase:`, then your explicit keys. `glados.py
effective-config` prints a digest of that resolved configuration;
run-pipeline pins it at the start of a run and re-checks it before each
step and on resume, so a bound or decision right the table supplies cannot
change under a run without an escalation. `effective-config` prints no
digest, and the run stops, when the table leaves a bound a workflow uses
absent, null or not a whole number of 1 or more, or misspells a decision
class or merge authority.

## Outcome types and sinks

Workflows end by emitting typed results — six **outcome types**: `progress`,
`verdict`, `escalation`, `bug`, `decision`, `observation` — and never name a
destination themselves. The manifest's `channels:` block binds each type to
**sinks**. Five sinks are built in — `mr-comment`, `issue`, `issue-comment`,
`label`, and `ledger` (the run record on the ledger branch only) — and a project can **declare its
own** under a `sinks:` block (e.g. `slack`). Example: with `escalation:
[issue]`, a workflow that hits its retry limit files an issue a human will
actually see.

The sink *name* set is open, but two guarantees keep an outcome from silently
disappearing. **At install:** every sink named in `channels:` must be built-in
or declared in `sinks:` (a typo like `[slak]` fails the install), and every
emitted outcome type must reach at least one team-visible sink or be confessed
(`visibility-acknowledged`) — never defaulted into. **At run time:** delivery
is verified — an outcome that reaches no team-visible sink escalates instead of
vanishing. The one exception is an outcome bound to `mr-comment` before any MR
exists: it is recorded under `## Pending MR delivery` and posted by the run
that opens the MR (or marked not applicable if none ever opens), which is not
a failed delivery. A declared sink must state its visibility,
`team-visible: true` or `team-visible: false` (a record-only sink); without
it the install fails. Everything else *inside* a sink declaration —
`channel:`, `format:`, `grouping:`, `threads:` — is freeform config the agent
interprets at run time for that sink's medium; the compiler never parses it.
Whatever a sink's config says, everything a run posts on a merge request
starts with `(GLaDOS <workflow>)`: that marker is how review-mr and
address-review tell GLaDOS's notes from a person's review. See
[guides/sinks.md](guides/sinks.md).

## The state registry

Every piece of state that workflows share — a reviewed commit SHA, an epic's
ticket table, the pending-observations pile — is a flat named key in
[src/kernel/state-registry.yaml](../src/kernel/state-registry.yaml), and each
core and module declares which keys it `reads:` and `writes:`. At install
time the compiler refuses any configuration where something is read that
nothing writes. Example: `address-review` reads `review.verdicts`, which only
`review-mr` writes — a manifest that disables `review-mr` but keeps
`address-review` fails the install with a named error, instead of
`address-review` silently finding nothing at run time.

## Personas and the panel

A **persona** is a markdown file giving a reviewer viewpoint — the shipped
library includes `security-engineer`, `test-engineer`, `ux-advocate`,
`architect`, and others, vendored into `.glados/personas/` by every install.
Review workflows seat a **panel**: several personas, each run as a fresh
subagent with no memory of writing the code, each returning its own verdict.
The tally rule is compiled in: any blocking finding means `REQUEST_CHANGES`,
and a missing panelist verdict means `ESCALATE` — never approval. Add your
own persona by dropping a file in `product-knowledge/personas/` and naming it
in the manifest; the next panel seats it, no reinstall (lane 3). Details:
[personas.md](personas.md).

## People's words and fresh reviewers

A **fresh reviewer** (a panelist, the evaluator, a fresh-agent design
review in a pipeline) is only as independent as its brief, and the agent
that did the work writes the brief. So the brief carries inputs, never the
author's conclusions: no earlier verdict, approval or gate result, no
disposition the author gave a finding. Everything the author wrote (plan,
shape, spec, the MR description) is labelled as the author's and is under
review like the code, and a scope statement excuses an absence, never what
the change adds.

A **person's words** (the ticket, an instruction in the session, a note on
the merge request) are quoted verbatim with where they were said, and bind
only as firmly as they were said. Each clause takes a tag: a **Directive**
("must", "never", a plain statement of what is wanted) binds; a
**Preference** ("should", "I'd like") sets a default that evidence may
override; a **Hunch** ("I think", "maybe", a stated cause) is a belief the
work tests against the code; **Assent** ("seems fine", choosing a
question's reading) approves the direction shown, not its mechanism. Where
the code suggests the words miss what the person wants, the work says so in
the open: "your words say X (tag); the code shows Y; I propose Z".

In a `run-pipeline` run, a **question for a person** is raised where
readings differ materially (an outcome someone named is met under one
reading and not another, or one needs an `escalate` choice), in a fixed
form: the decision, a scenario through today's code, the readings with
their cost, risk and reversibility, the finder's recommendation, and the
door. Only a person answers a **one-way door**, which parks the step; a
**two-way door** goes ahead on its default, for the person to confirm or
overturn. A question never replaces a finding.

On a merge request, everything GLaDOS posts starts with
`(GLaDOS <workflow>)`. review-mr and address-review read any other note
from someone with a role on the project, who did not write the change, as
that person's review: each point is a finding labelled as theirs, open
until the change meets it or the author answers it on the MR in the open,
and a blocking one closes only when the change meets it or that person
withdraws or waives it. The rules live in `src/vocabulary/`
(`review-inputs.md`, `person-words.md`, `questions.md`, `mr-notes.md`).
