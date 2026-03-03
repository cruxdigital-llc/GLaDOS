# GLaDOS Playbook

A practical guide to adopting GLaDOS in your project and your team — from first install to steady-state operations.

---

## Part 1: Getting Started (Solo Developer)

### Day 1: Install & Orient

1. **Install GLaDOS** for your agent of choice:
   ```bash
   ./bin/glados-install.sh --mode antigravity  # or claude, gemini
   ```
2. **Choose your path**:
   - **New project?** Start with `/mission` → `/plan-product` → `/plan-feature`.
   - **Existing codebase?** Run `/adopt-codebase` for a guided onboarding, or step through `/review-codebase` → `/establish-standards` → `/mission` manually.
3. **Establish 2-3 standards** right away. Don't boil the ocean — pick the most contentious or error-prone areas (e.g., "How do we handle errors?", "What's our test strategy?").

### Week 1: Build Muscle Memory

Run the full development loop for at least **one feature**:

```
/plan-feature → /spec-feature → /implement-feature → /verify-feature
```

This teaches you the GLaDOS rhythm and surfaces any standards you forgot to document. Pay attention to the **standards gate** — if it's too noisy, tune your standard severities (`should` → `may`).

### Week 2+: Let Patterns Emerge

By now the `pattern-observer` module is silently logging things to `glados/observations/`. After 3-5 features:

```
/recombobulate --scope observations-only
```

Review what was captured. Promote the real patterns to `standards/` or `philosophies/`, discard the noise.

---

## Part 2: Recommended Cadence

### Per Feature
| Step | Workflow | Who Approves |
|---|---|---|
| Plan | `/plan-feature` | Developer (self or peer) |
| Spec | `/spec-feature` | Developer + Personas (auto) |
| Standards Check | *automatic via standards-gate* | System (blocking on `must`) |
| Implement | `/implement-feature` | Developer |
| Verify | `/verify-feature` | Developer + Personas (auto) |

### Weekly (or Per Sprint)
| Activity | Workflow | Purpose |
|---|---|---|
| Retrospect | `/retrospect` | Human reflection — what went well, what didn't |
| Quick Consolidation | `/recombobulate --scope observations-only` | Promote any accumulated observations |

### Monthly (or Per Milestone)
| Activity | Workflow | Purpose |
|---|---|---|
| Full Audit | `/recombobulate --scope full` | Standards drift, dead code, consistency, documentation staleness |
| Philosophy Review | Manual review of `philosophies/` | Are our principles still right? |
| Persona Tuning | Review `personas/` | Add/retire personas based on project evolution |

### Quarterly
| Activity | Purpose |
|---|---|
| Standards Pruning | Remove standards nobody follows or that no longer serve the project |
| Roadmap Alignment | Ensure `ROADMAP.md` and `MISSION.md` still reflect reality |

---

## Part 3: Team Adoption

### The Evangelization Path

GLaDOS works best when adopted incrementally, not mandated top-down.

#### Stage 1: Champion (1 Developer)
One person installs GLaDOS, uses it for a sprint, and documents the experience. The goal is to answer: *"Does this actually help?"*

**What to demonstrate**:
- A feature built end-to-end through the GLaDOS loop.
- The `specs/` trace showing full decision history.
- A few captured observations that turned into real standards.

#### Stage 2: Pair (2-3 Developers)
Expand to a small group. This is where you discover:
- Which standards are truly shared vs. personal preference.
- Whether personas need tuning for your domain.
- How the observations system handles multiple contributors.

**Key action**: Run `/establish-standards` as a group exercise. The interview format naturally surfaces disagreements and builds consensus.

#### Stage 3: Team (Full Adoption)
Once the standards and philosophies feel right:
- Commit the `glados/` directory to version control.
- Add GLaDOS install to your onboarding docs.
- Use `/adopt-codebase` for any new team member's first session — it's a great way to learn the codebase with guided analysis.

