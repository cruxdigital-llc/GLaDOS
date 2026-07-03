# Migrating from GLaDOS v1.4.0 to v2.0.0

An afternoon of manual work per repo. No `glados migrate` machinery exists —
by design. This document is the whole procedure.

**Two facts before you start:**

- **v1 installs keep working until you reinstall.** Nothing in v2.0.0 touches
  an existing install; the compiled world arrives only when you run the v2
  installer against your repo. Migrate on your schedule.
- **Alias shims cover old workflow names permanently.** Every dead v1 name is
  a one-line alias to its v2 core, shipped forever — old CLAUDE.md files,
  agent memory, and human habit will invoke `plan-fix` for years, and a failed
  invocation would make the LLM reconstruct the v1 workflow from training
  data. The shims exist so that ghost never runs. You still want to update
  your docs, but nothing breaks if you miss one.

## What changed conceptually

- **Workflows became compiled cores.** v1 shipped 21 self-contained
  instruction files that each individually promised to trace, publish, and use
  the same vocabulary — and drifted. v2 workflows are short *cores* describing
  only their distinctive work; everything cross-cutting (the run-record
  epilogue, verdict vocabulary, module presence) is compiled into the
  installed text from one project manifest, `glados.yaml`.
- **The installer became an assembler with a type-checker.** Cores declare
  `reads:`/`writes:` against a flat state-key registry and `emits:` typed
  outcomes; install fails if anything is read that nothing writes, or if an
  emitted outcome type has no team-visible sink. Prose promises are replaced
  by install-time, CI-time, and host-hook enforcement.
- **State moved from machine-local scratch to the committed run ledger.**
  Every run writes exactly one record under `.glados/runs/`; epic state lives
  in the ledger on the integration branch, so a fresh session resumes from
  `git pull` instead of a scratchpad file that exists on one machine.

Full rationale, audit evidence, and the nine load-bearing decisions:
[docs/V2_STRATEGY.md](docs/V2_STRATEGY.md).

## The name map

Ten v1 workflow names are gone. The alias shims redirect all of them, so old
invocations still land — this table is for updating your own docs and habits.

| v1 workflow (dead) | v2 core |
|---|---|
| `mission` | `intent` |
| `plan-product` | `intent` |
| `autonomous-loop` | `run-epic --backlog` |
| `identify-bug` | `fix-bug` |
| `plan-fix` | `fix-bug` |
| `implement-fix` | `fix-bug` |
| `verify-fix` | `fix-bug` |
| `consolidate` | `steward` |
| `establish-standards` | `steward` |
| `recombobulate` | `steward` |

The four-stage bug pipeline is one core now; the phase you're in is a step
inside `fix-bug`, not a separate invocation. Likewise `steward` runs the whole
housekeeping pass (ledger compaction, standards promotion, docs refresh) that
v1 split across three workflows.

## Dead modules and what replaced them

| v1 module (dead) | Replaced by |
|---|---|
| `interaction-proxy` | `decisions:` keys in `glados.yaml` (`agent \| record \| escalate \| forbidden`) plus the `escalation` outcome channel. Decisions are now typed outcomes with a durable record instead of an in-session proxy conversation that left no trace. |
| `persona-review`, `persona-context`, `capabilities` | Manifest fields plus the review panel: the roster lives in `params.review-panel.personas` (and per-run in the run record), persona definitions are files under `product-knowledge/personas/` picked up by convention (the library set is vendored into `.glados/personas/` at install). Adding a persona is a file drop plus one manifest line — no reinstall. |
| `observability` | The compiled epilogue. Its job — record, commit, publish, release — is appended to every core at compile time and can no longer be skipped, forgotten, or restated divergently. |
| `evaluator-handoff` | Folded into `evaluator-spawn`, whose context-isolation contract survives intact. |
| `pattern-observer` | Folded into the `retrospect` core — observations are `observation` outcomes accumulating in `observations.pending`, promoted by the weekly `steward` pass. |

## The steps

### 1. Create `glados.yaml`

Copy `glados.yaml.example` to your repo root as `glados.yaml` and edit. Two
keys deserve attention:

- **`phase:` is required — there is no default.** An undeclared phase would
  mean the compiler chose values your team never stated. Guidance: **a repo
  with real users declares `production`**, whatever its code quality — phase
  states who gets hurt when the agent is wrong, not how proud you are of the
  code. Greenfield with no users is `nascent`; opted-in early adopters is
  `evolving`; a system you intend to leave is `sunset`. **The initial
  declaration is ungated** — you are describing reality, not claiming
  progress. Only later *transitions* between phases carry checklists.
- **`channels:`** — the defaults (`verdict: mr-comment`,
  `escalation`/`bug`: `issue`) are the ones that fix v1's trace-only-outcome
  failures. Weaken them only with the explicit
  `visibility-acknowledged: ledger-only` confession line.

### 2. Run install

Run the v2 installer for your runtime — `python bin/glados.py install --mode
<mode>`, where mode is one of `claude | claude-plugin | direct | gemini |
antigravity | aistudio`. It compiles cores + modules + vocabulary against
your manifest, runs the registry and sink checks, stamps the manifest hash,
and prints the assembly report — read it; it shows the provenance of every
resolved value and flags any phase-derived relaxations. This replaces the v1
file-copy install entirely.

### 3. Convert live `specs/` dirs to `.glados/runs/` entries

v1's per-feature `specs/` trace dirs are dead. For each dir that represents
work still in flight or worth remembering, write one run-record file in
`.glados/runs/` — a one-liner per dir is fine:

```
.glados/runs/2026-07-03-migrated-<slug>.md
    Migrated from specs/<slug>/. Outcome: <shipped in MR !N | abandoned | in
    flight on branch X>. See git history of specs/<slug>/ for the full trace.
```

Finished work whose outcome already lives in merged MRs needs nothing more
than that pointer. In-flight epics deserve a real `epic.progress` record
(ticket table, integration branch) so `run-epic` can resume from it.

### 4. Delete `specs/` and scratchpad epic files

After conversion, delete the `specs/` tree and any machine-local scratchpad
epic/progress files (e.g. `EPIC_PROGRESS.md` in an agent scratchpad). They are
readers-without-writers now: nothing in v2 updates them, and a stale copy that
looks authoritative is worse than absence. The git history of `specs/`
survives deletion; the run ledger is the living record.

### 5. Enable the CI template

The installer writes the CI include (`verify-ledger` and friends) but the
project owns turning it on — add the include to your CI configuration and push.
All rules start `report-only`; promote individual rules to `blocking` in the
manifest once they've proven quiet. Then run `glados doctor` to confirm the
check actually executes — a check that's declared but never runs is exactly
the silent failure v2 exists to kill, so doctor reports its absence loudly.

### 6. Optional: host-agent guard hooks

The compiled epilogue is a promise kept by an LLM at 90% context; the hooks
make it mechanical. Set up the guard for your runtime — Claude Code Stop-hook
(refuses session end without a committed run record), Gemini CLI AfterAgent
guard, or the agy Stop hook in `.agents/hooks.json`. See the per-runtime
setup recipes in the runtime docs (`docs/`, decision 9 of the strategy). CI
`verify-ledger` remains the universal backstop on every runtime, so the hooks
are belt-and-suspenders — recommended, not required.

## That's it

Old names keep working (shims), old installs keep working (until you
reinstall), and the first `verify-ledger` run gives you the baseline dashboard
that tells you whether the migration actually closed the loop.
