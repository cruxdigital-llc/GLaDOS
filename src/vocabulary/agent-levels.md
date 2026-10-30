## Agent levels

Each fresh agent runs at the level `glados.yaml` gives its kind:
`params.agents.reviewer` for a design reviewer, `params.agents.evaluator`
for an evaluator, `params.agents.panelist` for a review-panel seat and
`params.agents.refuter` for a refuter.

- **`session`**, the default, spawns it on this session's own model and
  effort: nothing is chosen.
- **Any other value** names a level under `params.agents.levels`. Take that
  level's entry for the runtime you are running in (`claude`, `codex`, or
  whatever name the project gives it) and spawn the agent with its `model`
  and `effort`, as your runtime's spawn takes them. A level that sets only
  one of the two leaves the other at the session's.
- **A level with no entry for your runtime**, or a runtime whose spawn takes
  no model or effort, runs the agent at `session`. Say so once in the run
  record, naming the level, so a project that meant to set one sees it did
  not.

GLaDOS names no model. The project names them, once each, under
`params.agents.levels`, in its runtime's own words, so a renamed model is a
one-line change there and no workflow text changes.
