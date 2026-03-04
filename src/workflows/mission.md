# (GLaDOS) Mission

## Prerequisites
- [ ] `{{STATUS}}` exists.

## Process

### 1. Initialize Trace
Create a directory: `specs/[YYYY-MM-DD]_mission-statement/`.
Create a `README.md` inside it.
Log the start of the session in `specs/[YYYY-MM-DD]_mission-statement/README.md`.

### 2. Context Gathering
Ask the user the following questions (one by one or grouped, depending on complexity):
1.  **Problem**: What specific problem or pain point does this product address?
2.  **Audience**: Who are the primary users?
3.  **Solution**: What is the core solution and what makes it unique?

### 3. Document Creation
Create or update `product-knowledge/MISSION.md` in the project root.

**Header Requirement**:
Top of file must include:
```markdown
<!--
GLaDOS-MANAGED DOCUMENT
Last Updated: [Date]
To modify: Edit this file directly. GLaDOS will read the current state before making future updates.
-->
```

**Structure**:
```markdown
# Product Mission

## Problem
[Description]...
```

### 4. Observability Update

> [!IMPORTANT]
> **Trace**: Log the interview summary and file creation in `specs/[YYYY-MM-DD]_mission-statement/README.md`.
> **Status**: Update the "Project Overview" section in `{{STATUS}}` with a link to `product-knowledge/MISSION.md`.

### 5. User Verification
Ask the user to review `product-knowledge/MISSION.md`.
