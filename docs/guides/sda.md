# SDA (Structured Development Artifacts) in GLaDOS v2

**SDA** is a tool-agnostic markdown format for tracking phased software
development work: a roadmap of trackable units, a status document, a work-unit
log, and a claims file recording who is working on what — all plain markdown
committed to the repo, so any agent, CI job, or human can read and write the
same state. The format is defined by versioned documents that ship with
GLaDOS:

- [docs/standards/sda-standard-v1.md](../standards/sda-standard-v1.md) — the
  standard itself (SDA v1.0), tooling-neutral
- [docs/standards/sda-profile-glados-v2.1.md](../standards/sda-profile-glados-v2.1.md)
  — the **v2.1 profile**, the current mapping: the v2 profile plus project
  workflows (`run-pipeline` records report their phase from their step
  table) and one claim and one work-unit row per unit of work
- [docs/standards/sda-profile-glados-v2.md](../standards/sda-profile-glados-v2.md)
  — the **v2 profile**, mapping the standard onto what v2 actually writes
  (the run ledger as work units, the compiled kernel as the claims/log
  writer); v2.1 amends it and leaves it unchanged
- [docs/standards/sda-profile-glados-v1.md](../standards/sda-profile-glados-v1.md)
  — the v1 profile, kept unchanged as the historical mapping for v1-era repos

This guide covers how you turn SDA on, what the installer scaffolds, and what
every workflow run does differently once it is on.

## Turning it on: `sda: true`

SDA conformance is a first-class, opt-in manifest key:

```yaml
# glados.yaml
sda: true        # explicit-only; default false
```

Two properties worth knowing:

- **Explicit-only.** No phase preset may set it. Conformance is a team
  declaration about how the repo coordinates — not something `production`
  turns on for you or `nascent` turns off. The assembly report shows the row
  as `sda: true (explicit)`.
- **Type-checked.** The key must be a bool; the installer rejects anything
  else.

Then re-run the install (`python bin/glados.py install --mode <mode> --target
/path/to/your/project`) so the artifacts get scaffolded. If you only ever use
the Claude Code plugin and never run the installer, the `/glados:init` skill
documents a manual fallback with the same result.

## What install scaffolds

With `sda: true`, the installer scaffolds the SDA artifacts — **create-only,
never clobbering** an existing file:

- **`claims.md`** at the project's root (the directory holding `glados.yaml`,
  which for a project in a subdirectory of its repository is that
  subdirectory) — the coordination file recording who has claimed what
- **`product-knowledge/SPEC_LOG.md`** — the work-unit log, created with the
  standard's table header
- an **`<!-- SDA: v1.0 -->` header** prepended to
  `product-knowledge/ROADMAP.md` and `PROJECT_STATUS.md` — only if the file
  exists and lacks it
- the **standards documents** (`sda-standard-v1.md` and every GLaDOS
  profile) copied into `product-knowledge/standards/`, so the repo carries
  its own reference

The assembly report lists exactly what was scaffolded. Existing SDA repos
lose nothing: files already present are left byte-for-byte alone.

## What runs do differently

The compiled preamble and epilogue of **every** workflow carry conditional
SDA steps — present in every compile, gated on the manifest at run time
(so the checked-in plugin build behaves identically to a repo install, and
flipping the key changes behavior on the next run without a recompile;
only the scaffolding is install-time):

- **Before mutating** (preamble): the run appends a claim to `claims.md` —
  workflow, scope, holder, timestamp. An existing uncleared claim on the same
  scope is treated as contention: coordinate, do not clobber.
- **Before ending** (epilogue): the run appends the work-unit row to
  `product-knowledge/SPEC_LOG.md` — date, workflow, scope, outcome, links —
  and clears its `claims.md` entry, both committed with the work on the
  working branch (the record itself goes to the `glados/ledger` branch). The
  row says the unit is done, so it lands on the target branch when, and
  only when, the change does, where SDA tooling reads it.
