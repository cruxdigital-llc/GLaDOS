## Branch naming

Branch names and MR targets come from `glados.yaml` → `branching:` — never
invent a scheme inline.

| Key | Governs |
|-----|---------|
| `branching.feature` | The pattern for a single feature/fix working branch. |
| `branching.epic-integration` | The pattern for an epic's integration branch, which child MRs target. |
| `branching.default-target` | The MR target when no epic integration branch is in play. |

Resolve the applicable key at run time and substitute the slug. Inside an epic,
read the integration branch from `epic.integration-branch` in the epic record;
outside one, target `branching.default-target`. If a needed pattern is absent
from the manifest, stop and emit an `escalation` — do not guess a convention.
