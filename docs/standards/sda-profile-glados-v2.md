# SDA Profile: GLaDOS v2.0

*Maps the Structured Development Artifacts (SDA) Standard v1.0 onto GLaDOS v2
conventions.*

---

## 1. Overview

This profile defines how a GLaDOS v2 install produces and consumes
SDA-conformant artifacts. It supersedes the
[GLaDOS Profile v1.0](sda-profile-glados-v1.md) for v2 installs; the v1
profile remains the accurate, historical mapping for v1-era repos and is not
edited. The [standard itself](sda-standard-v1.md) is unchanged — this
document remaps its concepts onto the artifacts v2 actually writes.

Conformance Level: Full, with **one declared divergence**: v2 work units are
single run-record files, not directories (section 4). Everything else —
roadmap, status document, claims, work-unit log, version headers — follows
the standard's grammar as written.

## 2. Activation: the `sda:` manifest key

SDA conformance in v2 is declared in one place: `glados.yaml` sets
`sda: true`. The key is **explicit-only** — it defaults to `false`, and phase
presets may not set it, because conformance is a team declaration about how
the repo coordinates, not a consequence of how mature the code is.

Two things key on it:

- **Install-time scaffolding.** `glados.py install` scaffolds the SDA
  artifacts (create-only, never clobbering): `claims.md` at the repo root,
  `product-knowledge/SPEC_LOG.md` with the work-unit-log header, the
  `<!-- SDA: v1.0 -->` version header prepended to existing
  `product-knowledge/ROADMAP.md` and `PROJECT_STATUS.md` that lack it, and
  the SDA standard + profile documents copied into
  `product-knowledge/standards/`. The assembly report carries an
  `sda: true (explicit)` row and lists what was scaffolded.
- **Runtime behavior.** The compiled preamble and epilogue of every workflow
  carry conditional SDA steps, present in every compile and gated on the
  manifest at run time: mutating runs record a claim in `claims.md` before
  touching shared state, and every run appends its work-unit row to
  `product-knowledge/SPEC_LOG.md` and clears its claim before ending. No
  recompile is needed to flip the behavior — only the scaffolding is
  install-time.

## 3. Repository Layout

    <repo-root>/
    ├── glados.yaml                 # sda: true — the conformance declaration
    ├── claims.md                   # Claims (standard, section 6)
    ├── .glados/
    │   └── runs/                   # Work units — the run ledger (section 4)
    └── product-knowledge/
        ├── ROADMAP.md              # Roadmap (standard, section 4)
        ├── PROJECT_STATUS.md       # Status Document (standard, section 5)
        ├── SPEC_LOG.md             # Work Unit Log (standard, section 3.6)
        └── standards/              # vendored SDA standard + profiles

## 4. Work Units: the Run Ledger

Where the v1 profile mapped work units onto `specs/` directories, this
profile declares the **run ledger** — `.glados/runs/` — the conforming
equivalent. v2 deliberately retired per-feature trace directories; the unit
of recorded work is now one committed markdown file per workflow run, written
by a compiled epilogue no workflow can skip and checked by the
`verify-ledger` CI backstop.

### 4.1 The declared divergence

The standard (section 3.1) defines a work unit as a *directory* of markdown
files. A v2 work unit is a *single file* that is simultaneously the work unit
and its trace log. The standard's underlying requirement — that a date and a
human-readable identifier be recoverable by the profile's parser — is met;
the directory shape is not. Consumers implementing this profile parse record
files; consumers applying the v1 profile's directory rules to a v2 repo find
no `specs/` tree and no work units, by design.

### 4.2 Naming

Pattern:

    .glados/runs/{YYYY-MM-DD}-{WORKFLOW}-{KEBAB_SLUG}.md

| Segment | Description |
|---|---|
| `YYYY-MM-DD` | ISO 8601 date the run started |
| `WORKFLOW` | The v2 core name (closed set — see [workflows.md](../workflows.md)) |
| `KEBAB_SLUG` | Human-readable identifier: `[a-z0-9]+(-[a-z0-9]+)*` |

