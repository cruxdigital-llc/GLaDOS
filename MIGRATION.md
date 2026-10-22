# Migrating from GLaDOS v1.4.0 to v2.0.0

Already on v2 and upgrading to 2.5? Skip to
[Upgrading a v2 install to 2.5](#upgrading-a-v2-install-to-25).

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
one record file under `.glados/runs/` and saves it to the `glados/ledger`
branch, so a fresh session resumes from that branch instead of a scratchpad
file that exists on one machine.

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
`.glados/`, `product-knowledge/SPEC_LOG.md`, and the one `/.glados/runs/*`
line it adds to the clone's git exclude file. Your source code, docs,
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
3. **Commit** — `glados.yaml`, `.glados/`, the SPEC_LOG rows, and the
   removed v1 files, in one migration commit. It takes no converted run
   record: `migrate` added `/.glados/runs/*` to the clone's git exclude
   file. Then save the records to the run ledger, the `glados/ledger`
   branch, with `python .glados/glados.py ledger save`.
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
glados: 16 cores, manifest 92c59ca6fa61…
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

## Upgrading a v2 install to 2.5

2.5 adds one workflow, `run-pipeline`, which runs the project's own
workflows (declared under `pipelines:`; see
[docs/guides/pipelines.md](docs/guides/pipelines.md)). It is enabled by
default, even with no `pipelines:` declared. Some manifests need a look
before you reinstall:

- **An explicit `disabled-workflows:` list.** Your list replaces the phase
  preset's list, so the sunset preset's new entry for `run-pipeline` does not
  reach it, and `run-pipeline` arrives enabled. A sunset project, or any
  project that disables `build-feature`, adds `run-pipeline` to its own list
  (with no pipelines declared, run-pipeline falls back to build-feature's
  stages).
- **`run-epic` and `build-feature` both disabled, `run-pipeline` left
  enabled, and no `branching.default-target`.** A list such as
  `[build-feature, run-epic]` installed on 2.4. run-pipeline reads the
  epic's integration branch and falls back to `branching.default-target`
  outside an epic, so install and check now fail with "state key
  'epic.integration-branch' is read by [run-pipeline] but no enabled writer
  covers it". Set `branching.default-target`, or add `run-pipeline` to
  `disabled-workflows:`.
- **A `decisions:` value that is not a decision class.** Every value must
  be one of `agent`, `record`, `escalate` or `forbidden`. 2.4 ignored any
  other value (`vendor-choice: ask`); 2.5 fails install and check on it,
  naming the key.
- **A loop bound that is not a whole number.** Every `max-cycles` under
  `params:` must be a whole number of 1 or more. 2.4 installed `"5"`,
  `true`, a list or `0`, leaving the loop no count to stop at; 2.5 fails
  install and check on it, naming the key and where the value came from,
  and a workflow that reads one at run time escalates instead of starting
  the loop. A `params:` entry written as a value instead of a mapping
  (`pipeline: 5`), which 2.4 ignored, fails the same way.
- **A `- key: value` list item.** It now reads as a mapping, as standard
  YAML does, where 2.4 read it as the string `'key: value'`. Lists of
  workflow or module names (`disabled-workflows:`, `default-modules:`,
  `workflows:`) reject a mapping with an error naming the key; anywhere
  else the value just changes shape. Quote the item (`- "key: value"`) if
  you meant the string.
- **A quoted key.** `"max-cycles": 3` now sets `max-cycles`, as standard
  YAML does. 2.4 kept the quotes, so the value went under a key nothing
  read, and none of the checks on `max-cycles` (or on a decision right
  written the same way) saw it. A quoted key beside its plain spelling is
  now a duplicate key.
- **YAML that 2.4 read differently from YAML.** The toolchain reads
  `glados.yaml`, the preset table and frontmatter as a YAML subset, and the
  agent reads them as YAML. 2.4 kept syntax it did not know as text, so
  `&a max-cycles: true`, `!!str max-cycles: true`, `"max\x2Dcycles": true`
  and a `<<:` merge key were each a key nothing checked while YAML reads
  max-cycles. 2.5 decodes every YAML escape in double quotes and refuses,
  naming the line: anchors, aliases and tags; merge keys; `?` keys; a key
  YAML reads as a null, bool, number or date (`null:`, `1:`, `yes:`; quote
  it if it is a name); a key holding a character that does not show (`\0`,
  a zero-width space); a tab outside quotes; text after a closing quote;
  `key:value` with no space (YAML reads it as one string); `: ` inside an
  unquoted value; an integer with a leading zero (`010`, octal to some
  readers); a block scalar with an indentation number (`|2`); an unknown
  escape (`\q`); and lines left of the first line, which 2.4 dropped. Quote
  the value, or write it plainly.

Two changes print a warning and fail nothing. A top-level key GLaDOS does
not read (usually a typo, such as `sinsk:`) is named at install, check and
validate, and listed by doctor. A `params:` key nothing reads (`max_cycles:`,
or a `run-pipeline:` namespace), which leaves the inherited value in force,
is named at install, check and validate with the keys that are read.

Check the manifest with the 2.5 toolchain before you reinstall. The
vendored `.glados/glados.py` is still the 2.4 one until you do, and it has
no `validate`, so run it from your new GLaDOS checkout:

```bash
python /path/to/GLaDOS/bin/glados.py validate --target /path/to/your/project
```

It reports every failure above without installing anything. After the 2.5
install, `python .glados/glados.py validate --target .` works too. The
explicit-list case is silent: check your list by hand.

Until you reinstall, a 2.5 `check` or `doctor` reports the 2.4 install as
stale: 2.5 fingerprints only the structural keys of `glados.yaml`, so the
hash the 2.4 install recorded no longer matches. Both say the install was
built by 2.4.0 and needs a reinstall. Plugin-only repos that copied
`hooks/claude-stop-hook.py` (see
[docs/getting-started/claude-plugin.md](docs/getting-started/claude-plugin.md))
copy it again: the 2.5 hook also checks the runs nested inside a run.

2.5 also adds `canon:`, the reference works a team follows (see
[docs/guides/canon.md](docs/guides/canon.md)). It is optional and changes
nothing until you declare it; install now creates an empty
`product-knowledge/canon/`. Five of the workflows that consult canon
(plan-feature, spec-feature, verify-feature, review-mr and run-pipeline) now
also emit `observation`, for a canon conflict; review-codebase and brunch
already did. Every preset binds it to the ledger, so
only a manifest that sets `observation: []` under `channels:` needs a sink
for it.

**Run records move to the ledger branch.** From 2.5, every run saves its
record and step artifacts to the `glados/ledger` branch with
`python .glados/glados.py ledger save`, and none goes on a work branch, so a
merge request's diff is the change; review-mr and address-review already
did this. The 2.5 install, like every `ledger` command, adds
`/.glados/runs/*` to the clone's git exclude file (`.git/info/exclude`), so
committing the reinstalled `.glados/` takes no record, and nothing is
committed for it. Nothing is migrated or rewritten. Records your branches
already carry stay there as history; a save does not copy them and a restore does
not overwrite them. A `glados/ledger` branch that already exists (cut from
the main line, as review-mr's commits made it) is built on as it is. The
vendored CI templates now fetch the ledger branch before `verify-ledger`
scans it (GitLab), and on a merge request `verify-ledger` lists any run
record the branch commits. Two things to do by hand:

- If the ledger branch is checked out in a worktree, remove that worktree
  (`git worktree remove <path>`): `ledger save` refuses to move a branch
  under a checkout.
- Plugin-only repos that copied the guard hooks copy them again: they now
  check that a run's record is saved to the ledger, not committed, and a
  run marker they cannot read (or `.glados/runs/` they cannot list) blocks
  the session end instead of counting as no record.

**GLaDOS marks what it posts on a merge request.** From 2.5, everything a
run posts on a merge request starts with `(GLaDOS <workflow>)`, and
review-mr and address-review read a note or reply without it, written by
someone with a role on the project, as that person's review, whichever
account posted it. Notes GLaDOS posted before the upgrade carry no marker.
On a merge request opened before you upgrade, edit each GLaDOS note so its
first line starts with `(GLaDOS <workflow>)` before running review-mr or
address-review on it: resolving its thread does not change how it is read.
