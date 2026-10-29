# Worked example: your first feature, from empty config to merged change

GLaDOS is a library of engineering workflows for AI coding agents. You install
it into a project, and it compiles a set of slash commands (like
`/glados:build-feature`) tailored to that project's configuration. When your
agent runs one, it follows a disciplined, team-visible process — reviews get
posted, decisions get recorded, every run leaves a record on the repo's
`glados/ledger` branch — instead of improvising. This walkthrough takes a fictional project
(`~/work/tickets-api`, a small GitLab-hosted Python service) from no GLaDOS at
all to a merged feature. Command lines are real; the install output was
captured from a real run. Output from the agent sessions is illustrative —
your agent's wording will differ, but the shape and the artifacts are what
the workflows require.

## 1. Create the manifest

The manifest is `glados.yaml`, a single configuration file in your project
root. It declares things every workflow needs to know: which platform you are
on (GitLab or GitHub), who is allowed to merge, and where each kind of outcome
(a review verdict, a bug, an escalation) should be posted so the team sees it.

```bash
git clone https://github.com/your-org/GLaDOS ~/work/GLaDOS
cp ~/work/GLaDOS/glados.yaml.example ~/work/tickets-api/glados.yaml
```

Open it and check three keys:

- `platform: gitlab` — the agent will use GitLab tooling (`glab`) for MRs and
  issues.
- `phase:` — required, no default. One word (`nascent | evolving | production
  | sunset`) stating who gets hurt when the agent is wrong. A repo with real
  users is `production`, whatever the code looks like. We'll keep `evolving`.
- `channels:` — routing rules from outcome type to destination. The defaults
  (`verdict: [mr-comment]`, `escalation: [issue]`, `bug: [issue]`) are what
  make the process team-visible; leave them.

## 2. Install

Run the compiler from your GLaDOS checkout, pointed at your project:

```bash
cd ~/work/GLaDOS
python bin/glados.py install --mode claude --target ~/work/tickets-api
# modes: claude | claude-plugin | direct | gemini | antigravity | aistudio | pi
```

