# (GLaDOS) Verify Feature

**Goal**: Verify the feature against requirements and standards.

## Prerequisites
-   Implementation is complete.

## Process

### 1. Resume Trace
-   Select the feature directory.
-   Log session resumption.

### 2. Automated Verification
Invoke module: `{{MODULES}}/capabilities.md`
-   **Context**: Check if Browser or DB tools can be used for extra verification.

1.  **Test Suite**: Run the full project test suite (Regression check).
2.  **Linting**: Run project linters.
3.  **Trace**: Log results in `README.md`.

### 3. Persona Verification
Invoke module: `{{MODULES}}/persona-context.md`
-   **Context**: Verifying the **Implementation** and **Test Results**.

### 4. Standards Gate (Post-Implementation)
Invoke module: `{{MODULES}}/standards-gate.md`
-   **Context**: Audit the implementation diff against applicable standards.
-   **Checkpoint**: `post-implementation`

# (GLaDOS) Verify Feature

**Goal**: Verify the feature against requirements and standards.

## Prerequisites
-   Implementation is complete.

## Process

### 1. Resume Trace
-   Select the feature directory.
-   Log session resumption.

### 2. Automated Verification
Invoke module: `.agent/modules/glados/capabilities.md`
-   **Context**: Check if Browser or DB tools can be used for extra verification.

1.  **Test Suite**: Run the full project test suite (Regression check).
2.  **Linting**: Run project linters.
3.  **Trace**: Log results in `README.md`.

### 3. Persona Verification
Invoke module: `.agent/modules/glados/persona-context.md`
-   **Context**: Verifying the **Implementation** and **Test Results**.

### 4. Standards Gate (Post-Implementation)
Invoke module: `.agent/modules/glados/standards-gate.md`
-   **Context**: Audit the implementation diff against applicable standards.
-   **Checkpoint**: `post-implementation`

### 5. Spec retrospection
Review the implementation and reconcile documentation:
1. **Spec alignment**: Compare final implementation against the initial spec documents. Update specs with any divergences (new methods, different error handling, additional cleanup, etc.).
2. **Standards audit**: Check if any files in `product-knowledge/standards/` contain code examples, pattern descriptions, or references to code that was modified or removed during implementation. Update stale examples to reflect the current state.
3. **Trace**: Log retrospection findings in `README.md`, and update the spec.md document to reflect

### 6. Test synchronization
Review the tests written for this feature — do they appropriately reflect the final implementation?
1. **Stale reference scan**: Search the feature's tests for imports or references to deleted or renamed modules. Remove or update any found.
2. **Fake behavioral alignment**: For each fake or test double used by the feature's tests, verify its behavior matches the real implementation's semantics. If the real code deduplicates, validates, or filters — the fake must too.
3. **New method coverage**: For every new public method introduced by this feature, verify a corresponding test exists.
4. **Sibling comparison**: Compare the feature's test coverage against the tests of its closest existing sibling (the most architecturally similar component). Any behavioral test present in the sibling but absent in the feature's tests is a likely gap.
5. **Test Suite**: Run the full project test suite (regression check).
6. **Linting**: Run project linters.
7. **Trace**: Log results in README.md

### 7. Completion
Invoke module: `.agent/modules/glados/observability.md`
-   **Context**: Close trace, move status to "Recent Changes".
-   **Extras**: Update `product-knowledge/ROADMAP.md`.
