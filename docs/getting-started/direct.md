# Direct (any agent, no command surface)

For developers whose AI agent has no slash-command system GLaDOS supports —
an in-house agent, a different IDE assistant, or plain API scripting — but
can read files in the repo and follow instructions.

If you use Claude Code, [Gemini CLI](https://github.com/google-gemini/gemini-cli)
(Google's open-source terminal agent),
[Google Antigravity](https://antigravity.google) (Google's agentic IDE; CLI
`agy`), or [Google AI Studio](https://aistudio.google.com), use their
dedicated modes instead — see the [chooser](README.md).

## Prerequisites

- Python 3.10 or newer on your PATH (the installer is one stdlib-only script).
- A local checkout of the GLaDOS repository.
- Your project is a git repository (run records are committed files).
- An agent that can read repo files and act on them.

## Install

From the GLaDOS checkout, give your project its configuration file, then
compile:

```bash
cd /path/to/GLaDOS
cp glados.yaml.example /path/to/your/project/glados.yaml
# open /path/to/your/project/glados.yaml and set at least:
#   platform:  gitlab | github
#   phase:     nascent | evolving | production | sunset   (required, no default)
python bin/glados.py install --mode direct --target /path/to/your/project
```

The installer compiles the workflow text against your `glados.yaml`, runs its
consistency checks, and prints an assembly report (also written to
`.glados/assembly-report.md`) showing every resolved setting and its origin.

## What got installed

```
your-project/
├── glados.yaml                      # your config (you created this)
├── product-knowledge/
│   ├── glados/                      # 25 compiled workflow files (.md):
│   │   ├── build-feature.md         #   15 workflows + 10 shims that redirect
│   │   ├── fix-bug.md               #   retired v1 names to the current file
│   │   └── ...
│   ├── PROJECT_STATUS.md            # project-owned knowledge skeleton
│   └── observations/ personas/ philosophies/ standards/
└── .glados/                         # committed support folder: vendored
    ├── glados.py                    #   installer/checker, workflow sources,
    ├── src/  ci/  hooks/  personas/ #   CI templates, guard scripts, personas
    ├── assembly-report.md  manifest-hash
    └── glados.yaml.example  presets.yaml   # vendored template + phase presets
```

Commit all of it.

## First run

There is no invocation syntax in this mode — a "command" is just a compiled
file your agent reads and follows. Tell your agent, verbatim:

```
Read and follow product-knowledge/glados/review-codebase.md
```

That workflow audits the codebase read-only and, like every GLaDOS run,
finishes by committing a run record — a short Markdown note under
`.glados/runs/` saying what was attempted and how it ended. Many teams add
one line per common workflow to their agent's standing instruction file
(CLAUDE.md, AGENTS.md, or equivalent) so "build the next feature" resolves to
the right compiled file.

## Verify

From your project root:

```bash
python .glados/glados.py check --target .
```

Expected: `glados check: OK — no drift, checks pass, manifest hash current`.
Anything else lists the exact problem (a stale compile, an edited or missing
compiled file).

## Guard hook

None. Hooks are runtime features (Claude Code, Gemini CLI, and `agy` each
have one — see [hooks/README.md](../../hooks/README.md)), and direct mode
assumes no runtime. Your enforcement is the CI check: the installer vendored
both templates into `.glados/ci/` and printed the enable stanza — for GitLab,
an `include:` of `.glados/ci/glados-check.gitlab-ci.yml` in `.gitlab-ci.yml`;
for GitHub, copy `.glados/ci/glados-check.github-actions.yml` into
`.github/workflows/`. Turn it on before relying on this mode.

## Gotcha: nothing guards the exits

In hook-equipped runtimes, ending a session mid-run without a committed run
record gets blocked or retried. Here, an agent that stops early simply
stops — the promise in the compiled text is all there is at session end.
Compensate deliberately: enable the CI check above (it flags drift and
missing records on every merge request / pull request — PR from here on),
and run `python .glados/glados.py verify-ledger --target .` occasionally; it
scans git history for review-ish commits and agent branches that never left
a run record — the silent losses this whole system exists to surface.
