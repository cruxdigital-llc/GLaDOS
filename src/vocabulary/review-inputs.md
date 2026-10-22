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
  and labelled as theirs, untagged.
- **A person set only what their quoted words name, as firmly as they
  said it.** Each clause takes the tag its words give until the person
  corrects it:
  - *Directive* ("must", "need", "never", "always", or a plain statement
    of what is wanted) binds.
  - *Preference* ("should", "I'd like", "prefer", or a hedged want: "I
    think we need") sets a default that evidence may override.
  - *Hunch* ("I think", "maybe", "probably", "I wonder") is a belief about
    what is true (a cause, what code does), which the artifact tests
    against the code, reporting what it finds; it stands unless
    contradicted.
  - *Assent* ("seems fine", "yes", "go with that", choosing a question's
    reading) approves only the direction of what they were shown, which
    stays its writer's: a chosen reading's outcome, not its mechanism,
    scope words or phrasing. Material evidence they were not shown reopens
    it as a question naming that evidence.
- **Challenge in the open.** Where evidence outside the change suggests
  a person's words miss what they want, the artifact says "your words say
  X (tag); the code shows Y; I propose Z", naming where. Against a
  Directive, which stands until they answer, or where it is material,
  that is a question for them; otherwise the work follows Z. Neither
  raising a challenge nor following one past a Preference or Hunch
  blocks: where the workflow takes no questions, a challenge is an
  advisory written as one. Any other departure from a person's words,
  under too soft a tag included, breaks a criterion the work received.
- **A scope statement excuses an absence, never a presence.** "Deferred to
  <item>" or "not in this MR" means the reviewer does not report that thing
  as missing, except a criterion the work received: only a person's quoted
  words naming it and letting it go waive one, never a go-ahead on an
  artifact that lists it unmet. No scope statement, the author's or a
  person's, makes what the change does add correct: what it adds is
  reviewed on its merits. Deferring a unit's consumer does not excuse the
  unit: that nothing calls it is still a finding.
