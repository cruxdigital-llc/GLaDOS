# Getting started — which runtime am I?

GLaDOS is a library of engineering workflows for AI coding agents. You install
it into a project, and it compiles a set of slash commands (for example
`/glados:build-feature`) tailored to that project's configuration. When your
agent runs one, it follows a disciplined, team-visible process — reviews get
posted, decisions get recorded, every run leaves a committed record — instead
of improvising.

The installer is one Python script, `bin/glados.py`, with six install modes.
Which mode you want depends entirely on **which tool your AI agent runs in**.
Pick your row:

| You work in… | Mode | Page |
|---|---|---|
| Claude Code (Anthropic's terminal agent), and you want the commands checked into this one repo | `claude` | [claude-code.md](claude-code.md) |
| Claude Code, and your team distributes GLaDOS as a Claude Code **plugin** shared across repos | `claude-plugin` | [claude-plugin.md](claude-plugin.md) |
| [Google Antigravity](https://antigravity.google) (Google's agentic IDE; CLI `agy`) | `antigravity` | [google-antigravity.md](google-antigravity.md) |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) (Google's open-source terminal agent) | `gemini` | [gemini-cli.md](gemini-cli.md) |
| [Google AI Studio](https://aistudio.google.com) (browser chat, no file access) | `aistudio` | [google-ai-studio.md](google-ai-studio.md) |
| Some other agent, or no agent-specific command surface at all | `direct` | [direct.md](direct.md) |

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
  persona library. Runs also write their records here, under `.glados/runs/`.
- **The compiled workflow text** — in whatever shape your runtime consumes
  (Markdown slash commands, TOML commands, or paste bundles). This is
  generated output: you change behavior by editing `glados.yaml` and
  re-running the installer, never by editing the compiled files.

## What a "run" leaves behind

Every workflow ends by writing a **run record** — a short committed Markdown
file in `.glados/runs/` saying what was attempted, what was decided, and how
it ended. Guard hooks (per runtime) and a CI job exist purely to make that
promise mechanical; each runtime page covers its own setup.

## Installing more than one mode

Modes coexist. Running the installer twice with different `--mode` values
against the same target is fine — each mode owns its own output directory and
cleans only its own files. A team split between Claude Code and Google
Antigravity installs both.

## After you're set up

- [PLAYBOOK.md](../../PLAYBOOK.md) — how to actually work with the workflows,
  day to day.
- [MIGRATION.md](../../MIGRATION.md) — coming from GLaDOS v1.
- [docs/workflows.md](../workflows.md) — what each of the 15 workflows does.
