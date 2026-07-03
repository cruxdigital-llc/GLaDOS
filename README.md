# GLaDOS

**GLaDOS** (Generative Logic and Documentation Operating System) v2 is a
**compiler for team attention**.

Code got cheap; understanding got scarce. v1 was 21 instruction files that each
individually promised to trace, publish, coordinate, and use the same words —
and prose promises don't compose. In v2, workflows shrink to short **cores**
describing only their distinctive work. Everything cross-cutting — where
outcomes publish, what words verdicts use, how the review panel is seated, what
happens at the end of every run — is **compiled into the workflow text at
install time from one project manifest**. The installer is an assembler with a
type-checker: it refuses to produce an install where something is read that
nothing writes, where an emitted outcome type has no team-visible sink, or
where a reference dangles. Enforcement lives at the three real enforcement
points a daemon-less markdown framework has — install time, CI time, and
host-agent hooks — never in prose hope.

The full rationale, audit evidence, and release sequencing live in
**[docs/V2_STRATEGY.md](docs/V2_STRATEGY.md)**.

---

## Quickstart

1. Copy the example manifest into your project root and edit it —
   `platform:`, `phase:`, and the channel bindings are the load-bearing keys:

   ```bash
   cp glados.yaml.example /path/to/your/project/glados.yaml
   ```

2. Compile and install for your runtime:

   ```bash
   python bin/glados.py install --mode claude
   # modes: claude | claude-plugin | direct | gemini | antigravity | aistudio
   ```

The install compiles the cores, vocabulary partials, and kernel fragments
against your manifest, runs the registry and sink checks, prints an assembly
report (every resolved value with its provenance), and emits the adapter output
for the chosen runtime. One compiled output feeds every mode; a fixture
self-test compiles all adapters so per-mode drift fails the build. The compiler
is under active development — see `bin/` for current status.

---

## The 15 cores

| Core | Does |
|---|---|
| `intent` | Establish or refresh the product mission and roadmap. |
| `plan-feature` | Analyze requirements and produce a high-level plan and review-persona roster for one feature. |
| `spec-feature` | Turn one feature's plan into finalized requirements and an implementable specification. |
| `implement-feature` | Write the code and tests that satisfy an approved specification. |
| `verify-feature` | Verify the implemented feature with a fresh evaluator that has no implementation context. |
| `build-feature` | Take one feature from selection to a verified, self-reviewed merge request (plan→spec→implement→verify, one sitting). |
| `fix-bug` | Take one bug from report through reproduction to a verified root-cause fix MR. |
| `review-mr` | Run one adversarial multi-persona review pass over an open merge request. |
| `address-review` | Resolve every open review finding in one coherent fix pass, then hand back for re-review. |
| `run-epic` | Drive a multi-ticket epic or the backlog to one human-reviewable integration MR. |
| `adopt-codebase` | Onboard an existing codebase — scaffold GLaDOS state and the manifest, then extract its knowledge. |
| `review-codebase` | Audit an existing codebase read-only and report structure, health, and observed-standards candidates. |
| `retrospect` | Review recent work to harvest observed standards, philosophies, and phase-fitness signals. |
| `steward` | The standing gardening pass — compact the run ledger, refresh stale docs, promote observations, sanity-check tests, ship one cleanup MR. |
| `brunch` | The codebase critique roundtable — evidence pre-flight, parallel persona reviewers, a moderator, one surgical fix MR. |

Every retired v1 command name remains as a permanent alias shim that routes to
its v2 core — old habits and old CLAUDE.md files keep working. See the name
map in [MIGRATION.md](MIGRATION.md).

---

## The manifest

`glados.yaml` is the one project-owned configuration file
([glados.yaml.example](glados.yaml.example) is the template). It declares the
platform, the required project phase, the **channel bindings** that route each
outcome type (`verdict`, `escalation`, `bug`, `progress`, `decision`,
`observation`) to team-visible sinks, merge authority, decision-rights keys,
branch conventions, per-workflow module selection, and module parameters.
Workflow cores emit outcome types and never name destinations; an emitted type
with zero team-visible sinks is an install error. Policies are manifest keys
that workflows read — no workflow file states a merge authority or a loop
bound, so contradictory sentences cannot exist.

## Project phase

`phase:` is a required manifest key — `nascent | evolving | production |
sunset` — declaring in one word who gets hurt when the agent is wrong and what
the team wants optimized. It expands into defaults for manifest keys that
already exist (precedence `baseline < phase preset < explicit`), never appears
in compiled workflow text, may never touch observability, and only a
human-merged MR can change it.

## The three-lane rule

Not everything compiles — the lanes decide what changes live and what passes
through a ceremony:

- **Lane 1 — compiled:** what the agent must not be able to skip. The
  epilogue, the verdict vocabulary, module presence/absence, constant rule
  text — inlined into each installed workflow. Changing structure is a
  manifest edit + recompile, deliberately a ceremony: the type-checker runs
  and the assembly report shows the team what changed.
- **Lane 2 — runtime-read:** values that change without ceremony. Compiled
  text instructs the agent to resolve channel bindings, merge authority,
  decision keys, loop-bound values, and the panel roster from `glados.yaml`
  at run time — a two-line manifest edit changes behavior on the next run.
- **Lane 3 — referenced on demand:** bulky, optional, harmless to skip.
  Persona definitions, rare-path procedures, standards documents. Add a
  persona by dropping a file in `product-knowledge/personas/` and adding one
  manifest line — the next panel seats it, no reinstall. The library personas
  ship vendored into `.glados/personas/` by every install mode; a project file
  of the same name wins.

---

## Scheduling the ceremonies

`steward` (housekeeping, typically Saturday) and `brunch` (the critique
roundtable, typically Sunday) are standing ceremonies. GLaDOS ships no
scheduler — every core is headless-invocable on every supported runtime, and
scheduling is the project's routine definition pointing at our core:

| Runtime | Headless recipe |
|---|---|
| Claude Code | A scheduled task that runs `/glados:steward` or `/glados:brunch`. |
| Gemini CLI | `gemini -p "/glados:brunch"` from cron or CI. |
| Antigravity (`agy`) | Non-interactive `agy` with `--output json` (stdout is dropped without it in non-TTY runs). |
| Any CI | A cron/scheduled pipeline job invoking the runtime headless. |
| AI Studio | The api-runner scripts from the paste-kit, targeting the Interactions API for scheduled read-mostly runs. |

## Boundary of responsibility

GLaDOS defines *contracts* — outcome types, channel kinds, the run-record
shape. The **project** provides the platform (GitLab or GitHub, error
tracking, CI wiring) and declares it in the manifest. The **agent** brings its
own hands — the project platform CLI, MCP servers, whatever its runtime
offers — to execute channel bindings. GLaDOS never wires a platform API
itself: it ships CI templates the project enables, and the doctor check
reports wiring that is declared but not actually running. On runtimes without
hands, the contract degrades honestly: the agent emits the exact commands and
file contents, and the operator or runner script executes them.

---

## Documentation

- [docs/V2_STRATEGY.md](docs/V2_STRATEGY.md) — the guiding strategy for v2.
- [docs/workflows.md](docs/workflows.md) — the cores and the v1 alias map.
- [docs/modules.md](docs/modules.md) — compiled modules and retired v1 modules.
- [docs/src.md](docs/src.md) — the source tree, kernel, and vocabulary.
