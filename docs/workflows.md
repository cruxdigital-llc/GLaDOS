# Workflows

> Reference page. If terms like *core*, *module*, *manifest*, or
> *run record* are new to you, read [concepts.md](concepts.md) first —
> everything past this line assumes that vocabulary.

A v2 workflow is a **core**: a markdown file in `src/workflows/` whose YAML
frontmatter declares its contract (`reads:` / `writes:` state-registry tokens,
`emits:` outcome types, `mutates:`, `requires:` modules) and whose body covers
only that workflow's distinctive work. At compile time the installer prepends
the kernel preamble, inlines the enabled modules and any vocabulary partials
the body includes, and appends the kernel epilogue — cores never restate
run-record bookkeeping, publication, verdict vocabularies, or loop-bound
numbers.

## The cores

### Orientation

| Core | Mutates | Emits | Does |
|---|---|---|---|
| `intent` | none | progress, decision | Establish or refresh the product mission and roadmap. |
| `adopt-codebase` | branch | progress | Onboard an existing codebase — scaffold GLaDOS state and the manifest, then extract its knowledge. |
| `review-codebase` | none | progress, observation | Audit an existing codebase read-only and report structure, health, and observed-standards candidates. |

### The feature loop

| Core | Mutates | Emits | Does |
|---|---|---|---|
| `plan-feature` | none | progress, decision, observation | Analyze requirements and produce a high-level plan and review-persona roster for one feature. |
| `spec-feature` | none | progress, observation | Turn one feature's plan into finalized requirements and an implementable specification. |
| `implement-feature` | branch | progress | Write the code and tests that satisfy an approved specification. |
| `verify-feature` | none | progress, verdict, escalation, observation | Verify the implemented feature with a fresh evaluator that has no implementation context. |
| `build-feature` | branch | progress, verdict, escalation | Take one feature from selection to a verified, self-reviewed merge request in one sitting. |
| `run-pipeline` | branch | progress, verdict, escalation, decision, observation | Run one of the project's own workflows (declared under `pipelines:` in `glados.yaml`) step by step, with every step tracked in a step table in the run record. |

### Review and repair

| Core | Mutates | Emits | Does |
|---|---|---|---|
| `review-mr` | none | progress, verdict, escalation, observation | Run one adversarial multi-persona review pass over an open merge request, reading each note a person with a role on the project left on it (one not starting `(GLaDOS <workflow>)`) as their review. |
| `address-review` | branch | progress, escalation | Resolve every open review finding, and every point a person raised on the MR, in one coherent fix pass, then hand back for re-review. |
| `fix-bug` | branch | progress, bug, verdict, escalation | Take one bug from report through reproduction to a verified root-cause fix MR. |

### Scale

| Core | Mutates | Emits | Does |
|---|---|---|---|
| `run-epic` | board | progress, escalation, decision | Drive a multi-ticket epic or the backlog to one human-reviewable integration MR. |

### Ceremonies

| Core | Mutates | Emits | Does |
|---|---|---|---|
| `retrospect` | none | progress, observation | Review recent work to harvest observed standards, philosophies, and phase-fitness signals. |
| `steward` | branch | progress, observation, bug | The standing gardening pass — compact the run ledger (saved straight to the `glados/ledger` branch), refresh stale docs and canon digests, promote pending observations, sanity-check the test suite, ship one cleanup MR for what changed on its branch. |
| `brunch` | branch | progress, verdict, bug, observation, escalation | The codebase critique roundtable — evidence pre-flight, parallel persona reviewers, a moderator ranking impact×effort, one surgical fix MR. |

## Project workflows

build-feature runs four stages in a fixed order. A project that wants a
different process declares its own workflows under `pipelines:` in
`glados.yaml`: ordered lists of GLaDOS's built-in steps (the four stages plus
`shape`, `open-mr` and `self-review`) and steps the project writes itself
(`steps:`, with bodies in `product-knowledge/steps/`). `run-pipeline` runs any
of them: `/glados:run-pipeline <name> <brief>`, and script installs also get
one shortcut per pipeline (`/glados:<name>`, or `/glados-<name>` in
Antigravity and pi). Before its first step a run validates the manifest
and pins `glados.yaml`, the step bodies and the configuration they resolve
to with the preset table (`glados.py effective-config`); a change to any of
them mid-run, or across a resume, escalates. run-epic gives each ticket the
declared pipeline whose `when:` fits it (only one whose sequence always
opens an MR), writing it in the ticket table's `pipeline` column, and builds
the ticket through run-pipeline; a ticket none fits gets build-feature.
build-feature and fix-bug are unchanged. The full guide is
[guides/pipelines.md](guides/pipelines.md).

## v1 aliases

The ten retired v1 command names live permanently in
`src/kernel/aliases.yaml`; every adapter emits each of them as a one-line shim
routing to its v2 core — a failed invocation would make an agent reconstruct
the v1 workflow from training data, an ungoverned ghost. The full name map is
in [MIGRATION.md](../MIGRATION.md).