- **Nested runs** (plan-feature, spec-feature and the other stages that
  build-feature or a pipeline's `run-pipeline` run starts inside itself) do
  neither. One unit of work gets one claim and one row, both owned by the
  outermost run: a row marks its subject done, so a row from a nested plan
  would mark the whole feature done early, and the enclosing run's claim is
  never contention for the runs inside it. The one exception is a ticket's
  build inside `run-epic`: each ticket has its own branch and MR, so its
  build claims and logs as a unit of work of its own.
- **Runs on another's merge request** (review-mr and address-review) claim
  nothing and append no row. The MR's unit is its opener's: a GLaDOS run
  that opened it committed the one row with the work, and a person's MR is
  not a GLaDOS unit to log. So a fix pass leaves the MR's branch only its
  change, and its record goes to the ledger like any other.
- **Parked runs** (a pipeline step waiting for a person: at a `human`
  checkpoint, on a one-way question, or on a stalled check, when the run
  ends before the answer; a run resuming a park that has no approval or
  answer yet; and run-epic ending with only parked tickets left) keep their
  claim and append no row: the work is not finished. The run that resumes it
  after the approval or answer clears the claim and appends the row when the
  unit ends.
- **Pipeline records** carry a step table whose statuses are words, never
  checkboxes, and the v2.1 profile reads a pipeline's phase from it: the
  `stage` of its first row that is not done, skipped or waived, until the
  work-unit row marks the subject done. A passing verify-feature record
  inside a pipeline does not. See [pipelines.md](pipelines.md).

With `sda: false` (or the key absent) the steps are skipped and nothing else
changes: the compiled workflows are otherwise identical.

The registry entries for these two files are `sda.claims` and `sda.spec-log`
in [src/kernel/state-registry.yaml](../../src/kernel/state-registry.yaml).

## How this fits the v2 architecture

- **Work units = the run ledger.** v2 retired v1's per-feature `specs/`
  directories; the v2 profile declares `.glados/runs/` records the conforming
  work-unit equivalent — each record is the work unit and its trace log in
  one file. See the profile's
  [declared divergence](../standards/sda-profile-glados-v2.md) for the honest
  fine print, and the [v2.1 amendments](../standards/sda-profile-glados-v2.1.md)
  for pipeline records, step artifacts and units of work. From 2.5 those
  records live on the `glados/ledger` branch rather than on work branches or
  the target (a merge request's diff is the change), so a tool that reads
  them reads that branch, or runs `python .glados/glados.py ledger restore`
  first to copy them into `.glados/runs/`; records committed before stay
  where they are. A project in a subdirectory of its repository keeps its
  records under `<dir>/.glados/runs/` on the ledger.
- **`SPEC_LOG.md` complements the ledger rather than duplicating it by
  hand.** The ledger is one file per run; the work-unit log is the one-line
  audit trail across runs — and because the epilogue writes it, it stays
  current by construction instead of by convention.
- **`claims.md` predates leases.** v2.0.0's always-on concurrency answer is
  the base-SHA yield rule; the claims file adds the "who holds what"
  declaration SDA consumers (and `run-epic`'s contention awareness) read.

## When to opt in

- **You run Wheatley.** The companion Kanban board renders its claims overlay
  from the claims file and its backlog from the SDA roadmap — see
  [wheatley.md](wheatley.md), including the path note (Wheatley reads the
  claims file under `product-knowledge/`, while GLaDOS reads and writes it
  only at the project's root, and re-creates it there on install, so do not move
  it: if you use both, link `product-knowledge/claims.md` to the root file
  instead).
- **You have an existing SDA repo.** Set the key and the artifacts carry
  over; scaffolding only creates what is missing and adds headers. (Coming
  from GLaDOS v1, `glados.py migrate` detects the artifacts and sets the key
  in the manifest it generates — see
  [../../MIGRATION.md](../../MIGRATION.md).)
- **You coordinate multiple agents or humans.** The claims file is the
  git-native way to say "this scope is taken", and with `sda: true` every
  mutating run says it automatically.
- **Other SDA tooling.** Boards, CI dashboards, cross-repo reports — anything
  that consumes the standard keeps working, because the format is
  deliberately tool-agnostic.

If none of these apply, leave the key off: the run ledger plus
`PROJECT_STATUS.md` and `ROADMAP.md` (all standard v2 artifacts) already
cover a single-team, single-agent project.

## Summary

| | |
|---|---|
| **Works today** | `sda: true` in `glados.yaml`: install scaffolds `claims.md`, `SPEC_LOG.md`, `SDA: v1.0` headers, and the standards docs (create-only); one claim and one `SPEC_LOG` work-unit row per unit of work, recorded by the outermost run (runs nested inside it add neither; each ticket run-epic builds is a unit of its own) — native kernel behavior, no recompile to flip |
| **Coming later** | The lease module's lockfile backend writes `claims.md`-compatible entries when `sda: true` — claims become a view over enforced leases (direction, not shipped) |
| **Your responsibility** | Set the key explicitly (no phase sets it for you) and re-run install to scaffold; keep `ROADMAP.md` inside the SDA grammar if consumers key on item IDs; keep `claims.md` at the project's root, and link it under `product-knowledge/` if pairing with Wheatley |

See also: [wheatley.md](wheatley.md) for the board that consumes these
artifacts, the [v2.1 profile](../standards/sda-profile-glados-v2.1.md) (and
the [v2 profile](../standards/sda-profile-glados-v2.md) it amends) for the
exact mapping, and [../../MIGRATION.md](../../MIGRATION.md) for the `migrate`
command that converts v1 traces to the run ledger (and logs each converted
dir as a `SPEC_LOG.md` work unit).
