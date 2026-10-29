<!-- claude-plugin bootstrap guard — this artifact was compiled from
     glados.yaml.example, not from the repo it runs in. -->
**Bootstrap guard.** This workflow was compiled from `glados.yaml.example`,
not this repo's manifest. Before step 1: if this repo has a `glados.yaml`,
read it now — its `phase:`, decision rights, channels, merge authority,
params, any project workflows and steps (`pipelines:`, `steps:`) and
any canon (`canon:`) govern this run wherever they differ from the text
below. If it has no `glados.yaml`, copy `glados.yaml.example` to
`glados.yaml` (or run `/glados:init`) and set `phase:` before doing
consequential work — do not guess a phase.

**Plugin paths.** This repo may have no `.glados/` directory. Three
read-only files then come from the plugin's own copy at the plugin root
(two levels above this file, the directory that holds
`compiled/claude-plugin/`): when `.glados/presets.yaml` is missing, the
preset table is `src/kernel/presets/phases.yaml` there; when
`.glados/personas/` is missing, the library personas are `src/personas/`
there; and when `.glados/glados.py` is missing, the toolchain is
`bin/glados.py` there. Project personas in `product-knowledge/personas/`
still win a name collision. Run records and the `.glados/runs/` markers
always live in this repo: create them here, never in the plugin.

Optimize for doing no harm; when the consequences of a choice are unclear, stop and ask rather than guess.

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

<!-- GLaDOS v2 compiled artifact — generated by glados.py; edit the source, not this file.
     workflow: steward
     glados-version: 2.6.0
     manifest-sha256: d23f47f077c49c8ea87c6c32bd5a5db2ffd9f7575be6895d939ea6e02ba8e73c
     modules-inlined: standards-gate
     compile-source: src/workflows/steward.md
-->

# (GLaDOS) Steward

**Goal**: the standing housekeeping ceremony — cleanup over critique. Steward
keeps the project's memory honest: it compacts settled run records into a
digest, refreshes documentation that has drifted from the code, promotes
pending observations into standards and philosophies, and sanity-checks the
test suite. Everything it changes on its branch rides **one cleanup MR per
pass**. The deep codebase critique is the brunch ceremony, not this one;
regenerating code from intent is out of scope too — that belongs to a later
regenerate-component core.

## Process

### 1. Cut the cleanup branch
- Create the working branch per the project's `branching` conventions in
  `glados.yaml`, named for the date and this workflow. The commit it is cut
  from is this run's base (`work.base-sha`, already recorded at run start).

### 2. Compact the run ledger
- Scan `.glados/runs/` for **settled** records: runs whose linked MR is merged
  or closed and whose outcomes need no further action. Leave in-flight and
  recent records alone, and any this branch tracks.
- For each settled record, append one row to the ledger digest
  (`.glados/runs/DIGEST.md` — create it if absent), then delete the record
  and its step artifacts:

  | Date | Workflow | Outcome | Links | One-line summary |
  |------|----------|---------|-------|------------------|

- Save the digest and every deleted path to the ledger
  (`.glados/glados.py ledger save <paths>`).
- The digest preserves the audit trail at one line per run; when in doubt
  whether a record is settled, keep it — compaction must never lose the only
  copy of an open thread.

### 3. Refresh documentation
- Bottom-up staleness pass: start at leaf-level docs (per-directory READMEs,
  sampled docstrings/inline docs) and work toward the root (top-level README,
  then the project status file, `intent.status` — its architecture and
  known-issues sections in particular).
- Update what is stale; do not rewrite what is accurate. Leave the mission
  document alone — deliberate updates to it belong to the intent core.

### 4. Refresh canon digests
- Skip this step when `glados.yaml` has no `canon:` block. This is the one
  workflow that fetches a canon source; every other workflow reads only the
  digest at each entry's `digest:` path.
