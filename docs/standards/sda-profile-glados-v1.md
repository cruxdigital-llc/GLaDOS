# SDA Profile: GLaDOS v1.0

*Maps the Structured Development Artifacts (SDA) Standard v1.0 onto GLaDOS conventions.*

---

## 1. Overview

This profile defines how GLaDOS — the Generalized Looping Autonomous Development Operating System — produces and consumes SDA-conformant artifacts. It is the reference profile for the SDA standard.

Conformance Level: Full

---

## 2. Repository Layout

    <repo-root>/
    ├── product-knowledge/
    │   ├── PROJECT_STATUS.md       # Status Document
    │   ├── MISSION.md              # Project mission (GLaDOS extension)
    │   ├── ROADMAP.md              # Roadmap
    │   ├── TECH_STACK.md           # Tech decisions (GLaDOS extension)
    │   ├── standards/              # Enforceable rules (GLaDOS extension)
    │   ├── philosophies/           # Design principles (GLaDOS extension)
    │   ├── personas/               # Review personas (GLaDOS extension)
    │   └── observations/           # Detected patterns (GLaDOS extension)
    ├── specs/                      # Work unit root
    │   └── <work-unit-directories>/
    └── claims.md                   # Claims (at repo root or product-knowledge/)

---

## 3. Work Unit Directory Naming

Pattern:

    specs/{YYYY-MM-DD}_{PREFIX}_{KEBAB_NAME}/

Regex:

    ^specs\/(\d{4}-\d{2}-\d{2})_(feature|fix|mission-statement|plan-product)_([a-z0-9]+(-[a-z0-9]+)*)\/

| Segment | Description |
|---|---|
| YYYY-MM-DD | ISO 8601 date the work was initiated |
| PREFIX | Work type: feature, fix, mission-statement, plan-product |
| KEBAB_NAME | Human-readable identifier in kebab-case |

The last _ separates the system prefix from the user-provided name.

Directories not matching this pattern are silently ignored.

Examples:

    specs/2026-03-28_feature_user-authentication/
    specs/2026-03-28_fix_login-timeout/
    specs/2026-04-01_plan-product_initial-roadmap/

---

## 4. Phases and Detection Rules

GLaDOS defines six phases, evaluated in this priority order (first match wins):

| Priority | Phase | Condition |
|---|---|---|
| 1 | done | tasks.md exists AND all checkboxes [x] AND README.md contains a verification session log |
| 2 | verifying | tasks.md exists AND all checkboxes [x] |
| 3 | implementing | tasks.md exists |
| 4 | speccing | spec.md exists |
| 5 | planning | plan.md OR requirements.md exists |
| 6 | unclaimed | Only README.md exists |

Phase flow: unclaimed -> planning -> speccing -> implementing -> verifying -> done

---

## 5. File Names

### 5.1 Required Files by Phase

| File | Phase Required | SDA Concept |
|---|---|---|
| README.md | Always | Trace Log |
| requirements.md | planning+ | Requirements |
| plan.md | planning+ | Plan |
| spec.md | speccing+ | Specification |
| tasks.md | implementing+ | Task List |

### 5.2 Optional Files

| File | When Used | Purpose |
|---|---|---|
| repro_steps.md | Bugfix work units | Reproduction steps (QA-authored) |
| SPEC_LOG.md | project-level | Historical record of completed specs (SDA Work Unit Log) |

### 5.3 File Formats

**README.md (Trace Log):**

    # Feature: {Name}

    **Date**: 2026-04-01
    **Phase**: implementing
    **Roadmap Section**: 1.2

    ## Summary
    {Brief description of this work unit}

    ## Goals
    - {Goal 1}
    - {Goal 2}

    ## Session Log

    ### Session 1 — 2026-04-01 (Plan)
    - Initiated feature planning
    - Created requirements.md and plan.md

    ### Session 2 — 2026-04-01 (Implement)
    - Created tasks.md
    - Implemented auth middleware in src/auth.ts

    ### Session 3 — 2026-04-02 (Verify)
    - Ran full test suite: 142/142 passing
    - Persona reviews complete (PM, Architect, QA)
    - Standards gate: all MUST rules passing

**tasks.md:**

    # Tasks: {Feature Name}

    - [x] 1. {Completed task}
    - [x] 2. {Completed task}
    - [ ] 3. {Pending task}

