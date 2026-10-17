# Composable workflows, the shape step, and canon

> Design rationale for GLaDOS 2.5. How to use these features is in
> [guides/pipelines.md](../guides/pipelines.md) and
> [guides/canon.md](../guides/canon.md); this page records why they look the
> way they do, the decisions taken, and what was left for later.

**Status:** shipped in 2.5.0. **Baseline:** 2.4.0.

## The problem

GLaDOS ships a closed set of workflows. The main feature path is four fixed
stages: plan, spec, implement, verify. Teams asked for three things it could
not express without forking:

- **Their own process.** A backend change might want plan, a code-shape
  sketch, an architecture review, a persona review, then spec, implement,
  verify and review. A refactor might want no plan at all. A design pass might
  never touch code. And "what an architecture review means here" is the
  team's to define.
- **A step that fixes the shape of the code before the spec.** Function and
  type names, signatures and dependency direction, without bodies, so the
  structure is reviewed while changing it is still a text edit. The point is
  to stop the agent going far down a path that is expensive to reverse.
- **Canon.** Reference works the team holds as authoritative (Clean
  Architecture, an internal architecture doc) that reviews should consult
  and cite.

## Constraints from the existing design

- **The compiler only builds GLaDOS's own text.** Cores and modules are a
  fixed list loaded from GLaDOS's `src/`. Projects customize through
  `glados.yaml`, personas, standards and philosophies.
- **The four-stage path is a table in build-feature's prose.** No code
  enforces the order, so making workflows configurable is about where that
  table comes from, not a new execution engine.
- **The Claude Code plugin cannot see project config at build time.** It is
  compiled once from `glados.yaml.example`. Anything project-specific has to
  be a compiled instruction that reads project config when it runs, the way
  declared sinks already work.
- **v1's customization was removed on purpose.** Overlays and the v1
  persona-review module failed because rules kept in referenced files drifted
  and got skipped ([V2_STRATEGY.md](../V2_STRATEGY.md), decision 1). So GLaDOS
  owns the contract (gate rules, loop bounds, where outcomes go, run records)
  and a project's file only says what to produce or check.

## Decisions

| Question | Decision |
|---|---|
| Do build-feature and fix-bug change? | No. Projects add workflows; they do not edit the shipped ones. Shared kernel and vocabulary fixes still flow into their compiled text. |
| Where does configuration live? | Declarations in `glados.yaml` (`steps:`, `pipelines:`, `canon:`). Step bodies in `product-knowledge/steps/`, canon digests in `product-knowledge/canon/`. |
| Must every workflow include plan, spec, implement and verify? | No. A pipeline is any ordered list of steps. Order is checked by inputs only. |
| Who reviews pre-code work, and does a person approve? | Configurable per step: `review: none \| in-context \| fresh-agent` and `checkpoint: none \| record \| human`. |
| Can the process adapt per feature? | Yes. The runner picks a pipeline per piece of work, and steps can be `required`, `optional` (with a `when:` the agent evaluates) or `advisory`. |
| Pseudo-code or real stubs? | Markdown signatures beside the run record (the `shape` step). Stubs committed early are the hard-to-reverse path the step exists to avoid; implement-feature writes stubs as its first task. |
| Canon by URL or by digest? | Agents read an in-repo digest. The URL is for provenance and for steward's reviewed refresh. |

### Teams own the shape; GLaDOS owns visibility

V2's hard rules were never about process shape. They are about the team being
able to see and trust what happened ("phase tunes attention and authority; it
may never tune observability"). Pipelines follow the same line. Whatever the
steps, every run still has a run record from the first minute, outcomes that
reach a team-visible place, decision rights, a claimed branch and base commit
before code changes, declared steps only, and bounded revise loops.

### Order by inputs, not positions

Each step produces an artifact kind (`plan`, `shape`, `spec`, `change`,
`verification`, `mr`) and needs some. Validation only checks that a step's
needs come from an earlier step. That lets a project step stand in for a
built-in: a refactor's `target-structure` step that produces a `spec`
satisfies implement-feature, whose own text already accepts a spec handed to
it by the caller.

### Read live, checked hard

Pipeline definitions are lane 2 (read live), which bends the v2 rule that
what the agent must not skip is compiled. The plugin leaves no choice. Every
rule about steps is compiled into `run-pipeline`, and skipping is made
visible: a step table written before any work, pinned hashes of
`glados.yaml` and step bodies, the table in the MR description, and
`glados.py validate` runnable with no install (including from the plugin).

### Verification before an MR is not forced

build-feature keeps its verified-before-MR gate. In a pipeline it is the
team's call; a pipeline that opens an MR with no verification step before it
gets a warning, and the MR description says no verification ran.

### Canon advises unless adopted

A departure from canon is advisory and still has to name a consequence. A
principle blocks only once a project standard (`must`) or philosophy (`core`)
adopts it. Precedence: recorded project decisions, then standards, then
philosophies, then canon. Digests are in the team's words, cite sections not
pages, and quote at most a sentence. A digest an agent drafts from memory is
marked `drafted-from: recall` and stays advisory until a person confirms it.
The consult instruction compiles only into the workflows that consult canon,
to keep the cost off every other core.

## Foundations fixed first

Five existing bugs sat under all three features and shipped in the same
release:

1. **Lane-2 edits made `check` report a stale compile.** The manifest hash now
   covers structural keys only, and the vendored assembly report is
   presence-checked.
2. **Nested runs clobbered the run marker.** `.glados/runs/stack` now lists
   every run in flight while `current` stays one line for older hooks. Nested
   runs work under the outer run's SDA claim and do not append their own
   SPEC_LOG row (which would have marked a feature done early). A ticket's
   build inside run-epic is its own unit of work.
3. **Outcomes bound to MR comments escalated before any MR existed.** They are
   now recorded as pending and posted when the MR opens.
4. **Preset-only defaults were invisible at run time.** The preamble now points
   at the vendored preset table; the plugin guard maps it, and library
   personas, to the plugin's own copies.
5. **Plugin-only repos had no `.glados/personas/`.** Covered by the same
   mapping.

## Choices made during implementation

- A pipeline that changes code, or has a `human` checkpoint, works on its own
  branch from its first step, so nested runs' record commits and a parked
  run's artifacts have somewhere to go.
- Under `decisions.pipeline-discretion: escalate`, a person names the
  pipeline; the agent does not choose from `when:` matches.
- A refusal at a `human` checkpoint sends the step back for revision whatever
  its modifier; a person who says stop ends the run.
- In YAML, `- key: value` list items now parse as mappings (standard YAML);
  lists that hold names reject them with a named error.

## Left for later

- A `verify-ledger` audit (with an enforcing mode) of pipeline step tables.
- A Stop-hook rule that refuses session end on a skipped required step.
- Wheatley showing pipeline name, current step and awaiting-approval badges.
- The lifecycle transitions PR, rebased onto this release.
- Pipelines that never produce an MR inside run-epic (run-epic assigns only
  pipelines that open one).
