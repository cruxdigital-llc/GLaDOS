# Using GLaDOS on GitHub

GLaDOS is a library of engineering workflows for AI coding agents. You install
it into a project workspace, and it compiles a set of slash commands (for
example `/glados:build-feature`) tailored to that project's configuration file,
`glados.yaml` (called the **manifest**). When your agent runs one of these
commands, it follows a disciplined, team-visible process — reviews get posted,
decisions get recorded, and every run leaves a committed record — instead of
improvising.

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
agentic IDE — CLI `agy`; antigravity.google), and `aistudio` (Google AI
Studio, aistudio.google.com).

## 2. What the agent needs: the `gh` CLI

GLaDOS never calls the GitHub API itself. The compiled workflows tell the
agent to act on GitHub *using its own tooling* — in practice the
[`gh` CLI](https://cli.github.com/), or a GitHub MCP server if the agent has
one. Before your first run, make sure:

- `gh` is installed and on the agent's PATH
- `gh auth status` succeeds for the account the agent should act as
- that account can comment on PRs, open issues, and apply labels in the repo

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
| `ledger` | A committed file under `.glados/runs/` in the repo (the **run ledger** — one record per workflow run) | plain git commit |

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

## 4. Enable the GitHub Actions check

Every install vendors two CI templates into `.glados/ci/` in your repo. They
run the compiler in check mode on every push and PR: recompute the compile
from the vendored sources and your manifest, diff against the installed files,
and fail on drift. The installer prints the enable instruction itself
(genuine output from `install` with `platform: github`):

```
glados: CI backstop vendored to .glados/ci/ — enable it with:
    cp .glados/ci/glados-check.github-actions.yml .github/workflows/glados-check.yml
```

Copy the file, commit it, and the `glados-check` workflow runs on `push` and
`pull_request`. It ships report-only; drop the `--report-only` flag inside the
copied file to make drift block the build (recommended once the project is in
production). A second, never-blocking step (`verify-ledger`) scans git history
for run records that look silently lost.

Confirm the wiring took:

```bash
python bin/glados.py doctor --target /path/to/your/project
```

`doctor` reports whether the CI check is actually running — a check that is
declared but never executes is exactly the failure it exists to catch.

## 5. Protect `glados.yaml` with CODEOWNERS

The manifest controls merge authority, decision rights, and the project
`phase:` (a one-word declaration of how careful the agent must be). Agents may
*propose* changes to it; a human should always approve them. Make that
structural:

```
# .github/CODEOWNERS
/glados.yaml @your-team-leads
```

With branch protection requiring code-owner review, no phase relaxation
merges without a named human signing off. `doctor` reports whether a
CODEOWNERS file exists and covers `glados.yaml` (informational only).

## Summary

| | |
|---|---|
| **Works today** | `platform: github`; all five sink kinds via `gh`; the vendored Actions check (report-only by default); `doctor` wiring and CODEOWNERS reports |
| **Coming in v2.1–v2.2** | Lease files for multi-agent coordination (v2.1); `verify-ledger` comparing emitted events against manifest claims (v2.1); attention-tier reporting (v2.2) |
| **Your responsibility** | Install and authenticate `gh` for the agent; copy the Actions template into `.github/workflows/` and commit it; add the CODEOWNERS line and branch protection |

See also: [gitlab.md](gitlab.md) for the GitLab equivalent,
[linear.md](linear.md) for teams that track issues in Linear, and
[../../MIGRATION.md](../../MIGRATION.md) for moving a v1 install to v2.
