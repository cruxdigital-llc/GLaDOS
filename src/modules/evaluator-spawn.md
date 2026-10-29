---
name: evaluator-spawn
kind: module
description: Spawn a context-isolated evaluator to verify finished work against a self-contained brief
reads: [work.base-sha, standards.index, run.active-personas, manifest.panel-personas]
writes: []
# Inlines vocabulary/loop-bounds.md — a core enabling this module must declare
# `escalation` in its emits (loop-bounds emits it on bound-hit/stalemate).
emits: [verdict]
mutates: none
requires: []
---

## Independent evaluation

An agent that implemented a change is predisposed to approve it. A fresh agent
that sees only what was supposed to be built and what was actually built will
catch problems the implementer is blind to. Two invariants, non-negotiable:

1. **Context isolation** — the evaluator starts with a clean context window.
   It inherits no conversation history, reasoning, or decisions from the agent
   that wrote the code.
2. **Filesystem-only communication** — generator and evaluator exchange
   exactly two artifacts, written beside the run record:
   `.glados/runs/<YYYY-MM-DD>-<workflow>-<slug>.evaluation-brief.md` (input)
   and `.glados/runs/<YYYY-MM-DD>-<workflow>-<slug>.evaluation.md` (output).
   No other state is shared.

### Assemble the evaluation brief

Write the brief self-contained — the evaluator must never need this
conversation:

| Section | Contents |
|---|---|
| What was requested | The requirements (for a fix, the reproduction steps), copied in full |
| What was agreed | The acceptance criteria, each with its source: the ticket, a person's words quoted (an answer to a question, with the reading it chose, among them), or the author's plan, shape or spec, labelled as the author's, each assumption they label included. A contract file takes precedence over the plan and spec only for what a person's words name; a criterion the author derived is the author's, under review like the code |
| What changed | File list plus a summary-level diff against the base commit recorded at run start (`work.base-sha`), or against the branch's merge-base with the target branch when that commit is not on the target — not the full diff; the evaluator reads files directly |
| How to verify | The full test suite and lint commands, as CI runs them, and the path of the CI configuration; app start commands/entry points; repro steps for fixes |
| Standards to enforce | The applicable standards, listed by file path so the evaluator reads them directly |
| Personas to consult | The feature's persona roster: `run.active-personas` (recorded by plan-feature); when that key is absent, the default roster in `params.review-panel.personas` from `glados.yaml`. List each persona as its name plus the path of its definition file so the evaluator reads it directly. Resolve each name project-first: `product-knowledge/personas/`, then the library personas in `.glados/personas/`. A name with no definition file in either is reported in the brief, not silently dropped |
| Canon digests | Only when this document has a *Consulting canon* section and an entry applies: each digest's path (never a summary), and the rules that section gives a fresh agent, copied verbatim. Otherwise leave this row out |
| Shape | Only when the run has a shape: its path, and each departure from it that implement-feature's `progress` outcome states, labelled as the author's. Otherwise leave this row out |
| What is deliberately out of scope | Anything the spec, plan or merge-request description declares deferred, each labelled with who deferred it: the author, or a person quoted. A deferral excuses an absence, as *What a fresh reviewer is given* sets out. Raise one where living with it breaks something, an unmet criterion the work received included, and say what breaks |
| Vocabulary | The rules in *Verdicts and finding severities* and *What a fresh reviewer is given*, copied verbatim |

<!-- glados:include vocabulary/review-inputs.md -->

<!-- glados:include vocabulary/verdicts.md -->

### Spawn the evaluator

<!-- glados:include vocabulary/agent-levels.md -->

Spawn a fresh agent with a clean context window, at the level
`params.agents.evaluator` names, and this prompt:

```
You are an evaluator. Your job is to find problems, not to confirm success.
You have no knowledge of how this work was done — only what it should do and
what it actually does. Be skeptical. Be thorough.

1. Read the evaluation brief at
   .glados/runs/<YYYY-MM-DD>-<workflow>-<slug>.evaluation-brief.md.
   It is your only context; do not ask for more.
2. Read the changed files directly. Ask for reads and searches that do not
   depend on one another together, in one step, not one per step.
3. Run every test and lint command in the brief. A test job in the CI
   configuration it names that the brief leaves out is an issue.
4. If the brief lists app entry points and you have the tools, start the app
   and use it. Do not judge by reading alone.
5. Mark each acceptance criterion PASS or FAIL, with the evidence you
   observed: the code that meets it and the test that pins it. One a test
   can pin that no test pins is an issue: blocking for a criterion the
   work received, advisory for the author's. A failed criterion the brief
   labels as the author's is not one the work received: it is an issue at
   the tier its consequence earns, and where the criterion itself is
   unnecessary, say so.
6. If the brief names a shape, list every public unit the diff adds that
   the shape does not list, and every shape unit the diff drops. One the
   brief does not list as a stated departure is an issue. A stated
   departure is not undeclared drift, but a unit it adds is still reviewed
   on its merits, and its stated reason is the author's.
7. Check the code against each standard listed in the brief, and against
   each canon digest it lists, at the weight the brief gives.
8. If the brief lists personas, read each definition file and critique the
   change from that persona's mandate.
9. List every issue: what is wrong, where (file + line), and its severity per
   the vocabulary in the brief.

Write your evaluation to
.glados/runs/<YYYY-MM-DD>-<workflow>-<slug>.evaluation.md with sections:
Acceptance criteria (criterion | source | PASS/FAIL | evidence), Shape
when the brief names one (unit | added/dropped | stated departure or not),
Standards (standard | met/violated | notes), Issues (numbered; location,
severity, what would fix it), Canon conflicts when the brief lists canon
digests (canon id | what overrides it), and Overall verdict — exactly one of:
PASS — every criterion the work received passed and no blocking issue found.
FAIL — list the blocking issues.
```

### On FAIL: fix, then re-evaluate fresh

- Fix the blocking issues.
- Reassemble the brief from scratch (the what-changed section is now stale)
  and spawn a **new** evaluator with a clean context. Never reuse, continue,
  or negotiate with the previous one — fix the code, not the evaluation.
- Each spawn is one evaluator cycle, and the cycles are bounded as
  *Loop bounds* sets out:

<!-- glados:include vocabulary/loop-bounds.md -->

### Hand the verdict back

PASS/FAIL is vocabulary internal to the generator⇄evaluator pair; it crosses
back into the workflow here and nowhere else. When the loop ends in an
evaluation that stands, this step produces a `verdict` outcome, mapped exactly
once, here: **PASS → `APPROVE`; FAIL → `REQUEST_CHANGES`**. A hit bound or
stalemate produces the `escalation` described above instead of a verdict.

That verdict is written, wherever it lands on a merge request, as
*Publishing a verdict* sets out.

<!-- glados:include vocabulary/comment-shape.md -->
