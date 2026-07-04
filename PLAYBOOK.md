# GLaDOS Playbook

A practical guide to adopting GLaDOS in your project and your team — from first install to steady-state operations. New here? The [README](README.md) and [docs/getting-started/](docs/getting-started/) cover what GLaDOS is and how to install it from zero; this playbook assumes that much and focuses on adopting it well.

> **Note**: Invocation syntax varies by runtime. `intent` is invoked as `/glados:intent` in Claude Code, `/glados:intent` in Gemini CLI (Google's open-source terminal agent; installed as TOML commands), and `/glados-intent` in Google Antigravity (Google's agentic IDE; CLI `agy`; antigravity.google; flat workflow files, name-prefixed). Google AI Studio (aistudio.google.com) has no command surface — you paste the workflow's self-contained bundle into the conversation. This guide uses bare command names for readability.

---

## Part 1: Getting Started (Solo Developer)

### Day 1: Install & Orient

1. **Create your manifest** — the `glados.yaml` configuration file GLaDOS reads. Copy [glados.yaml.example](glados.yaml.example) to your repo root as `glados.yaml` and edit it. The load-bearing keys are `platform:`, `phase:`, and the channel bindings — the lines that say which team-visible place each kind of result gets posted to (a merge-request comment, an issue, or the committed run log).
2. **Declare your phase** — it is required, with no default. Describe reality, not ambition: phase states who gets hurt when the agent is wrong, not how proud you are of the code. A repo with zero users is `nascent`; the moment real users exist, it is `production`, whatever the code looks like.
3. **Install** for your runtime:
   ```bash
   python bin/glados.py install --mode claude --target /path/to/your/project
   # modes: claude | claude-plugin | direct | gemini | antigravity | aistudio
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
| `steward` | Saturday | The housekeeping pass — condense old run records into a digest, refresh stale docs, promote pending observations, sanity-check the tests. **One cleanup MR.** |
| `brunch` | Sunday | The codebase critique roundtable — an evidence pre-flight (actually run the thing), parallel persona reviewers, a moderator who ranks findings by impact against effort. **One surgical fix MR.** |

(**Personas** are markdown files that give the reviewing agent a specific reviewer's viewpoint — security engineer, architect, QA, and so on. See [docs/personas.md](docs/personas.md).)

GLaDOS ships no scheduler — every workflow can run non-interactively (headless), and scheduling is the project's job. See the per-runtime recipes in the README ("The weekly rhythm").

The third loop runs per merge request, not per week: **`review-mr` ⇄ `address-review`**. Review runs several personas over the MR, each hunting for real problems, and posts a **verdict** — a one-word review outcome from a fixed vocabulary, such as APPROVE. Address-review resolves every open finding in one coherent pass and hands back. The loop repeats until the verdict is APPROVE or someone escalates to a human.

## The Run Ledger and Channels

Every workflow run leaves exactly one committed record in `.glados/runs/` — what ran, what it decided, what it emitted. This folder of records is the **run ledger**. Epic and feature state lives in the ledger on the branch, so a fresh session on any machine resumes from `git pull`, not from a scratch file that exists only where the last run happened. The results themselves — GLaDOS calls them outcomes, and there are six kinds: `verdict`, `escalation`, `bug`, `progress`, `decision`, `observation` — land wherever your `glados.yaml` channels point them: verdicts as MR comments, escalations and bugs as issues, by default. Nothing important lives only in a chat transcript. The weekly `steward` pass condenses settled records into a one-line-per-run digest, keeping the ledger readable. The assembly report printed at install is the ledger's front door: it shows where every resolved configuration value came from and marks anything your phase preset relaxed, so the team can see exactly what it traded away. If the report shows a relaxation you didn't intend, fix the manifest before the first run — not after the first incident.

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

### Weekly
| Activity | Workflow | Purpose |
|---|---|---|
| Housekeeping | `steward` | Ledger digest, doc refresh, observation promotion — one cleanup MR |
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
- Commit `glados.yaml`, `product-knowledge/`, and `.glados/` to version control (the ledger only works committed).
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
| **New Hire** | Runs `adopt-codebase` as onboarding. Reads `standards/` and the ledger digest as documentation. |

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

### Adding a Philosophy

Create a file in `product-knowledge/philosophies/`. Start with `preferred` weight and promote to `core` only after the team has lived with it. Keep philosophies high-level — if it has a code example, it's a standard.

### Changing Behavior: the Two Speeds

- **Live keys** (channels, merge-authority, decisions, params, the persona roster) are read from `glados.yaml` at run time — edit, and the next run behaves differently. No reinstall.
- **Structural keys** (per-workflow module lists, phase) take effect at `python bin/glados.py install --mode <mode> --target /path/to/your/project`. The recompile is a deliberate ceremony: the installer's consistency checks run, and the assembly report shows the team what changed. `python bin/glados.py doctor --target /path/to/your/project` flags installs that are stale against the manifest.

Never hand-edit installed workflow text — it is compiled output and the next install overwrites it. Change the manifest instead.

### v1 Names

Old command names (`mission`, `plan-product`, `identify-bug`, `plan-fix`, `implement-fix`, `verify-fix`, `consolidate`, `establish-standards`, `recombobulate`, `autonomous-loop`) are permanent alias shims routing to their v2 workflow (`intent`, `fix-bug`, `steward`, `run-epic --backlog`). Nothing breaks, but update your docs — see [MIGRATION.md](MIGRATION.md) for the full map.

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
| **Nothing lost silently** | The CI `verify-ledger` job (copied into `.glados/ci/` at install; enabled by the project per MIGRATION.md step 5) reports zero runs whose results never reached a team-visible place, week over week |
| **Outcomes are visible** | Verdicts sit on MRs, escalations and bugs are issues — no decision lives only in a chat transcript |
| **Preserved decisions** | Run records and `decision` outcomes explain *why*, resumable from `git pull` |
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
