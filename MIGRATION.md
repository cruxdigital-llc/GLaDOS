# Migrating from GLaDOS v1.4.0 to v2.0.0

One command does the mechanical work:

```bash
python bin/glados.py migrate --target /path/to/your/project
```

It detects what v1 left in your repo, generates the one v2 configuration file
(`glados.yaml`), converts your `specs/` history into v2's run ledger, and
prints exactly what to do next. You make one human decision (the `phase:`
word, below), run the v2 installer, and commit. Budget half an hour, most of
it reading.

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

Three sentences. **First:** v1's 21 self-contained workflow instruction files
became short *cores* that describe only their distinctive work — everything
cross-cutting (the run-record epilogue, verdict vocabulary, module presence)
is compiled into the installed text from one project configuration file in
your repo, `glados.yaml` (the *manifest*). **Second:** the installer became a
compiler with a type-checker — it assembles the commands for your agent
runtime and refuses any configuration under which a result (a review verdict,
an escalation) would silently disappear. **Third:** state moved from
machine-local scratch to the *run ledger* — every workflow run writes exactly
one committed record file under `.glados/runs/`, so a fresh session resumes
from `git pull` instead of a scratchpad file that exists on one machine.

Full rationale, audit evidence, and the nine load-bearing decisions:
[docs/V2_STRATEGY.md](docs/V2_STRATEGY.md). The v2 vocabulary used below
(core, manifest, run ledger, channel) is defined in plain words in
[docs/concepts.md](docs/concepts.md).

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

## The tool

Run it from a clone of this (GLaDOS) repository, pointed at your project.
Start with `--dry-run`, which prints the full plan and writes nothing:

```bash
python bin/glados.py migrate --dry-run --target /path/to/your/project
python bin/glados.py migrate --target /path/to/your/project
```

The real run is **non-destructive by default** — it only adds files — and
**idempotent**: running it twice changes nothing the second time. Existing
files always win; the tool never overwrites anything you have.

### What it detects

The first thing `migrate` does is inventory the v1 footprint and report it:

- **v1 command layouts**, per runtime: un-namespaced command files in
  `.claude/commands/` (v1 Claude Code installs put `plan-fix.md` and friends
  directly there; v2 uses the `.claude/commands/glados/` namespace), the
  `.gemini/skills/glados/` tree (v1 Gemini CLI layout), v1 workflow files
  under `.agents/workflows/` or `.agent/workflows/` (Google Antigravity), and
  v1 workflow/module files in `product-knowledge/{workflows,modules}/` (v1
  direct mode). Only files matching the known v1 name sets count — your own
  files in shared directories are never touched.
- **`specs/` directories** — v1's per-feature trace dirs, one per piece of
  work.
- **SDA artifacts** — `claims.md`, `product-knowledge/SPEC_LOG.md`,
  `SDA: v1.0` headers — meaning the repo conforms to the Structured
  Development Artifacts format ([docs/guides/sda.md](docs/guides/sda.md)).

From the layouts it finds, it **suggests the `--mode`** for the install you
run afterwards (e.g. a repo with v1 files in `.claude/commands/` suggests
`--mode claude`).

### What it generates

**`glados.yaml`, if absent** — seeded from
[`glados.yaml.example`](glados.yaml.example) with four adjustments:

- `platform:` is auto-detected from `git remote get-url origin`
  (gitlab.com → `gitlab`, github.com → `github`; anything else keeps the
  example default with a TODO comment for you to check).
