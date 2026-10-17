# Binaries

This directory contains the GLaDOS v2 toolchain.

## `glados.py`

The compiler, type-checker, and installer — one file, standard library only
(Python 3.10+). It replaces the v1 `glados-install.sh` / `glados-update.sh`
scripts; the update flow is simply re-running install.

**Subcommands** (see `python bin/glados.py --help`):

| Command | Does |
|---|---|
| `install` | Compile the sources against the target's `glados.yaml` and emit one adapter (`--mode claude \| claude-plugin \| direct \| gemini \| antigravity \| aistudio \| pi`). Warns, without failing, about unknown top-level `glados.yaml` keys. |
| `check` | CI mode: recompute the compile and diff it against the installed files; drift, failed type checks, or a stale manifest hash fail the job. The hash covers only the structural keys (`phase`, `optimize-for`, `default-modules`, `workflows`, `disabled-workflows`, `sda`, and each pipeline's name and description), so editing a live key such as `channels` or `params` never makes the compile stale; the type checks still run on those values, so an invalid one (an undeclared sink, an unconfessed relaxation, a misspelt decision class) fails it. Warns, without failing, about unknown top-level keys. |
| `validate` | Type-check the target's `glados.yaml` in memory, its `pipelines:` and `steps:` included (step bodies in `product-knowledge/steps/` too): every check `install` runs, with errors and warnings printed. Writes nothing, needs no install (a plugin-only repo runs it from the plugin's own `bin/glados.py`), exits 1 on any error. `run-pipeline` runs it before its first step. |
| `doctor` | Staleness + wiring report (never fails). |
| `migrate` | Guided v1 to v2 migration: detect v1 layouts, generate `glados.yaml` (phase left for a human), convert `specs/` history to run records. Non-destructive by default; `--dry-run` writes nothing, `--clean` removes the converted `specs/` dirs and the detected v1 command layouts. |
| `verify-ledger` | Scan git history for silent-loss candidates (report-only). |
| `compile-plugin` | Shorthand for `install --mode claude-plugin --target <repo>`. |

**Usage**:

```bash
python bin/glados.py install --mode <mode> --target <dir> [--source <glados repo>]
```

The self-test suite lives at `tests/run_tests.py`.