- For each entry with a `url`, fetch the source when this harness can, and
  hash the response body, byte for byte as fetched, with SHA-256 (the
  definition in the CANON.md template). Compare it with the digest's
  `source-sha256`:
  - **Unchanged:** leave the digest alone, unless `retrieved` is more than
    180 days old (when `glados doctor` flags it); then set it to today.
  - **Changed, or no hash recorded yet:** read the work and set it beside
    the digest. If a principle the digest summarizes changed, update the
    digest to match, in the team's words: the principles the change
    affects, `version`, `retrieved` and `source-sha256`. Keep each **Here,
    specifically:** as the team wrote it, and flag in the MR any the change
    may have made wrong. If none changed (often only the page around the
    work did: navigation, ads, a timestamp), treat it as unchanged, and
    write the new `source-sha256` only when none was recorded or when
    `retrieved` moves too, so a page that differs on every fetch does not
    edit the digest on every pass.
  - **Not fetched** (no fetch tool, a paywall, an error): treat it as a
    book, and say why.
- For a book, or any source not fetched, report the digest's age from
  `retrieved`. Never edit a digest from memory.
- List each digest whose frontmatter says `drafted-from: recall` as awaiting
  confirmation: a person checks it against the source and sets
  `drafted-from: source`. Never make that change yourself.
- List each declared digest that is missing.
- A refreshed digest keeps the template's rules: the team's words, at most
  one quoted sentence, under about 1,000 words. Digest edits ride this
  pass's cleanup MR, where a person reviews them like any other change.

### 5. Promote observations
- Read the pending observations (`observations.pending`). For each one,
  decide: **promote** or **discard** — do not leave items pending across
  passes without a reason.
- Promotions become concise standards or philosophy files in the standards
  tree (`standards.index`): lead with the rule, explain why second, include a
  code example drawn from the codebase; then update the index. A promotion is
  only as strong as its evidence — cite where the pattern recurs.
- An observation that canon conflicts with a recorded decision, a standard
  or a philosophy is settled the same way: change the standard or
  philosophy, or write the project's exception into that principle's
  **Here, specifically:** in the canon digest, so the conflict stops
  recurring.
- Discards get a one-line reason. Clear every processed item from the pending
  file, marked promoted or discarded.
- Each disposition produces an `observation` outcome — the promote/discard
  record is the calibration signal for whatever filed the observation.

### 6. Test sanity
- Run the project's full test suite. Capture the result for the MR's test
  plan, including new warnings and skips, not just failures.
- Breakage is not stewardship work: each distinct failure produces a `bug`
  outcome describing the breakage — **do not fix it inline**. A fix on a
  housekeeping branch muddies both the fix and the cleanup.
- A red suite does not block the pass: documentation, digest, and promotion
  changes still ship, with the breakage noted in the MR description.

### 7. Commit

## Git conventions

**Read the project's `CLAUDE.md` (or equivalent agent instructions) before any
git operation.** Its git, CI, branch, and review conventions are authoritative
and override every default below.

Defaults, where the project states nothing:

- **Conventional commits**: `fix:`, `feat:`, `refactor:`, `docs:`, `test:`,
  `chore:` — subject in the imperative, scoped where the project scopes.
- **Wrap at 80 characters** — subject line and every body line. Tighten a long
  subject (drop adjectives) rather than wrapping it.
- **No bylines, no attribution trailers** — no `Co-Authored-By:`, no
  "generated by" lines, no attribution footers on commits, MR bodies,
  issues, or comments.
- **Separate `git add`, `git commit`, `git push`** — never chained, so each
  result is visible on its own.
- Run the tests the change touches before committing code: the tests of
  each file it changes, and every test that names a name it changes. The
  project's full test suite and its exact CI checks run once, as the
  change's final verification: in a fresh evaluator where the workflow
  spawns one, otherwise before the push that opens the merge request. A
  later fix pass leaves the full run to the merge request's pipeline.
  Install any commit-msg hook the project declares before the first commit.
- Never force-push over work you did not write.


### 8. Open the cleanup MR
- One MR for the whole pass, targeting `branching.default-target` from
  `glados.yaml`. Description carries `## Summary` (what was compacted,
  refreshed, promoted, and the canon report from step 4) and `## Test plan`
  (the suite result from step 6).
