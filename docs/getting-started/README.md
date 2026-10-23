# Getting started — which runtime am I?

GLaDOS is a library of engineering workflows for AI coding agents. You install
it into a project, and it compiles a set of slash commands (for example
`/glados:build-feature`) tailored to that project's configuration. When your
agent runs one, it follows a disciplined, team-visible process — reviews get
posted, decisions get recorded, every run leaves a record on the repo's
`glados/ledger` branch — instead of improvising.

The installer is one Python script, `bin/glados.py`, with seven install modes.
Which mode you want depends entirely on **which tool your AI agent runs in**.
Pick your row:

| You work in… | Mode | Page |
|---|---|---|
| Claude Code (Anthropic's terminal agent), and you want the commands checked into this one repo | `claude` | [claude-code.md](claude-code.md) |
| Claude Code, and your team distributes GLaDOS as a Claude Code **plugin** shared across repos | `claude-plugin` | [claude-plugin.md](claude-plugin.md) |
| [Google Antigravity](https://antigravity.google) (Google's agentic IDE; CLI `agy`) | `antigravity` | [google-antigravity.md](google-antigravity.md) |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) (Google's open-source terminal agent) | `gemini` | [gemini-cli.md](gemini-cli.md) |
| [pi](https://pi.dev) (terminal coding agent) | `pi` | [pi.md](pi.md) |
| [Google AI Studio](https://aistudio.google.com) (browser chat, no file access) | `aistudio` | [google-ai-studio.md](google-ai-studio.md) |
| Some other agent, or no agent-specific command surface at all | `direct` | [direct.md](direct.md) |
| A repo with an existing **GLaDOS v1** install (any runtime) | run `migrate` first — it suggests your mode | [MIGRATION.md](../../MIGRATION.md) |

Not sure? If you type prompts into a terminal tool made by Anthropic, that's
Claude Code — start with [claude-code.md](claude-code.md). If you type prompts
into a browser page at aistudio.google.com, that's Google AI Studio.

## What every mode shares

Whatever mode you pick, three things end up in your project:

- **`glados.yaml`** — the one configuration file, copied from
  [`glados.yaml.example`](../../glados.yaml.example) and edited by you. It
  declares your git platform (GitLab or GitHub), the project's `phase:`
  (roughly: who gets hurt if the agent is wrong), and where each kind of
  outcome — review verdicts, escalations, bugs — must be posted so the team
  sees it.
- **`.glados/`** — a committed support folder the installer fills: a vendored
  copy of the installer itself (so CI can re-check the install without
  cloning GLaDOS), CI check templates, hook guard scripts, and a reviewer
  persona library. Runs write their records here too, under `.glados/runs/`,
  but never commit them: install adds `/.glados/runs/*` to the clone's git
  exclude file, and each run saves its records to the `glados/ledger` branch
  instead.
- **The compiled workflow text** — in whatever shape your runtime consumes
  (Markdown slash commands, TOML commands, or paste bundles). This is
  generated output: you change behavior by editing `glados.yaml` and
  re-running the installer, never by editing the compiled files.

## What a "run" leaves behind

Every workflow ends by writing a **run record** — a short Markdown file in
`.glados/runs/`, saved to the repo's `glados/ledger` branch rather than the
work's, saying what was attempted, what was decided, and how
it ended. Guard hooks (per runtime) and a CI job exist purely to make that
promise mechanical; each runtime page covers its own setup.

Every run starts by copying the ledger's records into `.glados/runs/`
(`python .glados/glados.py ledger restore`; a plugin-only repo has no
`.glados/glados.py` and runs the plugin's own `bin/glados.py`, as
[claude-plugin.md](claude-plugin.md) says); run it yourself to read what a
teammate's runs saved. If a session ended mid-run and the guard keeps
blocking, release the abandoned run by deleting both `.glados/runs/current`
and `.glados/runs/stack`.

Your project can also be a subdirectory of its repository, such as a package
in a monorepo. Install with `--target` set to that directory and run your
agent there. Its records keep that path on the ledger
(`packages/app/.glados/runs/…`), so two projects in one repository keep
separate records, and the guard hooks read the `.glados/runs/` of the
directory the agent runs in.

CI enforcement is supported only for a project at the repository root. The
vendored CI templates run `.glados/glados.py` from the repository's root,
and GitHub reads workflows only from the root's `.github/workflows/`, so for
a project in a subdirectory the installer prints no enable stanza, and
`python .glados/glados.py doctor --target .` reports `CI check wired: not
supported`. Such a project keeps the guard hooks and can run
`python .glados/glados.py check --target .` itself, but has no CI check.

## Installing more than one mode

Modes coexist. Running the installer twice with different `--mode` values
against the same target is fine — each mode owns its own output directory and
cleans only its own files. A team split between Claude Code and Google
Antigravity installs both.

## After you're set up

- [PLAYBOOK.md](../../PLAYBOOK.md) — how to actually work with the workflows,
  day to day.
- [MIGRATION.md](../../MIGRATION.md) — coming from GLaDOS v1: the guided
  `migrate` command and the steps around it.
- [docs/workflows.md](../workflows.md) — what each of the 16 workflows does.
