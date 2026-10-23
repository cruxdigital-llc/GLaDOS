## Loop bounds

Every retry loop is bounded, and the bound is a manifest value — never a number
written into workflow text. Resolve bounds from `glados.yaml` at run time:

| Loop | Bound |
|------|-------|
| review-mr ⇄ address-review cycles per MR round | `params.review-panel.max-cycles` |
| evaluator verify/fix cycles per feature | `params.evaluator.max-cycles` |
| standards-gate re-runs per gated artifact | `params.standards-gate.max-cycles` |
| revise cycles per pipeline step (run-pipeline) | `params.pipeline.max-cycles` |

Rules:

- A bound must resolve to a whole number of 1 or more. Anything else
  (missing, text, `true` or `false`, a list, 0 or less) is no bound: do not
  start the loop; emit an `escalation` naming the key and its value, and
  end the run.
- Count cycles in the run record and check the bound **before** starting the
  next cycle.
- On hitting a bound: stop, emit an `escalation` outcome carrying the open
  findings and the cycle history, and end the run. Never loop indefinitely.
- If a finding previously recorded as resolved **re-opens**, that is a
  stalemate regardless of the counter: stop and emit an `escalation`
  immediately rather than spending remaining cycles on it, except in
  run-pipeline's revise loop, which parks for a person (its **Bound**).
- An escalated loop is a finished run, not a failed one — the record states
  where it stopped and why.
