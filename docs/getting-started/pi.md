# pi

For developers who work in [pi](https://pi.dev), the minimal, extensible
terminal coding agent, and want the GLaDOS workflows there as slash commands.

Not sure which runtime you have? See the [chooser](README.md).

## Prerequisites

- Python 3.10 or newer on your PATH.
- A local checkout of the GLaDOS repository.
- Your project is a git repository (run records are committed files).
- pi installed (`pi` on your PATH; Node 22.19+).

## Install

```bash
cd /path/to/GLaDOS
cp glados.yaml.example /path/to/your/project/glados.yaml
# set platform: and phase: in the copy
python bin/glados.py install --mode pi --target /path/to/your/project
```

## What got installed

```
your-project/
├── glados.yaml
├── .pi/prompts/
│   ├── glados-build-feature.md   # 15 workflows + 10 shims for retired v1 names,
│   └── …                         #   as pi prompt templates
└── .glados/ …                    # same vendored state as every other mode
```

pi loads only direct `.md` children of a prompt directory, so the namespace is a
`glados-` filename prefix rather than a subdirectory. The installer only manages
`glados-*.md` there; your own prompt templates are never touched. Each template
ends with an *Invocation arguments* section, so `/glados-fix-bug "login 500s on
empty password"` passes the argument through. The installer refuses to compile
if a workflow's text would contain a pi argument placeholder (`$1`, `$@`,
`$ARGUMENTS`).

Project prompt templates load after you grant pi **project trust** for the
repo.

## Run your first command

```
pi
/glados-adopt-codebase
```

## Run-record guard and evaluator

pi has no settings-file hooks. The run-record guard (the pi equivalent of
`hooks/claude-stop-hook.py`) and the context-isolated evaluator that
`evaluator-spawn` asks for are pi extensions. Crux ships both in its
`cruxcode` pi package. Without
them, CI `verify-ledger` is still the backstop, and the agent will spawn its
evaluator however it can.