- `sda: true` is set automatically when SDA artifacts were detected, so your
  claims file and work-unit log stay maintained (see
  [SDA continuity](#sda-continuity) below).
- `phase:` is left blank as a REQUIRED-edit line. This is the one decision
  the tool refuses to make for you, and the installer fails fast until you
  fill it in — see [the `phase:` decision](#the-phase-decision) below.
- The example's explicit `decisions:` overrides (and its
  `relaxation-acknowledged:` confession) are **commented out**. The example
  writes them for its own `phase: evolving`; inherited verbatim they would
  fail a `production` or `sunset` install with relaxation errors your team
  never chose. Commented out, whichever phase you pick governs decision
  rights through its preset — any phase installs cleanly — and uncommenting
  a line later is a deliberate, confessable override.

If a `glados.yaml` already exists, `migrate` **never overwrites it** — it
reports how yours differs from the current example instead.

### What it converts

Each `specs/<dirname>/` becomes one digest record in the run ledger:

```
specs/2026-03-14-rate-limiter/  →  .glados/runs/2026-03-14-migrated-rate-limiter.md
```

The record's title comes from the directory name; the date from the
`YYYY-MM-DD` prefix if the dir has one, otherwise from the git log of the
directory (never from the wall clock — re-running next week produces the same
files). If the dir has a `README.md`, the record carries a short excerpt (its
first heading and last few lines); either way it ends with a pointer that the
full trace lives in the git history of `specs/<dirname>/`. Conversion is
create-only: an existing record with the same name wins.

When `sda: true`, each converted dir also gets one work-unit row appended to
`product-knowledge/SPEC_LOG.md` — rows already present (matched on the record
filename) are skipped, so re-runs never duplicate.

Finished work whose outcome already lives in merged MRs needs nothing more
than the digest. One case deserves manual attention afterwards: an epic still
*in flight* should get a real `epic.progress` record (ticket table,
integration branch) written on top of the digest, so `run-epic` can resume
from it.

### What it never touches

Everything the tool writes or removes is inside a fixed set of paths:
`specs/`, the v1 GLaDOS-owned command layouts listed above, `glados.yaml`,
`.glados/`, and `product-knowledge/SPEC_LOG.md`. Your source code, docs,
CI configuration, and anything else in the repo are out of bounds. Without
`--clean` it removes nothing at all.

### The `phase:` decision

`phase:` is required and has no default — an undeclared phase would mean the
compiler chose caution levels your team never stated. Guidance: **a repo with
real users declares `production`**, whatever its code quality — phase states
who gets hurt when the agent is wrong, not how proud you are of the code.
Greenfield with no users is `nascent`; opted-in early adopters is `evolving`;
a system you intend to leave is `sunset`. **The initial declaration is
ungated** — you are describing reality, not claiming progress. Only later
*transitions* between phases carry checklists: when a later install sees the
declared phase differ from the previously installed one, it prints an
advisory transition checklist to carry into the transition MR (a merge
request — GitLab's name for a pull request).

While you have the manifest open, two more keys deserve a look:

- **`channels:`** — the defaults (`verdict: mr-comment`,
  `escalation`/`bug`: `issue`) are the ones that fix v1's trace-only-outcome
  failures. Weaken them only with the explicit
  `visibility-acknowledged: ledger-only` confession line.
- **CODEOWNERS** — protect the manifest so a phase change is always a
  human-approved MR (agents may *propose* a phase change, never merge one):

  ```
  # .gitlab/CODEOWNERS (GitLab) or .github/CODEOWNERS (GitHub)
  /glados.yaml @your-team-leads
  ```

  `glados doctor` reports whether a CODEOWNERS file exists and covers
  `glados.yaml` (informational — it never fails the doctor run).

### Then: install, commit, optionally clean

1. **Fill `phase:`** in the generated `glados.yaml`.
2. **Run the installer** with the mode `migrate` suggested:

   ```bash
   python bin/glados.py install --mode <suggested> --target /path/to/your/project
   ```

   It compiles cores + modules + vocabulary against your manifest, runs the
   registry and sink checks, stamps the manifest hash, and prints the
   assembly report — read it; it shows the provenance of every resolved value
   and flags any phase-derived relaxations. The install also cleans the v1
   command layout for the mode it installs (only known v1 files — never your
   own).
3. **Commit** — `glados.yaml`, `.glados/`, the converted run records, the
   SPEC_LOG rows, and the removed v1 files, in one migration commit.
4. **Optionally `migrate --clean`** — re-run with `--clean` to remove the
   converted `specs/` dirs and any v1 command layouts the install didn't
   already clean (layouts for modes you didn't install). `--clean` removes a
   `specs/` dir only after verifying its converted record exists. Without
   `--clean`, the report lists what install will clean and what you may
   delete by hand — deleting `specs/` is recommended either way: nothing in
   v2 updates it, and a stale tree that looks authoritative is worse than
   absence. Its git history survives deletion.

## Worked example

A realistic v1 repo — Claude Code install, SDA-conformant, two specs dirs:

```
acme-api/
├── .claude/commands/            # v1 layout: un-namespaced command files
│   ├── plan-fix.md
│   ├── implement-fix.md
│   └── … (19 more)
├── claims.md                    # SDA artifacts
├── product-knowledge/
│   ├── SPEC_LOG.md
│   ├── ROADMAP.md               # carries the <!-- SDA: v1.0 --> header
│   └── standards/
├── specs/
│   ├── 2026-03-14-rate-limiter/
│   │   └── README.md
│   └── 2026-05-02-webhook-retries/
│       ├── README.md
│       └── notes.md
└── src/ …
```

The dry-run prints the full plan without writing (file listings shortened
here with `…`; the tool prints every path):

```
$ python bin/glados.py migrate --dry-run --target ../acme-api
glados migrate — /home/you/acme-api (dry-run: nothing is written)

== detected ==
  v1 layout [claude]: 21 file(s)
    - .claude/commands/address-review.md
    - .claude/commands/adopt-codebase.md
    … (19 more)
  specs/ directories: 2
    - specs/2026-03-14-rate-limiter
    - specs/2026-05-02-webhook-retries
  SDA artifacts: claims.md, product-knowledge/SPEC_LOG.md, product-knowledge/ROADMAP.md (SDA header)
  suggested install mode: claude

== manifest ==
  glados.yaml: absent — would generate from glados.yaml.example:
    - platform: gitlab (auto-detected from the origin remote)
    - sda: true (SDA artifacts detected)
    - phase: left REQUIRED — install fails fast until a human picks one
    - decisions: example overrides commented out — your phase's preset governs (uncomment to override)

== convert specs/ ==
  specs/2026-03-14-rate-limiter/ -> .glados/runs/2026-03-14-migrated-rate-limiter.md (would create)
  specs/2026-05-02-webhook-retries/ -> .glados/runs/2026-05-02-migrated-webhook-retries.md (would create)
  product-knowledge/SPEC_LOG.md: would append 2 work-unit row(s)

== cleanup ==
  nothing removed (non-destructive default); removable once migrated:
    - specs/2026-03-14-rate-limiter/ (converted to .glados/runs/2026-03-14-migrated-rate-limiter.md)
    - specs/2026-05-02-webhook-retries/ (converted to .glados/runs/2026-05-02-migrated-webhook-retries.md)
    - .claude/commands/address-review.md (v1 claude layout)
    … (20 more)
  note: `install --mode <m>` cleans the v1 layout of its own mode; `migrate --clean` removes all of the above

== next steps ==
  1. edit glados.yaml — set phase: (one of: nascent, evolving, production, sunset)
  2. python glados.py install --mode claude --target /home/you/acme-api
  3. commit the migrated tree
  4. re-run: python glados.py migrate --target /home/you/acme-api --clean (removes the converted specs/ dirs and v1 layouts)

glados migrate (dry-run): would convert 2 spec dir(s), generate 3 file(s), append 2 SPEC_LOG row(s)
```

The real run writes those files. The generated `glados.yaml` reads (comment
blocks carried over from the example elided):

```yaml
glados: 2

platform: gitlab            # gitlab | github (auto-detected from the origin remote)

# REQUIRED — no default. The team states its intent in one word.
# nascent | evolving | production | sunset
phase: # REQUIRED - pick one: nascent | evolving | production | sunset (who gets hurt when the agent is wrong; see MIGRATION.md)

# NOTE(migrate): the example's explicit decision overrides are commented out
# so whichever phase: you pick governs them (see the presets in
# .glados/presets.yaml after install). Uncomment a line only to override
# your phase deliberately - a laxer value then needs relaxation-acknowledged.
# decisions:
#   schema-migration: record
#   public-api-break: record
#   new-dependency: agent
#   delete-code: agent
#   destructive-data-op: escalate
```

A converted run record — `.glados/runs/2026-03-14-migrated-rate-limiter.md`:

```markdown
# Migrated spec: 2026-03-14-rate-limiter

- Converted from `specs/2026-03-14-rate-limiter/` by `glados.py migrate` (v1 -> v2).
- Date: 2026-03-14 (from the directory name).
- The full history lives in git: `git log -- specs/2026-03-14-rate-limiter` — the specs/ tree can be deleted after migration (migrate --clean does it).

## Excerpt (from `specs/2026-03-14-rate-limiter/README.md`)

# Rate limiter — spec

[...]

Token-bucket rate limiting for the public API.

## Decision

Bucket per API key: 100 req/min sustained, burst of 20.

## Outcome

Shipped in MR !58; tuning follow-up tracked in #214.
```

And `product-knowledge/SPEC_LOG.md` gains one row per converted dir:

```
| 2026-05-02 | migrate | specs/2026-05-02-webhook-retries | migrated | .glados/runs/2026-05-02-migrated-webhook-retries.md |
| 2026-03-14 | migrate | specs/2026-03-14-rate-limiter | migrated | .glados/runs/2026-03-14-migrated-rate-limiter.md |
```

Then the human steps: set `phase: production` (acme-api has real users), run
the install, read the assembly report, commit:

```
$ python bin/glados.py install --mode claude --target ../acme-api
glados: installed mode 'claude' into /home/you/acme-api
glados: 15 cores, manifest 92c59ca6fa61…
glados: cleaned 21 stale file(s): .claude/commands/adopt-codebase.md, …
```

A final `migrate --clean --target ../acme-api` removes the two converted
`specs/` dirs; the install already cleaned the 21 v1 command files.

## What does NOT migrate automatically

- **`PROJECT_STATUS.md` free-form sections.** If your v1 repo keeps a status
  document, reshaping its prose into the v2 template's sections
  ([src/templates/PROJECT_STATUS.md](src/templates/PROJECT_STATUS.md)) is a
  human editing job — the tool won't rewrite your prose. Machine-local
  scratchpad epic files (e.g. an `EPIC_PROGRESS.md` in an agent scratchpad)
  should simply be deleted once their epic has a ledger record: nothing in v2
  updates them.
- **CI enablement.** The installer vendors the CI templates (the drift/type
  `check` job plus the `verify-ledger` backstop) into `.glados/ci/` — both
  the GitLab and GitHub variants — and prints the enable stanza, but the
  project owns turning the check on: on GitLab, add
  `include: [{ local: .glados/ci/glados-check.gitlab-ci.yml }]` to your
  `.gitlab-ci.yml`; on GitHub, copy
  `.glados/ci/glados-check.github-actions.yml` into `.github/workflows/`.
  The check job ships `--report-only`; drop that flag once it's proven quiet
  (recommended when entering `production`). Then run `glados doctor` — it
  reports whether the check is actually wired, because a check that's
  declared but never runs is exactly the silent failure v2 exists to kill.
- **Host-agent guard hooks.** The compiled epilogue is a promise kept by an
  LLM at 90% context; the hooks make it mechanical — the Claude Code
  Stop-hook, the AfterAgent guard for Gemini CLI, or the Stop hook in
  `.agents/hooks.json` for Google Antigravity's `agy`. Per-runtime setup
  recipes live in [hooks/README.md](hooks/README.md). CI `verify-ledger`
  remains the universal backstop, so the hooks are belt-and-suspenders —
  recommended, not required.

## SDA continuity

If your v1 repo carries SDA artifacts, `migrate` notices and sets `sda: true`
in the generated manifest, so nothing about your conformance lapses: the
artifacts carry over as-is (install scaffolding is create-only and never
clobbers), every converted `specs/` dir is logged as a work unit in
`SPEC_LOG.md`, and every v2 run resumes maintaining the claims file and
work-unit log. The v2 profile —
[docs/standards/sda-profile-glados-v2.md](docs/standards/sda-profile-glados-v2.md)
— declares `.glados/runs/` records the conforming work-unit equivalent of
v1's `specs/` dirs. See [docs/guides/sda.md](docs/guides/sda.md).

## Rollback

Nothing destructive happens without `--clean`, so before that flag the
rollback is: delete the generated files (`glados.yaml` if you didn't have
one, `.glados/`, the appended SPEC_LOG rows) — or, if you already committed,
`git revert` the migration commit. After `--clean`, the removed `specs/` dirs
and v1 command files are still one `git revert` (or `git checkout <sha> --
specs/`) away — everything the tool deletes is tracked content whose history
git keeps. Your v1 install keeps working until the moment you run the v2
installer, and even then the alias shims keep every old name answering.

## That's it

Old names keep working (shims), old installs keep working (until you
reinstall), the tool does the file shuffling, and the first `verify-ledger`
run gives you the baseline dashboard that tells you whether the migration
actually closed the loop.
