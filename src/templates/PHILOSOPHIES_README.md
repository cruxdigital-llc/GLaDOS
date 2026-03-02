# Philosophies

This directory contains the project's high-level design philosophies — guiding principles that inform decision-making beyond specific coding standards.

## What is a Philosophy?

A standard says *what* to do: "All API responses use `{ success, data }` wrapper."
A philosophy says *why* and *when*: "All APIs should be RESTful" or "User flows should involve at most 3 clicks."

## File Format

```yaml
---
domain: api | ux | architecture | operations | testing | all
weight: core | preferred | aspirational
---
```

### Weight Levels

| Weight | Meaning | Enforcement |
|---|---|---|
| **core** | Non-negotiable. The team has explicitly committed to this. | Blocks workflow (like a `must` standard). |
| **preferred** | Default approach. Deviations require justification. | Warning in trace. |
| **aspirational** | Where we want to be. No enforcement yet. | Informational only. |

## Example

```markdown
---
domain: api
weight: core
---
# All APIs Should Be RESTful

## Statement
All public-facing APIs must follow REST conventions...

## Rationale
[Why we believe this]

## Exceptions
[When it's OK to break this]
```
