## Opening the merge request

The open-mr step commits the work on the branch and opens one merge request
for it. It never merges.

### Commit

Commit the work on the branch and push it, and save this run's record and
step artifacts so far to the ledger, so every link the description carries
resolves for whoever reviews the MR.

<!-- glados:include vocabulary/git-conventions.md -->

### Open the MR

- Target branch: when this run is inside an epic, read
  `epic.integration-branch`; otherwise resolve `branching.default-target`
  from `glados.yaml`.
- Open the MR with the project platform CLI (per `glados.yaml` `platform:`).
- The description carries:
  - `## Summary` and `## Test plan` sections, with the key changes bulleted;
  - the pipeline, the rule that selected it, and any selection mismatch the
    run recorded;
  - the step table as it stands, with a link to every artifact it names;
  - every finding an advisory step recorded;
  - when no step in this pipeline produced `verification`, this sentence in
    the Summary: "No verification step ran in this pipeline."
- Resolve `merge-authority` from `glados.yaml` for who may merge. This step
  states no authority.

### Deliver what waited for the MR

With the MR open, and before anything reviews it, post every item waiting
for it, as *No MR yet is not a failed delivery* (step 5 of *Before ending
this run*) sets out for the run that opens the MR.
