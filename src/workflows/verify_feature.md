# Verify Feature

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
Invoke module: `{{MODULES}}/persona_context.md`
-   **Context**: Verifying the **Implementation** and **Test Results**.

### 4. Standards Gate (Post-Implementation)
Invoke module: `{{MODULES}}/standards_gate.md`
-   **Context**: Audit the implementation diff against applicable standards.
-   **Checkpoint**: `post-implementation`

### 5. Completion
Invoke module: `{{MODULES}}/observability.md`
-   **Context**: Close trace, move status to "Recent Changes".
-   **Extras**: Update `ROADMAP.md`.
