# Workflows

Workflows are the entry points for Agent interaction. They define the high-level steps for specific tasks.

## Categories

### Greenfield / Setup
-   **`mission.md`**: Define the product mission.
-   **`plan-product.md`**: Establish the roadmap and tech stack.
-   **`establish-standards.md`**: Extract tribal knowledge into written standards.
-   **`review-codebase.md`**: Spider the directory to build `PROJECT_STATUS.md`.
-   **`adopt-codebase.md`**: Full brownfield onboarding sequence (orchestrates review, standards, mission).

### Feature Lifecycle (Split)
-   **`plan-feature.md`**: Analyze requirements and select personas.
-   **`spec-feature.md`**: Create detailed technical specifications.
-   **`implement-feature.md`**: Execute the coding loop.
-   **`verify-feature.md`**: Run tests and persona-based audits.

### Bugfix Lifecycle (Split)
-   **`identify-bug.md`**: Reproduce and isolate issues.
-   **`plan-fix.md`**: Design a regression-free fix.
-   **`implement-fix.md`**: Apply the fix.
-   **`verify-fix.md`**: Verify resolution.

### Maintenance
-   **`retrospect.md`**: Review recent work to improve standards or process.
-   **`recombobulate.md`**: Systematically clean up vibe debt, formalize patterns, audit standards.
-   **`consolidate.md`**: Alias for `recombobulate.md`.

### Autonomous Mode
-   **`autonomous-loop.md`**: Continuous feature delivery without user intervention. Reads the roadmap and executes Plan → Spec → Implement → Verify in a loop, answering its own questions via the interaction proxy.