- Resolve `merge-authority` from `glados.yaml` for who may merge — this
  document states no authority, and this step never merges.
- If nothing changed — nothing stale, nothing pending — skip
  the MR rather than manufacture one. The canon report (digest ages, recall
  drafts awaiting confirmation, missing digests) then goes in this run's
  `progress` outcome instead.
- This run produces a `progress` outcome carrying the MR reference (or the
  no-op note) and a summary of what was compacted and promoted.

## Standards gate

Before advancing past this point, audit the artifact the preceding step
produced — the spec when this gate runs before implementation, the working
diff when it runs before declaring the work done — against the project's
documented standards. The standards tree lives at
`product-knowledge/standards/` and that is the **only** standards root: a bare
`standards/` directory at the repo root is not read, not even as a fallback.

### Discover applicable standards

- Read `product-knowledge/standards/index.yml` for the registered standards.
  If the tree or its index is absent, say so in the gate report and pass the
  gate vacuously — an empty standards tree gates nothing, but skipping the
  gate silently is not the same thing.
- Each standard file carries YAML frontmatter:

  ```yaml
  ---
  scope: [api, backend]         # areas this standard applies to
  severity: must | should | may # RFC 2119
  keywords: [error, response]   # aids matching
  ---
  ```

- Filter to the standards that apply to the artifact at hand: `scope` tags
  against the areas and file types touched; `keywords` against the content of
  the spec or the changed files.
- A standard without frontmatter is `severity: should`, `scope: [all]`.
- Philosophy documents registered in the index participate like any other
  standard; treat `weight: core` as `severity: must`.

### Audit

## Verdicts and finding severities

There is exactly one severity scale and one verdict vocabulary. No reviewer,
panelist, or evaluator may introduce another tier or another verdict word.

**Finding severities — two tiers only:**

