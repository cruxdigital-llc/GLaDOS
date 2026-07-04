# GLaDOS

**G**enerative **L**ogic **a**nd **D**ocumentation **O**perating **S**ystem — yes, [that GLaDOS](https://en.wikipedia.org/wiki/GLaDOS). Unlike her namesake, this one writes everything down and lets you leave the testing chamber.

GLaDOS is a library of engineering workflows for AI coding agents — Claude
Code, Gemini CLI (Google's open-source terminal agent), Google Antigravity
(Google's agentic IDE; CLI `agy`; antigravity.google), and others. You
install it *into* a project: a small
compiler reads one configuration file in your repo (`glados.yaml`) and
generates a set of slash commands — `/glados:build-feature`,
`/glados:fix-bug`, `/glados:review-mr` — tailored to that project. When your
agent runs one, it follows a disciplined, team-visible process instead of
improvising: reviews get posted where the team can see them, decisions get
written down with their reasons, and every run leaves a committed record in
your repo.

What you get:

- **Ready-made workflows for the whole development loop** — plan, spec,
  implement, verify, review, bug-fix, epic runs, weekly cleanup — installed as
  slash commands your agent already knows how to invoke.
- **Nothing important lives only in a chat transcript.** Review verdicts land
  as merge-request comments (a merge request, or MR, is GitLab's name for a
  pull request), problems become issues, and every run writes a record file
  into `.glados/runs/` that is committed alongside the work.
- **One config file controls behavior.** `glados.yaml` declares who may merge,
  which decisions the agent may make on its own, and where each kind of result
  gets posted. The installer refuses any configuration under which a result
  would silently disappear.

## 60-second quickstart

From a clone of this repository:

```bash
cp glados.yaml.example /path/to/your/project/glados.yaml
```

Open the copy and set two keys. `platform:` is `gitlab` or `github`. `phase:`
is a one-word honest answer to "who gets hurt if the agent gets something
wrong?" — `nascent` (nobody; no users yet), `evolving` (early adopters),
`production` (real users), or `sunset` (winding down) — describe reality, not
ambition, because the word tunes how much caution gets compiled in.

Then install for your agent's runtime (here: Claude Code):

```bash
python bin/glados.py install --mode claude --target /path/to/your/project
# modes: claude | claude-plugin | direct | gemini | antigravity | aistudio
```

The installer prints an **assembly report** — every configuration value it
resolved and where it came from — and writes the commands into your project.
Now open your agent inside the project and run your first command:

```
/glados:adopt-codebase
```

The agent studies your codebase, writes what it learns (structure,
conventions, candidate coding standards) into `product-knowledge/`, and leaves
a record of the run in `.glados/runs/` — ordinary files you review and commit
like any other change.

## What a run looks like

Say a user reports a crash and you run `/glados:fix-bug`. The agent does not
jump straight to editing code: it first reproduces the bug and writes down
how; it fixes the root cause rather than the symptom; then a second, fresh
agent session — one that never saw the fix being written — independently
verifies it. What you end up with is a merge request with the review verdict
posted as a comment on it, plus a committed record in `.glados/runs/` saying
what was decided and why. Six months later, `git log` still knows the whole
story.

`fix-bug` is one of fifteen commands. The everyday ones are `build-feature`
(one feature from plan to a verified merge request in one sitting),
`review-mr` and `address-review` (the review loop), and `run-epic` (a whole
ticket queue). The full list, with what each does, is in
[docs/workflows.md](docs/workflows.md).

## Where things land in your repo

Everything is installed into your project workspace and committed to git:

```
your-project/
├── glados.yaml                  # the one config file you own and edit
├── .claude/commands/glados/     # the compiled slash commands (this dir is
│                                #   per-runtime — see the table below)
├── .glados/                     # GLaDOS working state, committed to git
│   ├── runs/                    # one record file per run (created on first run)
│   ├── assembly-report.md       # what the installer resolved, and from where
│   ├── personas/                # reviewer viewpoints: security, architecture, QA…
│   ├── ci/                      # optional CI job that catches config drift
│   └── src/                     # copies of the sources, so installs are reproducible
└── product-knowledge/           # your project's written knowledge
    ├── standards/               # rules the agent's work is checked against
    ├── philosophies/            # high-level principles
    ├── personas/                # your own reviewer viewpoints (override shipped ones)
    └── observations/            # recurring patterns noticed, awaiting promotion
```

The compiled command files are generated output — never edit them by hand.
Edit `glados.yaml` and re-run the install; a hand-edit is silently overwritten
by the next install.

## Supported runtimes

One compiled output feeds every mode, so behavior matches across runtimes.

| Runtime | `--mode` | What gets installed |
|---|---|---|
| Claude Code (Anthropic's terminal coding agent) | `claude` | Slash commands in `.claude/commands/glados/` — run `/glados:fix-bug` |
| Claude Code, packaged as a plugin | `claude-plugin` | A plugin build in `compiled/claude-plugin/` |
| Gemini CLI (Google's open-source terminal agent) | `gemini` | Commands in `.gemini/commands/glados/` — run `/glados:fix-bug` |
| Google Antigravity (Google's agentic IDE; CLI `agy`; antigravity.google) | `antigravity` | Workflow files in `.agents/workflows/` — run `/glados-fix-bug` |
| Google AI Studio (aistudio.google.com) | `aistudio` | Paste-in bundles in `glados/adapters/aistudio/bundles/` — no command surface; you paste a bundle into the chat |
| Any agent that can read a markdown file | `direct` | Plain workflow documents in `product-knowledge/glados/` |

## The weekly rhythm

Two commands are standing weekly jobs rather than things you run when you
think of them:

- **`/glados:steward`** (typically Saturday) — housekeeping. It condenses old
  run records into a short digest, refreshes stale docs, reviews the
  accumulated observations and promotes the real patterns into written
  standards, and sanity-checks the tests. Ships as one small cleanup merge
  request.
- **`/glados:brunch`** (typically Sunday) — a critique roundtable. Several
  reviewer personas examine the codebase in parallel (after actually running
  the project first), a moderator ranks the findings by impact against
  effort, and the top finding ships as one small fix merge request.

GLaDOS deliberately ships no scheduler. Every command can run
non-interactively, so use whatever your project already has: a cron job (e.g.
`gemini -p "/glados:brunch"` for Gemini CLI), a scheduled CI pipeline, or your
agent's own scheduled-task feature.

## What GLaDOS does and doesn't do

GLaDOS defines the process: what must be recorded, what words a verdict may
use, and where each kind of result must be visible to the team. It does
**not** talk to GitLab or GitHub itself. Your project declares its platform in
`glados.yaml`, and your agent uses its own tools — the `glab` or `gh` CLI, MCP
servers, whatever its runtime provides — to actually post comments and open
issues. GLaDOS ships CI job templates your project can enable, and
`python bin/glados.py doctor --target /path/to/your/project` reports anything
declared in the config but not actually wired up. On runtimes where the agent
cannot run commands at all (Google AI Studio), it degrades honestly: the agent
prints the exact commands and file contents, and you execute them.

## Learn more

In increasing depth:

1. **[docs/getting-started/](docs/getting-started/)** — a full install
   walkthrough and your first week.
2. **[docs/examples/](docs/examples/)** — worked, end-to-end examples of real
   runs.
3. **[docs/guides/](docs/guides/)** — task-oriented guides, including SDA
   conformance (`sda: true` in `glados.yaml` — claims + work-unit log
   maintained by every run) and the Wheatley board; see also
   [PLAYBOOK.md](PLAYBOOK.md) for adopting GLaDOS across a team.
4. **[docs/concepts.md](docs/concepts.md)** — how the compiler, the config
   file, and the run records actually work.
5. **Reference** — [docs/workflows.md](docs/workflows.md) (all fifteen
   commands and the v1→v2 name map), [docs/modules.md](docs/modules.md),
   [docs/personas.md](docs/personas.md), [docs/src.md](docs/src.md), and
   [docs/V2_STRATEGY.md](docs/V2_STRATEGY.md) (design rationale — the deep
   end).

Upgrading from GLaDOS v1? Every old command name keeps working as an alias;
[MIGRATION.md](MIGRATION.md) has the full map.
