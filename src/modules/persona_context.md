# GLaDOS Persona Context Module

**Goal**: Manage agent personas for both *review* (critiquing work) and *operating* (driving behavior) modes.

> Replaces the simpler `persona_review.md` module.

## Persona Types

| Type | Purpose | When Used |
|---|---|---|
| **review** | Critiques work during review gates | Persona Review steps in Plan/Spec/Verify |
| **operating** | Drives agent behavior throughout a session | Set at session start, affects all decisions |
| **hybrid** | Can do both | Available for reviews AND as operating persona |

## Persona File Format

Each persona file should include YAML frontmatter:

```yaml
---
type: review | operating | hybrid
priority_areas: [security, performance, ux]
standards_weight: [security/*, testing/*]  # glob patterns for relevant standards
---
```

## Instructions

### 1. Operating Persona (Session-Level)

If the user requests an operating persona (e.g., "act as the Security Expert"):

1. **Load**: Read the persona file from `{{PERSONAS}}/`.
2. **Activate**: Set as the active operating persona for the session.
3. **Log**: Record `Active Operating Persona: [Name]` in the trace `README.md`.
4. **Apply**: Throughout the session:
   - Prioritize concerns from the persona's `priority_areas`.
   - Weight standards listed in `standards_weight` more heavily.
   - Adopt the persona's tone, responsibilities, and key questions.

### 2. Review Loop (Gate-Level)

When invoked for review (at Plan, Spec, or Verify checkpoints):

1. **Discover**: Scan `{{PERSONAS}}/` for all persona files.
2. **Filter**:
   - Include all personas with `type: review` or `type: hybrid`.
   - *Optional*: If the trace `README.md` lists "Active Personas", limit to that subset.
   - If a `team.yml` manifest exists, use the team composition for the current workflow type.
3. **Review Loop**: For *each* active review persona:
   1. **Load Context**: Read the full persona definition.
   2. **Adopt Role**: "Acting as [Persona Name]..."
   3. **Audit**: Review the current work against the persona's:
      - **Responsibilities**: Is the core job being done?
      - **Key Questions**: Have they been answered?
      - **Standards Weight**: Cross-reference relevant standards from `standards_gate`.
   4. **Log Feedback**: Record critique in the trace.
      - *Format*: `**[Persona Name]**: [Feedback]`
4. **Synthesis**:
   - If *any* persona blocks: **Stop**. Present issues to user.
   - If all approve: **Proceed**.

### 3. Team Manifests

If `{{PERSONAS}}/team.yml` exists, it defines named team compositions:

```yaml
teams:
  security_review:
    personas: [architect, qa, security_expert]
    description: "For features with security implications"
  quick_review:
    personas: [architect]
    description: "For minor changes"
  full_review:
    personas: [product_manager, architect, qa]
    description: "Default for all features"
```

Workflows can reference a team by name. If no team is specified, `full_review` is used.
