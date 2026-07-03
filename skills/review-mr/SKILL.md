---
description: Run one adversarial multi-persona review pass over an open Merge Request
---

Read and follow the workflow at `${CLAUDE_PLUGIN_ROOT}/src/workflows/review-mr.md`.

When resolving path references in the workflow:
- `{{MODULES}}/` means `${CLAUDE_PLUGIN_ROOT}/src/modules/`
- `{{PERSONAS}}/` means `${CLAUDE_PLUGIN_ROOT}/src/personas/`
- `{{STATUS}}` means `product-knowledge/PROJECT_STATUS.md`
- `{{CMD}}` means the `/glados:` command prefix (e.g. `{{CMD}}address-review` → `/glados:address-review`)
