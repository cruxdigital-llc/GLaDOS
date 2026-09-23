## Root-cause synthesis

Three questions no panelist can answer from inside its own lens: one about the
change, one about the finding set, one about the change's extent. All are
answered once, over the whole diff and every panelist's findings together, and
all are answered on **every** pass — including one where the tally came
back clean, which is exactly where a shared cause hides. None may be
skipped: "the change removes the cause", "the findings do not converge" and
"the change is still the change that was asked for" are *answers*, stated
with their reasoning. Silence is not an answer.

All three answers belong in the run record. On the merge request the
synthesis appears only as a consolidated finding, when it produced one, and
as the scope statement of question 3, when that has something to say; a pass
whose findings do not converge says nothing about convergence to the author.

**1. Did the change attack the underlying cause?**

Name the underlying cause in one sentence first — the condition in the code
that made the reported problem possible, not a restatement of the problem —
then judge the diff against that sentence:

| What the diff does to the named cause | Reading |
|---|---|
| Removes it, or makes the bad state unrepresentable (a constraint, a type, one owner for the invariant) | **root-cause fix** |
| Leaves it in place and blocks the manifestations that were noticed | **symptom patch** |
| Leaves it in place because removing it is out of this change's scope, and says so | **scoped deferral** |

- A **symptom patch** whose cause is within this change's reach is a
  `blocking` finding: cite the cause, and name the change that would remove
  it.
- A **scoped deferral** the change declares — the cause named, the follow-up
  recorded so it outlives this MR — is a decision the author already made,
  and a review does not reopen a decision by reporting it as a gap. Raise it
  only where the deferral is itself unsafe, and then say what breaks while it
  stands rather than why the deferred thing would be good: the author knows
  why it would be good, which is why they wrote it down. What breaks decides
  the tier under the scale like any other finding — `blocking` where living
  with the deferral breaks behaviour, an acceptance criterion, security,
  tenancy or data, `advisory` otherwise. An undeclared deferral is a symptom
  patch.
- The ticket's framing does not settle this. A change that does exactly what
  the ticket asked can still be a symptom patch: the ticket is where the
  problem was noticed, not necessarily where it lives.

**2. Does the finding set converge on one cause?**

Cluster the panel's findings by the cause each one implies — ignoring which
persona raised it and which file it landed in. Several lenses reporting
several different defects around one bad seam is the signal this check exists
to catch. Where panelists returned a `root-cause` line, cluster those first;
where they did not, cluster from the findings themselves. A long finding list
is a reason to run this check harder, not evidence that the change is merely
sloppy.

A cluster is real when **one** change to the design would dissolve every
member of it. Test it that way: name that change, then walk each member and
say whether it survives. If members survive, they were never one cluster.

- A real cluster of two or more findings becomes **one** consolidated finding:
  the shared cause, the design change that dissolves it, and the member
  findings listed beneath it as evidence. It carries the highest severity
  among its members.
- The consolidated finding replaces its members as the unit of work — the
  remediation is that one design change, not one patch per member. The
  members stay listed so nothing is lost when the change lands.
- Two clusters, or none, is a normal result. Do not manufacture a shared cause
  to make a tidy story: an unforced cluster sends the author refactoring
  around a theory the code does not support. If the findings only rhyme, say
  they do not converge and leave them separate.
- Synthesis never lowers a severity and never collapses `blocking` findings
  into a single advisory suggestion.

**3. Is this still the change that was asked for?**

Set the ticket's acceptance criteria beside the diff and say whether the diff
is still answering them. A change grows for good reasons — a review asks
for a fix, the fix needs a mechanism, the mechanism raises a question
nobody had asked — and every step can be right while the sum is no longer
the work the ticket describes.

No lens can see this. A panelist reviews the diff it is given and judges it
well; the scope rule keeps it from raising findings about code the change did
not touch, and nothing keeps the CHANGE from growing. So a panel can return
correct finding after correct finding, cycle after cycle, all of them pointing
away from what the ticket asked. That is the failure this question exists to
catch, and the symptom is a review loop that converges on nothing while every
individual finding stands up.

Answer it in two parts:

- **Which acceptance criteria does the diff meet?** Name them. A criterion the
  diff does not meet is an ordinary finding under the severity scale — it
  breaks an acceptance criterion, so it blocks.
- **What is in the diff that no criterion asked for?** Name that too, with
  where it came from: work the ticket implies, work a review asked for, work
  the author added. Each is legitimate on its own; what matters is the size of
  the pile and whether it can be separated.

This produces a **statement, not a finding**. Unrequested work is not a defect
— the code may be correct and the review has no business calling correct code
wrong. It goes on the merge request as one line when there is something to
say: what has grown, and what would be left if it were split out. Naming a
follow-up is the author's call to make, not the review's to demand.

Two cautions. A change that is entirely in scope gets one sentence saying so,
not silence — the question is answered every pass. And this is not licence to
relitigate a scope the description already settles: work the author declared
is a decision already made, and the deferral rule above governs it.
