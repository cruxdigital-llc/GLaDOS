<!-- GLaDOS kernel fragment: compiled preamble.
     The compiler PREPENDS this to EVERY workflow core and replaces
     {{OPTIMIZE_FOR}} with the phase-resolved optimize-for sentence. Cores must
     not restate run-start bookkeeping or decision-rights handling; a core
     containing its own record-creation or decision-class text fails
     `glados lint`. -->

{{OPTIMIZE_FOR}}

## Before doing anything else (mandatory)

1. **Create the run record now** at
   `.glados/runs/<YYYY-MM-DD>-<workflow>-<slug>.md` — before any other work,
   after `.glados/glados.py ledger restore` copies in the ledger's records.
   Note the workflow, start time, and goal. Then set the in-flight markers
   the run-record guard hooks key on. `.glados/runs/current` holds the
   filename of the innermost run in flight; `.glados/runs/stack` lists every
   run in flight, one filename per line, outermost first, and its last line
   always equals `current`.
   - **Nested run.** This run is nested only when a workflow you are
     running in this session started it as one of its own steps
     (plan-feature from build-feature's stage table, a stage from
     run-pipeline's step table, a ticket's build from run-epic's per-ticket
     loop) and `current` names that workflow's record. If `stack` does not
     exist yet, create it holding the parent's filename. Append this run's
     filename to `stack` and write it into `current`. Note in this record
     that the run is nested and name the parent record, and list this
     record's path in the parent's record under `## Nested runs`.
   - **Fresh run.** Otherwise write this run's filename into `current` and
     write `stack` holding just this filename. Any other `current` or
     `stack` is stale, whatever its record says (a run that crashed, or an
     earlier session that ended mid-run): replace it, and note the stale
     filename(s) in this record. A run that resumes earlier work (run-epic
     picking up its ticket table) is fresh too; it builds on the earlier
     record as step 4 says.

   Both markers are transient run state: never commit them (the epilogue
   pops them). A run that dies early with a record beats one that succeeded
   invisibly; the epilogue finalizes this file, but it must exist from the
   first minute.
2. **Record `work.base-sha`** — the current base commit — in the record
   before mutating anything (branch, board, or shared files). The end-of-run
   yield check compares against it; without it, an external edit is
   undetectable and unrecoverable.
3. **Record your SDA claim (when `glados.yaml` sets `sda: true`)**: if this
   run mutates shared state, append your claim to `claims.md` at the repo
   root before the first mutation — workflow, scope, holder, timestamp. An
   existing uncleared claim on the same scope is contention: coordinate with
   its holder — build on their run or wait — do not clobber. The epilogue
   clears the entry. review-mr and address-review claim nothing. A nested
   run (step 1) adds no claim of its own and does not treat the claim of a
   run enclosing it (any record on `stack`) as contention: it works under
   that claim, which the outermost run clears.
   One exception: a ticket's build inside run-epic is a unit of work of its
   own (its own branch and MR), so it records and clears its own claim as
   an outermost run would; the epic's claim is still not contention, and
   runs nested inside that build work under the ticket's claim.
4. **Read prior run records first**, where this workflow revisits a subject
   (an MR, an epic, a component): scan `.glados/runs/` for records touching
   the same subject before redoing work. If a prior run already reviewed the
   current HEAD, produced the artifact, or holds the claim, build on that
   record instead of repeating the work — and say so in this run's record.

## Reading glados.yaml

When this workflow resolves a key from `glados.yaml` and the manifest does
not set it, take its default from the preset table, `.glados/presets.yaml`.
Layer it in this order, later layers winning: the table's `baseline`, then
the preset named by the manifest's `phase:`, then the keys the manifest sets
explicitly.

## Decision rights

Before making any decision listed under `decisions:` in `glados.yaml`,
resolve its class from the manifest and apply it:

| Class | What you do |
|---|---|
| `agent` | Decide, note the decision and its rationale in the run record, continue. |
| `record` | Decide, AND emit a `decision` outcome: what was decided, why, and how reversible it is. |
| `escalate` | Stop. Emit an `escalation` outcome and wait for a human — do not proceed on a guess. |
| `forbidden` | Refuse. Emit an `escalation` outcome and record the refusal in the run record — even if asked to proceed mid-run. |

Judge a decision against the target branch. A table, migration, interface
or format this branch adds is one decision, made once under its class;
reworking it before it reaches the target is part of that decision, not a
further schema migration or API break. That holds unless the project
deploys or publishes from a branch other than the target.

For judgment calls not listed in `decisions:`, apply the optimize-for line at
the top of this file, and record the consequential ones in the run record.
