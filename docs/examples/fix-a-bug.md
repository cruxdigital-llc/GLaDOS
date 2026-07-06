# Worked example: fixing a bug end to end

GLaDOS is a library of engineering workflows for AI coding agents: you install
it into a project (see [first-feature.md](first-feature.md) for the install
itself), and your agent gains slash commands that follow a disciplined,
team-visible process. This page walks the bug pipeline — one command,
`/glados:fix-bug`, that takes a bug from report through reproduction to a
verified root-cause fix on a merge request.

The project is the same fictional `tickets-api` from the first walkthrough:
GitLab-hosted, `glados.yaml` in the root with the default outcome routing
(`bug: [issue]`, `verdict: [mr-comment]`, `escalation: [issue]`). Session
output on this page is illustrative — the commands, file paths, and required
artifacts are real.

## 0. The report

A user writes in: *"Searching tickets with a quoted phrase returns a 500."*
Paste exactly that — or an issue URL, or a stack trace — into the command:

```
/glados:fix-bug searching tickets with a quoted phrase returns a 500
```

Two rules govern everything that follows: **fail fast** (a step that cannot
succeed stops the run loudly instead of limping forward) and **fix root
causes, not symptoms** (a fix that hides the symptom without explaining the
failure is a band-aid, and a band-aid is a bug with better camouflage).

## 1. Reproduce — and the bug becomes a tracked issue

First the agent builds a reproduction: a failing test where the defect can be
captured by one, a script otherwise. *Why this gate: patching what you cannot
reproduce is guessing.* If it cannot reproduce the bug, the run stops and
posts an escalation describing what was tried — it never proceeds on a hunch.

```python
def test_search_with_quoted_phrase_returns_results():
    resp = client.get("/tickets", params={"q": '"login failed"'})
    assert resp.status_code == 200   # currently: 500
```

The reproduction is published as a **`bug` outcome**. Outcomes are typed
results a workflow emits, and `glados.yaml`'s `channels:` section routes each
type to a destination the team can see. With the default `bug: [issue]`
binding, the agent files a GitLab issue with its own platform tooling:

```
$ glab issue create --title 'bug: quoted-phrase ticket search returns 500' ...
#213 https://gitlab.example.com/acme/tickets-api/-/issues/213
```

The issue carries the exact steps, inputs, observed-vs-expected behavior, and
the failing test. *Why: the defect is now on record independently of any
fix — if the fix stalls, the bug does not evaporate with the session.*

## 2–3. Branch, then find the root cause

The agent cuts a branch per the `branching.feature` pattern in `glados.yaml`
(the **manifest** — the project's one GLaDOS configuration file), here
`feat/quoted-search-500`, then isolates the fault before editing anything:
follow the stack trace and the failing test to the module at fault, ask "why
did this happen?" until the answer stops changing (5 Whys), and run two
checks — the **band-aid check** (does the proposed fix remove the cause or
only the symptom?) and the **side-effect check** (what else calls this path?).

Illustrative diagnosis: the search endpoint splits the query on whitespace
before the quote-parser runs, so quoted phrases produce an unbalanced token —
root cause in `search/parser.py:tokenize()`, not in the endpoint that 500s.

## 4. Implement — red must go green

The fix lands in `tokenize()`. The reproduction test from step 1 must flip
red → green; that flip is **the only accepted proof** that the fix addresses
the reproduced defect. If it does not flip, the root cause was misdiagnosed
and the agent returns to diagnosis — it never stacks a second patch on a
first guess. The test then joins the suite permanently as the regression
guard this bug pays forward.

## 5–6. Commit, then independent verification

Commits follow the project's conventions (conventional-commit prefixes, no
attribution lines, `git add`/`commit`/`push` run separately). Then a **fresh
evaluator** — a separate agent session with no memory of how the fix was
written — confirms the reproduction no longer reproduces, runs the full test
suite, and checks for side effects around the changed code. *Why: the agent
that wrote the fix is predisposed to bless it.* Each evaluation posts a
verdict; the fix/re-verify cycle is bounded by `params.evaluator.max-cycles`
in `glados.yaml`. Past the bound, the run stops and escalates — an unverified
fix is worse than an open bug, because it closes the ticket without closing
the defect.

## 7. The merge request

Only now does an MR open, targeting `branching.default-target` from the
manifest:

```
$ glab mr create --source-branch feat/quoted-search-500 --target-branch main \
    --title 'fix: parse quoted phrases before tokenizing ticket search' ...
!52 https://gitlab.example.com/acme/tickets-api/-/merge-requests/52
```

Its description links the three artifacts the pipeline produced: the bug
issue (#213), the reproduction, and the verification result. The bug is
closed by the **pair** — the fix MR plus its verified verdict; neither alone
closes it. Merging stays with whoever `merge-authority` in the manifest
names; the workflow never merges.

## What the run ledger shows

Like every workflow run, this one leaves a single committed record in
`.glados/runs/` (the run ledger — the project's durable memory).
Illustrative but shape-accurate:

```bash
$ cat .glados/runs/2026-07-03-fix-bug-quoted-search-500.md
# fix-bug: quoted-search-500  (2026-07-03)
- base-sha: 9d31e07c
- reproduction: test_search_with_quoted_phrase_returns_results (red)
- bug outcome: issue #213
- root cause: tokenize() splits on whitespace before quote parsing
- verify: cycle 1 APPROVE (fresh evaluator; suite green, repro green)
- MR: !52, target main
- outcomes: bug→#213, verdict→!52 comment, progress→ledger
```

From here the MR enters the same review loop as any feature —
`/glados:review-mr` ⇄ `/glados:address-review`, described in
[first-feature.md](first-feature.md#5-the-review-loop).

## Old names still work

If your notes or muscle memory say `identify-bug`, `plan-fix`,
`implement-fix`, or `verify-fix`: those were four separate commands in GLaDOS
v1. They are permanent aliases now — each redirects to `fix-bug`, and the
phase you meant is a step inside it. See
[../../MIGRATION.md](../../MIGRATION.md) for the full name map.
