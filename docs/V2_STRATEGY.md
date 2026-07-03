# GLaDOS v2 — Guiding Strategy

*Synthesized 2026-07-03 from: the maintainer's v2 vision (modularity + concurrency, attention/risk reframing, project phase), a 24-finding adversarially-verified audit of v1.4.0, four independent architecture proposals (contract-first kernel, risk-ledger-first, evolutionary, multi-agent-ops), three scored judgments, two red-team passes (execution, scope) on the winning direction, a follow-up three-design + red-team panel on project phase, and verified web research (July 2026) on the Google runtime surfaces (Gemini CLI, Antigravity, AI Studio).*

---

## The premise, sharpened

Code got cheap; understanding got scarce. v1's failure isn't any single workflow — it's that 21 instruction files each *individually promise* to trace, publish, coordinate, and use the same words, and the audit proves prose promises don't compose: all 24 verified findings reduce to five structural classes.

| Failure class | v1 evidence (audited) |
|---|---|
| **A. Trace-only outcomes** | Evaluator verdicts, review tallies, bug pipeline, epic state, proxy decisions — none ever reach a team-visible surface (10 findings) |
| **B. Readers without writers** | Integration-branch field, Active Tasks, Active Personas, reviewed-HEAD — read everywhere, written nowhere (5) |
| **C. Install/path drift** | `--mode claude` never installs modules at all; split-brain `standards/` paths (4) |
| **D. Duplication drift** | Panel roster ×3, loop bounds ×3, commit conventions ×3, docs missing the flagship loop (3) |
| **E. Vocabulary drift** | Six verdict vocabularies; two severity scales gating the middle tier oppositely; contradictory merge authority (2) |

**The organizing decision: GLaDOS v2 is a compiler for team attention.** Workflows shrink to short *cores* describing only their distinctive work. Everything cross-cutting — where outcomes publish, what words verdicts use, how leases are taken, what sits on a review panel — is **compiled into the workflow text at install time from one project manifest**. The installer stops being a file-copier and becomes an assembler with a type-checker: it refuses to produce an install where something is read that nothing writes, an outcome type has no team-visible sink, or a reference dangles. Enforcement lives at the three real enforcement points a daemon-less markdown framework has — **install time, CI time, and host-agent hooks** — never in prose hope.

This was the evolutionary proposal's spine (judged 131 vs 121 kernel / 115 risk-ledger / 102 multi-agent-ops); everything below grafts the judges' best-of-breed elements and the red-team fixes onto it.

---

## The nine load-bearing decisions

### 1. Three lanes: compile structure, read policy live, reference bulk
Not everything compiles — the rule is about *skip-resistance*, not freezing. Projects shift and change; the lanes decide what changes live and what passes through a ceremony.

**Lane 1 — compiled: what the agent must not be able to skip.** The epilogue, the verdict vocabulary, the `optimize-for` stanza, and module *presence/absence* are inlined into each workflow's installed text. An unselected module isn't a dangling `Invoke module:` line — it's absent. A constant's rule text (the loop-bound rule, commit conventions) exists on one source line and is stamped everywhere. One compiled output feeds every install mode. Structural change (turning the review panel on for a workflow) is a manifest edit + recompile — seconds of tooling, and deliberately a ceremony: it's the moment the type-checker runs and the assembly report shows the team what changed.
*Kills classes C and D categorically. The v1 evidence for why references can't carry load-bearing text: `--mode claude` dangled every module reference silently, and authors restated the panel roster beside explicit pointers to it because they didn't trust the reference to be followed.*

**Lane 2 — runtime-read: values that change without ceremony.** Compiled text *instructs the agent to resolve* these from `glados.yaml` (and `tiers.yaml`) at run time: channel bindings, merge authority, decision keys, loop-bound values, the panel's persona roster, phase policy values. A two-line manifest edit changes behavior on the next run — no recompile. `tiers.yaml` is necessarily this lane: it changes weekly by design. Phase preset defaults resolve through the same precedence (`baseline < phase preset < explicit`) via the vendored preset table, so lane-2 values stay live even though their defaults come from phase; only phase's *structural* consequences (e.g. `sunset` unloading build-feature) are lane 1 and take effect at the recompile the transition MR already forces.

