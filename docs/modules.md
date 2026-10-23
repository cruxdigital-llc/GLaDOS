# Modules

> Reference page. If terms like *core*, *manifest*, or *compile time*
> are new to you, read [concepts.md](concepts.md) first — everything
> past this line assumes that vocabulary.

A v2 module is a markdown file in `src/modules/` with `kind: module`
frontmatter declaring the same contract fields as a core (`reads:`,
`writes:`, `emits:`, `mutates:`, `requires:`). Modules are **inlined into
cores at compile time** — an enabled module's body appears in the installed
workflow text; an unselected module is simply absent, never a dangling
reference. Selection is per workflow in `glados.yaml` (`workflows:` lists,
with `default-modules:` for unlisted workflows); a core's `requires:` names
the modules that must be enabled for it: a workflow that `workflows:` does
not list gets them on top of `default-modules`, and a `workflows:` list that
leaves one out fails the install.

## Compiled modules

| Module | Emits | Does |
|---|---|---|
| `standards-gate` | escalation | Gate the work artifact against the project's documented standards before advancing. Re-runs are bounded by `params.standards-gate.max-cycles`. Like every `max-cycles` bound, it must be a whole number of 1 or more: any other value fails install, `check` and `validate`, and one that reaches a run makes the workflow escalate, naming the key, instead of starting the loop. |
| `mr-review-panel` | verdict | Run one adversarial, parallel, fresh-agent review panel over the open merge request. Seats the standing lenses plus manifest and feature personas. The brief carries inputs labelled by who wrote them, never the author's conclusions, and quotes each instruction people gave on the MR; a fresh agent tries to refute each `blocking` finding before the tally counts it, and only a refuted one is dropped. Parameterized by `params.review-panel`. |
| `evaluator-spawn` | verdict | Spawn a context-isolated evaluator to verify finished work against a self-contained brief: each acceptance criterion with its source (the ticket, a person's quoted words, or the author's plan, shape or spec, labelled as the author's), the standards, the feature's personas and any canon that applies, never the author's conclusions. Brief and evaluation are files beside the run record, saved to the `glados/ledger` branch with it. Parameterized by `params.evaluator`. |

## Retired v1 modules

The seven v1 module files are deleted from the tree; their jobs moved into v2
structure (the compiled epilogue, manifest keys, `mr-review-panel`,
`evaluator-spawn`, and the `retrospect` core). The full mapping is in the
"Dead modules and what replaced them" table of
[MIGRATION.md](../MIGRATION.md).
