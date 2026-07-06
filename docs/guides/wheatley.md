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
`product-knowledge/claims.md`, while GLaDOS's SDA support (see
[sda.md](sda.md)) scaffolds and writes `claims.md` at the repo root. If you
use both, keep the claims file where Wheatley looks — under
`product-knowledge/`.

## What works on a GLaDOS v2 project today

Three of the four inputs are alive and well in v2:

- **`product-knowledge/PROJECT_STATUS.md`** — every v2 install scaffolds it,
  and the `steward` workflow (the standing housekeeping pass) refreshes it.
  The *active tasks* view works.
- **`product-knowledge/ROADMAP.md`** — the `intent` workflow (the core that
  establishes or refreshes the product mission and roadmap) creates and
  maintains it. The *unclaimed / backlog* column works.
- **The claims file — when `glados.yaml` sets `sda: true`.** SDA conformance
  is a first-class manifest key in v2: install scaffolds `claims.md`, and the
  compiled preamble/epilogue of every workflow record a claim before mutating
  and clear it at run end. The *who's working on what* overlay works, and
  stays current by construction rather than by convention. (Mind the path
  wrinkle above.)

So on a v2 repo with `sda: true`, Wheatley is a useful
backlog-status-and-claims viewer.

## The honest compatibility gap

One input is a v1 artifact that v2 deliberately retired, and one setting is
still required:

- **`specs/` is gone.** v1 wrote a per-feature trace directory under
  `specs/`; v2 replaced that with the **run ledger** — exactly one committed
  record per workflow run under `.glados/runs/`. The v2 `migrate` command
  ([MIGRATION.md](../../MIGRATION.md)) converts live `specs/` dirs into
  ledger entries, and its `--clean` flag deletes the tree. Wheatley reads
  `specs/`, so its *in-flight* columns (Planning through Verifying) are empty
  on a v2 repo. Closing this needs Wheatley-side work (reading
  `.glados/runs/`) planned alongside the GLaDOS v2.1 coordination release —
  not shipped in either project.
- **`claims.md` exists only when `sda: true`.** The key is explicit-only and
  defaults to false; without it, v2's concurrency answer is the invisible
  base-SHA yield rule and the claims overlay is empty.

Net effect: **on a v2 repo the in-flight columns are empty, and the claims
overlay is empty unless `sda: true`.** Nothing breaks — a column whose source
file doesn't exist just renders empty.

## Direction, not shipped

The intended reconciliation pairs Wheatley's v2 support with the GLaDOS
**v2.1 coordination release**:

- v2.1 introduces the **lease module** (lockfile backend): a lease is a
  committed file saying *who* holds *what scope*, with an intent and a TTL.
  When `sda: true`, the lockfile backend will write `claims.md`-compatible
  entries — the claims file becomes a view over enforced leases instead of a
  kernel-prose convention.
- `.glados/runs/` becomes the in-flight data source: the run ledger already
  records which workflow (plan, spec, implement, verify) each run executed,
  which is the phase information Wheatley used to infer from `specs/`
  directory contents.

Treat this as direction: none of it is shipped in Wheatley or in GLaDOS
v2.0.0 today. What ships today is the claims overlay via `sda: true` — see
[sda.md](sda.md).

## Summary

| | |
|---|---|
| **Works today** | Backlog column from `product-knowledge/ROADMAP.md` (maintained by the `intent` workflow); active tasks from `product-knowledge/PROJECT_STATUS.md`; claims overlay on repos with `sda: true` (kernel-maintained `claims.md` — keep it under `product-knowledge/` for Wheatley) |
| **Coming in v2.1–v2.2** | The lease lockfile backend writing `claims.md`-compatible entries when `sda: true`; Wheatley reading `.glados/runs/` as in-flight state — stated direction, not shipped in either project |
| **Your responsibility** | Run Wheatley (Docker) and mount/point it at the repo; set `sda: true` if you want the claims overlay; keep `claims.md` where Wheatley looks; don't expect in-flight columns on a v2 repo yet |

See also: [sda.md](sda.md) for the `sda:` key and the artifacts Wheatley
reads, and [../../MIGRATION.md](../../MIGRATION.md) for why v2 retired
`specs/`.
