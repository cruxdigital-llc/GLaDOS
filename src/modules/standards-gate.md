# GLaDOS Standards Gate Module

**Goal**: Enforce documented standards by auditing work artifacts (specs, code diffs) and blocking on violations.

## Usage
Invoked at two checkpoints:
1. **Pre-implementation**: After `{{CMD}}spec-feature`, before `{{CMD}}implement-feature`.
2. **Post-implementation**: During `{{CMD}}verify-feature`, before declaring success.

## Instructions

### 1. Discover Applicable Standards
-   **Scan**: Read `standards/index.yml` for all registered standards.
-   **Load Frontmatter**: Each standard file should include a YAML frontmatter block:
    ```yaml
    ---
    scope: [api, backend]      # areas this applies to
    severity: must | should | may
    keywords: [error, response] # aids auto-matching
    ---
    ```
-   **Filter**: Match standards to the current work based on:
    -   `scope` tags vs. the file types/areas being touched.
    -   `keywords` vs. the content of the spec or changed files.
-   If a standard has no frontmatter, treat it as `severity: should` and `scope: [all]`.

### 2. Severity Tiers (RFC 2119)
| Tier | Behavior | Label |
|---|---|---|
| **must** | Blocks the workflow. Work cannot proceed until resolved. | ❌ VIOLATION |
| **should** | Logged as a warning in the trace. Does not block. | ⚠️ WARNING |
| **may** | Informational. Noted in the trace for awareness. | ℹ️ NOTE |

### 3. Audit
For each applicable standard:
1.  **Read**: Load the full standard content.
2.  **Compare**: Check the spec (pre-implementation) or code diff (post-implementation) against the standard's rules.
3.  **Verdict**: Assign one of:
    -   `✅ PASSES` — The work adheres to this standard.
    -   `❌ VIOLATION` — The work breaks a `must` standard.
    -   `⚠️ WARNING` — The work breaks a `should` standard.
    -   `ℹ️ NOTE` — A `may` standard is relevant but not followed (informational).

### 4. Gate Decision
-   **If any `❌ VIOLATION` exists**:
    -   **STOP**: Do not proceed to the next phase.
    -   **Log**: Record each violation in the trace `README.md`.
    -   **Action**: Present violations to the user. They must either:
        1. Fix the code/spec to comply, OR
        2. Update the standard (if it's outdated).
-   **If only `⚠️ WARNING` or `ℹ️ NOTE`**:
    -   **Log**: Record in the trace `README.md`.
    -   **Proceed**: Work continues.

### 5. Philosophy Cross-Check
If `philosophies/` exists:
1.  **Load**: Read all philosophy files with `weight: core`.
2.  **Audit**: Check if the work conflicts with any core philosophy.
3.  **Gate**: Core philosophy violations are treated as `❌ VIOLATION` — blocking.
4.  **Log**: Present the conflict. User must fix the code or update the philosophy.

### 6. Report
Generate a summary table in the trace:

```markdown
## Standards Gate Report
| Standard | Scope | Severity | Verdict |
|---|---|---|---|
| API Response Format | api | must | ✅ PASSES |
| Error Logging | backend | should | ⚠️ WARNING |
```
