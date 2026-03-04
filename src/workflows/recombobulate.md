# (GLaDOS) Recombobulate

**Goal**: Systematically clean up "vibe debt" — tighten the codebase, formalize implicit patterns, resolve standards drift, and retire dead code.

> **Alias**: `/glados/consolidate`

## Prerequisites
- [ ] `{{STATUS}}` exists.
- [ ] GLaDOS has been actively used (observations or standards exist).

## Scope Control
This workflow supports a `--scope` flag to control breadth:

| Scope | What it does |
|---|---|
| `observations-only` | Review and promote/discard items from `glados/observations/` *(default)* |
| `standards-only` | Audit codebase against existing `standards/` and `philosophies/` |
| `dead-code` | Scan for unreferenced files, unused exports, orphan tests |
| `full` | All of the above plus consistency audit and documentation staleness check |

If no scope is specified, default to `observations-only` (safest, most common use case).

---

## Process

### Phase 1: Observe
1.  Read `glados/observations/observed-standards.md` and `observed-philosophies.md`.
2.  Scan recent `specs/` traces for patterns, corrections, and deviations.
3.  List all current `standards/` and `philosophies/` files.
4.  Log discovery summary in the trace.

### Phase 2: Analyze
Based on the selected scope:

#### Observations Analysis *(observations-only, full)*
-   Review each pending observation.
-   Group related observations.
-   Assign confidence based on frequency and source quality.

#### Standards Drift *(standards-only, full)*
-   For each standard: compare current codebase against the documented rule.
-   Identify files that violate standards.
-   Flag standards that the codebase has *legitimately evolved past*.

#### Philosophy Alignment *(standards-only, full)*
-   Do recent implementations align with stated philosophies?
-   Are any philosophies contradicted by current patterns?

#### Dead Code Detection *(dead-code, full)*
-   Scan for unreferenced files and unused exports.
-   Identify orphan tests (tests for removed code).
-   Check for stale configuration files.

#### Consistency Audit *(full only)*
-   Look for inconsistent implementations of the same pattern.
-   Identify divergent approaches to the same problem.

#### Documentation Staleness *(full only)*
-   Are `{{STATUS}}`, `ROADMAP.md`, `MISSION.md` current?
-   Are `standards/` files up to date with actual practices?

### Phase 3: Propose

> [!IMPORTANT]
> **STOP**: This phase produces a report. The user MUST review before Phase 4.

Create `specs/[YYYY-MM-DD]_recombobulate/report.md`:

```markdown
# Recombobulate Report

## Observation Promotions
| Observation | Type | Confidence | Recommendation |
|---|---|---|---|
| Docker for tests | standard | High | Promote to `standards/testing/docker.md` (must) |
| Prefer composition | philosophy | Medium | Promote to `philosophies/composition.md` (preferred) |

## Standards Drift
| Standard | Status | Recommendation |
|---|---|---|
| API Response Format | ✅ Aligned | No action |
| Error Logging | ❌ Drifted | Fix code OR update standard |

## Dead Code Candidates
- [file] - [reason]

## Consistency Issues
- [pattern] appears in [N] different forms across [files]

## Documentation Staleness
- [file] last meaningful update: [date]
```

Present the report to the user.

### Phase 4: Execute
For each **user-approved** item:
-   **Observation promotions** → Create files in `standards/` or `philosophies/` with proper frontmatter.
-   **Standards drift (fix code)** → Create implementation plans for the changes.
-   **Standards drift (update standard)** → Edit the standard file.
-   **Dead code** → Remove with a decommission trace.
-   **Consistency fixes** → Create refactoring plans.

### Phase 5: Formalize
1.  **Clear processed items** from `glados/observations/` (mark as `promoted` or `discarded`).
2.  Update `{{STATUS}}` with a "Recombobulate" entry in "Recent Changes".
3.  Update `standards/index.yml` if new standards were added.
4.  Create `philosophies/index.yml` if new philosophies were formalized.
5.  Log completion in the trace.

---

## Suggested Cadence
After completing 5+ features or at the end of a sprint, consider running:
```
/recombobulate --scope observations-only
```
