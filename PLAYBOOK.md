# GLaDOS Playbook

A practical guide to adopting GLaDOS in your project and your team — from first install to steady-state operations. New here? The [README](README.md) and [docs/getting-started/](docs/getting-started/) cover what GLaDOS is and how to install it from zero; this playbook assumes that much and focuses on adopting it well.

> **Note**: Invocation syntax varies by runtime. `intent` is invoked as `/glados:intent` in Claude Code, `/glados:intent` in Gemini CLI (Google's open-source terminal agent; installed as TOML commands), `/glados-intent` in Google Antigravity (Google's agentic IDE; CLI `agy`; antigravity.google; flat workflow files, name-prefixed), and `/glados-intent` in pi (the minimal terminal coding agent; prompt templates in `.pi/prompts/`, name-prefixed). Google AI Studio (aistudio.google.com) has no command surface — you paste the workflow's self-contained bundle into the conversation. This guide uses bare command names for readability.

---

## Part 1: Getting Started (Solo Developer)

### Day 1: Install & Orient

1. **Create your manifest** — the `glados.yaml` configuration file GLaDOS reads. Copy [glados.yaml.example](glados.yaml.example) to your repo root as `glados.yaml` and edit it. The load-bearing keys are `platform:`, `phase:`, and the channel bindings — the lines that say which team-visible place each kind of result gets posted to (a merge-request comment, an issue, or the run ledger: the record each run saves to the repo's `glados/ledger` branch).
2. **Declare your phase** — it is required, with no default. Describe reality, not ambition: phase states who gets hurt when the agent is wrong, not how proud you are of the code. A repo with zero users is `nascent`; the moment real users exist, it is `production`, whatever the code looks like. The example's `decisions:` block, and the `relaxation-acknowledged: [delete-code]` line after it, are written for `evolving`: for `production` or `sunset`, delete both so the phase's preset governs (install refuses each value laxer than the preset's, and a confession left behind is restated in every assembly report). For `sunset`, delete `disabled-workflows: []` as well: it would re-enable `build-feature` and `run-pipeline`, which that phase turns off. Under `nascent` both may stay: where the block is stricter than nascent's preset (`schema-migration: record`, where nascent has `agent`) its value applies, and the confession relaxes nothing; delete both to take nascent's own.
3. **Install** for your runtime:
   ```bash
   python bin/glados.py install --mode claude --target /path/to/your/project
   # modes: claude | claude-plugin | direct | gemini | antigravity | aistudio | pi
   ```
   Read the **assembly report** it prints — a table of every configuration value the installer resolved, where each came from, and a loud marker on anything your phase relaxed.
4. **Choose your path**:
   - **New project?** Start with `intent` to establish the mission and roadmap.
   - **Existing codebase?** Run `adopt-codebase` for a guided onboarding, or step through `review-codebase` → `intent` manually.
5. **Seed 2-3 standards** right away — short markdown files in `product-knowledge/standards/`, each stating a rule the agent's work will be checked against. Don't boil the ocean — pick the most contentious or error-prone areas (e.g., "How do we handle errors?", "What's our test strategy?").

### Week 1: Build Muscle Memory

Run the full development loop for at least **one feature** — either the four stages by hand:

```
plan-feature → spec-feature → implement-feature → verify-feature
```

or `build-feature`, which sequences all four and opens a review-ready merge request (MR — GitHub calls it a pull request) in one sitting. This teaches you the GLaDOS rhythm and surfaces any standards you forgot to document. Pay attention to the **standards gate** — the automatic check, built into each workflow, that compares the agent's work against your written standards. Every standard carries a severity: `must` blocks the workflow, `should` only advises. If the gate is too noisy, tune your standard severities.

### Week 2+: Let Patterns Emerge

`retrospect` reviews recent work and writes down **observations** — recurring patterns it noticed — into `product-knowledge/observations/` (retrospect owns this in v2; there is no separate pattern-observing workflow). Observations accumulate as pending items until the weekly `steward` pass promotes the real patterns into `standards/` or `philosophies/` and discards the noise, with a one-line reason either way.

---

## The Weekly Rhythm

Two standing ceremonies — scheduled, recurring jobs — keep the project healthy without anyone remembering to run them:

| Ceremony | Typical day | Produces |
|---|---|---|
| `steward` | Saturday | The housekeeping pass — condense old run records into a digest on the `glados/ledger` branch, refresh stale docs and canon digests, promote pending observations, sanity-check the tests. **One cleanup MR** for everything but the digest. |
| `brunch` | Sunday | The codebase critique roundtable — an evidence pre-flight (actually run the thing), parallel persona reviewers, a moderator who ranks findings by impact against effort. **One surgical fix MR.** |

(**Personas** are markdown files that give the reviewing agent a specific reviewer's viewpoint — security engineer, architect, QA, and so on. See [docs/personas.md](docs/personas.md).)

GLaDOS ships no scheduler — every workflow can run non-interactively (headless), and scheduling is the project's job. See the per-runtime recipes in the README ("The weekly rhythm").

The third loop runs per merge request, not per week: **`review-mr` ⇄ `address-review`**. Review runs several personas over the MR, each hunting for real problems, and posts a **verdict** — a one-word review outcome from a fixed vocabulary, such as APPROVE. Address-review resolves every open finding in one coherent pass and hands back. People review the same MR as they always have: everything GLaDOS posts starts with `(GLaDOS <workflow>)`, and any other note from someone with a role on the project, who did not write the change, is read as that person's review. Each point is a finding labelled as theirs, which the author meets or answers on the MR in the open, and a blocking one closes only when the change meets it or that person withdraws or waives it. The loop repeats until the verdict is APPROVE with every person's point answered and no one-way question waiting on its person, or until the cycle bound (`params.review-panel.max-cycles`) escalates to a human.

## The Run Ledger and Channels

Every workflow run leaves exactly one record, with its step artifacts — what ran, what it decided, what it emitted. Agents write them in `.glados/runs/` and save them to the repo's `glados/ledger` branch (`glados.py ledger save`), never to the work's branch, so a merge request's diff is the change. That branch of records is the **run ledger**. Epic and feature state lives in it, so a fresh session on any machine resumes from it (`glados.py ledger restore`), not from a scratch file that exists only where the last run happened. The results themselves — GLaDOS calls them outcomes, and there are six kinds: `verdict`, `escalation`, `bug`, `progress`, `decision`, `observation` — land wherever your `glados.yaml` channels point them: verdicts as MR comments, escalations and bugs as issues, by default. Nothing important lives only in a chat transcript. The weekly `steward` pass condenses settled records into a one-line-per-run digest, keeping the ledger readable. The assembly report printed at install is the ledger's front door: it shows where every resolved configuration value came from and marks anything your phase preset relaxed, so the team can see exactly what it traded away. If the report shows a relaxation you didn't intend, fix the manifest before the first run — not after the first incident.

---

## Part 2: Recommended Cadence

### Per Feature
| Step | Workflow | Who Approves |
|---|---|---|
| Plan | `plan-feature` | Developer (self or peer) |
| Spec | `spec-feature` | Developer + Personas (auto) |
| Standards Check | *automatic via the standards gate* | System (blocking on `must`) |
| Implement | `implement-feature` | Developer |
| Verify | `verify-feature` | A fresh evaluator — a separate agent session that never saw the implementation |
| Review | `review-mr` ⇄ `address-review` | Per the `merge-authority` key in `glados.yaml` (who may merge) |

`build-feature` runs the first five as one sitting; `fix-bug` is the same shape for bugs (report → reproduction → verified root-cause fix MR); `run-epic` drives a multi-ticket epic — or the whole backlog with `--backlog` — to one human-reviewable integration MR.

When the team's process differs from that order (a refactor with no plan, a design that stops before code, an architecture review before the spec), declare it under `pipelines:` in `glados.yaml` and run it with `run-pipeline`. Have the same people own `glados.yaml` and `product-knowledge/steps/` in CODEOWNERS. See [docs/guides/pipelines.md](docs/guides/pipelines.md).

When the team follows reference works (a book on architecture, a domain-modelling text, an internal paper), declare them under `canon:` and write a short digest of each in `product-knowledge/canon/`, in your own words. Planning, speccing, verification and review then cite its principles by id. A departure stays advisory until the team adopts the principle in a `must` standard, so start with the few principles that change real decisions, and adopt the ones the team will hold a merge to. Put `product-knowledge/canon/` under the same CODEOWNERS as `glados.yaml`. See [docs/guides/canon.md](docs/guides/canon.md).

### Weekly
| Activity | Workflow | Purpose |
|---|---|---|
| Housekeeping | `steward` | Ledger digest (saved to the `glados/ledger` branch), doc refresh, canon digest refresh, observation promotion — one cleanup MR for all but the digest |
| Critique | `brunch` | Persona roundtable — one surgical fix MR |
| Retrospect | `retrospect` | Human reflection; writes down observations and flags when your declared phase no longer matches reality |

### Monthly (or Per Milestone)
| Activity | Purpose |
|---|---|
| Philosophy Review | Manual review of `philosophies/` — are our principles still right? |
| Persona Tuning | Add/retire personas; read brunch's discard breakdowns as calibration signal |

### Quarterly
| Activity | Purpose |
|---|---|
| Standards Pruning | Remove standards nobody follows or that no longer serve the project |
| Intent Refresh | Run `intent` — does the mission/roadmap still reflect reality? |
| Phase Check | Does your declared `phase:` still describe reality? Transitions are a one-line MR against `glados.yaml`. |

---

## Part 3: Team Adoption

GLaDOS works best when adopted incrementally, not mandated top-down.

#### Stage 1: Champion (1 Developer)
One person installs GLaDOS, uses it for a sprint, and documents the experience. The goal is to answer: *"Does this actually help?"*

**What to demonstrate**: a feature built end-to-end through the loop; the run ledger showing the full decision history; verdicts and escalations landing on MRs and issues instead of vanishing; a brunch MR that fixed something real.

#### Stage 2: Pair (2-3 Developers)
Expand to a small group. This is where you discover which standards are truly shared vs. personal preference, and whether the personas need tuning for your domain. **Key action**: review a `steward` promotion MR together — arguing over whether an observation deserves to be a standard naturally surfaces disagreements and builds consensus.

#### Stage 3: Team (Full Adoption)
- Commit `glados.yaml`, `product-knowledge/`, and `.glados/` to version control. Runs save their records to the `glados/ledger` branch and push it themselves, so let the accounts and CI tokens that run GLaDOS push that branch: a protected-branch rule that rejects the push leaves the record saved in that clone only, and `ledger save` exits 1 saying so (the next save pushes it). Install, `ledger save` and `ledger restore` add `/.glados/runs/*` to the clone's git exclude file (`/<dir>/.glados/runs/*` for a project in a subdirectory of its repository), which keeps records off every branch.
- Add the GLaDOS install to your onboarding docs.
- Use `adopt-codebase` for any new team member's first session — guided analysis is a great way to learn a codebase.

#### Stage 4: Multi-Team
Each repo owns its own manifest and phase — never share those. Share persona definitions and org-wide standards (e.g., security, accessibility) via a common fork or submodule; keep `philosophies/` local, they are intentionally per-team.

### Team Workflow: Who Does What

| Role | GLaDOS Activity |
|---|---|
| **Developer** | Runs the development loop daily. Works the `review-mr` ⇄ `address-review` loop on their MRs. |
| **Tech Lead** | Reviews the weekly steward and brunch MRs. Owns the `merge-authority` and `decisions:` keys in `glados.yaml`. Tunes personas. |
| **Product Owner** | Owns `intent` (mission + roadmap). Reviews `plan-feature` outputs. |
| **New Hire** | Runs `adopt-codebase` as onboarding. Reads `standards/` and the ledger digest (`.glados/runs/DIGEST.md`, which lives on the `glados/ledger` branch; `python .glados/glados.py ledger restore` copies it in) as documentation. |

---

## Part 4: Customization Guide

### Adding a Persona

Drop a markdown file into `product-knowledge/personas/` and add its name to `params.review-panel.personas` in `glados.yaml`. The next review panel seats it — no reinstall. (The personas shipped with GLaDOS are copied into `.glados/personas/` at install; the project directory is searched first, so a project file of the same name wins.)

```yaml
---
type: review           # review, or moderator (brunch seats exactly one)
priority_areas: [security, compliance]
---
# Security Expert Persona
```

### Choosing Agent Levels

Every fresh agent — a design reviewer, an evaluator, a review-panel seat, a refuter — runs on the session's own model and effort unless `params.agents` in `glados.yaml` gives its kind a level. A level maps each runtime you use to that runtime's own words for a model and an effort, so GLaDOS itself names no model and a renamed one is a one-line change in your manifest. Put the strongest model where a miss is expensive, such as design reviews and the evaluator, and a faster one where the work is narrower. A runtime a level leaves out runs it at `session`. No reinstall; `validate` refuses a role naming a level that does not exist.

```yaml
params:
  agents:
    reviewer: deep
    evaluator: deep
    panelist: standard
    levels:
      deep:
        claude:
          model: opus           # Claude Code aliases follow the newest model
          effort: high
      standard:
        claude:
          model: sonnet
          effort: medium
```

### Adding a Philosophy

Create a file in `product-knowledge/philosophies/`. Start with `preferred` weight and promote to `core` only after the team has lived with it. Keep philosophies high-level — if it has a code example, it's a standard.

### Changing Behavior: the Two Speeds

- **Live keys** (channels, merge-authority, decisions, params, branching, the persona roster, `steps:`, a pipeline's sequence and step options, `canon:`) are read from `glados.yaml` at run time — edit, and the next run behaves differently. No reinstall. The edit is still checked: `python bin/glados.py validate --target /path/to/your/project` (and `check` in CI) refuses an invalid value, such as a misspelt decision class or a loop bound that is not a whole number of 1 or more. A `run-pipeline` run pins the configuration it started with, so an edit made while one is running escalates that run.
- **Structural keys** (phase, optimize-for, `default-modules` and per-workflow module lists, `disabled-workflows`, `sda`, and each pipeline's name and description) take effect at `python bin/glados.py install --mode <mode> --target /path/to/your/project`. The recompile is a deliberate ceremony: the installer's consistency checks run, and the assembly report shows the team what changed. `python bin/glados.py doctor --target /path/to/your/project` flags installs that are stale against the manifest.

Never hand-edit installed workflow text — it is compiled output and the next install overwrites it. Change the manifest instead.

### v1 Names

Old command names (`mission`, `plan-product`, `identify-bug`, `plan-fix`, `implement-fix`, `verify-fix`, `consolidate`, `establish-standards`, `recombobulate`, `autonomous-loop`) are permanent alias shims routing to their v2 workflow (`intent`, `fix-bug`, `steward`, `run-epic --backlog`). Nothing breaks, but update your docs — see [MIGRATION.md](MIGRATION.md) for the full map and the guided `glados.py migrate` command.

---

## Part 5: Anti-Patterns

| Anti-Pattern | Why It Fails | What to Do Instead |
|---|---|---|
| **Documenting 50 standards on day one** | Alert fatigue. Agent ignores everything. | Start with 2-3 `must` standards. Add more as patterns emerge. |
| **Making everything `must` severity** | Nothing feels important when everything is critical. | Use the full severity spectrum. Most standards should be `should`. |
| **Declaring a flattering phase** | `nascent` on a repo with users strips caution from exactly the code that can hurt people. | Phase describes reality. The assembly report marks every relaxation — read it. |
| **Routing every result only to the run ledger** | Verdicts and escalations nobody sees is the v1 failure mode, refiled. | Keep the defaults (`verdict: mr-comment`, `escalation`/`bug`: `issue`). Weakening them requires a written confession line in `glados.yaml` (`visibility-acknowledged`) — treat needing one as a smell. |
| **Skipping `retrospect`** | No observations accumulate; steward has nothing to promote; standards fossilize. | Make it a ritual — even 10 minutes after a sprint. |
| **Skipping the weekly ceremonies** | Ledger bloat, doc drift, and vibe debt accumulate silently. | Schedule `steward` and `brunch` weekly; they each cost one MR review. |
| **Hand-editing compiled workflows** | The next install silently reverts your change. | Edit `glados.yaml` (live keys) or recompile (structural keys). |
| **Mandating GLaDOS top-down** | Resistance and resentment. | Let champions demonstrate value first. |

---

## Part 6: Measuring Success

| Signal | How to Check |
|---|---|
| **Fewer "wait, we don't do it that way" moments** | The standards gate catches violations before review |
| **Faster onboarding** | New hires use `adopt-codebase` and read standards instead of asking 50 questions |
| **Nothing lost silently** | The CI `verify-ledger` job (copied into `.glados/ci/` at install; enabling it is the project's job — see "What does NOT migrate automatically" in [MIGRATION.md](MIGRATION.md)) counts the run-record commits in recent history and lists the commits whose subjects mention a verdict, review or escalation (silent-loss candidates, to check against the MRs and issues). Week over week those candidates are accounted for, it warns of no agent branches without a run record, and it lists no run record committed on a merge request's branch |
| **Outcomes are visible** | Verdicts sit on MRs, escalations and bugs are issues — no decision lives only in a chat transcript |
| **Preserved decisions** | Run records and `decision` outcomes explain *why*, resumable from the `glados/ledger` branch |
| **Living standards** | Steward regularly promotes observations; brunch MRs stay small because big findings got fixed earlier |

---

## Quick Reference

```
First Day:     adopt-codebase (existing codebase) or intent (new project)
Every Feature: build-feature   (or plan → spec → implement → verify by hand)
Every MR:      review-mr ⇄ address-review
Every Week:    steward (cleanup MR) + brunch (fix MR) + retrospect
Backlog/Epic:  run-epic [--backlog]
On Demand:     fix-bug, review-codebase, intent (refresh)
```

Deeper reading, in increasing depth: [docs/examples/](docs/examples/) for worked runs, [docs/concepts.md](docs/concepts.md) for how the pieces fit, and the reference pages ([docs/workflows.md](docs/workflows.md), [docs/modules.md](docs/modules.md), [docs/personas.md](docs/personas.md), [docs/src.md](docs/src.md)).
