# Personas

> Reference page. If terms like *review panel*, *manifest*, or *module*
> are new to you, read [concepts.md](concepts.md) first — everything
> past this line assumes that vocabulary.

Personas define specific viewpoints and responsibilities that the agent adopts during review gates and/or throughout active sessions.

## Persona Types

| Type | Description |
|---|---|
| **review** | Seated on review panels (`mr-review-panel`, `brunch`), consulted by the `evaluator-spawn` evaluator, and seated in spec-feature's and `run-pipeline`'s persona passes and `run-pipeline`'s fresh-agent design reviews — a specific *lens* applied during review |
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

## Canon seats

A `canon:` entry in `glados.yaml` names the reviewers that apply it under `seats:`: one of the five standing lenses (`uat`, `adversarial`, `standards`, `philosophy`, `dead-code`) or a persona by file name, from the library or from `product-knowledge/personas/`. Without `seats:`, an entry goes to the Philosophy lens; a list you write replaces that default. A seated persona gets the digest paths routed to it with its mandate, never a summary, plus canon's rules for weight, citation and conflicts, so its canon findings stay advisory unless a standard adopts the principle. On a panel where none of an entry's seats sits, the Philosophy lens takes it; brunch seats personas only, so there every reviewer gets it. `install`, `check` and `validate` reject a seat that is neither a lens nor a persona. See [guides/canon.md](guides/canon.md).

A persona can also stand in for canon on a GLaDOS without it: write the work's principles as a project persona and seat it on the panel. The guide's last section shows how, and how to move it into a digest later.
