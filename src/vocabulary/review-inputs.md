## What a fresh reviewer is given

A fresh reviewer is only as independent as its brief, and the agent that did
the work writes the brief. So a brief carries inputs, never the author's
conclusions about them.

- **Only the listed inputs.** A brief carries what the workflow that writes
  it lists for it and nothing else: no verdict, approval or gate result from
  an earlier pass, no disposition the author gave a finding, no instruction
  about what is or is not a defect. A finding still open from an earlier
  pass may be named, as open.
- **Say who wrote each input.** The author is whoever wrote the change,
  agent or person. Everything the author wrote (plan, shape, spec, a
  contract file, the MR description) is labelled as the author's, and is
  under review like the code. A person's words, meaning anyone's but the
  author's (the ticket, an instruction given in the session or on the MR),
  are quoted verbatim with where they were said (a file path or an MR note)
  and labelled as theirs. A person set only what their quoted words name: a
  go-ahead approves the direction of what they were shown, which stays its
  writer's; an answer choosing a question's reading binds that reading's
  outcome, not its mechanism, scope words or phrasing.
- **Words bind as firmly as they were said.** "Must", "need", "never" or a
  plain statement of what is wanted, in a person's own phrasing, binds.
  Hedged words ("I think", "maybe", "should", "I'd like", "seems
  reasonable") and a chosen reading's words beyond its outcome set a
  default that evidence can revise. Evidence against a default is never a
  blocking finding: where it changes an outcome the person names, it is a
  question for them (an advisory written as one where the workflow takes
  none); otherwise the work follows it and says so.
- **A scope statement excuses an absence, never a presence.** "Deferred to
  <item>" or "not in this MR" means the reviewer does not report that thing
  as missing, except a criterion the work received: only a person's quoted
  words naming it and letting it go waive one, never a go-ahead on an
  artifact that lists it unmet. No scope statement, the author's or a
  person's, makes what the change does add correct: what it adds is
  reviewed on its merits. Deferring a unit's consumer does not excuse the
  unit: that nothing calls it is still a finding.
