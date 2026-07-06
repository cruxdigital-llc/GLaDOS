## Verdicts and finding severities

There is exactly one severity scale and one verdict vocabulary. No reviewer,
panelist, or evaluator may introduce another tier or another verdict word.

**Finding severities — two tiers only:**

| Severity | Meaning |
|----------|---------|
| `blocking` | The change must not merge as-is: a defect, a broken acceptance criterion, a violated standard, a security/data-loss hole, or a test gap that hides one of these. |
| `advisory` | Worth stating, not worth blocking: style, naming, simplification, a suggestion the author may reasonably decline. |

Classify every finding as one or the other. If you are unsure which, it is
`blocking` — uncertainty about whether something blocks is itself blocking.

**Verdicts:** `APPROVE | REQUEST_CHANGES | ESCALATE`.

**Composition rules (applied at the tally, not left to individual reviewers):**

- Any `blocking` finding ⇒ `REQUEST_CHANGES`.
- A missing or malformed panelist verdict ⇒ `ESCALATE` — never approval.
  Silence is not consent; respawn or escalate, do not count it as a pass.
- Advisory-only findings MAY yield `APPROVE` with notes, but each advisory
  finding's disposition must be stated: **fix** (with the commit) or
  **decline** (with a one-line reason). An unaddressed advisory list is not
  an approval.
