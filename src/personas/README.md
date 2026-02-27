# Personas

Personas define specific viewpoints and responsibilities that the agent adopts during review gates and/or throughout active sessions.

## Persona Types

| Type | Description |
|---|---|
| **review** | Used during `persona_context` review gates — a specific *lens* applied during review |
| **operating** | Drives agent *behavior* during execution — priorities, tone, tool preferences |
| **hybrid** | Works as both review and operating persona |

## File Format

Each persona file includes YAML frontmatter:

```yaml
---
type: review | operating | hybrid
priority_areas: [security, performance]
standards_weight: [security/*]
---
```

## Default Personas

-   **`architect.md`** (hybrid): System design, coding standards, and technical debt.
-   **`product_manager.md`** (review): User value, requirements traceability, and scope control.
-   **`qa.md`** (hybrid): Testability, edge cases, and regression prevention.

## Team Manifests

Create `team.yml` to define named persona combinations for different workflow types:

```yaml
teams:
  full_review:
    personas: [product_manager, architect, qa]
  quick_review:
    personas: [architect]
```

## Customization

Add new personas by placing a markdown file with the proper frontmatter in this directory.
