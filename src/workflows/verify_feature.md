# Verify Feature

**Goal**: Verify the feature against requirements and standards.

## Prerequisites
-   Implementation is complete.

## Process

### 1. Resume Trace
-   Select the feature directory.
-   Log session resumption.

### 2. Automated Verification
Invoke module: `glados/modules/capabilities.md`
-   **Context**: Check if Browser or DB tools can be used for extra verification.

1.  **Test Suite**: Run the full project test suite (Regression check).
2.  **Linting**: Run project linters.
3.  **Trace**: Log results in `README.md`.

### 3. Persona Verification
Invoke module: `glados/modules/persona_review.md`
-   **Context**: Verifying the **Implementation** and **Test Results**.

### 5. Completion
Invoke module: `glados/modules/observability.md`
-   **Context**: Close trace, move status to "Recent Changes".
-   **Extras**: Update `ROADMAP.md`.
