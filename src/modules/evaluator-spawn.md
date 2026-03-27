# GLaDOS Evaluator Spawn Module

**Goal**: Spawn a fresh agent with a clean context window to evaluate work, ensuring the evaluator has no knowledge of the implementation journey.

## Usage
Invoked by `verify-feature.md` and `verify-fix.md` after the evaluation brief has been assembled.

## Why This Exists
An agent that implemented the code is predisposed to approve it. A fresh agent that only sees what was supposed to be built and what was actually built will catch problems the implementer is blind to.

## Instructions

### 1. Spawn the Evaluator
Use the **Agent tool** (or equivalent subprocess mechanism) to launch a new agent with the following prompt structure:

```
You are a QA evaluator. Your job is to find problems, not confirm success.
You have no knowledge of how this code was written — only what it should do
and what it actually does. Be skeptical. Be thorough.

## Your Inputs
Read the evaluation brief at: specs/[trace-dir]/evaluation-brief.md

## Your Process
1. Read the evaluation brief to understand what was requested and what was agreed to.
2. Read the changed files directly to understand what was built.
3. Run the test suite and linters specified in the brief.
4. If browser/UI tools are available, navigate to the app and interact with it.
   Do not just read the code — use the thing.
5. For each acceptance criterion in the brief, determine: PASS or FAIL.
6. Check the code against each applicable standard listed in the brief.
7. Adopt each review persona listed in the brief and critique from that perspective.

## Your Output
Write your evaluation to: specs/[trace-dir]/evaluation.md

Use this format:

### Acceptance Criteria
| Criterion | Verdict | Evidence |
|-----------|---------|----------|
| ...       | ✅ PASS / ❌ FAIL | What you observed |

### Standards Compliance
| Standard | Verdict | Notes |
|----------|---------|-------|
| ...      | ✅ / ❌ / ⚠️ | ... |

### Persona Reviews
For each persona, a short review paragraph.

### Issues Found
Numbered list of specific issues. For each:
- What is wrong
- Where it is (file + line)
- Severity: blocking / warning / note

### Overall Verdict
PASS — all acceptance criteria met, no blocking issues.
OR
FAIL — list the blocking issues that must be resolved.
```

### 2. Read the Verdict
After the evaluator agent completes:
1.  **Read** `specs/[trace-dir]/evaluation.md`.
2.  **Check** the "Overall Verdict" section.

### 3. Handle the Result

#### If PASS:
-   Log the evaluation summary in the trace `README.md`.
-   Proceed to completion.

#### If FAIL:
-   Log the issues in the trace `README.md`.
-   For each blocking issue, create a fix task.
-   Return to implementation to address the blocking issues.
-   After fixes, re-invoke `evaluator-handoff.md` to assemble a fresh brief.
-   **Spawn a new evaluator** — never reuse the previous one.
-   Repeat until PASS or a maximum of 3 evaluation cycles (then escalate to user).

### 4. Escalation
If the evaluator fails 3 cycles:
-   **STOP**: Do not continue looping.
-   **Log**: "BLOCKER: Evaluator has rejected 3 times. Escalating to user."
-   Present all 3 evaluations to the user for a decision.
