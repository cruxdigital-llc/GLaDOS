# Claude Code (script install)

For developers who run Claude Code — Anthropic's terminal coding agent — and
want the GLaDOS workflow commands compiled directly into this one repository.

If your team instead distributes GLaDOS as a shared Claude Code plugin, see
[claude-plugin.md](claude-plugin.md). Not sure which runtime you have? See the
[chooser](README.md).

## Prerequisites

- Python 3.10 or newer on your PATH (the installer is one stdlib-only script).
  Where only `python3` is on the PATH (macOS, and Debian or Ubuntu without
  `python-is-python3`), write `python3` wherever this page says `python`,
  and in the hook command you wire: a hook that cannot start lets the
  session end.
- A local checkout of the GLaDOS repository.
- Your project is in a git repository, at its top level or in a subdirectory
  such as a monorepo package (CI enforcement is supported only at the top
  level; [details](README.md#what-a-run-leaves-behind)),
  and its clone can push a `glados/ledger` branch to `origin`: every run
  commits its record to that branch (`ledger save`) and pushes it. A
  branch-protection rule that covers `glados/ledger` refuses the push, and the
  records then stay in that one clone.

## Install

From the GLaDOS checkout, first give your project its configuration file,
then compile:

```bash
cd /path/to/GLaDOS
cp glados.yaml.example /path/to/your/project/glados.yaml
# open /path/to/your/project/glados.yaml and set at least:
#   platform:  gitlab | github
#   phase:     nascent | evolving | production | sunset   (required, no default)
python bin/glados.py install --mode claude --target /path/to/your/project
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
consistency checks (it refuses to install a configuration where, say, a review
verdict has nowhere team-visible to go), and prints an **assembly report** —
a full listing of every resolved setting and where its value came from. Read
it once; it is also written to `.glados/assembly-report.md`.

## What got installed

```
your-project/
├── glados.yaml                      # your config (you created this)
├── .claude/commands/glados/         # 26 slash commands (.md files):
│   ├── build-feature.md             #   16 workflows + 10 shims that redirect
│   ├── fix-bug.md                   #   retired v1 names to their new names,
│   ├── review-mr.md                 #   plus one per pipeline you declare
│   └── ...
├── .glados/                         # committed support folder
│   ├── glados.py                    # vendored installer/checker (for CI + verify)
│   ├── assembly-report.md           # what compiled, from which settings
│   ├── manifest-hash                # fingerprint of the structural glados.yaml keys it was built from
│   ├── src/                         # vendored workflow sources
│   ├── ci/                          # CI check templates (GitLab + GitHub)
│   ├── hooks/                       # session-end guard scripts
│   ├── personas/                    # reviewer persona library
│   └── glados.yaml.example, presets.yaml  # vendored template + phase presets
└── product-knowledge/               # project-owned knowledge skeleton
    ├── PROJECT_STATUS.md
    └── canon/ observations/ personas/ philosophies/ standards/ steps/
```

Commit all of it.

## First run

Open Claude Code in your project and type a slash command. The commands are
namespaced under `glados:` (from the `.claude/commands/glados/` directory).
A good, read-only first run:

```
/glados:review-codebase
```

This audits the codebase and reports structure and health without changing
any code — and, like every GLaDOS run, finishes by saving a run record to
the `glados/ledger` branch.

## Verify

From your project root:

```bash
python .glados/glados.py check --target .
```

Expected output:

```
glados check: OK — no drift, checks pass, manifest hash current
```

Anything else lists the exact problem (a stale compile, a missing or edited
file). The same command runs in CI via the vendored templates — the installer
prints the one-paste enable stanza for your platform (GitLab `include:` or a
GitHub workflow copy). That is for a project at the repository root only:
for one in a subdirectory the installer says CI enforcement is not
supported there and prints no stanza
([details](README.md#what-a-run-leaves-behind)).

## Guard hook

Every run promises to save its run record before ending. Claude Code has a
**Stop hook** that makes this mechanical: it blocks the session from ending
while any run in flight lacks a saved record, meaning its record and step
artifacts are not on the `glados/ledger` branch as they are on disk. That
includes the innermost run and every run it is nested inside (build-feature
runs plan-feature and the other stages as runs of their own, listed in
`.glados/runs/stack`). It also blocks, rather than letting the session go,
when it cannot tell what is in flight: a marker (`.glados/runs/current` or
`.glados/runs/stack`) it cannot read or decode, `.glados/runs/` or a
directory in it that it cannot list, or a marker line naming something that
is not a regular file of exactly that name (a directory, a link to a
directory or to nothing, a name that differs in case). The block names the
files and the command that saves them, `python .glados/glados.py ledger
save`; to release a run you have abandoned, delete both
`.glados/runs/current` and `.glados/runs/stack`.

The guard script is already vendored at `.glados/hooks/claude-stop-hook.py`;
wire it into `.claude/settings.json` with the snippet in
[hooks/README.md](../../hooks/README.md). It reads `.glados/runs/` in the
directory Claude Code runs in, so for a project in a subdirectory of its
repository, start Claude Code there. It only activates while a run is
actually in flight, so ordinary sessions are never disturbed.

## Gotcha: two kinds of config edits

Most `glados.yaml` keys (channels, merge authority, decisions, sinks,
branching, `params` with its review personas and loop bounds, each
pipeline's `when:`, `sequence:` and `step-options:`, `steps:`, `canon:`) are
read **live at run time** — edit the file and the next run obeys, no
reinstall. A `run-pipeline` run pins the configuration it starts with,
`.glados/presets.yaml` included (`python .glados/glados.py effective-config
--target .` prints its digest), and re-checks it before each step and when
it resumes, so an edit made mid-run or while the run is parked stops it with
an escalation rather than changing its rules partway.

A live edit is still checked: `check` fails on a value no run can obey,
such as a loop bound that is not a whole number of 1 or more (`0`, `"5"`,
`true`, a list) or a decision class other than `agent`, `record`,
`escalate` or `forbidden`. `python .glados/glados.py validate --target .`
reports the same problems without writing anything.

Structural keys (`phase:`, `optimize-for:`, `default-modules:`,
`workflows:`, `disabled-workflows:`, `sda:`, and each pipeline's name and
`description:`, which name its `/glados:<pipeline>` shortcut) are baked
into the compiled command text: after editing those, re-run the `install`
command above, or `check` will fail with `stale compile` and CI will flag
the drift. `python .glados/glados.py doctor --target .` reports staleness
without failing anything.