Both `WORKFLOW` and `KEBAB_SLUG` are kebab-case, so parsers MUST disambiguate
by matching the longest known workflow name after the date; the remainder is
the identifier. Files not matching the pattern are ignored.

Example: `.glados/runs/2026-07-03-fix-bug-login-timeout.md` — date
`2026-07-03`, workflow `fix-bug`, identifier `login-timeout`.

### 4.3 Trace log

The run record is the trace log (standard, section 3.3). The compiled
preamble creates it before any other work (initiation time, workflow, goal);
the compiled epilogue finalizes it: outcome, key decisions with their
decision-rights class, verdicts, links (MR, issues, commits), and the state
keys written. Verification results in a `verify-feature` (or fix-bug verify
stage) record are the terminal-phase log marker.

### 4.4 Checkpoint files

v2 does not shard checkpoints into separate files within a work unit. The
checkpoint *concepts* map onto the run records of the workflows that produce
them:

| SDA concept | Produced by | Lives in |
|---|---|---|
| Requirements + Plan | `plan-feature` | that run's record (and the `progress` outcome carrying the plan) |
| Specification | `spec-feature` | that run's record |
| Task List | `implement-feature` / `build-feature` | that run's record, standard checkbox syntax |

Task lists inside records MUST use markdown checkbox syntax (`- [ ]` /
`- [x]`), so checkbox completion remains usable as a phase signal.

## 5. Phases and Detection Rules

The v1 profile detected phase from file *presence within a directory*. This
profile detects a subject's phase from *which run records exist for it and
what they record* — the same three mechanisms the standard allows (file
presence, completion markers, log markers), applied to the ledger. Evaluated
in priority order, first match wins:

| Priority | Phase | Condition |
|---|---|---|
| 1 | done | a verification record (verify-feature, or fix-bug's verify stage) with a passing outcome — or the subject's work-unit row is present in `SPEC_LOG.md` (log marker) |
| 2 | verifying | an implementation record with all task checkboxes `[x]`, verification not yet recorded |
| 3 | implementing | an `implement-feature` / `build-feature` record exists |
| 4 | speccing | a `spec-feature` record exists |
| 5 | planning | a `plan-feature` record exists |
| 6 | unclaimed | the subject appears in the roadmap with no active claim and no record |

Phase flow: unclaimed → planning → speccing → implementing → verifying → done.

## 6. File Locations

| SDA Concept | GLaDOS v2 Location | Written by |
|---|---|---|
| Work units (+ trace log) | `.glados/runs/` | every run: compiled preamble creates, epilogue finalizes |
| Work Unit Log | `product-knowledge/SPEC_LOG.md` | compiled epilogue, one row per run when `sda: true` |
| Claims | `claims.md` (repo root) | compiled preamble (claim) and epilogue (clear) when `sda: true` |
| Roadmap | `product-knowledge/ROADMAP.md` | the `intent` workflow |
| Status Document | `product-knowledge/PROJECT_STATUS.md` | `adopt-codebase`, refreshed by `steward` |

These locations are registered as state keys (`sda.claims`,
`sda.spec-log`, `intent.roadmap`, `intent.status`) in
[src/kernel/state-registry.yaml](../../src/kernel/state-registry.yaml).

## 7. Work Unit Log: `SPEC_LOG.md`

Conforms to the standard's section 3.6. The compiled epilogue appends one row
per run — date, workflow, scope, outcome, links — newest first, in the table
format the scaffolded header establishes. Because the epilogue writes it, the
log is maintained *by construction* rather than by convention: the answer to
"when are entries written" (which the standard leaves to profiles) is "at the
end of every run, before the record commit".

## 8. Claims: `claims.md`

The claims file follows the standard's section 6 grammar: `# Claims` title,
one entry per line, `claimed → released | expired` lifecycle, last entry wins.
The v2 mapping:

- **Claiming** — the compiled preamble of any run that mutates shared state
  appends a `claimed` entry before the first mutation, recording workflow,
  scope, holder, and timestamp.
- **Clearing** — the compiled epilogue "clears" the entry by appending its
  `released` state with the release timestamp (release/expire are terminal
  within a claim epoch; re-claiming creates a new entry).
- **Contention** — an existing uncleared claim on the same scope means
  coordinate, never clobber; `run-epic` additionally consults the file for
  contention awareness before dispatching tickets.
- **Claimant field** — carries `workflow / holder` (free text, no pipes),
  e.g. `build-feature / claude`.

**Declared extension (scope tokens).** The standard's `ITEM_ID` is a roadmap
item ID (`\d+\.\d+\.\d+`). GLaDOS v2 work is not always roadmap-addressed, so
this profile widens the ID position to `ITEM_ID | scope-token` where a scope
token is kebab-case (a branch, component, or epic slug). Strict SDA v1.0
validators will flag scope-token entries as format errors; projects that
require strict Full conformance should claim roadmap items only.

**Direction (v2.1, not shipped):** the lease module's lockfile backend will
write `claims.md`-compatible entries when `sda: true`, making the claim file
a view over enforced leases rather than a parallel convention.

## 9. Roadmap and Status Document

Both follow the standard as written (sections 4 and 5); v2 changes who
maintains them, not their grammar:

- `product-knowledge/ROADMAP.md` is created and refreshed by the `intent`
  workflow. When `sda: true`, keep it inside the standard's three-level
  Phase → Section → Item grammar with `{phase}.{section}.{item}` IDs — item
  IDs are what claims and boards key on. Scaffolding guarantees only the
  `<!-- SDA: v1.0 -->` header on an existing file; the grammar is the
  team's (and the `intent` workflow's) to keep.
