# Gemini CLI

For developers who work in [Gemini CLI](https://github.com/google-gemini/gemini-cli)
— Google's open-source terminal agent — and want the GLaDOS workflows
available there as slash commands.

Not sure which runtime you have? See the [chooser](README.md).

## Prerequisites

- Python 3.10 or newer on your PATH (the installer is one stdlib-only script).
- A local checkout of the GLaDOS repository.
- Your project is a git repository (run records are committed files).
- Gemini CLI installed (`gemini` on your PATH).

## Install

From the GLaDOS checkout, give your project its configuration file, then
compile:

```bash
cd /path/to/GLaDOS
cp glados.yaml.example /path/to/your/project/glados.yaml
# open /path/to/your/project/glados.yaml and set at least:
#   platform:  gitlab | github
#   phase:     nascent | evolving | production | sunset   (required, no default)
python bin/glados.py install --mode gemini --target /path/to/your/project
```

The installer compiles the workflow text against your `glados.yaml`, runs its
consistency checks, and prints an assembly report (also written to
`.glados/assembly-report.md`) showing every resolved setting and its origin.

## What got installed

```
your-project/
├── glados.yaml                      # your config (you created this)
├── .gemini/commands/glados/         # 25 TOML custom-command files:
│   ├── build-feature.toml           #   15 workflows + 10 shims redirecting
│   ├── fix-bug.toml                 #   retired v1 names. Each file holds a
│   └── ...                          #   description plus the full compiled
│                                    #   workflow text as its prompt
├── .glados/                         # committed support folder: vendored
│   ├── glados.py                    #   installer/checker, workflow sources,
│   ├── src/  ci/  hooks/  personas/ #   CI templates, guard scripts, personas
│   ├── assembly-report.md  manifest-hash
│   └── glados.yaml.example  presets.yaml   # vendored template + phase presets
└── product-knowledge/               # project-owned knowledge skeleton
    ├── PROJECT_STATUS.md
    └── observations/ personas/ philosophies/ standards/
```

Commit all of it. Gemini CLI turns each TOML file under
`.gemini/commands/glados/` into a slash command namespaced by the directory
name, so the syntax matches Claude Code's.

## First run

Inside a `gemini` session in your project, a good read-only first run:

```
/glados:review-codebase
```

This audits the codebase and reports structure and health without changing
code — and, like every GLaDOS run, finishes by committing a run record under
`.glados/runs/`.

Every command is also headless-invocable, which is how the standing
housekeeping ceremonies get scheduled from cron or CI:

```bash
gemini -p "/glados:steward"
```

## Verify

From your project root:

```bash
python .glados/glados.py check --target .
```

Expected: `glados check: OK — no drift, checks pass, manifest hash current`.
The same check runs in CI via the templates vendored to `.glados/ci/` — the
installer prints the one-paste enable stanza for GitLab or GitHub.

## Guard hook

Gemini CLI's session-end event cannot block, but its **AfterAgent** hook can:
exiting with code 2 retries the turn, so the guard can insist the in-flight
run commits its run record before the session moves on. Wire
`.glados/hooks/gemini-afteragent-guard.py` (vendored by the install) into
`.gemini/settings.json` using the snippet in
[hooks/README.md](../../hooks/README.md). The guard stays silent unless a
run is actually in flight, so ordinary sessions are undisturbed.

## Gotcha: the TOML files are compiler output

Each `.toml` embeds the entire compiled workflow as one TOML string. Never
edit these files by hand: the installer owns `.gemini/commands/glados/` —
on the next install, hand edits are overwritten and any file the compiler
didn't plan is deleted as stale. To change behavior, edit `glados.yaml`
(most keys are read live at run time; structural keys need a re-install) or
the sources in the GLaDOS repo, then re-run the install command above.
