## Self-review

The self-review step reviews the MR's diff as a critic, before the review
panel runs.

- Review the diff against the spec (or the project step that stood in for
  it), the shape when there is one, and the closest in-tree precedent. Hunt
  for real defects and note strengths worth keeping. A contentless "looks
  good" self-review is a skipped step, not a passed one.
- Classify each finding on the *Verdicts and finding severities* scale. This
  step produces a `verdict` outcome, which lands on the MR as *Publishing a
  verdict* sets out.
- Its verdict follows **After the MR opens** in run-pipeline's step 4: it is
  posted when the step ends, and its findings start no revise loop,
  whatever the step's modifier.
- Do not edit the branch while findings are open; queue fixes so review line
  references stay stable.

<!-- glados:include vocabulary/comment-shape.md -->
