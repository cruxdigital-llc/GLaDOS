# Google Antigravity

For developers who work in [Google Antigravity](https://antigravity.google) —
Google's agentic IDE, with its companion terminal agent `agy` — and want the
GLaDOS workflows available as slash commands there.

Not sure which runtime you have? See the [chooser](README.md).

## Prerequisites

- Python 3.10 or newer on your PATH (the installer is one stdlib-only script).
- A local checkout of the GLaDOS repository.
- Your project is a git repository (run records are committed files).
- Google Antigravity (IDE and/or `agy` CLI) set up for the project.

## Install

From the GLaDOS checkout, give your project its configuration file, then
compile:

```bash
cd /path/to/GLaDOS
cp glados.yaml.example /path/to/your/project/glados.yaml
# open /path/to/your/project/glados.yaml and set at least:
#   platform:  gitlab | github
#   phase:     nascent | evolving | production | sunset   (required, no default)
python bin/glados.py install --mode antigravity --target /path/to/your/project
```

The installer compiles the workflow text against your `glados.yaml`, runs its
consistency checks, and prints an assembly report (also written to
`.glados/assembly-report.md`) showing every resolved setting and its origin.

## What got installed

```
your-project/
├── glados.yaml                      # your config (you created this)
├── .agents/
│   ├── workflows/                   # 25 flat workflow files, name-prefixed:
│   │   ├── glados-build-feature.md  #   15 workflows + 10 shims redirecting
│   │   ├── glados-fix-bug.md        #   retired v1 names
│   │   └── ...
│   └── hooks.json                   # run-record guard wiring (written only
│                                    #   if the file didn't already exist)
├── .glados/                         # committed support folder: vendored
│   ├── glados.py                    #   installer/checker, workflow sources,
│   ├── src/  ci/  hooks/  personas/ #   CI templates, guard scripts, personas
│   ├── assembly-report.md  manifest-hash
│   └── glados.yaml.example  presets.yaml   # vendored template + phase presets
└── product-knowledge/               # project-owned knowledge skeleton
    ├── PROJECT_STATUS.md
    └── observations/ personas/ philosophies/ standards/
```

Commit all of it. Antigravity maps each file under `.agents/workflows/` to a
slash command by *filename*, so the files are flat and carry the `glados-`
prefix — that is why the invocation below has a dash where other runtimes
have a colon. The installer only ever touches `glados-*.md` files in that
directory; your own workflows there are safe.

## First run

In the Antigravity agent panel (or an `agy` session), a good read-only first
run:

```
/glados-review-codebase
```

This audits the codebase and reports structure and health without changing
code — and, like every GLaDOS run, finishes by committing a run record under
`.glados/runs/`.

## Verify

From your project root:

```bash
python .glados/glados.py check --target .
```

Expected: `glados check: OK — no drift, checks pass, manifest hash current`.
The same check runs in CI via the templates vendored to `.glados/ci/` — the
installer prints the one-paste enable stanza for GitLab or GitHub.

## Guard hook

`agy` supports a Stop hook that surfaces a warning when a session ends while
a run is in flight without its committed run record. The installer already
wrote the wiring to `.agents/hooks.json` (if that file existed, it printed
the block to add manually). Details, including the IDE's lack of a hook
surface, in [hooks/README.md](../../hooks/README.md); the CI check remains
the universal backstop.

## Gotcha: headless `agy` needs `--output json`

Non-interactive `agy` runs (cron jobs, CI, any non-TTY invocation — for
example a scheduled `/glados-steward` housekeeping pass) silently drop their
stdout unless you pass `--output json`. Always add it when scripting:

```bash
agy --output json -p "/glados-steward"
```

Two smaller notes: Antigravity caps a workflow's frontmatter description at
250 characters (the installer truncates for you), and some setups ignore
relative hook-command paths in `.agents/hooks.json` — if the guard never
fires, make the script path absolute.
