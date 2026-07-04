# Using GLaDOS with Wheatley

Wheatley is GLaDOS's companion project board: a lightweight, local-first Kanban board that uses a
GLaDOS-managed repo's markdown files as its database. No external service, no
syncing, no separate state — **the repo is the board**. It runs as a Docker
container, either mounted over your local checkout (sidecar mode) or pointed
at a remote repo via the GitHub/GitLab API (cloud mode), and serves the board
at `http://localhost:3000`.

This guide explains what Wheatley reads, what still works on a GLaDOS v2
project, and — honestly — what does not work yet.

## What Wheatley reads

Wheatley renders columns (**Unclaimed → Planning → Speccing → Implementing →
Verifying → Done**) from four artifacts:

| Artifact | Feeds |
|---|---|
| `product-knowledge/ROADMAP.md` | Unclaimed items (the backlog) |
| `specs/` directories | In-flight features and their current phase |
| `product-knowledge/PROJECT_STATUS.md` | Active tasks |
| `product-knowledge/claims.md` | Who is working on what |

Task claiming is atomic because claims are git commits — git itself resolves
contention between two people (or agents) grabbing the same card.

One path wrinkle: Wheatley's server reads the claims file at
`product-knowledge/claims.md`, while the GLaDOS init skill's SDA opt-in (see
[sda.md](sda.md)) writes `claims.md` at the repo root. If you use both, keep
the claims file where Wheatley looks — under `product-knowledge/`.

## What works on a GLaDOS v2 project today

Two of the four inputs are alive and well in v2:

- **`product-knowledge/PROJECT_STATUS.md`** — every v2 install scaffolds it,
  and the `steward` workflow (the standing housekeeping pass) refreshes it.
  The *active tasks* view works.
- **`product-knowledge/ROADMAP.md`** — the `intent` workflow (the core that
  establishes or refreshes the product mission and roadmap) creates and
  maintains it. The *unclaimed / backlog* column works.

So on a pure-v2 repo, Wheatley is a useful roadmap-and-status viewer.

## The honest compatibility gap

The other two inputs are v1 artifacts that v2 deliberately retired:

- **`specs/` is gone.** v1 wrote a per-feature trace directory under
  `specs/`; v2 replaced that with the **run ledger** — exactly one committed
  record per workflow run under `.glados/runs/`. The v2 migration guide
  ([MIGRATION.md](../../MIGRATION.md), steps 3–4) explicitly converts live
  `specs/` dirs into ledger entries and then deletes the tree. Wheatley reads
  `specs/`, so its *in-flight* columns (Planning through Verifying) are empty
  on a v2 repo.
- **`claims.md` is SDA-opt-in only.** v2 does not create a claims file unless
  you enabled SDA conformance during init (and v2's actual concurrency answer
  is the base-SHA yield rule now, leases later). Without it, the *who's
  working on what* overlay is empty.

Net effect: **on a pure-v2 repo, Wheatley shows the backlog and active status
but no in-flight or claims cards.** Nothing breaks — the columns are just
empty, because the files they read no longer exist.

## Direction, not shipped

The intended reconciliation pairs Wheatley's v2 support with the GLaDOS
**v2.1 coordination release**:

- v2.1 introduces the **lease module** (lockfile backend): a lease is a
  committed file saying *who* holds *what scope*, with an intent and a TTL —
  which is precisely what `claims.md` encoded. Lease files become the claims
  column's data source.
- `.glados/runs/` becomes the in-flight data source: the run ledger already
  records which workflow (plan, spec, implement, verify) each run executed,
  which is the phase information Wheatley used to infer from `specs/`
  directory contents.

Treat this as direction: none of it is shipped in Wheatley or in GLaDOS
v2.0.0 today. If you need full board columns right now, the supported path is
enabling SDA conformance (claims file + SDA roadmap) via the init skill — see
[sda.md](sda.md).

## Summary

| | |
|---|---|
| **Works today** | Backlog column from `product-knowledge/ROADMAP.md` (maintained by the `intent` workflow); active tasks from `product-knowledge/PROJECT_STATUS.md`; full board on repos with SDA opt-in artifacts |
| **Coming in v2.1–v2.2** | Wheatley reading v2.1 lease files as claims and `.glados/runs/` as in-flight state — stated direction, not shipped in either project |
| **Your responsibility** | Run Wheatley (Docker) and mount/point it at the repo; keep `claims.md` under `product-knowledge/` if you use SDA + Wheatley together; don't expect in-flight/claims columns on a pure-v2 repo |

See also: [sda.md](sda.md) for the opt-in artifacts Wheatley reads, and
[../../MIGRATION.md](../../MIGRATION.md) for why v2 retired `specs/`.
