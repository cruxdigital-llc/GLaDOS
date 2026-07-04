# Claude Code (script install)

For developers who run Claude Code — Anthropic's terminal coding agent — and
want the GLaDOS workflow commands compiled directly into this one repository.

If your team instead distributes GLaDOS as a shared Claude Code plugin, see
[claude-plugin.md](claude-plugin.md). Not sure which runtime you have? See the
[chooser](README.md).

## Prerequisites

- Python 3.10 or newer on your PATH (the installer is one stdlib-only script).
- A local checkout of the GLaDOS repository.
- Your project is a git repository (run records are committed files).

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

The installer compiles the workflow text against your `glados.yaml`, runs its
consistency checks (it refuses to install a configuration where, say, a review
verdict has nowhere team-visible to go), and prints an **assembly report** —
a full listing of every resolved setting and where its value came from. Read
it once; it is also written to `.glados/assembly-report.md`.

## What got installed

```
your-project/
├── glados.yaml                      # your config (you created this)
├── .claude/commands/glados/         # 25 slash commands (.md files):
│   ├── build-feature.md             #   15 workflows + 10 shims that redirect
│   ├── fix-bug.md                   #   retired v1 names to their new names
│   ├── review-mr.md
│   └── ...
├── .glados/                         # committed support folder
│   ├── glados.py                    # vendored installer/checker (for CI + verify)
│   ├── assembly-report.md           # what compiled, from which settings
│   ├── manifest-hash                # fingerprint of the glados.yaml it was built from
│   ├── src/                         # vendored workflow sources
│   ├── ci/                          # CI check templates (GitLab + GitHub)
│   ├── hooks/                       # session-end guard scripts
│   ├── personas/                    # reviewer persona library
│   └── glados.yaml.example, presets.yaml  # vendored template + phase presets
└── product-knowledge/               # project-owned knowledge skeleton
    ├── PROJECT_STATUS.md
    └── observations/ personas/ philosophies/ standards/
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
any code — and, like every GLaDOS run, finishes by committing a run record
under `.glados/runs/`.

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
GitHub workflow copy).

## Guard hook

Every run promises to commit its run record before ending. Claude Code has a
**Stop hook** that makes this mechanical: it blocks the session from ending
while a run is in flight without a committed record. The guard script is
already vendored at `.glados/hooks/claude-stop-hook.py`; wire it into
`.claude/settings.json` with the snippet in
[hooks/README.md](../../hooks/README.md). It only activates while a run is
actually in flight, so ordinary sessions are never disturbed.

## Gotcha: two kinds of config edits

Most `glados.yaml` keys (channels, merge authority, review personas, loop
bounds) are read **live at run time** — edit the file and the next run obeys,
no reinstall. But structural keys (`phase:`, per-workflow module lists,
`disabled-workflows:`) are baked into the compiled command text: after
editing those, re-run the `install` command above, or `check` will fail with
`stale compile` and CI will flag the drift. `python .glados/glados.py doctor
--target .` reports staleness without failing anything.