#### Stage 4: Multi-Team
For organizations with multiple repos:
- Create a **shared overlay** with org-wide standards (e.g., `security`, `accessibility`).
- Each team maintains its own `philosophies/` — these are intentionally local.
- Share the overlay via a common GLaDOS fork or a Git submodule.

---

### Team Workflow: Who Does What

| Role | GLaDOS Activity |
|---|---|
| **Developer** | Runs the development loop daily. Owns `specs/` for their features. |
| **Tech Lead** | Reviews standards and philosophies. Runs `/recombobulate --scope full` periodically. Tunes personas. |
| **Product Owner** | Maintains `MISSION.md` and `ROADMAP.md`. Reviews `/plan-feature` outputs. |
| **New Hire** | Runs `/adopt-codebase` as onboarding. Reads `standards/` and `philosophies/` as documentation. |

---

## Part 4: Customization Guide

### Adding a Persona

Drop a markdown file into `glados/personas/` or `src/personas/`:

```yaml
---
type: review           # review, operating, or hybrid
priority_areas: [security, compliance]
standards_weight: [security/*]
---
# Security Expert Persona

**Role**: You are a Security Engineer focused on...
```

Common custom personas:
- **Security Expert**: For teams with compliance requirements.
- **Accessibility Lead**: For user-facing products.
- **DevOps Engineer**: For infrastructure-heavy features.
- **Domain Expert**: When your business logic has specific invariants.

### Adding a Philosophy

Create a file in `glados/philosophies/`:

```yaml
---
domain: architecture
weight: core
---
# Convention Over Configuration

## Statement
When designing new features, prefer conventions...
```

Start with `preferred` weight and promote to `core` only after the team has lived with it.

### Creating Overlays

For team-specific customizations that shouldn't alter the base GLaDOS:

1. Create `glados/overlays/my-team/`.
2. Copy any workflow or module you want to customize.
3. Edit it.
4. Apply: `./bin/glados-update.sh --ingest-overlays`.

This keeps your customizations separate from upstream updates.

---

## Part 5: Anti-Patterns

Things that will undermine GLaDOS adoption:

| Anti-Pattern | Why It Fails | What to Do Instead |
|---|---|---|
| **Documenting 50 standards on day one** | Alert fatigue. Agent ignores everything. | Start with 2-3 `must` standards. Add more as patterns emerge. |
| **Making everything `must` severity** | Nothing feels important when everything is critical. | Use the full `must`/`should`/`may` spectrum. Most standards should be `should`. |
| **Skipping `/retrospect`** | Vibe debt accumulates silently. | Make it a ritual — even 10 minutes after a sprint. |
| **Never running `/recombobulate`** | Observations pile up, standards drift unnoticed. | Schedule monthly at minimum. |
| **Treating philosophies like standards** | Philosophies guide; they don't prescribe syntax. | Keep philosophies high-level. If it has a code example, it's a standard. |
| **Mandating GLaDOS top-down** | Resistance and resentment. | Let champions demonstrate value first. |

---

## Part 6: Measuring Success

How to know GLaDOS is working:

| Signal | How to Check |
|---|---|
| **Fewer "wait, we don't do it that way" moments** | Standards gate catches violations before review |
| **Faster onboarding** | New hires use `/adopt-codebase` and read standards instead of asking 50 questions |
| **Consistent codebase** | `/recombobulate --scope full` finds fewer drift issues over time |
| **Preserved decisions** | `specs/` traces explain *why* things were built the way they were |
| **Living standards** | `glados/observations/` regularly produces promotable patterns |

---

## Quick Reference

```
First Day:     /adopt-codebase (brownfield) or /mission (greenfield)
Every Feature: /plan → /spec → /implement → /verify
Every Sprint:  /retrospect + /recombobulate --scope observations-only
Every Month:   /recombobulate --scope full
On Demand:     /establish-standards, /identify-bug, /plan-fix
```
