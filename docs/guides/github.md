# Using GLaDOS on GitHub

GLaDOS is a library of engineering workflows for AI coding agents. You install
it into a project workspace, and it compiles a set of slash commands (for
example `/glados:build-feature`) tailored to that project's configuration file,
`glados.yaml` (called the **manifest**). When your agent runs one of these
commands, it follows a disciplined, team-visible process — reviews get posted,
decisions get recorded, and every run leaves a record on the repo's
`glados/ledger` branch — instead of improvising.

This guide covers everything GitHub-specific: the `gh` CLI, where outcomes
land, the CI check, and protecting the manifest with CODEOWNERS.

A note on words: GLaDOS documentation says "merge request (MR)" because it
grew up on GitLab. On GitHub that is a pull request — this page says PR.

## 1. Declare the platform

In `glados.yaml` at your project root (copy
[glados.yaml.example](../../glados.yaml.example) if you don't have one yet):

```yaml
platform: github            # gitlab | github
```

Then compile and install for your agent runtime:

```bash
python bin/glados.py install --mode claude --target /path/to/your/project
```

Run this from a GLaDOS checkout. `--mode claude` targets Claude Code; the
other modes are `claude-plugin`, `direct`, `gemini` (Gemini CLI, Google's
open-source terminal agent), `antigravity` (Google Antigravity, Google's
agentic IDE — CLI `agy`; antigravity.google), `pi` (pi, the terminal coding
agent; pi.dev), and `aistudio` (Google AI Studio, aistudio.google.com).

## 2. What the agent needs: the `gh` CLI

GLaDOS never calls the GitHub API itself. The compiled workflows tell the
agent to act on GitHub *using its own tooling* — in practice the
[`gh` CLI](https://cli.github.com/), or a GitHub MCP server if the agent has
one. Before your first run, make sure:

- `gh` is installed and on the agent's PATH
- `gh auth status` succeeds for the account the agent should act as
- that account can comment on PRs, open issues, and apply labels in the repo,
  read a PR's comments, reviews and inline review comments, and push
  branches, `glados/ledger` included

Every run saves its record to the `glados/ledger` branch with
`python .glados/glados.py ledger save`, pushed directly and never
force-pushed, so keep `glados/ledger` out of any branch protection rule or
ruleset that requires a pull request; a refused push leaves the record
saved only in that clone. Install adds `/.glados/runs/*` to the clone's git
exclude file, so no record lands in a commit on your branches. A project in
a subdirectory of its repository (a monorepo package) gets
`/<dir>/.glados/runs/*` and keeps its records under `<dir>/.glados/runs/` on
the ledger; run the agent in that subdirectory, because the guard hooks read
`.glados/runs/` in the directory the agent runs in
([hooks/README.md](../../hooks/README.md)). Such a project gets no CI
check: CI enforcement is supported only for a project at the repository
root (section 4).

If the agent has no working GitHub tooling, the contract degrades honestly:
workflows emit the exact `gh` commands for a human to run instead of failing
silently.

## 3. Where each channel sink lands

The manifest's `channels:` section routes each **outcome type** (a kind of
result a workflow produces — a review verdict, a discovered bug, a decision)
to one or more **sinks** (places the team can see it). On GitHub, each sink
kind maps to:

| Sink kind | Lands as | Typical command |
|---|---|---|
| `mr-comment` | A comment on the open PR | `gh pr comment <num> --body ...` |
| `issue` | A new GitHub issue | `gh issue create --title ... --body ...` |
| `issue-comment` | A comment on an existing issue | `gh issue comment <num> --body ...` |
| `label` | A label on the PR or issue | `gh pr edit <num> --add-label ...` |
| `ledger` | A file under `.glados/runs/`, saved to the repo's `glados/ledger` branch (the **run ledger** — one record per workflow run, never on the work's branch) | `glados.py ledger save` |

A working GitHub binding looks like:

```yaml
channels:
  progress:    [ledger]
  verdict:     [mr-comment]     # review results appear on the PR
  escalation:  [issue]          # "a human must look at this" opens an issue
  bug:         [issue]
  decision:    [ledger]
  observation: [ledger]
```

The installer type-checks this: an outcome type that a workflow produces but
that no team-visible sink receives is an install error, not a silent gap.

