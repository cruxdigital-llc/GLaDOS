# Gemini CLI

For developers who work in [Gemini CLI](https://github.com/google-gemini/gemini-cli)
— Google's open-source terminal agent — and want the GLaDOS workflows
available there as slash commands.

Not sure which runtime you have? See the [chooser](README.md).

## Prerequisites

- Python 3.10 or newer on your PATH (the installer is one stdlib-only script).
  Where only `python3` is on the PATH (macOS, and Debian or Ubuntu without
  `python-is-python3`), write `python3` wherever this page says `python`,
  and in the hook command you wire: a hook that cannot start lets the
  agent finish unchecked.
- A local checkout of the GLaDOS repository.
- Your project is in a git repository, at its top level or in a subdirectory
  such as a monorepo package (CI enforcement is supported only at the top
  level; [details](README.md#what-a-run-leaves-behind)),
  and its clone can push a `glados/ledger` branch to `origin`: every run
  commits its record to that branch (`ledger save`) and pushes it. A
  branch-protection rule that covers `glados/ledger` refuses the push, and the
  records then stay in that one clone.
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

The installer compiles the workflow text against your `glados.yaml`, runs its
consistency checks, and prints an assembly report (also written to
`.glados/assembly-report.md`) showing every resolved setting and its origin.

## What got installed

```
your-project/
├── glados.yaml                      # your config (you created this)
├── .gemini/commands/glados/         # 26 TOML custom-command files:
│   ├── build-feature.toml           #   16 workflows + 10 shims redirecting
│   ├── fix-bug.toml                 #   retired v1 names (+ one per declared
│   │                                #   pipeline). Each file holds a
│   └── ...                          #   description plus the full compiled
│                                    #   workflow text as its prompt
├── .glados/                         # committed support folder: vendored
│   ├── glados.py                    #   installer/checker, workflow sources,
│   ├── src/  ci/  hooks/  personas/ #   CI templates, guard scripts, personas
│   ├── assembly-report.md  manifest-hash
│   └── glados.yaml.example  presets.yaml   # vendored template + phase presets
└── product-knowledge/               # project-owned knowledge skeleton
    ├── PROJECT_STATUS.md
    └── canon/ observations/ personas/ philosophies/ standards/ steps/
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
code — and, like every GLaDOS run, finishes by saving a run record to the
`glados/ledger` branch.

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
exiting with code 2 retries the turn. The guard uses that to insist that
every run in flight, the innermost run and each run it is nested inside
(listed in `.glados/runs/stack`), saves its run record and step artifacts to
the `glados/ledger` branch (`python .glados/glados.py ledger save`) before
the session moves on. It also retries when it cannot tell what is in flight:
a marker (`.glados/runs/current` or `.glados/runs/stack`) it cannot read or
decode, `.glados/runs/` or a directory in it that it cannot list, or a
marker line naming something that is not a regular file of exactly that
name. Wire `.glados/hooks/gemini-afteragent-guard.py` (vendored by the
install) into `.gemini/settings.json` using the snippet in
[hooks/README.md](../../hooks/README.md). It reads `.glados/runs/` in the
directory Gemini CLI runs in, so for a project in a subdirectory of its
repository, start `gemini` there. The guard stays silent unless a run is
actually in flight, so ordinary sessions are undisturbed; to release a run
you have abandoned, delete both `.glados/runs/current` and
`.glados/runs/stack`.

## Gotcha: the TOML files are compiler output

Each `.toml` embeds the entire compiled workflow as one TOML string. Never
edit these files by hand: the installer owns `.gemini/commands/glados/` —
on the next install, hand edits are overwritten and any file the compiler
didn't plan is deleted as stale. To change behavior, edit `glados.yaml`
(most keys are read live at run time; structural keys need a re-install;
[claude-code.md](claude-code.md#gotcha-two-kinds-of-config-edits) lists
both kinds) or the sources in the GLaDOS repo, then re-run the install
command above.
