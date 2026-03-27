# (GLaDOS) Verify Fix

**Goal**: Ensure no regressions and close the bug using a fresh evaluator agent with no implementation context.

## Prerequisites
-   Fix is implemented and passes repro test.

## Process

### 1. Resume Trace
-   Select bug directory.
-   Log resumption.

### 2. Assemble Evaluation Brief
Invoke module: `{{MODULES}}/evaluator-handoff.md`
-   **Context**: Gather repro steps, plan, changed files, test commands, applicable standards, and review personas (QA + Architect) into a self-contained brief.

### 3. Spawn Evaluator
Invoke module: `{{MODULES}}/evaluator-spawn.md`
-   **Context**: Launch a fresh agent to verify the fix. The evaluator will run the full test suite, confirm the repro steps no longer reproduce the bug, check for side effects, and review from QA and Architect perspectives.
-   **Loop**: If the evaluator returns FAIL, fix the blocking issues, reassemble the brief, and spawn a new evaluator. Maximum 3 cycles before escalating to user.

### 4. Cleanup
-   Merge the reproduction test into the main test suite (if appropriate) to prevent regression.

### 5. Spec Retrospection
Review the implementation and reconcile documentation:
1. **Spec alignment**: Compare final implementation against the initial spec documents. Update specs with any divergences (new methods, different error handling, additional cleanup, etc.).
2. **Standards audit**: Check if any files in `product-knowledge/standards/` contain code examples, pattern descriptions, or references to code that was modified or removed during implementation. Update stale examples to reflect the current state.
3. **Trace**: Log retrospection findings in `README.md`, and update the spec.md document to reflect.

### 6. Test Synchronization
Review the tests written for this fix — do they appropriately reflect the final implementation?
1. **Stale reference scan**: Search the fix's tests for imports or references to deleted or renamed modules. Remove or update any found.
2. **Fake behavioral alignment**: For each fake or test double used by the fix's tests, verify its behavior matches the real implementation's semantics. If the real code deduplicates, validates, or filters — the fake must too.
3. **New method coverage**: For every new public method introduced by this fix, verify a corresponding test exists.
4. **Sibling comparison**: Compare the fix's test coverage against the tests of its closest existing sibling (the most architecturally similar component). Any behavioral test present in the sibling but absent in the fix's tests is a likely gap.
5. **Test Suite**: Run the full project test suite (regression check).
6. **Linting**: Run project linters.
7. **Trace**: Log results in README.md.

### 7. Completion
1.  **Status**: Update `{{STATUS}}`:
    -   Remove from "Known Issues".
    -   Add to "Recent Changes".
2.  **Trace**: Mark `specs/[...]/README.md` as CLOSED.
