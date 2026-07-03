---
name: build-feature
kind: core
description: Take one feature from selection to a verified, self-reviewed merge request
reads: [epic.integration-branch, intent.status, manifest.branching, manifest.merge-authority, manifest.platform]
writes: [work.base-sha]
emits: [progress, verdict, escalation]
mutates: branch
requires: []
---

# (GLaDOS) Build Feature

**Goal**: take one feature from idea to a review-ready merge request. This core
sequences the four stage workflows, gates the MR on verification, then
self-reviews the diff. It is the entry point of the review loop
(build-feature → review-mr ⇄ address-review).

## Process

### 1. Select the feature
- Take the feature from the caller (an epic ticket or a user brief). With no
  caller, pick the top actionable item from the project status file
  (`intent.status`). If nothing is actionable, this run produces an
  `escalation` outcome and stops.

### 2. Claim the branch
- Resolve `branching` from `glados.yaml`; create the working branch per its
  `feature` naming pattern. The commit the branch is cut from is this run's
  base (`work.base-sha`, already recorded at run start).

### 3. Run the pipeline
Run each stage as its own workflow, in order. Each consumes the previous
stage's output — do not fold stages together or skip ahead.

| Stage     | Do                                  | Produces                        |
|-----------|-------------------------------------|---------------------------------|
| Plan      | run the plan-feature workflow       | goals, approach, persona roster |
| Spec      | run the spec-feature workflow       | requirements + spec             |
| Implement | run the implement-feature workflow  | the working diff, with tests    |
| Verify    | run the verify-feature workflow     | independent verification result |

- **Verified-before-MR gate**: do not proceed past this step until
  verify-feature succeeds. If it cannot succeed within its cycle bound (the
  bound comes from `params.evaluator.max-cycles` in `glados.yaml`), this run
  produces an `escalation` outcome and stops — an unverified MR is worse than
  no MR.

### 4. Commit

<!-- glados:include vocabulary/git-conventions.md -->

### 5. Open the merge request
- Target branch: when this build runs inside an epic, read
  `epic.integration-branch`; otherwise resolve `branching.default-target` from
  `glados.yaml`.
- Open the MR with the project platform CLI (per `glados.yaml` `platform:`).
- Description carries `## Summary` and `## Test plan` sections; bullet the key
  changes; link the spec and the verification result.
- Resolve `merge-authority` from `glados.yaml` for who may merge — this
  document states no authority, and this step never merges.

### 6. Self-review
- Review your own diff as a critic: against the spec and the closest in-tree
  precedent. Hunt for real defects and note strengths worth keeping — a
  contentless "looks good" self-review is a skipped step, not a passed one.
- This step produces a `verdict` outcome.
- Do not edit the branch while findings are open; queue fixes so review line
  references stay stable.

### 7. Handoff
- This run produces a `progress` outcome carrying the MR reference and the
  self-review result.
- Run the review-mr workflow to begin the adversarial review loop.
