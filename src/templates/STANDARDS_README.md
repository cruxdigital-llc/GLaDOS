# Standards

This directory contains the project's documented coding and architectural standards.

## File Format

Each standard file should include YAML frontmatter:

```yaml
---
scope: [api, backend, frontend, testing, infrastructure, all]
severity: must | should | may
keywords: [relevant, matching, terms]
---
```

### Severity (RFC 2119)
- **must**: Mandatory. Violations block the workflow.
- **should**: Recommended. Violations produce a warning but do not block.
- **may**: Optional. Noted for awareness only.

### Scope
Tags that help the `standards_gate` module match relevant standards to the current work.

## Index

All standards should be registered in `index.yml`:

```yaml
standards:
  - file: api/response_format.md
    scope: [api]
    severity: must
  - file: testing/docker_tests.md
    scope: [testing]
    severity: must
```
