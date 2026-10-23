# Direct (any agent, no command surface)

For developers whose AI agent has no slash-command system GLaDOS supports —
an in-house agent, a different IDE assistant, or plain API scripting — but
can read files in the repo and follow instructions.

If you use Claude Code, [Gemini CLI](https://github.com/google-gemini/gemini-cli)
(Google's open-source terminal agent),
[Google Antigravity](https://antigravity.google) (Google's agentic IDE; CLI
`agy`), [pi](https://pi.dev), or [Google AI Studio](https://aistudio.google.com),
use their dedicated modes instead — see the [chooser](README.md).

## Prerequisites

- Python 3.10 or newer on your PATH (the installer is one stdlib-only script).
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
├── product-knowledge/
│   ├── glados/                      # 26 compiled workflow files (.md):
│   │   ├── build-feature.md         #   16 workflows + 10 shims that redirect
│   │   ├── fix-bug.md               #   retired v1 names to the current file,
│   │   └── ...                      #   plus a pointer per declared pipeline
│   ├── PROJECT_STATUS.md            # project-owned knowledge skeleton
│   └── canon/ observations/ personas/ philosophies/ standards/ steps/
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
finishes by saving a run record — a short Markdown note written under
`.glados/runs/` and saved to the `glados/ledger` branch — saying what was
attempted and how it ended. Many teams add
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
`.github/workflows/`. Turn it on before relying on this mode. A project in
a subdirectory of its repository has no CI check: CI enforcement is
supported only for a project at the repository root
([details](README.md#what-a-run-leaves-behind)), so this mode relies on the
compiled text and on running `check` and `verify-ledger` yourself.

## Gotcha: nothing guards the exits

In hook-equipped runtimes, ending a session mid-run without a saved run
record gets blocked or retried. Here, an agent that stops early simply
stops — the promise in the compiled text is all there is at session end.
Compensate deliberately. Enable the CI check above: its check job flags
drift on every merge request / pull request (PR from here on), and its
report-only verify-ledger job counts the record commits on the
`glados/ledger` branch and lists any run record a merge request commits to
its own branch. Also run
`python .glados/glados.py verify-ledger --target . --base origin/main`
(your target branch) occasionally, after a `git fetch` so the clone has the
ledger branch. It
scans git history for review-ish commits and agent branches that never left
a run record — the silent losses this whole system exists to surface — and
lists any record your branch commits instead of saving it to the ledger. A
record still sitting unsaved in `.glados/runs/` is saved with
`python .glados/glados.py ledger save`.
