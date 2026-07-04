# Concepts

GLaDOS is a library of engineering workflows for AI coding agents. You install
it into a project; it compiles a set of slash commands (such as
`/glados:build-feature`) tailored to that project's configuration. When your
agent runs one, it follows a disciplined, team-visible process — reviews get
posted, decisions get recorded, every run leaves a committed record — instead
of improvising.

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
Antigravity, Google's agentic IDE — CLI `agy`; antigravity.google), or
`aistudio` (Google AI Studio, aistudio.google.com — emitted as paste-ready
bundles, since AI Studio has no tools of its own). One compiled output feeds
every mode. The source tree the compiler assembles from is described in
[src.md](src.md).

## The manifest: `glados.yaml`

The **manifest** is one YAML file at your project root — the single place your
team states policy. Its load-bearing keys:

- **`channels:`** — where results get posted. Each result type is bound to
  one or more destinations, e.g. `verdict: [mr-comment]` means review
  verdicts land as merge-request (pull-request) comments.
- **`decisions:`** — what the agent may decide alone. Each named decision
  gets one of `agent` (just do it), `record` (do it, but write a decision
  record), `escalate` (ask a human), `forbidden`. Example:
  `new-dependency: agent`, `destructive-data-op: escalate`.
- **`merge-authority:`** — who may merge: `human`, `agent-integration-only`,
  or `agent`.

Workflow text never states any of these; it reads the keys at run time. Two
workflows therefore cannot contradict each other about who merges — the
sentence that could contradict does not exist. Start from the commented
template, [glados.yaml.example](../glados.yaml.example).

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
what was decided, how it ended — into `.glados/runs/` and commits it. Example:
`.glados/runs/2026-07-03-fix-bug-login-timeout.md`. That is the run ledger: a
fresh session, a teammate, or a CI job resumes an epic or audits a decision
from `git pull` alone, with no access to anyone's chat transcript.

Two sentences on enforcement: at run start the workflow writes an in-flight
marker file, `.glados/runs/current` (never committed), and deletes it when the
record is finalized. Small guard scripts vendored into `.glados/hooks/` block
the agent session from ending while that marker exists without a committed
record, and a CI check (`glados.py verify-ledger`) is the backstop on runtimes
without hooks — wiring recipes in [hooks/README.md](../hooks/README.md).

## Cores, modules, and vocabulary

A **workflow core** is the short instruction file for one workflow's
distinctive work — there are 15, e.g. `review-mr`, `fix-bug` (catalog:
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
  standards documents. Drop a file in the right directory, name it in the
  manifest, and the next run picks it up.

`python bin/glados.py doctor --target /path/to/your/project` reports when a
lane-1 (structural) key changed after the last install, i.e. when a recompile
is due.

## Outcome types and sinks

Workflows end by emitting typed results — six **outcome types**: `progress`,
`verdict`, `escalation`, `bug`, `decision`, `observation` — and never name a
destination themselves. The manifest's `channels:` block binds each type to
**sinks**: `mr-comment`, `issue`, `issue-comment`, `label`, or `ledger` (the
run record only). Example: with `escalation: [issue]`, a workflow that hits
its retry limit files an issue a human will actually see. An outcome type
that an enabled workflow emits but no team-visible sink receives is an
install error — silence has to be confessed explicitly in the manifest
(`visibility-acknowledged`), never defaulted into.

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
