## Publishing a verdict

How a `verdict` reads when it lands on a merge request. This is the default
shape: a project that configures its `mr-comment` sink overrides whichever
part of it that config speaks to, and a project that configures nothing gets
exactly this.

**Everything here governs wording and order, never content.** A finding that
reaches this step has already survived the tally — and, where it blocks,
refutation — so it goes on the comment whatever shape it arrives in. Nothing
in this section decides whether something is a finding, lowers a severity, or
moves a finding between tiers; that was settled upstream, where the reasoning
could be recorded. A rule here that seems to call for leaving something out
is being misread. If a finding resists every attempt to state it well, post
it badly worded and say so.

### Order

1. **The verdict line.** The composed verdict, the count of blocking
   findings, the cycle number and the SHA reviewed, on one line.
2. **What has to change**, on a comment carrying a blocking finding. One line
   per blocking finding: what has to change, and where. No evidence, no
   mechanism, no measurement. This list is the only place the asks are
   written — each finding below sits under its own line rather than
   restating it — so an author who reads only this far can start work and
   cannot mistake what is being asked. Every blocking finding gets its line;
   if the list runs long, that is the synthesis's cue to look again for a
   shared cause, never a reason to leave one out.

   A comment with no blocking finding has no such list. Its verdict line is
   the summary, followed by one sentence naming the cause the change was up
   against and whether the diff removed it — on a clean pass, that sentence
   is the only thing the review has to say.
3. **What the last cycle's work closed**, from the second cycle on. One line
   per finding the previous pass left open: closed, or still open. It goes
   above the findings because it is the first thing an author looks for —
   the only part that tells them the work they just did landed.
4. **The blocking findings**, each as one collapsed block whose summary is its
   line from item 2, word for word:

       <details><summary>1. the line from item 2, verbatim</summary>

       The claim — what breaks, file:line, what to do — in a few plain
       sentences. Then the evidence: the reproduction, the measurement, the
       walk through the mechanism, why the obvious fix is the wrong one.

       </details>

   A consolidated finding — several members dissolved by one design change —
   is posted as the one finding it is, its members listed inside as evidence.
5. **Advisories**, one line each.
6. **Breaches that predate the change**, if the panel found any: one line,
   pointing at wherever the project tracks bringing existing code up to
   standard. The tally has already pooled them; if more than one line of them
   reaches here, it still gets one line.
7. **The lens roll-call**, one collapsed line (`UAT ✓ · Adversarial ✗ · …`).
   Which lens raised a finding is bookkeeping, never a section header.

An `ESCALATE` adds one sentence saying why — the cycle bound reached, a
contradiction the panel could not settle, a seat that never returned. A
composed escalation can carry no blocking finding at all, so that sentence may
be the only thing the author has to act on.

A verdict that came from an evaluator rather than a panel has no roll-call and
no consolidation to report; skip what it cannot fill rather than inventing it,
and say in one line which pipeline produced it.

Nothing else crosses from the run record: not the refuted findings, not the
diff the pass read, not the process by which the verdict was reached.

### Voice

- Write to a senior engineer who is busy and skeptical and will not read past
  the first screen. Plain English, not model prose.
- Lead with the verdict. No preamble, and no recap of what the change does —
  the author wrote it.
- Open each finding with the plain sentence you would say out loud. The rule
  or standard it rests on goes underneath as evidence, never in place of the
  sentence.
- Name a concrete failure — "this drops the tenant filter, so a broker in firm
  A sees firm B's reports" — not "consider whether this may impact isolation".
- Leave out praise, emoji headers, restatements of the severity scale or the
  review process, and commentary about the panel.
- *Verdicts and finding severities* asks that each thing be said once and
  that each ask be priced. Both apply to the comment as written: the surface
  is where a point made twice costs the most.

### Length

- The visible text — everything outside the folds — aims at one screen, about
  three hundred words. It is a check, not a cap. Past it, look for proof
  sitting on the surface that belongs inside a fold, and for findings that
  should have been consolidated; a comment gets shorter by moving its proof
  one click down, never by dropping it.
- **A fold is cheap, not free.** In a web view the reader pays for folded
  evidence only when they open it. `glab`, plain-text mail and most terminals
  render the tags literally, so there the evidence is last rather than hidden.
  That is the other reason the surface has to stand on its own: if a sentence
  only makes sense once the block beneath it is open, it is in the wrong half.
- **Never fold an ask.** A reader who expands nothing must still learn every
  blocking thing they have to do — which item 2 guarantees, and which is what
  makes folding the rest safe.

### Evidence

- Cite a line number only from a read of the file at the head under review,
  never from memory of the diff; re-open the cited file before the finding
  goes out. A wrong line number is a wrong finding, and an author who meets
  three bad citations stops reading the fourth comment.
- A finding the refutation stage marked unconfirmed says so inside itself and
  keeps its tier: "blocking — unconfirmed: is `x` reachable with …?" The
  author answers a question instead of chasing a defect.
