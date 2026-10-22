## Fresh-agent design review

A review of a step's artifact by a new agent that did not write it. It
keeps the evaluator's two invariants:

1. **Context isolation.** The reviewer starts with a clean context window.
   It inherits no conversation history, reasoning or decisions from this run.
2. **Filesystem-only communication.** The run and the reviewer exchange
   exactly two files beside the run record, numbered n by the check
   (**Bound** in step 4): `<record>.<id>.review-brief-<n>.md` (input) and
   `<record>.<id>.review-<n>.md` (output). Nothing else is shared.

### Assemble the review brief

Write the brief self-contained:

| Section | Contents |
|---|---|
| What to review | The artifact path or paths: the step's own file, or for a gate, the artifact it audits. For code, the changed files and the base commit (`work.base-sha`, or the branch's merge-base with the target branch when that commit is not on the target). |
| What to check | For a project step, its body: `product-knowledge/steps/<id>.md`. For a built-in step, what its artifact must contain, copied from the document that defines it (this one for shape, the stage's own workflow for plan-feature and spec-feature), and the plan or brief it answers. |
| What was asked | The ticket, each instruction a person gave this run, and each question answered, with its readings and answer, copied verbatim with where said: the criteria the work received |
| Personas to seat | Each persona's name and definition file path, resolved as *Persona pass* resolves them |
| Standards and canon | The applicable files under `product-knowledge/standards/` (philosophies included) and, when `glados.yaml` declares `canon:`, the digest of each entry that applies at the reviewed step, as *Consulting canon* sets out, and the rules that section gives a fresh agent, copied verbatim. Paths, never summaries. |
| What is deliberately out of scope | Anything the plan, the spec or an earlier step deferred, each labelled with who deferred it: the author, or a person quoted. A deferral excuses an absence, as *What a fresh reviewer is given* sets out. Raise one where living with it breaks something, an unmet criterion the work received included, and say what breaks |
| Findings still open | Those the cycle table leaves open, by number, copied verbatim from where they were raised |
| Vocabulary | The rules in *Verdicts and finding severities*, *What a fresh reviewer is given* and *Questions for a person*, copied verbatim |

<!-- glados:include vocabulary/review-inputs.md -->

<!-- glados:include vocabulary/questions.md -->

<!-- glados:include vocabulary/verdicts.md -->

### Spawn the reviewer

Spawn a fresh agent with this prompt:

```
You are a design reviewer. Your job is to find problems, not to approve.
You have no knowledge of how this artifact was made, only what it should be
and what it is.

1. Read the review brief at <record>.<id>.review-brief-<n>.md. It is your
   only context; do not ask for more.
2. Read every file the brief names, directly.
3. Check the artifact against what the brief says to check, through each
   persona it seats, against each standard it lists, and against the
   principles in each canon digest it lists, at the weight the brief gives.
4. Run no tests and edit nothing.
5. Report each finding the brief names as open: closed, only when nothing
   else in the artifact has the same defect (no other path, input or place
   of its kind); not closed, and where it still holds; or not a defect,
   and why. One not closed is still blocking.
6. List every other issue: what is wrong, where (file, and section or
   line), its severity per the vocabulary in the brief, and what would fix
   it.
7. Check each assumption the artifact labels, and raise questions for a
   person, as the vocabulary in the brief sets out.

Write your review to <record>.<id>.review-<n>.md with sections: Checks
(item | met/not met | notes), Open findings (number | status | where or
why), Issues (numbered; location, severity, what would fix it), Questions
for a person, Canon conflicts when the brief lists canon digests (canon
id | what overrides it), and Result, exactly one of:
PASS: no blocking issue.
FAIL: list the blocking issues, open findings not closed included.
```

### Use the result

- FAIL is a `blocking` finding for the step, handled by its modifier. The
  result feeds the step's cycle table (**Bound**) and, for a gate, its pass
  or fail.
- Each check spawns a **new** reviewer from a freshly written brief. Never
  reuse, continue or negotiate with an earlier one: fix the artifact, not the
  review.
- File each canon conflict the review lists, as *Consulting canon* sets
  out. A conflict is never a finding and never fails the review.
