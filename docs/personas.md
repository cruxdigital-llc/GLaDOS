# Personas

Personas define specific viewpoints and responsibilities that the agent adopts during review gates and/or throughout active sessions.

## Persona Types

| Type | Description |
|---|---|
| **review** | Seated on review panels (`mr-review-panel`, `brunch`) — a specific *lens* applied during review |
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
-   **`product-manager.md`** (review): User value, requirements traceability, and scope control.
-   **`qa.md`** (hybrid): Testability, edge cases, and regression prevention.

## Team Manifests

Create `team.yml` to define named persona combinations for different workflow types:

```yaml
teams:
  full_review:
    personas: [product-manager, architect, qa]
  quick_review:
    personas: [architect]
```

## Customization

Add new personas by placing a markdown file with the proper frontmatter in your project's `product-knowledge/personas/` directory and naming it in `params.review-panel.personas`. The library personas here are vendored into `.glados/personas/` at install; the project directory is searched first.
