# (GLaDOS) Spec Feature

**Goal**: Create a detailed technical specification for the feature.

## Prerequisites
- [ ] Feature directory exists (`specs/[YYYY-MM-DD]_feature_[name]/`).
- [ ] **CRITICAL**: Ensure you are NOT working in a `plans/` directory. If `plans/` exists, ignore it and use `specs/`.

## Process

### 1. Resume Trace
-   Ask user which feature to spec (list available `specs/` directories).
-   Read `requirements.md` and `plan.md` from that directory.
-   Log session resumption in `README.md`.

### 2. Detailed Specification
-   Ask clarifying questions based on the Plan.
-   Define:
    -   **Data Models**: Database schema changes.
    -   **API Interface**: Endpoints and payloads.
    -   **Edge Cases**: Error handling.
-   Create `specs/[...]/spec.md`.

### 3. Review (Persona-based)
Invoke module: `{{MODULES}}/persona-context.md`
-   **Context**: Reviewing the **Specification**.

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