This compiles the workflow sources against your manifest and writes slash
commands into `.claude/commands/glados/` (for `--mode claude`; other modes
write their runtime's equivalent). It also prints an **assembly report** —
every configuration value it resolved and where the value came from. Captured
from a real install (trimmed):

```
glados: installed mode 'claude' into /home/you/work/tickets-api
glados: 16 cores, manifest d23f47f077c4…
glados: added /.glados/runs/* to the clone's git exclude file — run records go to the glados/ledger branch, never in a commit

# GLaDOS assembly report

- phase: `evolving`
- enabled cores: 16 / 16

| Key | Value | Provenance |
|-----|-------|------------|
| phase | evolving | (explicit) |
| platform | gitlab | (explicit) |
| merge-authority | human | (explicit) |
| channels.verdict | [mr-comment] | (explicit) |
| params.review-panel.max-cycles | 5 | (explicit) |
...
## RELAXED(phase) markers: 1

Values the phase preset relaxes below the strict baseline:

- RELAXED(phase) `pipeline-discretion` = `agent`
```

("Cores" is the compiler's word for the workflow source files — 16 cores
compile into 16 commands; [concepts.md](../concepts.md) has the full
vocabulary.) Read the report — it shows what the configuration traded away
*before* the first run, not after the first incident. Commit everything it
generated. The run records never are: that exclude line keeps
`.glados/runs/` out of every commit, and each run saves its record to the
`glados/ledger` branch.

## 3. Establish intent

A brand-new project starts with `/glados:intent` (in Claude Code; Gemini CLI
— Google's open-source terminal agent — uses the same `/glados:intent` form;
Google Antigravity, Google's agentic IDE at antigravity.google with CLI
`agy`, and pi use `/glados-intent`).
It interviews you — because planning workflows treat its output as ground
truth, and a missing mission makes every later plan a guess. Expect four
questions, each becoming a section of `product-knowledge/MISSION.md`:

| It asks | Pins down |
|---|---|
| What specific problem or pain does this address? | Problem |
| Who are the primary users? | Audience |
| What is the core solution, and what makes it distinct? | Solution |
| What is this product deliberately *not*? | Non-goals |

It also writes a roadmap with *Now / Next / Later* horizons; *Now* items are scoped tightly enough to build directly.

## 4. Build the feature

```
/glados:build-feature add rate limiting to the public ticket-creation endpoint
```

One command runs four stages in sequence, each a workflow of its own. Between
them sit gates — checkpoints the agent is not allowed to skip:

1. **Plan** — goals, success criteria, non-goals, approach, and the roster of
   review personas (specialist reviewer roles, defined as files) that will
   later judge the work. *Why: deciding who reviews before writing code stops
   the author from picking friendly judges afterward.*
2. **Spec** — requirements plus a technical spec (data models, API contracts,
   edge cases), checked against the project's written standards. *Why: a
   contract problem caught here is a text edit, not a rewrite.*
3. **Implement** — the code and tests, on a branch named per the manifest's
   `branching.feature` pattern (`feat/rate-limit-ticket-creation`).
4. **Verify** — a **fresh evaluator**: a separate agent session with no memory
   of how the code was written runs the tests, exercises the app, and judges
   each acceptance criterion. *Why: the agent that wrote the code is
   predisposed to approve it.*

The **verified-before-MR gate** then holds: no merge request is opened until
verification passes (bounded by `params.evaluator.max-cycles` in the
manifest — on failure past the bound, the run stops and posts an escalation
issue instead, because an unverified MR is worse than no MR). Then the agent
opens the MR with `glab`, self-reviews its own diff as a critic, and hands
off to the review loop. It never merges — `merge-authority: human` says only
you do.

## 5. The review loop

```
/glados:review-mr
```

This seats an adversarial review panel: one fresh agent per persona (standing
lenses like UAT, Adversarial, and Standards, plus the roster from step 4),
all briefed to break the change, all running in parallel. Each returns a
verdict — `APPROVE | REQUEST_CHANGES | ESCALATE` — with findings classified
`blocking` or `advisory`. The composed verdict is posted **as an MR comment**
(that is your `channels.verdict` binding at work). Its first line starts with
`(GLaDOS review-mr)`, the marker review-mr and address-review use to tell
GLaDOS's notes from people's. It leads with the verdict and lists what has
to change, one line per blocking finding; the evidence sits folded beneath,
and which lens raised a finding is a one-line roll-call at the end.
Illustrative:

> (GLaDOS review-mr) **REQUEST_CHANGES** · 1 blocking · cycle 1 · `9e4d2b1`
>
> 1. `limiter.py:41`: keep the rate window in shared state, so a restart or
>    a second worker cannot reset it.
>
> <details><summary>1. `limiter.py:41`: keep the rate window in shared state, so a restart or a second worker cannot reset it.</summary>
>
> The window lives in process memory: a restart resets it, and two workers
> each allow the full rate.
>
> </details>
>
> Advisory: extract the window constant.
>
> UAT ✓ · Adversarial ✗ · Standards ✓ · Philosophy ✓ · Dead-code ✓ · architect ✓

Each panelist's brief carries inputs, never the author's conclusions: the
diff; the ticket and anything a person said, in the session or on the MR,
quoted as theirs; and the plan, spec and MR description, labelled as the
author's and reviewed like the code. Only a criterion the ticket or a person
set can block as unmet; one the author derived is design under review.

Your own notes on the MR count as review. A note or reply whose first line
does not start with `(GLaDOS <workflow>)`, from someone with a role on the
project, is read as that person's, and a new point of yours starts a new
round of cycles. address-review must meet each point or answer it on the MR
in the open ("your words say X; the code shows Y; I propose Z"), and a
`blocking` point of yours closes only when the change meets it or you
withdraw or waive it in your own words.

A dirty pass hands off to `/glados:address-review`, which fixes every open
finding in one coherent pass, runs the tests the fixes touch, pushes (the
merge request's pipeline runs the full suite), and maps each finding to its
resolution (fixed, with the commit — or declined, with a one-line reason).
Then `/glados:review-mr` runs again against the new commit.
The loop repeats until the MR is review-clean, a fix pass commits nothing,
or the cycle bound (`params.review-panel.max-cycles: 5`, a whole number of 1
or more written unquoted: install, `check` and `validate` reject `0`, `"5"`,
`true` or a list) stops it with an escalation. *Why the
bound: an infinite argue-with-the-panel loop burns budget and hides a
disagreement a human should settle.* On approval, you merge.

## 6. What the run ledger shows

Every run leaves exactly one markdown record, saved from `.glados/runs/` to
the `glados/ledger` branch — the **run ledger**, the project's durable memory
of what ran and why. Runs nest: build-feature runs plan-feature,
spec-feature, implement-feature and verify-feature as runs of their own, so
this feature leaves a record for build-feature and one for each stage, and
build-feature's lists the stage records under `## Nested runs`.
Illustrative but shape-accurate:

```bash
$ cat .glados/runs/2026-07-03-build-feature-rate-limit.md
# build-feature: rate-limit-ticket-creation  (2026-07-03)
- base-sha: 4f2c91ab
- plan: roster [architect] + standing lenses; risk: shared limiter state
- decision (agent): new dependency `limits==3.x` — reversible, no schema
- verify: cycle 1 REQUEST_CHANGES (test gap), cycle 2 APPROVE
- MR: !47 opened, target main; self-review: 1 advisory (fixed, a1b9c30)
- outcomes: progress→ledger, verdict→!47 comment

## Nested runs
- .glados/runs/2026-07-03-plan-feature-rate-limit.md
- .glados/runs/2026-07-03-spec-feature-rate-limit.md
- .glados/runs/2026-07-03-implement-feature-rate-limit.md
- .glados/runs/2026-07-03-verify-feature-rate-limit.md
```

Because the record is saved to the `glados/ledger` branch, a teammate or a fresh agent session resumes from it (`glados.py ledger restore`), not from someone's chat transcript.

## Where next

- [fix-a-bug.md](fix-a-bug.md) — the same discipline applied to a bug report.
- [weekly-ceremonies.md](weekly-ceremonies.md) — the standing housekeeping
  and critique passes, and how to schedule them.
- [../../PLAYBOOK.md](../../PLAYBOOK.md) — adoption cadence and team rollout.
