# (GLaDOS) Verify Feature

**Goal**: Verify the feature against requirements and standards using a fresh evaluator agent with no implementation context.

## Prerequisites
-   Implementation is complete.

## Process

### 1. Resume Trace
-   Select the feature directory.
-   Log session resumption.

### 2. Assemble Evaluation Brief
Invoke module: `{{MODULES}}/evaluator-handoff.md`
-   **Context**: Gather requirements, spec, changed files, test commands, applicable standards, and review personas into a self-contained brief.

### 3. Spawn Evaluator
Invoke module: `{{MODULES}}/evaluator-spawn.md`
-   **Context**: Launch a fresh agent to evaluate the feature. The evaluator will run tests, interact with the app if browser tools are available, check standards compliance, and review from each persona's perspective.
-   **Loop**: If the evaluator returns FAIL, fix the blocking issues, reassemble the brief, and spawn a new evaluator. Maximum 3 cycles before escalating to user.

### 4. Spec Retrospection
After the evaluator passes, review the implementation and reconcile documentation:
1. **Spec alignment**: Compare final implementation against the initial spec documents. Update specs with any divergences (new methods, different error handling, additional cleanup, etc.).
2. **Standards audit**: Check if any files in `product-knowledge/standards/` contain code examples, pattern descriptions, or references to code that was modified or removed during implementation. Update stale examples to reflect the current state.
3. **Trace**: Log retrospection findings in `README.md`, and update the spec.md document to reflect.

### 5. Test Synchronization
Review the tests written for this feature — do they appropriately reflect the final implementation?
1. **Stale reference scan**: Search the feature's tests for imports or references to deleted or renamed modules. Remove or update any found.
2. **Fake behavioral alignment**: For each fake or test double used by the feature's tests, verify its behavior matches the real implementation's semantics. If the real code deduplicates, validates, or filters — the fake must too.
3. **New method coverage**: For every new public method introduced by this feature, verify a corresponding test exists.
4. **Sibling comparison**: Compare the feature's test coverage against the tests of its closest existing sibling (the most architecturally similar component). Any behavioral test present in the sibling but absent in the feature's tests is a likely gap.
5. **Test Suite**: Run the full project test suite (regression check).
6. **Linting**: Run project linters.
7. **Trace**: Log results in README.md.

### 6. Completion
Invoke module: `{{MODULES}}/observability.md`
-   **Context**: Close trace, move status to "Recent Changes".
-   **Extras**: Update `product-knowledge/ROADMAP.md`.
