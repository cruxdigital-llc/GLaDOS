# Worked example: the weekly ceremonies (steward and brunch)

GLaDOS is a library of engineering workflows for AI coding agents — installed
into a project, it gives your agent slash commands that follow disciplined,
team-visible processes ([first-feature.md](first-feature.md) covers the
install). Two of those workflows are **standing ceremonies**: runs you
schedule rather than trigger, so the project stays healthy without anyone
remembering to ask.

| Ceremony | Typical day | What it is | Produces |
|---|---|---|---|
| `/glados:steward` | Saturday | The housekeeping pass | **One cleanup MR** |
| `/glados:brunch` | Sunday | The multi-reviewer critique roundtable | **One surgical fix MR** |

Each costs the team exactly one MR review per week. Session output on this
page is illustrative; commands, file paths, and scheduling recipes are real.

## Steward: the housekeeping pass

Steward keeps the project's memory honest. On one dated cleanup branch it:

1. **Compacts the run ledger.** Every workflow run commits a record to
   `.glados/runs/` (the run ledger — the project's durable memory). Steward
   folds *settled* records — runs whose linked MR is merged or closed — into
   `.glados/runs/DIGEST.md` at one line per run, then deletes the originals.
   In-flight records are left alone; when in doubt, it keeps the record.
2. **Refreshes stale documentation**, bottom-up: per-directory READMEs first,
   then the top-level README and the project status file. It updates what
   drifted and leaves accurate text alone.
3. **Promotes pending observations.** Other workflows accumulate candidate
   patterns ("we always wrap handlers in X") in a pending file. Steward
   decides each one: promote it into a written standard the review panel will
   enforce, or discard it with a one-line reason. Nothing stays pending
   without a reason.
4. **Sanity-checks the test suite.** A full run, captured for the MR's test
   plan. Breakage is *not* fixed inline — each distinct failure is filed as a
   bug (via `glados.yaml`'s `bug: [issue]` routing), because a fix on a
   housekeeping branch muddies both the fix and the cleanup.

Everything rides one MR. If nothing settled, nothing drifted, and nothing was
pending, steward skips the MR rather than manufacture one. Illustrative MR:

> **chore: weekly steward pass 2026-07-04** (!58)
> Summary: compacted 9 settled run records into DIGEST.md; refreshed
> `api/README.md` (endpoint table drifted); promoted 1 observation to
> `standards/error-envelopes.md`, discarded 2; suite green (412 passed,
> 3 skipped). Filed #219 for the flaky websocket test.

## Brunch: the critique roundtable

Brunch is the deep codebase critique steward deliberately is not. The MR is
the deliverable, not a stack of tickets — every finding is met with "can we
fix this right now?" before "should we track this for later?"

1. **Evidence pre-flight — run the thing.** Reading code is a shallow review,
   so the agent first runs every check the project supports: linters and type
   checker, the full test suite, the build, booting the stack, walking the UI
   if one exists, dependency audit, recent CI signal. The captured output is
   the **evidence bundle** every reviewer receives. A check that fails *is
   itself a finding*; if no evidence can be gathered at all, the run stops
   and escalates — a roundtable without evidence is not a brunch.
2. **Parallel reviewers.** One fresh agent per review persona (specialist
   reviewer roles defined as markdown files — the library set ships in
   `.glados/personas/`, and your own in `product-knowledge/personas/` win
   name collisions). Each reviews independently through its lens; they never
   coordinate, and disagreement is allowed.
3. **A moderator ranks and prunes.** A separate moderator persona — never
   seated as a reviewer — classifies every finding by impact × effort and
   selects the **top 1–2 "Fix Now" findings**. Everything else goes through a
   ticket-hygiene waterfall, in order: **Fix > Amend > Discard > Track**.
   Amending an existing issue beats filing a new one; most advisory findings
   are discarded with a reason; a *new* ticket must be blocking, untracked,
   genuinely worth doing, and too big to fix now — two new tickets per
   ceremony is the hard ceiling.
4. **One surgical fix MR.** The selected finding(s) get fixed on a branch —
   the finding, not the neighborhood — with the full suite green before push.
   The MR lists each finding addressed with its reviewer and severity.

Brunch also appends the moderator's discard breakdown (how many findings were
out of scope, disproportionate, or just venting, per reviewer) to the pending
observations file. Read it monthly: a persona whose findings are mostly
discarded needs tempering — that breakdown is your tuning signal.

## Scheduling the ceremonies

GLaDOS ships no scheduler, on purpose: every workflow can be invoked headless
on every supported runtime, and scheduling belongs to the project. Recipes,
consolidated from the README and PLAYBOOK — adjust days and paths to taste.

**Claude Code** — use scheduled tasks (ask Claude: "every Saturday at 09:00,
run /glados:steward in ~/work/tickets-api"), or drive headless mode from any
scheduler:

```bash
# crontab: steward Saturday 09:00, brunch Sunday 09:00
0 9 * * 6 cd ~/work/tickets-api && claude -p "/glados:steward"
0 9 * * 0 cd ~/work/tickets-api && claude -p "/glados:brunch"
```

**Gemini CLI** (Google's open-source terminal agent) — same shape; the
install for `--mode gemini` registers the commands as TOML custom commands:

```bash
0 9 * * 6 cd ~/work/tickets-api && gemini -p "/glados:steward"
```

**Google Antigravity** (Google's agentic IDE; CLI `agy`; antigravity.google)
— commands install as flat workflow files, invoked with a dash
(`/glados-steward`). Non-interactive `agy` drops stdout when not attached to
a terminal, so always request structured output to a file:

```bash
0 9 * * 6 cd ~/work/tickets-api && agy -p "/glados-steward" --output json > steward-run.json
```

**CI schedules** — any runner works, since the ceremonies only need a git
checkout and the agent CLI. GitLab: a scheduled pipeline
(CI/CD → Schedules) running a job like:

```yaml
steward:
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
  script:
    - claude -p "/glados:steward"
```

GitHub Actions: the same job under `on: schedule: - cron: "0 9 * * 6"`.

**Google AI Studio** (aistudio.google.com) — no command surface exists, so
`--mode aistudio` installs a paste-kit: self-contained workflow bundles plus
api-runner scripts that call the Gemini API directly for scheduled,
read-mostly runs; write actions are emitted as exact commands for the runner
or operator to execute.

Whatever the runtime, the result lands in the same places: one MR per
ceremony to review Monday morning, outcomes posted where `glados.yaml` routes
them, and a committed run record in `.glados/runs/` either way — even a no-op
steward pass says so on the record.

## If you knew GLaDOS v1

`consolidate`, `establish-standards`, and `recombobulate` are permanent
aliases that all route to `steward` — the v1 split is gone. See
[../../MIGRATION.md](../../MIGRATION.md).