**requirements.md:**

    # Requirements: {Feature Name}

    ## Goal
    {What needs to be achieved}

    ## Success Criteria
    - {Criterion 1}
    - {Criterion 2}

    ## Constraints
    - {Constraint 1}

**plan.md:**

    # Plan: {Feature Name}

    ## Approach
    {High-level description of how we'll build this}

    ## Key Decisions
    - {Decision 1}: {Rationale}

    ## Risks
    - {Risk 1}: {Mitigation}

**spec.md:**

    # Specification: {Feature Name}

    ## Data Models
    {Schema changes, new types}

    ## API Interface
    {Endpoints, payloads, contracts}

    ## Edge Cases
    {Error handling, boundary conditions}

    ## Dependencies
    {What this touches, what it needs}

---

## 6. File Locations

| SDA Concept | GLaDOS Location |
|---|---|
| Work units | specs/ |
| Roadmap | product-knowledge/ROADMAP.md |
| Status document | product-knowledge/PROJECT_STATUS.md |
| Claims | claims.md (repo root) |
| Work Unit Log | product-knowledge/SPEC_LOG.md |

---

## 7. GLaDOS Extensions

These are additional artifacts not defined by the SDA standard but part of the GLaDOS governance layer.

### 7.1 Product Knowledge

| File/Directory | Purpose |
|---|---|
| product-knowledge/MISSION.md | Project mission, vision, and north star |
| product-knowledge/TECH_STACK.md | Technology choices and rationale |
| product-knowledge/standards/ | Enforceable coding/architectural rules (RFC 2119 severity) |
| product-knowledge/philosophies/ | Design principles and agreements |
| product-knowledge/observations/ | Implicitly detected patterns (staging for promotion) |
| product-knowledge/personas/ | Role-based review personas (PM, Architect, QA, custom) |
| product-knowledge/overlays/ | Local workflow customizations |
| product-knowledge/SPEC_LOG.md | Historical record of completed work units with merge commits |

### 7.2 Standards Gate

GLaDOS enforces documented standards at two checkpoints:
- Pre-implementation: After spec.md is written, before coding begins
- Post-implementation: After coding, before verification is complete

Three severity tiers:
- must — blocks the workflow
- should — logged as warning in trace
- may — informational

### 7.3 Persona Reviews

At the spec and verify phases, GLaDOS invokes persona-based reviews:
- Product Manager: "Is this valuable?"
- Architect: "Is this scalable?"
- QA: "Is this breakable?"

Custom personas can be added via product-knowledge/personas/.

### 7.4 Pattern Observer

The pattern-observer module passively detects implicit standards during normal work and logs them to product-knowledge/observations/ for later promotion via the recombobulate workflow.

---

## 8. Workflow Mapping

GLaDOS workflows map to SDA phases as follows:

| GLaDOS Workflow | SDA Phase Produced | Files Created |
|---|---|---|
| /glados/plan-feature | planning | README.md, requirements.md, plan.md |
| /glados/spec-feature | speccing | spec.md (adds to existing directory) |
| /glados/implement-feature | implementing | tasks.md (adds to existing directory) |
| /glados/verify-feature | verifying -> done | Updates README.md with verification log |
| /glados/identify-bug | planning | README.md, repro_steps.md |
| /glados/plan-fix | planning | plan.md (adds to existing bug directory) |
| /glados/implement-fix | implementing | tasks.md (adds to existing bug directory) |

Each workflow also updates product-knowledge/PROJECT_STATUS.md via the observability module.

---

## 9. Conformance Checklist

- [ ] Work unit directories are under specs/ and match YYYY-MM-DD_{prefix}_{kebab-name}/
- [ ] Every work unit has a README.md trace log
- [ ] Phase is detectable using the six-rule priority table
- [ ] product-knowledge/ROADMAP.md follows SDA roadmap grammar with {P}.{S}.{I} item IDs
- [ ] product-knowledge/PROJECT_STATUS.md follows SDA status document format
- [ ] claims.md (if present) follows SDA claims grammar
- [ ] All files use markdown checkbox syntax for completion tracking

---

## 10. Version History

| Version | Date | Notes |
|---|---|---|
| 1.0 | 2026-04-01 | Initial extraction from GLaDOS + Wheatley implied standard |
