# Adopt Codebase

**Goal**: Comprehensive brownfield onboarding — analyze, document, and integrate an existing codebase into the GLaDOS framework.

## Prerequisites
- [ ] GLaDOS installed.
- [ ] Codebase exists (this is NOT a greenfield workflow).

## Process

### 1. Initialize Trace
Create a directory: `specs/[YYYY-MM-DD]_adopt_codebase/`.
Create a `README.md` inside it.
Log the start of the adoption session.

### 2. Structural Analysis
Run the `/review-codebase` workflow.
-   This populates `{{STATUS}}` with architecture, tech stack, and initial findings.
-   **Extended analysis** (beyond base review):
    -   **Dependency Graph**: Identify patterns from dependencies (e.g., "Express + Prisma → REST API pattern").
    -   **Convention Detection**: Auto-detect naming conventions, directory patterns, test frameworks.
    -   **Existing Docs Ingestion**: If `CONTRIBUTING.md`, `ARCHITECTURE.md`, or similar exist, incorporate findings.
    -   **Health Check**: Report on test coverage presence, linter configs, CI/CD setup.

### 3. Standards Extraction
Run the `/establish-standards` workflow.
-   Extract discovered patterns into `standards/` files with proper frontmatter.
-   **Focus Areas**: Suggest areas based on Step 2 findings rather than asking cold.

### 4. Philosophy Discovery *(if philosophies/ is initialized)*
If `philosophies/` exists:
-   Ask the user about high-level principles:
    -   "What are the non-negotiable architectural decisions?"
    -   "What design principles does the team follow?"
    -   "What trade-offs has the team explicitly chosen?" (e.g., "speed over correctness" or vice versa)
-   Create philosophy files with proper frontmatter.

### 5. Mission Alignment
Run the `/mission` workflow.
-   Ensure `MISSION.md` exists and aligns with the discovered codebase purpose.

### 6. Validation Checkpoint

> [!IMPORTANT]
> **STOP**: Present a summary to the user before finalizing.

Present:
-   Architecture summary (from `{{STATUS}}`).
-   Discovered standards (list from `standards/`).
-   Discovered philosophies (if any).
-   Inferred conventions with confidence levels.
-   Identified gaps (areas not yet analyzed).

Ask: "Does this accurately represent your codebase? What should I correct?"

### 7. Finalize
-   Update `{{STATUS}}` with adoption metadata:
    ```markdown
    ## Adoption Status
    **Adopted**: [Date]
    **Coverage**: [Which areas analyzed]
    **Gaps**: [What remains unreviewed]

    ## Inferred Conventions
    - [Convention] - Confidence: [High/Medium/Low]
    ```
-   Log final summary in the trace.

### 8. Handoff
Suggest: "Your codebase is onboarded. Run `/plan-feature` to start building, or `/recombobulate` periodically to keep things tight."
