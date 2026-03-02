# Establish Standards

**Goal**: Extract tribal knowledge from the codebase into concise, documented standards.

## Prerequisites
- [ ] `{{STATUS}}` exists.

## Process

### 1. Initialize Trace
Create a directory: `specs/[YYYY-MM-DD]_establish_standards/`.
Create a `README.md` inside it.
Log the start of the session in `specs/[YYYY-MM-DD]_establish_standards/README.md`.

### 2. Focus Area Selection
If no area is specified by the user, sidebar with the user to identify one:
1.  **Analyze**: Look at file structure and patterns.
2.  **Suggest**: Propose 3-5 focus areas (e.g., "API Routes", "React Components", "Testing").
3.  **Confirm**: Ask the user which area to focus on.

### 3. Pattern Discovery
For the selected area:
1.  **Read**: Inspect 5-10 representative files.
2.  **Identify**: Look for consistent, unusual, or opinionated patterns.
3.  **Present**: List potential standards to the user.
    -   *Example*: "I see all API responses use a `{ success, data }` wrapper."
4.  **Select**: Ask the user which patterns to document.

### 4. Standards Drafting
For *each* selected pattern (one by one):
1.  **Interrogate**: Ask "Why?" (e.g., "Why do we use this wrapper?").
2.  **Draft**: Write a concise standard based on the answer.
    -   *Rule*: "Lead with the rule, explain why second."
    -   *Format*: Use code examples.
3.  **Verify**: Show the draft to the user before creating the file.
4.  **Create**: Write the file to `standards/[area]/[topic].md`.
    -   **Include Header**:
        ```markdown
        <!--
        GLaDOS-MANAGED STANDARD
        Last Updated: [Date]
        -->
        ```

### 5. Indexing
Update `standards/index.yml` with the new files.

### 6. Observability Update

> [!IMPORTANT]
> **Trace**: Log the discovered patterns and created standard files in `specs/[YYYY-MM-DD]_establish_standards/README.md`.
> **Status**: Update `{{STATUS}}` to reflect new standards in the "Architecture" or "Standards" section.

### 7. Completion
Ask if the user wants to continue to another area.
