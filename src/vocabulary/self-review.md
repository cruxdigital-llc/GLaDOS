## Self-review

The self-review step reviews the MR's diff as a critic, before the review
panel sees it.

- Review the diff against the spec (or the project step that stood in for
  it), the shape when there is one, and the closest in-tree precedent. Hunt
  for real defects and note strengths worth keeping. A contentless "looks
  good" self-review is a skipped step, not a passed one.
- Classify each finding on the *Verdicts and finding severities* scale. This
  step produces a `verdict` outcome, which lands on the MR as *Publishing a
  verdict* sets out.
- Its findings start no revise loop, whatever the step's modifier: they
  travel in that `verdict` to review-mr and address-review, and the step's
  row ends `done` once the verdict is produced.
- Do not edit the branch while findings are open; queue fixes so review line
  references stay stable.
- Hand off: the MR goes to review-mr after the sequence's last step, as
  run-pipeline's step 5 sets out; with self-review last, that is now.

<!-- glados:include vocabulary/comment-shape.md -->
