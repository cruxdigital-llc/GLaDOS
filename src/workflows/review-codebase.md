---
name: review-codebase
kind: core
description: Audit an existing codebase read-only and report structure, health, and observed-standards candidates
reads: [intent.status]
writes: [observations.pending]
emits: [progress, observation]
mutates: none
requires: []
---

# (GLaDOS) Review Codebase

**Goal**: audit an existing codebase read-only — structure, stack, conventions,
health — and turn what you find into a findings report plus observed-standard
candidates. This core changes no source code; the only files it may create are
observation candidates awaiting promotion.

## Process

### 1. Map the terrain
- **Layout**: list the top-level directories and the modules under them; note
  entry points and how the pieces are wired together.
- **Stack**: read the package manifests (`package.json`, `pyproject.toml`,
  `go.mod`, …) for languages, frameworks, and pinned toolchains.
- **Docs**: read `README`, `CONTRIBUTING`, `ARCHITECTURE`, and any `docs/`
  tree. Treat every claim as something to verify against the code, not as
  established fact.

### 2. Analyze
- **Architecture**: name the dominant patterns (layered, hexagonal, MVC,
  event-driven, …) and where the code deviates from them.
- **Conventions**: detect the naming, directory, error-handling, and
  test-layout conventions the code actually follows; distinguish enforced
  (linter/CI config) from merely habitual.
- **Debt**: collect TODO/FIXME markers, dead code, and duplication significant
  enough to name in the report.

### 3. Health check
| Dimension | Evidence to gather |
|-----------|--------------------|
| Tests     | framework present; suite actually runs; coverage tooling |
| Linting   | linter/formatter configs present; a run comes back clean |
| CI        | pipeline definition exists and covers test + lint |
| Types     | static typing configured and enforced |

Run the cheap checks (the suite, the linter) rather than trusting config
presence — a config nobody runs is not health.

### 4. Compare against the declared status
- Read the project status file (`intent.status`). Where the code contradicts
  it — work claimed done that does not exist, issues marked fixed that still
  reproduce, architecture described that is not there — record the drift as
  findings. If no status file exists, name that gap in the report; creating
  one is a separate workflow's job, not this audit's.

### 5. Surface standards candidates
- For each convention the codebase follows consistently but nowhere codifies,
  write one candidate file into the pending-observations home
  (`observations.pending`): the observed rule, the evidence (files, counts),
  and a suggested standard statement.
- Each candidate produces an `observation` outcome. Promotion into standards
  is the steward workflow's job — never promote directly from an audit.

### 6. Report
- Assemble the findings report: architecture summary, the health table, drift
  against the declared status, debt worth tracking, and the candidates raised.
- The report is this run's `progress` outcome. Recommend the natural next
  workflow (plan-feature when the map suggests a direction; retrospect when
  the project's history needs mining first), then stop — the caller decides.