Everything GLaDOS posts on a PR starts with `(GLaDOS <workflow>)`.
review-mr and address-review read every comment, review (with its state)
and inline review comment without that marker, written by someone with a
role on the repo who did not write the change, as that person's review,
whichever account posted it: each point is a finding labelled as theirs, at
the strength they said it, and only they withdraw or waive a blocking one.
On a PR opened before you upgraded to 2.5, edit each GLaDOS comment so its
first line starts with the marker before running either workflow on it.

## 4. Enable the GitHub Actions check

Every install vendors two CI templates into `.glados/ci/` in your repo. They
run the compiler in check mode on every push and PR: recompute the compile
from the vendored sources and your manifest, diff against the installed files,
and fail on drift. The installer prints the enable instruction itself
(genuine output from `install` with `platform: github`):

```
glados: CI backstop vendored to .glados/ci/ — enable it with:
    mkdir -p .github/workflows
    cp .glados/ci/glados-check.github-actions.yml .github/workflows/glados-check.yml
```

Run both lines (the first makes `.github/workflows/`, which a repository
with no workflow yet lacks), commit the copy, and the `glados-check`
workflow runs on `push` and `pull_request`. It ships report-only; drop the
`--report-only` flag inside the copied file to make drift block the build
(recommended once the project is in production). The copy is yours: a
reinstall vendors `.glados/ci/` again but never touches
`.github/workflows/`. A second, never-blocking step (`verify-ledger`) scans
recent git history on every branch (`fetch-depth: 0` brings them all,
`glados/ledger` included) for run records that look silently lost and, on a pull request,
lists any run record the branch commits since its base: records belong on
`glados/ledger`, never in a PR's diff, so save a listed one with
`glados.py ledger save` and drop it from the branch.

Confirm the wiring took:

```bash
python bin/glados.py doctor --target /path/to/your/project
```

`doctor` reports whether the check is wired in: a workflow under
`.github/workflows/` that runs `glados.py check`. It cannot see whether that
workflow runs, so look for the `glados-check` job on your next pull request —
a check that is declared but never executes is exactly the failure it exists
to catch.

CI enforcement is supported only for a project at the repository root. The
workflow runs `.glados/glados.py` from the repository's root, and GitHub
reads workflows only from the root's `.github/workflows/`, so for a project
in a subdirectory of its repository (a monorepo package) the commands above
would make a workflow that never runs. For such a project the installer
prints instead that CI enforcement is not supported there, and `doctor`
reports `CI check wired: not supported`; run `python .glados/glados.py check
--target .` in the project's directory yourself.

## 5. Protect `glados.yaml` with CODEOWNERS

The manifest controls merge authority, decision rights, and the project
`phase:` (a one-word declaration of how careful the agent must be). Agents may
*propose* changes to it; a human should always approve them. Make that
structural:

```
# .github/CODEOWNERS
/glados.yaml               @your-team-leads
/product-knowledge/steps/  @your-team-leads
/product-knowledge/canon/  @your-team-leads
```

With branch protection requiring code-owner review, no phase relaxation
merges without a named human signing off. A project step's body can loosen a
pipeline gate as surely as `glados.yaml` can, and a canon digest decides
what reviews hold a change to, so both get the same owners. `doctor` reports
whether a CODEOWNERS file exists and covers `glados.yaml`, and each of those
directories the project uses (informational only).

## Summary

| | |
|---|---|
| **Works today** | `platform: github`; all five sink kinds via `gh`; run records on the `glados/ledger` branch (`glados.py ledger save \| restore \| link`); the vendored Actions check (report-only by default); `doctor` wiring and CODEOWNERS reports |
| **Coming later** | Lease files for multi-agent coordination; `verify-ledger` comparing emitted events against manifest claims; attention-tier reporting (direction, not shipped) |
| **Your responsibility** | Install and authenticate `gh` for the agent, with push access to `glados/ledger`; copy the Actions template into `.github/workflows/` and commit it; add the CODEOWNERS lines and branch protection |

See also: [gitlab.md](gitlab.md) for the GitLab equivalent,
[linear.md](linear.md) for teams that track issues in Linear, and
[../../MIGRATION.md](../../MIGRATION.md) for moving a v1 install to v2.
