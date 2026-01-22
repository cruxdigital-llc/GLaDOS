# Spec Feature

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
Invoke module: `glados/modules/persona_review.md`
-   **Context**: Reviewing the **Specification**.

### 4. Observability Update
> [!IMPORTANT]
> Invoke module: `glados/modules/observability.md`
> -   **Context**: Log spec creation and review results.

### 5. Handoff
-   Suggest running `/implement-feature` next.
