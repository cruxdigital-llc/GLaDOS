---
name: standards-gate
kind: module
description: Gate the work artifact against the project's documented standards before advancing
reads: [standards.index]
writes: []
emits: []
mutates: none
requires: []
---

## Standards gate

Before advancing past this point, audit the artifact the preceding step
produced — the spec when this gate runs before implementation, the working
diff when it runs before declaring the work done — against the project's
documented standards. The standards tree lives at
`product-knowledge/standards/` and that is the **only** standards root: a bare
`standards/` directory at the repo root is not read, not even as a fallback.

### Discover applicable standards

- Read `product-knowledge/standards/index.yml` for the registered standards.
  If the tree or its index is absent, say so in the gate report and pass the
  gate vacuously — an empty standards tree gates nothing, but skipping the
  gate silently is not the same thing.
- Each standard file carries YAML frontmatter:

  ```yaml
  ---
  scope: [api, backend]         # areas this standard applies to
  severity: must | should | may # RFC 2119
  keywords: [error, response]   # aids matching
  ---
  ```

- Filter to the standards that apply to the artifact at hand: `scope` tags
  against the areas and file types touched; `keywords` against the content of
  the spec or the changed files.
- A standard without frontmatter is `severity: should`, `scope: [all]`.
- Philosophy documents registered in the index participate like any other
  standard; treat `weight: core` as `severity: must`.

### Audit

<!-- glados:include vocabulary/verdicts.md -->

For each applicable standard, read its full content and compare the artifact
against it. A standard the artifact adheres to produces no finding. A breached
standard produces exactly one finding, classified on the single severity scale
above by the standard's declared severity:

| Standard severity | Finding    |
|-------------------|------------|
| `must`            | `blocking` |
| `should` / `may`  | `advisory` |

A standard's `must`/`should`/`may` is authoring metadata about the standard;
findings themselves take only the two tiers — no third tier exists at the
gate.

### Gate decision

- **Any `blocking` finding**: stop. Do not advance to the next step until the
  artifact is brought into compliance, then re-run the gate on the corrected
  artifact. If the standard itself appears wrong or outdated, do not weaken or
  bypass it inline — record the conflict in the gate report as a candidate for
  the standards owner to review, and either comply anyway or halt the work
  here with the conflict stated.
- **Only `advisory` findings**: proceed. State each advisory finding's
  disposition as the severity scale requires — fixed, or declined with a
  one-line reason.

### Report

Close the gate with a summary table; the surrounding workflow carries it in
its findings and outcomes:

```markdown
## Standards Gate
| Standard            | Scope   | Severity | Finding  |
|---------------------|---------|----------|----------|
| API Response Format | api     | must     | none     |
| Error Logging       | backend | should   | advisory |
```
