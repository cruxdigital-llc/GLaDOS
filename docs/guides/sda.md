# SDA (Structured Development Artifacts) in GLaDOS v2

**SDA** is a tool-agnostic markdown format for tracking phased software
development work: a roadmap of trackable units, a status document, and a
claims file recording who is working on what — all plain markdown committed
to the repo, so any agent, CI job, or human can read and write the same
state. The format is defined by two versioned documents that ship with
GLaDOS:

- [docs/standards/sda-standard-v1.md](../standards/sda-standard-v1.md) — the
  standard itself (SDA v1.0), tooling-neutral
- [docs/standards/sda-profile-glados-v1.md](../standards/sda-profile-glados-v1.md)
  — the GLaDOS profile, mapping the standard's concepts onto GLaDOS
  conventions

This guide covers SDA's current status in GLaDOS v2: how you opt in, what v2
replaced, and when opting in is still the right call.

## Current status: opt-in, via the init skill

SDA conformance is **not** part of a default v2 install, and there is no
installer flag for it — `python bin/glados.py install --help` offers only
`--target`, `--mode`, and `--source`, and the compiler source contains no SDA
handling at all. The one entry point is the **init skill**: the
`/glados:init` bootstrap command that creates the manifest (`glados.yaml`,
the project configuration file) and scaffolds `product-knowledge/`. Its step
3 asks:

> "Would you like to enable SDA (Structured Development Artifacts)
> conformance?"

Answer yes and it copies, from the GLaDOS templates:

- **`claims.md`** at the project root — the coordination file recording who
  has claimed which roadmap item (dated with today's date)
- **`product-knowledge/SPEC_LOG.md`** — the historical record of feature
  specifications, one entry per landed feature with its merge commit
- **`product-knowledge/ROADMAP.md`** — from the SDA-conformant roadmap
  template (or, if a roadmap already exists, it gets an `<!-- SDA: v1.0 -->`
  header instead of being replaced)
- an `<!-- SDA: v1.0 -->` header on `product-knowledge/PROJECT_STATUS.md` if
  missing
- both versioned standards documents above into
  `product-knowledge/standards/`, so the repo carries its own reference copy

Nothing else in the install changes: the compiled workflows, channels, and CI
templates are identical with or without SDA.

## What v2 replaced

v2 restructured the two artifacts SDA leaned on hardest, which is why SDA
moved from ambient convention to explicit opt-in:

- **`SPEC_LOG.md` → the run ledger.** v2's committed record of work is
  `.glados/runs/` — exactly one markdown record per workflow run, written by
  a compiled epilogue no workflow can skip, checked by the `verify-ledger` CI
  backstop. A separate hand-curated spec log duplicates that; on a pure-v2
  repo the ledger is the living record and `SPEC_LOG.md` exists only for SDA
  conformance.
- **`claims.md` → leases (v2.1).** v2.0.0 ships only the always-on base-SHA
  yield rule (detect that someone else moved the branch; yield rather than
  force-push). The full "who holds what" primitive arrives in the v2.1
  coordination release as **lease files** — committed lockfiles carrying
  scope, holder, intent, and TTL, released automatically by the epilogue.
  That is `claims.md`'s job, done with enforcement. Until v2.1 lands,
  `claims.md` is the available claims mechanism.

## When you would still opt in

- **You run Wheatley.** The companion Kanban board renders its claims overlay
  from the claims file and its backlog from the SDA roadmap — see
  [wheatley.md](wheatley.md), including the path note (Wheatley reads the
  claims file under `product-knowledge/`, while init writes it at the repo
  root — keep it where Wheatley looks if you use both).
- **You have an existing SDA repo.** Projects already carrying SDA artifacts
  (v1-era GLaDOS repos, or other tooling that speaks the format) should keep
  conformance so their history and integrations stay valid; init preserves
  existing files and only adds headers.
- **You coordinate multiple agents before v2.1.** Until leases ship, a
  claims file is the documented, git-native way to say "this item is taken."
- **Other SDA tooling.** Anything that consumes the standard — boards, CI
  dashboards, cross-repo reports — keeps working because the format is
  deliberately tool-agnostic.

If none of these apply, skip it: the run ledger plus `PROJECT_STATUS.md` and
`ROADMAP.md` (all standard v2 artifacts) already cover a single-team,
single-agent project.

## Summary

| | |
|---|---|
| **Works today** | Opt-in through `/glados:init` step 3: claims file, `SPEC_LOG.md`, SDA roadmap template, `SDA: v1.0` headers, and both standards docs copied into `product-knowledge/standards/` |
| **Coming in v2.1–v2.2** | Lease files (lockfile backend) subsume `claims.md` with epilogue-enforced release; `verify-ledger` upgraded to compare emitted events against manifest claims |
| **Your responsibility** | Decide at init time (no `--sda` installer flag exists); keep SDA files current by hand or via agent instructions — no v2 compile check enforces SDA conformance; relocate `claims.md` under `product-knowledge/` if pairing with Wheatley |

See also: [wheatley.md](wheatley.md) for the board that consumes these
artifacts, and [../../MIGRATION.md](../../MIGRATION.md) for how v1 traces
convert to the run ledger.
