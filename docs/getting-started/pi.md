# pi

For developers who work in [pi](https://pi.dev), the minimal, extensible
terminal coding agent, and want the GLaDOS workflows there as slash commands.

Not sure which runtime you have? See the [chooser](README.md).

## Prerequisites

- Python 3.10 or newer on your PATH.
  Where only `python3` is on the PATH (macOS, and Debian or Ubuntu without
  `python-is-python3`), write `python3` wherever this page says `python`.
- A local checkout of the GLaDOS repository.
- Your project is in a git repository, at its top level or in a subdirectory
  such as a monorepo package (CI enforcement is supported only at the top
  level; [details](README.md#what-a-run-leaves-behind)),
  and its clone can push a `glados/ledger` branch to `origin`: every run
  commits its record to that branch (`ledger save`) and pushes it. A
  branch-protection rule that covers `glados/ledger` refuses the push, and the
  records then stay in that one clone.
- pi installed (`pi` on your PATH; Node 22.19+).

## Install

```bash
cd /path/to/GLaDOS
cp glados.yaml.example /path/to/your/project/glados.yaml
# set platform: and phase: in the copy
python bin/glados.py install --mode pi --target /path/to/your/project
```

For `production` or `sunset`, delete the copy's `decisions:` block and the
`relaxation-acknowledged: [delete-code]` line after it before you install.
Both are written for `evolving`: install refuses each decision laxer than
the phase's preset, and a confession left behind is restated in every
assembly report. With both gone, the phase's preset governs. For `sunset`,
delete `disabled-workflows: []` as well: it would re-enable `build-feature`
and `run-pipeline`, which that phase turns off. Under `nascent` both may
stay: where the block is stricter than nascent's preset
(`schema-migration: record`, where nascent has `agent`) its value applies,
and the confession relaxes nothing. Delete both to take nascent's own.

## What got installed

```
your-project/
├── glados.yaml
├── .pi/prompts/
│   ├── glados-build-feature.md   # 16 workflows + 10 shims for retired v1 names
│   └── …                         #   (+ one per declared pipeline), as pi
│                                 #   prompt templates
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

## Verify

From your project root:

```bash
python .glados/glados.py check --target .
```

Expected: `glados check: OK — no drift, checks pass, manifest hash current`.
The same check, and the `verify-ledger` run-record backstop, run in CI via the
templates vendored to `.glados/ci/`. The installer prints the one-paste enable
stanza for GitLab or GitHub.

## Run-record guard and evaluator

pi has no settings-file hooks. The run-record guard (the pi equivalent of
`hooks/claude-stop-hook.py`) and the context-isolated evaluator that
`evaluator-spawn` asks for are pi extensions. Crux ships both in its
`cruxcode` pi package. Without
them, CI `verify-ledger` is still the backstop, and the agent will spawn its
evaluator however it can. That guard does not yet read `.glados/runs/stack`,
the list of nested runs in flight, as the hooks GLaDOS ships do (see
[hooks/README.md](../../hooks/README.md)).
