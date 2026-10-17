<!-- GLaDOS kernel fragment: compiled epilogue.
     The compiler appends this to EVERY workflow core. Cores must not define
     their own ending; a core containing trace/publish/commit instructions of
     its own fails `glados lint`. -->

## Before ending this run (mandatory)

A run without a committed run record and a published outcome is an incomplete
run — finish these steps even if the work above was cut short, and say so in
the record rather than omitting it.

1. **Finalize the run record** at `.glados/runs/<YYYY-MM-DD>-<workflow>-<slug>.md`:
   outcome, key decisions (with their decision-rights class), verdicts if any,
   links (MR, issues, commits), and any state keys this run wrote
   (`review.reviewed-head`, `epic.progress` updates, …). If this run was cut
   short, record how far it got — a partial record beats a missing one. A
   record is a screen, not an essay: reasoning that already lives in the
   published comment or in the diff is not repeated in it.
2. **Yield check**: compare the recorded `work.base-sha` against the current
   base. If an external edit moved it, emit `yielded (external_edit)` in the
   record, then rebase or release — never force-push over someone else's work.
3. **SDA work-unit log (when `glados.yaml` sets `sda: true`)**: a run that is
   not nested (preamble step 1) appends the single work-unit row for the
   whole unit of work to `product-knowledge/SPEC_LOG.md` — date, workflow,
   scope, outcome, links — and clears its entry in `claims.md`, so both ride
   the record commit below. A nested run does neither: it holds no claim of
   its own, and a work-unit row marks its subject done, so a nested plan's
   row would mark the whole feature done early. Its record path is already
   listed in the parent's record, and the outermost run's row covers it.
   The exception is the one the preamble names: a ticket's build inside
   run-epic is a unit of work of its own, so it appends the ticket's row
   and clears the ticket's claim; the runs nested inside it do neither.
   A run that ends with its unit of work still waiting on an approval has
   not finished it: run-pipeline parking at a `human` checkpoint or
   resuming a park that has no approval yet, and run-epic stopping with
   only parked tickets left. It keeps its claim and appends no row, and the
   run that resumes the work does both when the unit ends.
4. **Commit the record** on the current working branch:
   `chore(glados): record <workflow> run`. Runs that act on a merge request
   under review — review-mr, address-review — commit their record to the
   `glados/ledger` branch instead, never to the author's branch: the MR
   carries the change and the comment, and the ledger carries the trail.
5. **Publish outcomes**: read `glados.yaml` → `channels:` (which sinks each
   outcome type goes to) and `sinks:` (how each sink behaves). For every
   outcome type this run emitted, deliver it to each bound sink using the
   project's own platform CLI/tooling (glab/gh/MCP), **rendering per that
   sink's declared config** — interpret its keys sensibly for the sink's
   medium and this team's conventions, and record in the run record which keys
   you honored and which you did not recognise, so a typo surfaces as a line
   in the record instead of as silence. Built-in sinks are `mr-comment`,
   `issue`, `issue-comment`, `label`, and `ledger`; a project may declare
   others (e.g. `slack`). `progress` always lands in the ledger at minimum.
   - **`grouping:`** decides how many comments one outcome becomes:
     `aggregate` — one comment carrying the whole outcome, and the reading to
     take when the key is absent; `per-persona` — one per seated persona;
     `per-finding` — one per finding. `threads: resolvable` posts each of
     those as its own resolvable thread where the platform supports it.
   - **`summary:`** applies only where `grouping:` splits an outcome across
     several comments, and controls whether an additional composed-verdict
     comment joins them. Under `aggregate` the single comment already **is**
     the composed verdict, so `summary: false` suppresses nothing: an outcome
     bound to a sink always produces at least one comment there. A reading of
     any sink config that ends in posting nothing is a misreading.
   - **Delivery is verified, not assumed.** Every sink bound to an outcome
     type must actually receive it. If a bound sink is unreachable or the post
     fails, record the failure in the run record and emit an `escalation`.
     Delivery to a different sink does not cover the one that failed: a
     verdict that never reached the MR leaves the change looking unreviewed,
     however many other sinks got a copy. Never silently drop an outcome.
   - **No MR yet is not a failed delivery.** When an outcome is bound to
     `mr-comment` and no MR exists yet for the work it is about (a verdict
     from verify-feature inside build-feature, a `decision` from a nested
     plan-feature, run-epic's backlog selection), deliver it to its other
     bound sinks and record it in the run record under `## Pending MR
     delivery`. This does not escalate. The run that opens the MR posts
     every pending MR item from its own record, from the records of the
     runs nested inside it, and from a parked run it resumed (with the runs
     nested inside that one) as soon as the MR is open, before handing the
     MR to review (build-feature right after it opens the MR in its step 5,
     before its self-review; a pipeline's open-mr step), then marks each
     item delivered in the record that holds it. Any item still pending
     when this step runs, with its MR open, is posted now. When the
     outermost run ends and no MR exists for the work an item is about
     (run-epic's backlog selection, a standalone plan), mark that item "no
     MR for this work; mr-comment delivery not applicable" instead of
     escalating, even if nested runs opened MRs for their own work. A run
     that ends with its unit still waiting on an approval (step 3) has not
     ended it: its items stay pending for the run that resumes the work and
     opens the MR. Once
     the MR exists, a post that fails is a failed delivery as above. These
     record updates (this run's record, and any nested record you marked
     delivered) ride the step 4 commit when made before it; any made in
     this step go in one more `chore(glados): record <workflow> run` commit
     before step 6.
   - Reaching only the ledger is not itself a failure. `progress`, `decision`,
     and `observation` may be bound ledger-only by design, as may any outcome
     type in a project whose manifest confesses `visibility-acknowledged:
     ledger-only`. Escalate on a sink that failed, never on a binding the
     manifest deliberately declared.
   - **One escalation per run, and it is never itself escalated.** Collect
     every failed delivery from this run into a single `escalation` naming all
     of them, rather than emitting one per failed post. If that escalation
     also fails to deliver, record both failures in the run record and stop —
     do not raise a further escalation for it. Without this floor a single
     unreachable platform produces an unbounded chain, every link failing for
     exactly the reason that produced it, and the run manufactures noise at
     the moment the team can least act on it.
6. **Release** anything held: leases (when enabled) and other in-flight
   markers. Then pop this run off the marker stack: remove this run's line
   from `.glados/runs/stack`; if lines remain, write the last remaining line
   into `.glados/runs/current` (the enclosing run is in flight again);
   otherwise delete both `current` and `stack`. With no `stack` file, delete
   `current`. Never leave a marker naming this finished run: a leftover
   marker makes the run-record guard hooks block the next session.
