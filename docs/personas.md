# Personas

> Reference page. If terms like *review panel*, *manifest*, or *module*
> are new to you, read [concepts.md](concepts.md) first — everything
> past this line assumes that vocabulary.

Personas define specific viewpoints and responsibilities that the agent adopts during review gates and/or throughout active sessions.

## Persona Types

| Type | Description |
|---|---|
| **review** | Seated on review panels (`mr-review-panel`, `brunch`) — a specific *lens* applied during review |
| **operating** | Drives agent *behavior* during execution — priorities, tone, tool preferences |
| **hybrid** | Works as both review and operating persona |
| **moderator** | Seated only as `brunch`'s roundtable moderator — ranks and prunes the reviewers' findings, never reviews itself. The library ships exactly one: `brunch-moderator`. |

## File Format

Each persona file includes YAML frontmatter:

```yaml
---
type: review | operating | hybrid | moderator
priority_areas: [security, performance]
standards_weight: [security/*]
---
```

## Default Personas

The shipped persona library lives in [`src/personas/`](../src/personas/) —
each file's frontmatter declares its type and focus, and every install vendors
the library into the target's `.glados/personas/`.

## Customization

Add new personas by placing a markdown file with the proper frontmatter in your project's `product-knowledge/personas/` directory and naming it in `params.review-panel.personas`. The library personas here are vendored into `.glados/personas/` at install; the project directory is searched first.
