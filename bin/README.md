# Binaries

This directory contains the GLaDOS v2 toolchain.

## `glados.py`

The compiler, type-checker, and installer — one file, standard library only
(Python 3.10+). It replaces the v1 `glados-install.sh` / `glados-update.sh`
scripts; the update flow is simply re-running install.

**Subcommands** (see `python bin/glados.py --help`):

| Command | Does |
|---|---|
| `install` | Compile the sources against the target's `glados.yaml` and emit one adapter (`--mode claude \| claude-plugin \| direct \| gemini \| antigravity \| aistudio`). |
| `check` | CI mode: recompute the compile and diff it against the installed files; drift, failed type checks, or a stale manifest hash fail the job. |
| `doctor` | Staleness + wiring report (never fails). |
| `verify-ledger` | Scan git history for silent-loss candidates (report-only). |
| `compile-plugin` | Shorthand for `install --mode claude-plugin --target <repo>`. |

**Usage**:

```bash
python bin/glados.py install --mode <mode> --target <dir> [--source <glados repo>]
```

The self-test suite lives at `tests/run_tests.py`.
