---
name: glados-framework
description: An advanced agentic software development framework. Use this skill when the user wants to plan features, write specifications, implement code, verify changes, or manage the project (mission, roadmap). It provides strict traceability and role-based reviews.
---

# GLaDOS Framework

You have activated the GLaDOS Framework. This skill provides a set of rigorous workflows to guide software development.

## Available Workflows

You can find the specific instructions for each workflow in the `workflows/` directory provided by this skill.

### Core Development
-   **Plan Feature**: `workflows/plan-feature.md` - Analyze requirements, select personas, update roadmap.
-   **Spec Feature**: `workflows/spec-feature.md` - Create detailed technical specifications.
-   **Implement Feature**: `workflows/implement-feature.md` - Execute the coding loop with traceability.
-   **Verify Feature**: `workflows/verify-feature.md` - Run tests and architectural sign-off.
-   **Identify Bug**: `workflows/identify-bug.md` - Reproduce and isolate issues.
-   **Plan Fix**: `workflows/plan-fix.md` - Design a regression-free fix.
-   **Implement Fix**: `workflows/implement-fix.md` - Apply the fix.
-   **Verify Fix**: `workflows/verify-fix.md` - Verify resolution.

### Project Setup & Maintenance
-   **Mission**: `workflows/mission.md`
-   **Plan Product**: `workflows/plan-product.md`
-   **Establish Standards**: `workflows/establish-standards.md`
-   **Review Codebase**: `workflows/review-codebase.md`
-   **Adopt Codebase**: `workflows/adopt-codebase.md` - Full brownfield onboarding.
-   **Retrospect**: `workflows/retrospect.md`
-   **Recombobulate**: `workflows/recombobulate.md` - Clean up vibe debt, formalize patterns.
-   **Consolidate**: `workflows/consolidate.md` - Alias for Recombobulate.

## Architecture

This skill also includes:
-   **Modules** (`modules/`): Reusable logic for Observability, Persona Context (review + operating modes), Standards Gate (3-tier enforcement), Pattern Observer (implicit standard detection), and Capabilities.
-   **Personas** (`personas/`): Role definitions with type metadata (review, operating, hybrid).

## Instructions

1.  **Identify the User's Goal**: implementation, planning, debugging?
2.  **Select the Workflow**: Read the corresponding file from `workflows/`.
3.  **Execute**: Follow the workflow steps exactly.
    -   When the workflow says "Invoke module", look for the file in the `modules/` directory of this skill.
    -   When the workflow says "Scan personas", look in the `personas/` directory of this skill.
