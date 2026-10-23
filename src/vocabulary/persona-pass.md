## Persona pass

An in-context review: the agent that produced an artifact reads it again
through each seated review persona. It is not the adversarial review loop,
which runs later against the diff.

- **Seat the personas.** Read `run.active-personas` (seated by
  plan-feature); when that key is absent, resolve the default roster from
  `params.review-panel.personas` in `glados.yaml`. Add any persona the step's
  body names under "Personas to seat". Resolve each name in the project's
  `product-knowledge/personas/` first, then in the library vendored in
  `.glados/personas/`. A name found in neither is said in the record, never
  dropped silently. With no persona seated, say so in one line: the pass was
  empty, not skipped.
- **Press.** Each persona presses the question the plan assigned it, when
  there is a plan, plus its own mandate: what does this artifact get wrong,
  leave undefined, or make expensive later? The pass also presses each
  principle of the canon that applies at this step, from the seat it names,
  as *Consulting canon* sets out.
- **Fold.** Fold fixes into the artifact. Note each declined objection in the
  artifact with a one-line reason.
- **For a gate, the pass is the audit.** The personas check what the gate's
  body says to check. Each problem is a finding, on the *Verdicts and finding
  severities* scale, in the gate's own file; the audited artifact changes
  only through the gate's revise loop. With no persona seated, this agent
  does the audit itself against the body, as under `review: none`, and the
  gate's file says so: an empty pass never passes a gate.
