# Google AI Studio

For developers whose only agent surface is [Google AI Studio](https://aistudio.google.com)
— Google's browser-based prompt workbench — where the model has no access to
your files, git, or CI, and you want GLaDOS's planning and review workflows
anyway.

Not sure which runtime you have? See the [chooser](README.md).

## What this mode actually is

AI Studio can't run commands, so there are no slash commands to install.
Instead, the installer checks a **paste kit** into your repo: one
self-contained Markdown bundle per workflow, which you paste into AI Studio's
System Instructions field. Only the read-mostly workflows ship as bundles —
planning, specs, reviews, retrospectives. Execution-heavy workflows (like
implementing a feature) are deliberately absent or advisory-only: AI Studio
is a planning/review/spec surface, not a hands-on-keyboard one.

## Prerequisites

- Python 3.10 or newer on your PATH (the installer is one stdlib-only script).
- A local checkout of the GLaDOS repository.
- Your project is a git repository (run records are committed files).
- A Google account for AI Studio; a Gemini API key only if you use the
  bundled script runner.

## Install

From the GLaDOS checkout, give your project its configuration file, then
compile:

```bash
cd /path/to/GLaDOS
cp glados.yaml.example /path/to/your/project/glados.yaml
# open /path/to/your/project/glados.yaml and set at least:
#   platform:  gitlab | github
#   phase:     nascent | evolving | production | sunset   (required, no default)
python bin/glados.py install --mode aistudio --target /path/to/your/project
```

## What got installed

```
your-project/
├── glados.yaml                      # your config (you created this)
├── glados/adapters/aistudio/
│   ├── README.md                    # the paste flow, step by step
│   ├── MANIFEST.md                  # bundle list + the config fingerprint
│   │                                #   each bundle was compiled from
│   ├── bundles/                     # 7 paste bundles (intent, plan-feature,
│   │   ├── plan-feature.aistudio.md #   spec-feature, review-mr,
│   │   ├── review-mr.aistudio.md    #   review-codebase, retrospect,
│   │   └── ...                      #   fix-bug-advisory) + pointer stubs
│   │                                #   for retired v1 names
│   ├── schemas/run_record.schema.json  # optional structured-output schema
│   └── api-runner/
│       ├── run_workflow.py          # scripted runs via the Gemini API
│       └── schedule.example.md      # cron / Task Scheduler / CI recipes
├── .glados/                         # committed support folder (vendored
│   └── ...                          #   checker, sources, CI templates)
└── product-knowledge/               # project-owned knowledge skeleton
```

Commit all of it.

## First run

1. Open a new prompt in AI Studio.
2. Paste the contents of
   `glados/adapters/aistudio/bundles/review-codebase.aistudio.md` into the
   **System Instructions** field.
3. Paste the repo context the workflow needs (relevant files, the issue
   text) as your first user message, then run.
4. Save the prompt to reuse the workflow later (AI Studio autosaves prompts
   to your Google Drive).

For unattended scheduled runs there is also a script path — see
`api-runner/schedule.example.md`; it calls the Gemini API directly with the
same bundles and needs `GEMINI_API_KEY` set.

## Verify

From your project root:

```bash
python .glados/glados.py check --target .
```

Expected: `glados check: OK — no drift, checks pass, manifest hash current`.

## Guard hook

AI Studio has no hook surface at all. Two substitutes: each bundle ends every
response with a mandatory run-record checklist, and
`schemas/run_record.schema.json` can be set as the structured-output schema
so omitting the run record is a schema violation. The CI check vendored to
`.glados/ci/` (the installer prints the enable stanza) is the real backstop —
context in [hooks/README.md](../../hooks/README.md).

## Gotcha: the model has no hands — you are the executor

Every bundle opens with a runtime contract: the model must emit a fenced
block headed `=== WRITE FILE: <repo-relative-path> ===` for any file it wants
written, and `=== RUN: ===` for any git or platform command. **Nothing has
happened until you apply those blocks yourself** — including committing the
run record to `.glados/runs/`. Don't read a transcript as work done. Two
related cautions: bundles inline your `glados.yaml` values at compile time,
so re-run the install whenever the config changes (`MANIFEST.md` records the
fingerprint); and pasting proprietary code into free-tier AI Studio may
expose it to product-improvement use — check your tier's data policy first.
