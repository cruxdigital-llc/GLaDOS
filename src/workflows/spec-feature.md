# (GLaDOS) Spec Feature

**Goal**: Create a detailed technical specification for the feature.

## Prerequisites
- [ ] Feature directory exists (`specs/[YYYY-MM-DD]_feature_[kebab-case-name]/`).
- [ ] `requirements_data.json` and `plan_data.json` exist in that directory.
- [ ] **CRITICAL**: Ensure you are NOT working in a `plans/` directory. If `plans/` exists, ignore it and use `specs/`.

## Process

### 1. Resume Trace
-   Ask user which feature to spec (list available `specs/` directories).
-   Read `requirements_data.json` and `plan_data.json` from that directory (or run `python3 {{GLADOS_DSPY}} show --input-dir specs/[...]/ --artifact requirements`).
-   Log session resumption in `README.md`.

### 2. Detailed Specification
-   Ask clarifying questions based on the Plan.
-   Run the DSPy engine to generate the specification:
    ```
    python3 {{GLADOS_DSPY}} spec \
      --input-dir specs/[...feature dir]/ \
      --context-dir product-knowledge/ \
      --output-dir specs/[...feature dir]/
    ```
-   Review the generated `spec_data.json` with the user.
-   If revisions are needed, re-run after clarifying requirements.

### 3. Review (Persona-based)
Invoke module: `{{MODULES}}/persona-context.md`
-   **Context**: Reviewing the **Specification** (`spec_data.json`).

### 4. Standards Gate (Pre-Implementation)
Invoke module: `{{MODULES}}/standards-gate.md`
-   **Context**: Audit the specification against applicable standards before implementation begins.
-   **Checkpoint**: `pre-implementation`

### 5. Observability Update
> [!IMPORTANT]
> Invoke module: `{{MODULES}}/observability.md`
> -   **Context**: Log spec creation, review results, and standards gate report.

### 6. Handoff
-   Suggest running `/glados/implement-feature` next.