**Lane 3 — referenced on demand: bulky, optional, harmless to skip.** Persona definitions, rare-path procedures, standards documents. **Teams add a persona by dropping a file in `personas/` and adding one manifest line — the next panel seats it, no reinstall.** Install-time validation checks the reference graph that exists at compile; lane-3 content added later is picked up by convention.

**Red-team fix folded in:** compilation has a *lifecycle*, not a moment. The compiled output embeds a manifest hash; `glados doctor` (and CI) flags stale compiles when a *structural* key changes after install — lane-2 edits never go stale because they're read live.

### 2. Typed outcomes, routed by project config — the observability answer
Workflow cores **emit outcome types** (`verdict`, `escalation`, `bug`, `progress`, later `tier-change`) and never name destinations. The manifest binds each type to sinks: MR comment, issue, issue-comment, repo ledger, several at once. **An emitted type with zero team-visible sinks is an install error** — one validation rule replaces 21 workflows remembering to post.
This *is* the modularity ask: README vs ROADMAP vs PR comments vs issue tracker is a channel binding, not a workflow rewrite.
*Kills class A structurally. Kernel's Router grafted onto evolutionary's channels.*
**Red-team fix:** day-one manifest defaults bind `verdict: mr-comment` and `escalation|bug: issue` (not `repo:`-only — that would re-ship class A with better filing). A project choosing ledger-only visibility for those types must write a literal `visibility-acknowledged: ledger-only` line: defection becomes a signed confession.

### 3. A flat state-key registry, checked at install and audited at runtime
Every piece of shared state is a **named key in one registry** (`status.integration-branch`, `reviewed-head`, `active-personas`, …) with a declared home. Cores and modules declare `reads:` / `writes:` in frontmatter; install fails if any read key has no installed writer.
**Scope cap (red-team):** keys are *flat enumerated tokens*, set-membership checked — no templated paths, no dotted lookups, no wildcards. ~30 edges across ~13 cores and ~7 modules: a 50-line script and a hand-auditable table, not a resolver that creeps into a language.
**Meta-drift guard (multi-agent-ops graft):** `verify-ledger` at runtime compares what runs *actually emitted* against manifest claims — catching manifests that overstate `writes:` while the prose quietly stopped doing the writing. That's the only defense anyone proposed against v2's manifests drifting the way v1's prose did.
*Kills class B, including its recurrence one level up.*

### 4. One vocabulary; policies are keys, not sentences
- **Findings:** two tiers — `blocking | advisory`. Deleting the middle tier dissolves the blocking/major/minor vs blocking/warning/note contradiction permanently.
- **Verdicts:** `APPROVE | REQUEST_CHANGES | ESCALATE`, with composition rules defined once: any `blocking` ⇒ `REQUEST_CHANGES`; **a missing panelist verdict ⇒ `ESCALATE`, never approval** — validated at the tally, not just instructed in the panelist prompt.
- **Policies:** merge authority, branch naming, loop bounds are **manifest keys that workflows read**. The review-mr/run-epic merge contradiction becomes impossible because neither file states an authority — contradictory sentences can't exist when the sentences don't exist.
*Kills class E and the drift half of D.*