| Severity | Meaning |
|----------|---------|
| `blocking` | The change must not merge as-is: it breaks behaviour, breaks an acceptance criterion the work received (one the ticket or someone other than the author set; the author's own are design under review), opens a security, tenancy or data-loss hole, crosses a boundary the project's architecture standards draw, or leaves a test gap that hides one of these. |
| `advisory` | Worth one line, not worth blocking: style, naming, simplification, prose, a standard whose breach changes no behaviour and crosses no boundary, any suggestion the author may decline. |

Code is the truth and prose points at it. A finding about a comment, a
docstring, a README, a commit message or a merge-request description is
`advisory`, always: prose cannot break the build, and a review that blocks on
it teaches the team to skim the next one. Fix prose you pass through when the
fix is cheap; otherwise say it in one line.

Unsure whether a finding blocks? Then it is `advisory`, written as the
question it is. A wrong `blocking` finding costs more than a missed one: it
sends the author to refactor around a defect that does not exist.

**A finding is about code the change introduced.** Most codebases predate the
standards they are now held to, so a lens reading a touched file finds
breaches the author never wrote. Those are not this review's findings. A
breach that already existed in a file the change touches is noted, not
blocking, and the whole set of them is worth **one line** pointing at
wherever the project tracks bringing existing code up to standard — never one
finding per instance. Listing them buries the three findings the author can
act on among the fifteen they cannot, and an author who has skimmed one
review skims the next one, which is how a real finding gets missed.

Pre-existing means already on the target branch. Commits this branch already
carries (an earlier revision, an earlier run's work) are part of the change
and are not precedent. This settles what counts as pre-existing, not what a
delta pass re-reads.

Two things are not pre-existing, whatever their line numbers say: a breach
the change makes worse, and one the change now depends on. Both are findings
about this change and land at whatever tier they earn.

**For every type, field, parameter, public method or function, and
exception type a change adds, name the line that reads, calls or handles
it.** No reader, no field. Say which line, not that one probably
exists — a reader you cannot point at is the finding. A reader acts on the
value in production code: it branches on it, computes with it, or passes it
out of the change to a receiver that acts on it. A test, a copy into
another field, a check of the value against itself or its twin, and a
serializer whose output no receiver acts on are not readers; a check that
only rejects the value reads it only when some production code can produce
the value it rejects. A unit is public when code outside its own module can reach it.
For a public method or function the change adds, or keeps while removing its
last production caller, name its production caller; for one the project
publishes as its API, name that export instead. For an exception type the
change adds, name the handler that decides what happens next and what it
decides for this failure; the framework's default is not a handler.

This cuts the opposite way from the observation it is usually confused with.
"This value is computed and then dropped" is a true sentence that sounds like
a request to carry the value further, and carrying it is the expensive answer:
a field, a shape to hold it, a caller to thread it, and a test for each. The
cheap answer is almost always that nobody wanted the value, and the fix is to
stop computing it. Ask which before asking for plumbing. The same applies to a
value carried across a step boundary that the later step never acts on: that
is not information, it is coupling, and the step that stores a result does not
need to know why the step before it kept one.

A review can establish that nothing reads a field. It cannot establish that
nothing *should* — a reader someone is about to write is invisible here, and
"a later ticket will use it" is a real answer that only the people who know
what the system is for can weigh. So this is stated as the fact and never as
a demand: "nothing reads `x`" is the finding; "delete `x`" is a suggestion
the author may decline like any other. It is `advisory` unless the unread or
uncalled thing also breaks something.

**A finding is a claim and its evidence, and they are not the same length.**
The claim is what breaks, where, and what to do about it — a few lines, in
plain sentences. The evidence is the reproduction, the measurement, the walk
through the mechanism, the reason the obvious fix is the wrong one. Both are
owed. Only the claim is owed *on the first screen*.

Wherever a verdict is published, write it so that a reader who expands
nothing still learns every blocking thing they have to do. Evidence goes
beneath its claim, folded where the platform can fold it and last where it
cannot. This is what keeps two rules from fighting: a review may never drop a
finding, and a review nobody finishes reading has dropped all of them. A
comment gets shorter by putting its proof one click down, never by leaving
the proof out — and a finding that cannot state its ask in one line at the
top has not been understood well enough to post.

**An advisory earns its line by naming a consequence.** The two tiers say
how much a finding is worth acting on. Neither says whether it was worth
writing down, so `advisory` becomes where each lens files everything it
noticed, and the list fills with items whose only effect is that the code
would read differently to the person who raised them.

Before publishing one, name what acting on it changes. One of:

- **behaviour**, under some input;
- **whether a defect would be caught**, where the finding is about a test;
- **what someone has to work with when it fails**, where it is about a
  message, a log or a record that somebody actually reads.

A finding with none of the three is not being dropped, because it was
never a finding — it is a preference. Fix it in passing if you are already
in the file; otherwise let it go. Where you cannot tell whether a
consequence exists, it stays: the rule for an uncertain finding is
unchanged, and this is not a licence to argue yourself out of one.

This does not exempt naming, interfaces or structure. A name that makes a
reader believe something false about what the thing does has a
consequence, and so does a boundary the architecture draws and the code
crosses. What disqualifies a finding is that a different choice would
merely be tidier — so the test is whether you can NAME the consequence,
never which category the finding falls into.

**And price what you ask for.** A finding states a problem; a reader turns
it into work, and the size of that work is often invisible from the line
that asked. "This message should carry the index" is one clause and can
be a restructure. Where the fix is not obviously small, say what you think
it costs — and if you have not looked, say that instead of implying it is
cheap. A reviewer who has not priced the work has not finished the
finding, and an advisory whose fix is large is either worth stating as
that trade or not worth stating.

**Say each thing once.** The claim/evidence split makes a review shorter
by moving proof out of the way; it does nothing about the same POINT
appearing twice on the surface, which in practice is the larger cost. A
summary bullet and the finding's opening sentence say the same thing. So
does a line reporting a fix landed and the finding beneath it that closed.
So does a scope statement and the advisory that implies it. Each pair
reads as two facts and is one, and the second telling is always the weaker
one, because by then it is competing with the detail around it.

Where a review publishes a summary of what it is asking for, that summary
is the ONLY place those asks are written, and each finding is presented
under the line that summarises it rather than restating it. Before
publishing, read only what a reader sees without expanding anything and
count how many times the author is told the same thing: every count above
one is length that bought nothing, and cutting it removes no finding.

**Verdicts:** `APPROVE | REQUEST_CHANGES | ESCALATE`.

**Composition rules (applied at the tally, not left to individual reviewers):**

- Any `blocking` finding ⇒ `REQUEST_CHANGES`.
- A missing or malformed panelist verdict ⇒ `ESCALATE` — never approval.
  Silence is not consent; respawn or escalate, do not count it as a pass.
- Advisory-only findings ⇒ `APPROVE`. Advisories are offered, not owed: the
  author may fix, decline or ignore them, and approval waits on none of them.


For each applicable standard, read its full content and compare the artifact
against it. A standard the artifact adheres to produces no finding. A breached
standard produces exactly one finding, classified on the single severity scale
above by the standard's declared severity:

| Standard severity  | Finding    |
|--------------------|------------|
| `must`             | `blocking` |
| `should` / `may`   | `advisory` |
| canon, not adopted | `advisory` |

A standard's `must`/`should`/`may` is authoring metadata about the standard;
findings themselves take only the two tiers — no third tier exists at the
gate.

### Gate decision

- **Any `blocking` finding**: stop. Do not advance to the next step until the
  artifact is brought into compliance, then re-run the gate on the corrected
  artifact. If the standard itself appears wrong or outdated, do not weaken or
  bypass it inline — record the conflict in the gate report as a candidate for
  the standards owner to review, and either comply anyway or halt the work
  here with the conflict stated.
- **Only `advisory` findings**: proceed. State each advisory finding's
  disposition as the severity scale requires — fixed, or declined with a
  one-line reason.

Each re-run of the gate on a corrected artifact is one gate cycle, bounded
by `params.standards-gate.max-cycles` as *Loop bounds* sets out. A run
enclosing this one (preamble step 1) stops too, rather than advancing on an
artifact the gate did not pass:

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


### Report

Close the gate with a summary table; the surrounding workflow carries it in
its findings and outcomes:

```markdown
## Standards Gate
| Standard            | Scope   | Severity | Finding  |
|---------------------|---------|----------|----------|
| API Response Format | api     | must     | none     |
| Error Logging       | backend | should   | advisory |
```

## Before ending this run (mandatory)

A run without a saved run record and a published outcome is an incomplete
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
   scope, outcome, links — and clears its entry in `claims.md`; review-mr
   and address-review, on another's MR, do neither. A nested run
   does neither: it holds no claim of its own, and a work-unit row marks its
   subject done, so a nested plan's row would mark the whole feature done
   early. Its record path is already listed in the parent's record, and the
   outermost run's row covers it.
   The exception is the one the preamble names: a ticket's build inside
   run-epic is a unit of work of its own, so it appends the ticket's row
   and clears the ticket's claim; the runs nested inside it do neither.
   A run that ends with its unit of work still waiting on a person has
   not finished it: run-pipeline parking a step or resuming a park that
   has no approval or answer yet, and run-epic stopping with only parked
   tickets left. It keeps its claim and appends no row, and the
   run that resumes the work does both when the unit ends.
4. **Save the record to the ledger.** Every run's record and step
   artifacts live on the `glados/ledger` branch, never on a work branch:
   the MR carries the change and the comment, and the ledger carries the
   trail. `.glados/glados.py ledger save` commits every new or changed file
   under `.glados/runs/` there and pushes it. Link a record or artifact by
   its ledger copy (`ledger link <path>`), never by a work-branch path.
   Commit and push step 3's row and claim, and any pending observations, on
   the working branch: `chore(glados): log <workflow> run`.
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
   Everything a run posts on a merge request, in any step, starts with
   `(GLaDOS <workflow>)`, whatever a sink's config says.
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
     that ends with its unit still waiting on a person (step 3) has not
     ended it: its items stay pending for the run that resumes the work and
     opens the MR. Once
     the MR exists, a post that fails is a failed delivery as above. Save
     again for any record update made in this step, before step 6.
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
