### Ticket lifecycle (when `glados.yaml` sets a `lifecycle:` block)

If `glados.yaml` has a `lifecycle:` block whose `driver:` is not `none`, mirror
this run's stage onto the work item's tracker state as you cross each boundary,
using the project's own platform CLI (`glab`/`gh`/MCP) — exactly as you publish
the `label` sink. GLaDOS never calls the platform API itself. If there is no
`lifecycle:` block, or `driver: none`, skip this section entirely.

- **Firing points.** When you reach a stage that has an entry under
  `lifecycle.transitions`, set the ticket to that entry's state value:
  `claim-branch` when you create this run's working branch; `open-mr` when you
  open the merge request; `escalated` when this run emits an `escalation`.
  (`merged` is **not** moved by a GLaDOS run — it is realized platform-side,
  e.g. `Closes #<id>` on merge; see `docs/guides/lifecycle.md`.)
- **How to set it, per `lifecycle.driver`:**
  - `gitlab-scoped-label` — replace the ticket's `<lifecycle.field>::*` scoped
    label with `<lifecycle.field>::<state value>` (scoped labels are mutually
    exclusive, so setting the new one clears the old) via `glab`.
  - `github-label` — remove the other lifecycle state labels from the issue and
    add the mapped one via `gh`.
  - `gitlab-work-item-status` / `github-projects-status` — not supported in this
    version; do not guess an API — emit an `escalation` noting the driver is
    deferred, and continue.
- **Transition, not emission.** Set the ticket to exactly one lifecycle state,
  replacing the previous one — never accumulate states. It is idempotent: if the
  ticket is already in the target state, do nothing.
- **`policy: advance-only`** (the default when unset): within the linear
  `claim-branch → open-mr → merged` progression, only ever move forward — a
  retried or resumed run must not drag a ticket backward — and never overwrite a
  state a human set outside `lifecycle.transitions` (a manually parked ticket
  stays parked). The `escalated` state is a signal, not a step in that
  progression: set it whenever this run escalates, regardless of policy.
  `policy: free` lifts the forward-only and manual-park guards.
- **Best-effort, never a gate.** A failed transition does not abort the run:
  record the failure in the run record and emit an `escalation`, then carry on.
  Being public about state must not let a flaky tracker API block an otherwise
  good merge request.
