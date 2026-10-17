## Fresh-agent design review

A review of a step's artifact by a new agent that did not write it. An author
reviewing its own work is the weak case; this is the strong one. It keeps the
evaluator's two invariants:

1. **Context isolation.** The reviewer starts with a clean context window.
   It inherits no conversation history, reasoning or decisions from this run.
2. **Filesystem-only communication.** The run and the reviewer exchange
   exactly two files, written beside the run record:
   `<record>.<id>.review-brief.md` (input) and `<record>.<id>.review.md`
   (output). Nothing else is shared.

### Assemble the review brief

Write the brief self-contained. The reviewer must never need this
conversation:

| Section | Contents |
|---|---|
| What to review | The artifact path or paths: the step's own file, or for a gate, the artifact it audits. For code, the changed files and the base commit (`work.base-sha`). |
| What to check | For a project step, its body: `product-knowledge/steps/<id>.md`. For a built-in step, what its artifact must contain, copied from the document that defines it (this one for shape, the stage's own workflow for plan-feature and spec-feature), and the plan or brief it answers. |
| Personas to seat | Each persona's name and definition file path, resolved as *Persona pass* resolves them |
| Standards and canon | The applicable files under `product-knowledge/standards/` (philosophies included) and, when `glados.yaml` declares `canon:`, the digest of each entry that applies at the reviewed step, as *Consulting canon* sets out (a lone reviewer holds every seat), and the rules that section gives a fresh agent, copied verbatim. Paths, never summaries. |
| What is deliberately out of scope | Anything the plan, the spec or an earlier step deferred: a decision already made, not a gap to report back. Raise one only where living with it breaks something, and then say what breaks |
| Vocabulary | The rules in *Verdicts and finding severities*, copied verbatim |

<!-- glados:include vocabulary/verdicts.md -->

### Spawn the reviewer

Spawn a fresh agent with a clean context window and this prompt:

```
You are a design reviewer. Your job is to find problems, not to approve.
You have no knowledge of how this artifact was made, only what it should be
and what it is.

1. Read the review brief at <record>.<id>.review-brief.md. It is your only
   context; do not ask for more.
2. Read every file the brief names, directly.
3. Check the artifact against what the brief says to check, through each
   persona it seats, against each standard it lists, and against the
   principles in each canon digest it lists, at the weight the brief gives.
4. Run no tests and edit nothing.
5. List every issue: what is wrong, where (file, and section or line), its
   severity per the vocabulary in the brief, and what would fix it.

Write your review to <record>.<id>.review.md with sections: Checks
(item | met/not met | notes), Issues (numbered; location, severity, what
would fix it), Canon conflicts when the brief lists canon digests (canon
id | what overrides it), and Result, exactly one of:
PASS: no blocking issue found.
FAIL: list the blocking issues.
```

### Use the result

- FAIL is a `blocking` finding for the step, handled by its modifier: revise
  the artifact, then review again. PASS with advisory issues records them in
  the step's row.
- Each cycle spawns a **new** reviewer from a freshly written brief. Never
  reuse, continue or negotiate with an earlier one: fix the artifact, not the
  review. Cycles count against the step's bound, `params.pipeline.max-cycles`.
- File each canon conflict the review lists, as *Consulting canon* sets
  out. A conflict is never a finding and never fails the review.
- Record the brief and review paths in the step's row. The result feeds the
  step table and, for a gate, its pass or fail. It never becomes a `verdict`
  outcome.