### 5. The run ledger + compiled epilogue + host hook — durable by construction
Every run produces exactly one **run record** in `.glados/runs/`, committed, with a **compiled epilogue** no workflow can omit: finalize record → commit → publish outcome summary to bound channels → release leases. Epic state moves from machine-local scratchpads into the ledger on the integration branch — a fresh session resumes from `git pull`.
**Red-team fixes folded in:**
- *Two-strata ledger:* mutating workflows write records on their working branch; review/score records append to a dedicated ledger branch so review-mr (which must not dirty the author's branch) has a home, and the consolidated-diff promise survives.
- *The epilogue is the design's biggest bet* — a promise kept by an LLM at 90% context. So it ships with mechanics, not hope: a **Claude Code Stop-hook that refuses session end without a committed run record** ships in v2.0.0 as a first-class component (promoted from fallback by all three judges), and CI `verify-ledger` converts any silent loss into a visible red. The hook is ~30 lines and available today.
- *`glados install` scaffolds the CI template and `glados doctor` verifies the check actually runs* — the project owns enabling it (per the boundary of responsibility, decision 9), but a check that's declared and never running is a reader without a writer, so its absence is loudly reported rather than silently assumed. Every check rule ships `report-only` first, promoted per-rule to `blocking` in the manifest: teams tighten what has proven quiet, mirroring the tier philosophy.
- *The Stop-hook generalizes to a per-runtime enforcement ladder* (decision 9): Claude Code Stop-hook, Gemini CLI AfterAgent guard, agy Stop hook — and CI `verify-ledger` as the one backstop that exists everywhere.

### 6. Leases — one abstraction, one backend first: the concurrency answer
The unit is `lease(scope, holder, intent, ttl)`, compiled into any workflow that declares it mutates shared state; release is in the epilogue so leases can't leak.
**Scope discipline (red-team):** zero of the 24 findings are concurrency failures — so v2.0.0 ships only the *cheap, scar-driven* rule: **record base SHA at claim; on external edit detected before commit, emit `yielded(external_edit)`, rebase or release — never force-push.** (This converts the documented shared-tree clobbering pathology into an observable event, five lines of epilogue prose.) The lease module proper lands in v2.1 with **the lockfile backend only**; the swappable-backend interface waits until one backend has survived contact. Fencing/generation numbers only if real stale-holder incidents show up. Humans participate via the same primitive when the issue-claim backend eventually lands (a human assigning themselves a ticket is a lease agents must respect).

**The multi-runtime requirement strengthens the lockfile choice:** files + git are the *only* coordination substrate every supported runtime shares — Claude Code, Gemini CLI, agy, the Antigravity IDE, and even an AI Studio operator applying emitted commands all read and push the same repo. A lease that lives anywhere else (host-specific state, platform-specific assignment) excludes some actor on day one; a lease that is a pushed file excludes no one.

### 7. Risk tiers and ceremonies — data consumers, shipped when the data exists
The attention model is the point of v2 — and it is *fed by the ledger*, so it ships after the ledger produces data. Design is settled now:
- **`tiers.yaml`** — per-component `green | yellow | red` + evidence (smoke status, trailing gap, blast radius). **CODEOWNERS-protected: an agent cannot self-promote a component to green** — the one enforcement that must never depend on LLM compliance, placed at a platform-enforced point.
- **The asymmetry is hard-coded:** demotion cheap and automatic (one production incident or gap spike), promotion expensive and human (a reviewed MR against the tier file, carrying the *raw forecasts*, not just scores — the approver grades the grader). A wrongly-green component is the worst failure in the system; the bias points away from it.
- **Tier-indexed policy bundles** (`build@green` = implement/smoke/self-merge; `build@red` = draft-only, agent comments instead of commits) make the tier the selector of rigor — the direct mechanization of green/yellow/red ownership semantics, and it resolves merge authority per-tier instead of per-workflow.
- **Forecast-then-diff:** forecast committed before the diff is revealed; CI checks commit-timestamp ordering; the overnight run posts its diff summary *after* the forecast deadline (time the reveal rather than police the peek). Unfalsifiable forecasts score *maximum* gap; **a missing forecast records `gap: unknown` — unknown days block promotion but never demotion**, so a skipped ceremony degrades into visible evidence-of-absence instead of freezing the loop.
- **Smoke as teeth, without parsing source:** the smoke endpoint **self-enumerates** — it returns the app's live route table; CI diffs that JSON against `smoke.yaml`. The framework does a set comparison; the app does the reflection. Declared depths (`connectivity | full`, `stubbed: true` flagged as weaker evidence). Green *requires* smoke.
- **External observability wired to tiers:** Sentry→issue creation is platform config done once; the module contributes `triage-errors`, and **a production error in a green component is a maximal gap event** feeding automatic demotion — the smoke-passed-vs-reality-fine gap, closed.

**Standing ceremonies — Saturday and Sunday Brunch (ship in v2.0.0).** Unlike forecast-then-diff, these two are mature practice (running today as local routines) and need no ledger history, so they ship with the plumbing:
- **`steward` (Saturday):** housekeeping-over-critique — run-ledger compaction (the v2 descendant of spec→SPEC_LOG consolidation), documentation refresh, observation promotion into standards/philosophies, test sanity — producing one cleanup MR per pass. Absorbs Saturday's content as the core's canonical shape.
- **`brunch` (Sunday Brunch):** the codebase critique roundtable — evidence pre-flight (run the thing: tests, boot, UAT, scans; "review by reading only" is itself a finding) → parallel persona reviewers, each a fresh subagent with its own persona file → a **moderator** who ranks impact×effort, selects the top 1–2 "Fix Now" findings, and ships **one surgical MR**. The ticket-hygiene waterfall (Fix > Amend > Discard > Track; 0–1 new tickets normal, 2 the ceiling) and the discard-classification table (Out of Scope / Too Much / Just Mean) come along intact — the discard breakdown is persona-calibration signal, emitted as `observation` outcomes. The reviewer + moderator persona set (test-engineer, qa, ux-advocate, code-cleanliness, data-modeler, scalability-engineer, security-engineer, devops-engineer, brunch-moderator) ships in `src/personas/` — they currently exist only as prose inside a machine-local routine.
- **Scheduling is the project's job; enablement is ours.** GLaDOS ships no scheduler. Each ceremony core is headless-invocable on every supported runtime, and the docs show the per-runtime scheduling recipe: Claude Code scheduled tasks, `gemini -p "/glados:brunch"`, `agy` non-interactive (with `--output json` — see the runtime notes), cron/CI schedules, or the AI Studio API runner. "Nightly in most active projects" is a project's routine definition pointing at our core.

### 8. Project phase — the strategic dial, compiled away
Phase answers the one question tiers never can: **who gets hurt when the agent is wrong, and what does the team want optimized?** Tiers are evidence about components the repo can observe; phase encodes facts the repo structurally cannot observe (do users exist, did anyone sign a contract, do we intend to leave) plus intent. Neither is derivable from the other — which is exactly why both exist and why they must never blur.

**The model — four phases, two renames from the original sketch:**

| Phase | Team values | Users | A bad merge costs |
|---|---|---|---|
| `nascent` | Learning velocity; code is hypothesis | The builders themselves | An hour of your own time |
| `evolving` | Velocity with a memory; churn must be narrated | Early adopters who opted in | A design partner's afternoon |
| `production` | Stability, trust; understanding is the asset | People who don't forgive | An incident, maybe churn |
| `sunset` | Safe decay | People who depend on current behavior | Harm on the way out |

- **"Productionizing" is not a phase** — it's the *entry checklist into* `production`. Legitimate months-long hardening is tier-promotion work inside production: the board starts yellow/red and components earn green. Living in "productionizing" for a year is the phase-lie the tier board exists to prevent.
- **"Legacy" is not a phase** — it names a feeling and conflates operating-forever with leaving. Preserve-mode is `production` plus two explicit overrides (`backlog.scope: fix-only`, draft-only builds). `sunset` earns its slot because it flips workflow *existence* (build-feature unloads; wontfix-to-decommission-note becomes a first-class decided outcome).

**Mechanics — a preset over existing keys, not a runtime primitive.** `phase:` is one **required** manifest key (no default — an undeclared phase means the compiler chose values the team never stated). It expands into manifest keys that already exist — module selection, channel bindings, merge authority, loop bounds, ceremony toggles, decision keys — with precedence `baseline < phase preset < explicit keys`, and the phase word appears nowhere in compiled workflow text (a grep-testable property). Per the three-lane rule: phase defaults for lane-2 keys resolve live at run time through the vendored preset table; only its lane-1 structural consequences require the recompile that the transition MR forces anyway. The preset table is vendored into `.glados/` so a GLaDOS upgrade that changes what `nascent` means arrives as a reviewable diff. **Anti-inflation cap, compiler-checked:** a preset may only set keys that exist independently in the manifest schema — phase is a spelling of defaults, never a place where new policy is born.

**Opacity defenses** (a preset is *organized omission*, and the audit showed omission strips safety): every resolved key in the assembly report carries a provenance tag (`baseline` / `phase:X` / `explicit`); any phase-derived value weaker than baseline gets a `RELAXED(phase)` marker with a header count; the report is committed and diffable; an explicit key weakening below the declared phase's preset requires the confession idiom (`relaxation-acknowledged:`). And four things are **phase-untouchable invariants** the compiler rejects any preset touching: outcome-sink visibility, the registry check, the Stop-hook/ledger, and the yield rule. *Phase tunes attention and authority; it may never tune observability.* You can be fast and observed; you may not be fast and invisible.

**Decision rights — "which decisions you want made."** Per-phase enumerated decision keys with a closed value set: `agent | record | escalate | forbidden`. `record` emits a typed `decision` outcome (what, reversibility, phase) through the normal sink machinery — nascent's 2am schema change is decided *and narrated*; `forbidden` compiles to refusal plus an escalation emit, so non-compliance is ledger-visible. No prose category lists — "internal refactors under smoke coverage" as a rights band is policies-as-sentences, the thing decision 4 kills. For the unenumerable tail of judgment, exactly one compiled `optimize-for` sentence is stamped into every core's preamble ("optimize for learning per unit of attention; there are no users to harm" — never containing the phase word). Run-ledger records carry the phase, so all later evidence is phase-attributable.

**Granularity and the tier interaction — one board, ever.** Phase is declared **per deployable system** (v2.0.0: one per manifest). A nascent module inside a production system is *not* "nascent" — blast radius is set by the deployable, not the directory; it's a red/yellow component of a production system, which is what tiers already express. Phase sets the tier board's *boundary conditions*, one-directionally: the default tier for unlisted components, the promotion evidence bar, and `tiers.mode: single-tier` in nascent — **the tier board doesn't exist pre-users; the →production transition creates it** (a board nobody believes is worse than no board). Policy resolves as a compile-time `bundle[phase][tier]` lookup — tiers answer "how much do we trust this component"; phase answers "what does trust license here." No clamp arithmetic, no ceilings that override earned evidence, phase never appears in `tiers.yaml`, tiers never encode intent.

**Transitions — the human pen, forever.** A phase change is a one-line MR against `glados.yaml`, CODEOWNERS-protected like `tiers.yaml`; agents may propose, never merge. **Initial declaration is ungated (you describe reality); transitions are gated (you claim progress)** — a brownfield repo with real users installs as `production` day one without needing ledger history. Entry checklists (→production: smoke seeded and self-enumerating, CI rules blocking, escalation sink human-visible, tiers.yaml initialized + CODEOWNERS) are emitted into the transition MR; items are checkable or `waived: <reason>` — and waivers print in every subsequent assembly report. Backward moves require the confession line (`users-acknowledged: none`). Evidence *suggests* transitions but never automates them: retrospect emits advisory signals — external bug reporters while nascent ("you have users whether you admit it or not"), fix-only quarters, escalations rubber-stamped >50%, rising errors in a sunsetting system — through normal channels; `phase-declared: <date, MR>` lets `glados doctor` nag on stale declarations.

*Phase also resolves open question 3: solo-maintainer mode isn't a special mode — it's `phase: nascent` turning forecast-then-diff off legitimately.*

### 9. Runtimes: one compiled output, five adapters, an enforcement ladder
Multi-runtime support is a requirement, not an option. The compiler produces one canonical output; adapters are thin emit shims — and the July-2026 research (verified against primary sources) settles what each must emit:

| Runtime | Adapter emits | Epilogue enforcement |
|---|---|---|
| **Claude Code** (plugin) | `skills/<core>/SKILL.md` wrappers, as today | Stop-hook (blocks session end) |
| **Direct** | compiled file tree into the repo | CI backstop only |
| **Gemini CLI** | TOML commands `.gemini/commands/glados/<core>.toml` (`/glados:x`; headless-capable via `gemini -p`) + optionally the Agent Skills form (`.agents/skills/` — the same SKILL.md open standard Claude uses) | **AfterAgent hook** (exit 2 = retry the turn — a real blocking guard; SessionEnd is best-effort only). Guard must be conditioned on an in-flight run marker so interactive use stays bearable |
| **Antigravity** (IDE + `agy` CLI) | `.agents/workflows/glados-<core>.md` (**flat** — filename→slash-command, YAML `description` frontmatter; the `.agent/`→`.agents/` rename is handled, singular still read) + workspace `.agents/hooks.json` for agy | agy has a real **Stop hook** in `.agents/hooks.json`; the IDE has no verified hook surface → CI backstop. Headless agy caveat: issue #76 (`-p` drops stdout non-TTY) → always `--output json`/file |
| **AI Studio** | a **paste-kit + API runner**, checked into the repo: self-contained per-workflow bundles (runtime-contract preamble: no tools — emit `=== WRITE FILE: ===` / `=== RUN: ===` blocks the operator applies; epilogue as a mandatory response-suffix), an optional structured-output schema making run-record omission a schema violation, and `run_workflow.py/.mjs` scripts targeting the **Interactions API** (GA June 2026) for scheduled read-mostly runs | Structured-output schema at best; the operator or api-runner commits the run record. Execution-heavy cores (implement/run-epic) are emitted in advisory mode or skipped — AI Studio is a planning/review/spec surface |

Three findings worth naming: **(a)** v1's `.gemini/skills/glados/SKILL.md` guess became retroactively valid — Gemini CLI adopted the Agent Skills open standard in Jan 2026 — but its `.agent/modules/`/`personas/`/`templates/` dirs for Antigravity were always inert fiction, and nested workflow dirs don't map to slash commands (flat + prefix it is). **(b)** Google consolidated: Gemini CLI transitioned toward Antigravity CLI (May 2026) with the consumer serving path cut June 2026 — the Gemini CLI adapter is now an enterprise/API-key-niche target, Antigravity is the mainstream Google surface, and the formats (TOML commands, skills, hooks) carried over, so one adapter's work largely feeds both. **(c)** The **CI `verify-ledger` check is the only enforcement that exists on every runtime** — hooks are per-runtime accelerators where they exist; CI is the universal backstop. The repo's fixture self-test compiles all five adapters, so a mode that stops shipping modules — v1's flagship bug — fails the build.

**The boundary of responsibility (platform actions are not ours):** GLaDOS defines *contracts* — outcome types, channel kinds, run-record shape. The **project** provides the platform (GitLab or GitHub, Sentry, CI wiring) and declares it in the manifest. The **agent** brings its own hands — `glab`, `gh`, MCP servers, whatever its runtime offers — to execute channel bindings. GLaDOS never wires a platform API itself: it ships CI *templates* the project enables, and `glados doctor` detects wiring that's declared but not actually running (a check that never runs is a reader without a writer). On runtimes without hands (AI Studio), the contract degrades honestly: the agent emits the exact commands and file contents; the operator or runner script executes them.

---

## What dies from v1

**Deleted:** `interaction-proxy` (decisions with no durable record *is* the failure class — replaced by the escalation channel + tier policy: green = don't ask, red = always ask); `persona-review` (already declared superseded); `evaluator-handoff` (folds into `evaluator-spawn`, whose context-isolation contract is v1's best asset and survives intact); `capabilities` + `persona-context` (become manifest fields); the `observability` module as written (its job *is* the compiled epilogue); `specs/` trace dirs, scratchpad epic files, free-form `PROJECT_STATUS.md` sections (replaced by the ledger and a schema'd status file); every verdict vocabulary but one.

**Folded:** `identify-bug`/`plan-fix`/`implement-fix`/`verify-fix` → one `fix-bug`; `autonomous-loop` → `run-epic --backlog`; `pattern-observer` → `retrospect`; `consolidate`+`recombobulate`+`establish-standards` → `steward` + `regenerate-component`; `mission`+`plan-product` → `intent`.

**Created new:** `brunch` (the Sunday Brunch roundtable, decision 7) and the ceremony persona set in `src/personas/`.

**Net: 21 workflows → ~15 cores; 10 modules → ~7.** Judges' note stands: the smallest honest command surface (~7 everyday verbs) is the right *target* as tier-indexed bundles mature.

**Install modes:** v2.0.0 ships **five adapters** — claude-plugin, direct, gemini-cli, antigravity, ai-studio (see decision 9) — all fed by the one compiled output, with the fixture self-test compiling every adapter so per-mode drift fails the build. What dies is v1's per-mode *decision logic* about what installs, and the invented conventions research debunked (nested command dirs, Antigravity modules/personas/templates dirs).

**On command shims, the red-teams disagreed — resolution: keep them, permanently.** The scope red-team wanted them cut; the execution red-team showed why that loses: old CLAUDE.md files, agent memory, and human habit will invoke `plan-fix` for years, and a failed invocation makes the LLM *reconstruct the v1 workflow from training data* — an ungoverned ghost running inside v2. Ten permanent one-line alias files — one per dead v1 name in `src/kernel/aliases.yaml` — are the cheapest insurance in the whole design.

**Intent-first regeneration** (`intent/<component>.md` + `regenerate-component`) is confirmed direction — the durable work becomes keeping intent clean — but it's the riskiest workflow in the design and ships last, in the attention release, where tier evidence can gate what's safe to regenerate.

---

## Sequencing — plumbing before vision

The scope red-team's decisive observation: the tier/ceremony stack fixes **zero** of the 24 findings, and gap scores need weeks of run records before a weekly retune means anything. Tiers are consumers of the ledger; shipping them first isn't just risky, it's the order in which they *can't work*.

**Week 0 — build the measuring instrument first.**
`verify-ledger` in report-only mode, run against v1 *as-is*. No compiler, no manifest, no design decisions — just "diff branches/MRs against expected artifacts and report." The 24 findings become a live dashboard on real repos: the baseline every later bet is scored by, and the best adoption evidence available.

**v2.0.0 — the plumbing release (target: 2–4 weeks).** Fixes all 24 findings.
Installer→assembler (inlining, vocabulary partials, compiled epilogue, manifest hash); minimal `glados.yaml` (platform, three channel bindings — `verdict: mr-comment`, `escalation|bug: issue`, `progress: repo` — per-workflow module lists, mandatory `default-modules:` for unlisted workflows, assembly report printed at install); flat state-key registry + set-membership check; run ledger with the two-strata rule; merge authority as a manifest key; base-SHA yield rule; Claude Code Stop-hook; CI include written by the installer, rules report-only first; the full consolidation and delete list; MIGRATION.md + v1-detect→prefilled-manifest (no `glados migrate` machinery); permanent alias shims.
**Plus the phase sliver** (costs days, and makes the plumbing release adoptable on greenfield repos without production-grade ceremony): required `phase:` key, the four presets expanding over v2.0.0 keys only, provenance/`RELAXED` reporting, decision keys + the `decision` outcome type, the `optimize-for` preamble stanza, CODEOWNERS on `glados.yaml`, transition MRs with *advisory* checklists.
**Plus the runtime + ceremony scope** (per decisions 7 and 9): all five adapters with the fixture self-test; the per-runtime enforcement ladder (Stop-hook / AfterAgent guard / agy hooks.json / structured-output schema); the `brunch` core + ceremony personas; `steward` carrying Saturday's shape; per-runtime headless-scheduling recipes in the docs.
*Exit criterion: `verify-ledger` reports zero silent-loss events across two weeks of real use.*

**v2.1 — the coordination release.**
Lease module, lockfile backend only; lease-before-branch in `run-epic`/backlog; `verify-ledger` upgraded to compare emitted events against manifest claims; fencing only if incidents demand it; a second install mode or lease backend only when someone asks. Phase: transition checklists promoted to blocking; per-phase lease defaults; the `decision` digest.
*Exit criterion: two agents on one board for a week without a clobber.*

**v2.2 — the attention release (the actual vision, now fed by real data).**
`tiers.yaml` + CODEOWNERS + the demotion/promotion asymmetry + tier-indexed policy bundles (one feature, shipped together); forecast-then-diff with timestamp ordering, gap scoring advisory-only for the first month; weekly retune as an MR; smoke registry convention + self-enumeration CI check; Sentry wiring + `triage-errors` + error-in-green = maximal gap; `intent/` + `regenerate-component`. Phase: the phase×tier couplings (default tier, single-tier mode, `bundle[phase][tier]`) ship *with* tiers as one feature; monorepo `systems:` dispatch rides the tier-bundle dispatcher; transition-suggestion heuristics land here, fed by real ledger data.

---

## Named risks we are accepting

1. **The epilogue bet.** Publication-by-compiled-prose can fail exactly when it matters (context pressure). Mitigation is layered — cheap publication, Stop-hook, CI verify-ledger — and *measured*: v2.0.0's exit criterion exists to prove or disprove the bet in week 2, not month 6.
2. **The compiler becomes the unmaintained component.** v1's 657-line sed script drifted; v2 concentrates more on that point. Mitigations: compiler + checker as one dependency-free Python file, vendored into `.glados/` at install so CI and every actor run the same version; scope caps above keep it a file, not a build system.
3. **The manifest is the next drift surface.** It's one file, schema'd, validated at install, and audited at runtime by verify-ledger's claims-vs-events comparison — drift is possible, silent drift is not.
4. **Ceremony compliance is cultural.** Forecast-then-diff has soft teeth by design; the mitigation is that non-compliance is *recorded* (`gap: unknown`) and only ever costs promotion, never freezes the system.

---

## Open questions for the maintainer

1. **Platform assumptions:** v2.0.0 CI checks target GitLab CI + GitHub Actions both, or GitLab-first (the installed base) with Actions in v2.1?
2. **The ledger branch name and `.glados/` layout** — worth settling early since every artifact convention hangs off it.
3. ~~Solo-maintainer mode~~ — **resolved by phase**: `phase: nascent` turns forecast-then-diff off legitimately; the ceremony activates with the →production transition.
4. **`glados check` distribution:** vendored Python file (recommended above) vs. installed package — affects how Windows-hosted agents run it identically to CI.
5. **Phase preset contents:** the four preset tables (which keys each phase sets, to what values) are sketched but deserve a deliberate pass with real projects in mind — e.g. what `evolving` sets `decisions.public-api-break` to (`record` was the panel's answer: churn is licensed but must be narrated).
