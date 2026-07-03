---
name: evaluator-spawn
kind: module
description: Spawn a context-isolated evaluator to verify finished work against a self-contained brief
reads: [work.base-sha, standards.index]
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
| What was agreed | The acceptance criteria from the spec or plan; a contract file, if one exists, takes precedence |
| What changed | File list plus a summary-level diff against the base commit recorded at run start (`work.base-sha`) — not the full diff; the evaluator reads files directly |
| How to verify | Test and lint commands, app start commands/entry points, repro steps for fixes |
| Standards to enforce | The applicable standards, listed by file path so the evaluator reads them directly |
| Vocabulary | The severity and verdict rules below, copied verbatim |

<!-- glados:include vocabulary/verdicts.md -->

### Spawn the evaluator

Spawn a fresh agent with a clean context window and this prompt:

```
You are an evaluator. Your job is to find problems, not to confirm success.
You have no knowledge of how this work was done — only what it should do and
what it actually does. Be skeptical. Be thorough.

1. Read the evaluation brief at
   .glados/runs/<YYYY-MM-DD>-<workflow>-<slug>.evaluation-brief.md.
   It is your only context; do not ask for more.
2. Read the changed files directly.
3. Run every test and lint command in the brief.
4. If the brief lists app entry points and you have the tools, start the app
   and use it. Do not judge by reading alone.
5. Mark each acceptance criterion PASS or FAIL, with the evidence you
   observed.
6. Check the code against each standard listed in the brief.
7. List every issue: what is wrong, where (file + line), and its severity per
   the vocabulary in the brief.

Write your evaluation to
.glados/runs/<YYYY-MM-DD>-<workflow>-<slug>.evaluation.md with sections:
Acceptance criteria (criterion | PASS/FAIL | evidence), Standards
(standard | met/violated | notes), Issues (numbered; location, severity,
what would fix it), and Overall verdict — exactly one of:
PASS — every criterion passed and no blocking issue found.
FAIL — list the blocking issues.
```

### On FAIL: fix, then re-evaluate fresh

- Fix the blocking issues.
- Reassemble the brief from scratch (the what-changed section is now stale)
  and spawn a **new** evaluator with a clean context. Never reuse, continue,
  or negotiate with the previous one — fix the code, not the evaluation.
- Each spawn is one evaluator cycle:

<!-- glados:include vocabulary/loop-bounds.md -->

### Hand the verdict back

PASS/FAIL is vocabulary internal to the generator⇄evaluator pair; it crosses
back into the workflow here and nowhere else. When the loop ends in an
evaluation that stands, this step produces a `verdict` outcome, mapped exactly
once, here: **PASS → `APPROVE`; FAIL → `REQUEST_CHANGES`**. A hit bound or
stalemate produces the `escalation` described above instead of a verdict.
