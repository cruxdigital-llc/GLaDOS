# Personas

Personas define specific viewpoints and responsibilities that the agent adopts during the Review and Verification phases.

## Default Personas

-   **`product_manager.md`**: Focuses on user value, requirements traceability, and scope control.
-   **`architect.md`**: Focuses on system design, coding standards (`standards/`), and technical debt.
-   **`qa.md`**: Focuses on testability, edge cases, and regression prevention.

## Customization

You can add new personas by simply placing a markdown file in this directory (e.g., `security_expert.md`). The `persona_review` module will automatically detect them during installation/execution.
