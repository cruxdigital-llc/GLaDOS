# Module: Pattern Observer

**Goal**: Passively detect and log implicit standards and philosophies during normal workflow execution.

## Usage
This module runs alongside any workflow. It is **non-blocking** — it never interrupts the current workflow.

## Instructions

### 1. Watch
During workflow execution, observe when the user provides guidance that is not already documented in `standards/` or `philosophies/`:

**Detection Triggers**:
-   **User Correction**: The user explicitly overrides an agent decision (e.g., "No, use Docker for that").
-   **Repeated Pattern**: A pattern appears 3+ times across different specs or sessions.
-   **Explicit Statement**: The user says "we always...", "never...", "our policy is...", or similar.

### 2. Classify
For each detected pattern, determine:
-   **Standard** (specific, enforceable): "All test commands must run in Docker."
-   **Philosophy** (directional, guiding): "We prefer composition over inheritance."

### 3. Log
Append to the appropriate file in `glados/observations/`:

#### For Standards → `glados/observations/observed-standards.md`
```markdown
### [Date] - [Short Title]
- **Source**: [How it was detected — user correction, repeated pattern, explicit statement]
- **Context**: [What was happening when this was observed]
- **Proposed Standard**: "[The rule, stated clearly]"
- **Suggested Severity**: must | should | may
- **Confidence**: High | Medium | Low
- **Status**: pending
```

#### For Philosophies → `glados/observations/observed-philosophies.md`
```markdown
### [Date] - [Short Title]
- **Source**: [How it was detected]
- **Context**: [What was happening]
- **Proposed Philosophy**: "[The principle, stated clearly]"
- **Suggested Weight**: core | preferred | aspirational
- **Suggested Domain**: [api, ux, architecture, etc.]
- **Confidence**: High | Medium | Low
- **Status**: pending
```

### 4. No Blocking
-   **NEVER** interrupt the current workflow to log an observation.
-   **NEVER** ask the user to confirm an observation mid-workflow.
-   Observations are reviewed during `/recombobulate`.
