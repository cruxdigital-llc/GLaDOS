## Verdicts and finding severities

There is exactly one severity scale and one verdict vocabulary. No reviewer,
panelist, or evaluator may introduce another tier or another verdict word.

**Finding severities — two tiers only:**

| Severity | Meaning |
|----------|---------|
| `blocking` | The change must not merge as-is: it breaks behaviour, breaks an acceptance criterion, opens a security, tenancy or data-loss hole, crosses a boundary the project's architecture standards draw, or leaves a test gap that hides one of these. |
| `advisory` | Worth one line, not worth blocking: style, naming, simplification, prose, a standard whose breach changes no behaviour and crosses no boundary, any suggestion the author may decline. |

Code is the truth and prose points at it. A finding about a comment, a
docstring, a README, a commit message or a merge-request description is
`advisory`, always: prose cannot break the build, and a review that blocks on
it teaches the team to skim the next one. Fix prose you pass through when the
fix is cheap; otherwise say it in one line.

Unsure whether a finding blocks? Then it is `advisory`, written as the
question it is. A wrong `blocking` finding costs more than a missed one: it
sends the author to refactor around a defect that does not exist.

**A finding is about code the change introduced.** Most codebases predate the
standards they are now held to, so a lens reading a touched file finds
breaches the author never wrote. Those are not this review's findings. A
breach that already existed in a file the change touches is noted, not
blocking, and the whole set of them is worth **one line** pointing at
wherever the project tracks bringing existing code up to standard — never one
finding per instance. Listing them buries the three findings the author can
act on among the fifteen they cannot, and an author who has skimmed one
review skims the next one, which is how a real finding gets missed.

Two things are not pre-existing, whatever their line numbers say: a breach
the change makes worse, and one the change now depends on. Both are findings
about this change and land at whatever tier they earn.

**For every type, field or parameter a change adds, name the line that reads
it.** No reader, no field. Say which line, not that one probably exists —
a reader you cannot point at is the finding.

This cuts the opposite way from the observation it is usually confused with.
"This value is computed and then dropped" is a true sentence that sounds like
a request to carry the value further, and carrying it is the expensive answer:
a field, a shape to hold it, a caller to thread it, and a test for each. The
cheap answer is almost always that nobody wanted the value, and the fix is to
stop computing it. Ask which before asking for plumbing. The same applies to a
value carried across a step boundary that the later step never acts on: that
is not information, it is coupling, and the step that stores a result does not
need to know why the step before it kept one.

A review can establish that nothing reads a field. It cannot establish that
nothing *should* — a reader someone is about to write is invisible here, and
"a later ticket will use it" is a real answer that only the people who know
what the system is for can weigh. So this is stated as the fact and never as
a demand: "nothing reads `x`" is the finding; "delete `x`" is a suggestion
the author may decline like any other. It is `advisory` unless the unread
thing also breaks something.

**A finding is a claim and its evidence, and they are not the same length.**
The claim is what breaks, where, and what to do about it — a few lines, in
plain sentences. The evidence is the reproduction, the measurement, the walk
through the mechanism, the reason the obvious fix is the wrong one. Both are
owed. Only the claim is owed *on the first screen*.

Wherever a verdict is published, write it so that a reader who expands
nothing still learns every blocking thing they have to do. Evidence goes
beneath its claim, folded where the platform can fold it and last where it
cannot. This is what keeps two rules from fighting: a review may never drop a
finding, and a review nobody finishes reading has dropped all of them. A
comment gets shorter by putting its proof one click down, never by leaving
the proof out — and a finding that cannot state its ask in one line at the
top has not been understood well enough to post.

**Verdicts:** `APPROVE | REQUEST_CHANGES | ESCALATE`.

**Composition rules (applied at the tally, not left to individual reviewers):**

- Any `blocking` finding ⇒ `REQUEST_CHANGES`.
- A missing or malformed panelist verdict ⇒ `ESCALATE` — never approval.
  Silence is not consent; respawn or escalate, do not count it as a pass.
- Advisory-only findings ⇒ `APPROVE`. Advisories are offered, not owed: the
  author may fix, decline or ignore them, and approval waits on none of them.
