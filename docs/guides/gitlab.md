# Using GLaDOS on GitLab

GLaDOS is a library of engineering workflows for AI coding agents. You install
it into a project workspace, and it compiles a set of slash commands (for
example `/glados:build-feature`) tailored to that project's configuration file,
`glados.yaml` (called the **manifest**). When your agent runs one of these
commands, it follows a disciplined, team-visible process — reviews get posted,
decisions get recorded, and every run leaves a committed record — instead of
improvising.

GitLab is GLaDOS's home platform, so the defaults fit it with no translation:
"merge request (MR)" means exactly what GitLab means by it. This guide covers
the `glab` CLI, where outcomes land, the GitLab CI include, and protecting the
manifest with CODEOWNERS.

## 1. Declare the platform

In `glados.yaml` at your project root (copy
[glados.yaml.example](../../glados.yaml.example) if you don't have one yet):

```yaml
platform: gitlab            # gitlab | github
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

## 2. What the agent needs: the `glab` CLI

GLaDOS never calls the GitLab API itself. The compiled workflows tell the
agent to act on GitLab *using its own tooling* — in practice the
[`glab` CLI](https://gitlab.com/gitlab-org/cli), or a GitLab MCP server if the
agent has one. Before your first run, make sure:

- `glab` is installed and on the agent's PATH
- `glab auth status` succeeds for the account the agent should act as
- that account can comment on MRs, open issues, and apply labels in the project

One practical note for sandboxed agent shells: `glab` may store its token in
an OS keyring the sandbox cannot read. If `glab auth status` reports no token
inside the agent's shell but works in yours, put the token in `glab`'s config
file (or export `GITLAB_TOKEN`) so the agent's non-interactive shell can use
it. If the agent has no working GitLab tooling at all, the contract degrades
honestly: workflows emit the exact `glab` commands for a human to run.

## 3. Where each channel sink lands

The manifest's `channels:` section routes each **outcome type** (a kind of
result a workflow produces — a review verdict, a discovered bug, a decision)
to one or more **sinks** (places the team can see it). On GitLab, each sink
kind maps to:

| Sink kind | Lands as | Typical command |
|---|---|---|
| `mr-comment` | A comment on the open merge request | `glab mr note <num> --message ...` |
| `issue` | A new GitLab issue | `glab issue create --title ... --description ...` |
| `issue-comment` | A comment on an existing issue | `glab issue note <num> --message ...` |
| `label` | A label on the MR or issue | `glab mr update <num> --label ...` |
| `ledger` | A committed file under `.glados/runs/` in the repo (the **run ledger** — one record per workflow run) | plain git commit |

A working GitLab binding looks like:

```yaml
channels:
  progress:    [ledger]
  verdict:     [mr-comment]     # review results appear on the MR
  escalation:  [issue]          # "a human must look at this" opens an issue
  bug:         [issue]
  decision:    [ledger]
  observation: [ledger]
```

The installer type-checks this: an outcome type that a workflow produces but
that no team-visible sink receives is an install error, not a silent gap.

## 4. Enable the GitLab CI include

Every install vendors two CI templates into `.glados/ci/` in your repo. They
run the compiler in check mode on every branch push and MR pipeline:
recompute the compile from the vendored sources and your manifest, diff
against the installed files, and fail on drift. The installer prints the
enable instruction itself (genuine output from `install` with
`platform: gitlab`):

```
glados: CI backstop vendored to .glados/ci/ — enable it in .gitlab-ci.yml:
    include:
      - local: '.glados/ci/glados-check.gitlab-ci.yml'
```

Add that `include:` to your `.gitlab-ci.yml` and commit. Two jobs appear in
the `test` stage: `glados-check` (report-only at first; drop the
`--report-only` flag inside the vendored file to make drift block the
pipeline — recommended once the project is in production) and
`glados-verify-ledger` (`allow_failure: true`, scans full git history for run
records that look silently lost, never gates a merge).

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
# .gitlab/CODEOWNERS
/glados.yaml @your-team-leads
```

Combine with a protected branch and approval rules requiring code owners, and
no phase relaxation merges without a named human signing off. `doctor`
reports whether a CODEOWNERS file exists and covers `glados.yaml`
(informational only).

## Summary

| | |
|---|---|
| **Works today** | `platform: gitlab`; all five sink kinds via `glab`; the vendored CI include (report-only by default); `doctor` wiring and CODEOWNERS reports |
| **Coming in v2.1–v2.2** | Lease files for multi-agent coordination (v2.1); `verify-ledger` comparing emitted events against manifest claims (v2.1); attention-tier reporting (v2.2) |
| **Your responsibility** | Install and authenticate `glab` for the agent (token reachable from its shell); add the CI `include:` to `.gitlab-ci.yml`; add the CODEOWNERS line and approval rules |

See also: [github.md](github.md) for the GitHub equivalent,
[linear.md](linear.md) for teams that track issues in Linear, and
[../../MIGRATION.md](../../MIGRATION.md) for moving a v1 install to v2.
