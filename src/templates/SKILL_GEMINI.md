---
name: glados-framework
description: An advanced agentic software development framework. Use this skill when the user wants to plan features, write specifications, implement code, verify changes, or manage the project (mission, roadmap). It provides strict traceability and role-based reviews.
---

# GLaDOS Framework

You have activated the GLaDOS Framework. This skill provides a set of rigorous workflows to guide software development.

## Available Workflows

You can find the specific instructions for each workflow in the `workflows/` directory provided by this skill.

### Core Development
-   **Plan Feature**: `workflows/plan_feature.md` - Analyze requirements, select personas, update roadmap.
-   **Spec Feature**: `workflows/spec_feature.md` - Create detailed technical specifications.
-   **Implement Feature**: `workflows/implement_feature.md` - Execute the coding loop with traceability.
-   **Verify Feature**: `workflows/verify_feature.md` - Run tests and architectural sign-off.
-   **Identify Bug**: `workflows/identify_bug.md` - Reproduce and isolate issues.
-   **Plan Fix**: `workflows/plan_fix.md` - Design a regression-free fix.
-   **Implement Fix**: `workflows/implement_fix.md` - Apply the fix.
-   **Verify Fix**: `workflows/verify_fix.md` - Verify resolution.

### Project Setup & Maintenance
-   **Mission**: `workflows/mission.md`
-   **Plan Product**: `workflows/plan_product.md`
-   **Establish Standards**: `workflows/establish_standards.md`
-   **Review Codebase**: `workflows/review_codebase.md`
-   **Retrospect**: `workflows/retrospect.md`

## Architecture

This skill also includes:
-   **Modules** (`modules/`): Reusable logic for Observability (`observability.md`) and Persona Reviews (`persona_review.md`).
-   **Personas** (`personas/`): Role definitions (Product Manager, Architect, QA) used during reviews.

## Instructions

1.  **Identify the User's Goal**: implementation, planning, debugging?
2.  **Select the Workflow**: Read the corresponding file from `workflows/`.
3.  **Execute**: Follow the workflow steps exactly.
    -   When the workflow says "Invoke module", look for the file in the `modules/` directory of this skill.
    -   When the workflow says "Scan personas", look in the `personas/` directory of this skill.
