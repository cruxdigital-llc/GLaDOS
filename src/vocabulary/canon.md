## Consulting canon

Canon is the reference works the project declares under `canon:` in
`glados.yaml`. If it has no `canon:` block, skip this section.

- **Which entries apply.** The consult point is the workflow you are running
  or, inside run-pipeline, the current step (`shape`, or a project step's
  id); a step's review and standards gate belong to that step. An entry
  applies when its `applies-to` names the consult point. With no
  `applies-to`, it applies at `plan-feature`, `shape`, `spec-feature`,
  `verify-feature` and `review-mr`. A canon id cited in a project step's
  body applies there too.
- **Read the digest, never the URL.** Read the file at the `digest:` path
  of each entry that applies. Never fetch its `url` during a run. If a
  digest is missing or unreadable, say so in the record or report and go
  on without it. Never fill a principle in from memory.
- **Seats.** An entry's `seats` (default `philosophy`) names the standing
  lenses or personas that apply it. Working in context, press each principle
  from the seat it names. A fresh agent (panelist, evaluator, design
  reviewer) gets the digest paths for its seats, never a summary, and the
  Weight, Recall drafts, Cite and Conflicts rules here, copied verbatim.
  An evaluator or a lone reviewer holds every seat. An entry whose seats
  are not on the panel goes to the Philosophy lens, or to every reviewer
  where there is none.
- **Weight.** Precedence, highest first: a decision the project recorded,
  its standards, its philosophies, canon. A departure from canon is an
  `advisory` finding unless a `must` standard or a `core` philosophy adopts
  the principle by citing its canon id; then it is a breach of that
  document, and the finding cites both. Either way the finding names its
  consequence: what changes in behaviour, which defect goes uncaught, or
  what someone has to work with when it fails.
- **Recall drafts.** A digest marked `drafted-from: recall` is cited with
  "(drafted from recall)" and never raises a finding above `advisory` on
  its own.
- **Cite** a principle as `canon:<name>#<principle-id>` with the digest
  path. Principle ids are the digest's `## <principle-id>` headings. Never
  paste digest text into an artifact, record or comment. An artifact you
  produce names each principle it relies on or departs from, with the
  reason for a departure.
- **Conflicts.** When canon disagrees with a higher-ranked source, the
  higher one governs, and the disagreement is an observation, not a
  finding: add an entry to the pending observations (`observations.pending`)
  naming the canon id and what overrides it, and emit an `observation`
  outcome. review-mr, which never commits to the branch it reviews,
  carries it in the outcome only. A fresh agent lists each conflict under
  **Canon conflicts** in its output instead, and the workflow that spawned
  it files it.
