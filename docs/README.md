# GLaDOS Documentation

GLaDOS is a library of engineering workflows for AI coding agents. You
install it into a project workspace, and it compiles a set of slash
commands (for example `/glados:build-feature`) tailored to that project's
configuration. When your agent runs one, it follows a disciplined,
team-visible process — reviews get posted, decisions get recorded, and
every run leaves a committed record — instead of improvising.

The pages below are ordered from most to least accessible. Start at the
top; each layer assumes you have read the ones above it, never the ones
below. If you landed here without any context, the
[project README](../README.md) is the front door.

## Start here

- [getting-started/](getting-started/) — pick your agent runtime — Claude
  Code, Gemini CLI (Google's open-source terminal agent), Google
  Antigravity (Google's agentic IDE; CLI `agy`; antigravity.google), or
  Google AI Studio (aistudio.google.com) — and install GLaDOS into a
  project. No prior GLaDOS knowledge needed.

## Learn by example

- [examples/](examples/) — end-to-end walkthroughs of real workflow runs
  (your first feature, fixing a bug, the weekly ceremonies): the commands
  you type and the artifacts they leave behind.

## How-to guides

- [guides/](guides/) — platform recipes for running GLaDOS on GitHub or
  GitLab: where reviews get posted, how the CI check is enabled, and how
  merge/pull requests flow.
- [../PLAYBOOK.md](../PLAYBOOK.md) — the team-adoption playbook: rolling
  GLaDOS out across a team, week by week.

## Concepts

- [concepts.md](concepts.md) — the vocabulary, defined in plain words:
  what a workflow core, a module, the manifest (`glados.yaml`), a run
  record, and a channel are, and how the compiler assembles them into
  installed commands. Read this before any reference page.

## Reference

Deep-end pages. Each assumes the [concepts](concepts.md) vocabulary
after its opening paragraph.

- [workflows.md](workflows.md) — every workflow GLaDOS ships: what it
  does, what it may change, and what it reports.
- [modules.md](modules.md) — the optional behaviors compiled into
  workflows per project configuration.
- [personas.md](personas.md) — the reviewer viewpoints seated on review
  panels, and how to add your own.
- [src.md](src.md) — map of the source tree the compiler assembles into
  installed workflow text.
- [overlays.md](overlays.md) — v1's customization mechanism, now
  retired, and what replaced it in v2.
- [standards/](standards/) — the SDA (Structured Development Artifacts)
  Standard v1.0 and the GLaDOS Profiles: v2.0 (how a v2 install conforms —
  the current mapping, enabled by `sda: true`) and v1.0 (historical).
- [V2_STRATEGY.md](V2_STRATEGY.md) — design rationale for v2: the audit
  evidence and the nine load-bearing decisions. The deep end.
- [../MIGRATION.md](../MIGRATION.md) — for v1 users: the guided migration
  path — `glados.py migrate` does the mechanical work; the guide covers
  the one decision it leaves to you and what changed conceptually.
