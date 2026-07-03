# Modules

A v2 module is a markdown file in `src/modules/` with `kind: module`
frontmatter declaring the same contract fields as a core (`reads:`,
`writes:`, `emits:`, `mutates:`, `requires:`). Modules are **inlined into
cores at compile time** — an enabled module's body appears in the installed
workflow text; an unselected module is simply absent, never a dangling
reference. Selection is per workflow in `glados.yaml` (`workflows:` lists,
with `default-modules:` for unlisted workflows); a core's `requires:` names
the modules that must be enabled for it, and the compiler rejects a manifest
that omits them.

## Compiled modules

| Module | Emits | Does |
|---|---|---|
| `standards-gate` | — | Gate the work artifact against the project's documented standards before advancing. |
| `mr-review-panel` | verdict | Run one adversarial, parallel, fresh-agent review panel over the open merge request. Seats the standing lenses plus manifest and feature personas; parameterized by `params.review-panel`. |
| `evaluator-spawn` | verdict | Spawn a context-isolated evaluator to verify finished work against a self-contained brief. Parameterized by `params.evaluator`. |

## Retired v1 modules

The seven v1 module files are deleted from the tree; their jobs moved into v2
structure (the compiled epilogue, manifest keys, `mr-review-panel`,
`evaluator-spawn`, and the `retrospect` core). The full mapping is in the
"Dead modules and what replaced them" table of
[MIGRATION.md](../MIGRATION.md).
