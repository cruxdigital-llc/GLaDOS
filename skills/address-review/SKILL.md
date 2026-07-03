---
description: Resolve every open review finding in one coherent fix pass, then hand back to review-mr
---

Read and follow the workflow at `${CLAUDE_PLUGIN_ROOT}/src/workflows/address-review.md`.

When resolving path references in the workflow:
- `{{MODULES}}/` means `${CLAUDE_PLUGIN_ROOT}/src/modules/`
- `{{PERSONAS}}/` means `${CLAUDE_PLUGIN_ROOT}/src/personas/`
- `{{STATUS}}` means `product-knowledge/PROJECT_STATUS.md`
- `{{CMD}}` means the `/glados:` command prefix (e.g. `{{CMD}}review-mr` → `/glados:review-mr`)