- `product-knowledge/PROJECT_STATUS.md` is scaffolded by every v2 install and
  refreshed by `steward`, with the standard's required H2 sections.

## 10. GLaDOS Extensions

Beyond the standard, a v2 repo carries the GLaDOS governance layer:
`product-knowledge/` (mission, standards, philosophies, personas,
observations), the manifest (`glados.yaml`) with its typed outcome channels
and decision rights, and the run ledger's enforcement stack (run-record guard
hooks, `verify-ledger` CI). None of these are SDA concepts; all are ordinary
markdown/YAML an SDA consumer MUST ignore. Frontmatter metadata (standard,
section 3.5) MAY appear in run records; no keys are required.

## 11. Conformance Checklist

- [ ] `glados.yaml` sets `sda: true` (explicit — not from a phase preset)
- [ ] Run records land under `.glados/runs/` and match
      `{YYYY-MM-DD}-{workflow}-{kebab-slug}.md`
- [ ] Every run record traces initiation, decisions, outcome, and links
- [ ] Phase is detectable via the six-rule table in section 5
- [ ] `product-knowledge/SPEC_LOG.md` gains one row per run, newest first
- [ ] `claims.md` follows the claims grammar (scope-token extension declared)
- [ ] `product-knowledge/ROADMAP.md` follows the roadmap grammar with
      `{P}.{S}.{I}` item IDs
- [ ] `product-knowledge/PROJECT_STATUS.md` has the required H2 sections
- [ ] Version headers (`<!-- SDA: v1.0 -->`) present on roadmap and status

## 12. Version History

| Version | Date | Notes |
|---|---|---|
| 2.0 | 2026-07-03 | v2 remapping: run ledger declared the work-unit equivalent (single-file divergence); claims + work-unit log written by the compiled kernel's conditional SDA steps, gated on the `sda:` manifest key |
| 1.0 | 2026-04-01 | See [sda-profile-glados-v1.md](sda-profile-glados-v1.md) — the v1 mapping (specs/ directories), unchanged and historical |
