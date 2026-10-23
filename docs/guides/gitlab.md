# Using GLaDOS on GitLab

GLaDOS is a library of engineering workflows for AI coding agents. You install
it into a project workspace, and it compiles a set of slash commands (for
example `/glados:build-feature`) tailored to that project's configuration file,
`glados.yaml` (called the **manifest**). When your agent runs one of these
commands, it follows a disciplined, team-visible process — reviews get posted,
decisions get recorded, and every run leaves a record on the project's
`glados/ledger` branch — instead of improvising.

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
agentic IDE — CLI `agy`; antigravity.google), `pi` (pi, the terminal coding
agent; pi.dev), and `aistudio` (Google AI Studio, aistudio.google.com).

## 2. What the agent needs: the `glab` CLI

GLaDOS never calls the GitLab API itself. The compiled workflows tell the
agent to act on GitLab *using its own tooling* — in practice the
[`glab` CLI](https://gitlab.com/gitlab-org/cli), or a GitLab MCP server if the
agent has one. Before your first run, make sure:

- `glab` is installed and on the agent's PATH
- `glab auth status` succeeds for the account the agent should act as
- that account can comment on MRs, open issues, and apply labels in the
  project, read an MR's notes and threads, and push branches,
  `glados/ledger` included

One practical note for sandboxed agent shells: `glab` may store its token in
an OS keyring the sandbox cannot read. If `glab auth status` reports no token
inside the agent's shell but works in yours, put the token in `glab`'s config
file (or export `GITLAB_TOKEN`) so the agent's non-interactive shell can use
it. If the agent has no working GitLab tooling at all, the contract degrades
honestly: workflows emit the exact `glab` commands for a human to run.

Every run saves its record to the `glados/ledger` branch with
`python .glados/glados.py ledger save`, pushed directly and never
force-pushed, so keep `glados/ledger` out of any protected-branch rule that
blocks the agent's pushes; a refused push leaves the record saved only in
that clone. Install adds `/.glados/runs/*` to the clone's git exclude file,
so no record lands in a commit on your branches. A project in a
subdirectory of its repository (a monorepo package) gets
`/<dir>/.glados/runs/*` and keeps its records under `<dir>/.glados/runs/` on
the ledger; run the agent in that subdirectory, because the guard hooks read
`.glados/runs/` in the directory the agent runs in
([hooks/README.md](../../hooks/README.md)). Such a project gets no CI
check: CI enforcement is supported only for a project at the repository
root (section 4).

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
| `ledger` | A file under `.glados/runs/`, saved to the repo's `glados/ledger` branch (the **run ledger** — one record per workflow run, never on the work's branch) | `glados.py ledger save` |

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

Everything GLaDOS posts on an MR starts with `(GLaDOS <workflow>)`.
review-mr and address-review read every note and reply without that marker,
written by someone with a role on the project who did not write the change,
as that person's review, whichever account posted it: each point is a
finding labelled as theirs, at the strength they said it, and only they
withdraw or waive a blocking one. On an MR opened before you upgraded to
2.5, edit each GLaDOS note so its first line starts with the marker before
running either workflow on it.

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
the `test` stage: `glados-check` (report-only at first) and
`glados-verify-ledger` (`allow_failure: true`, never gates a merge): it
installs git, fetches the `glados/ledger` branch where the run records live,
scans the recent history of the branch under test and the ledger branch (a
GitLab job clones no other branch) for run records that look silently lost
and, on a merge request, lists any run record the branch commits since its
diff base. Records belong on `glados/ledger`, never in an MR's diff, so
save a listed one with `glados.py ledger save` and drop it from the branch.

To make drift block the pipeline (recommended once the project is in
production), override the job's script in your `.gitlab-ci.yml`, under the
`include:`; a job you define with the included job's name replaces the keys
you give:

```yaml
glados-check:
  script:
    - python .glados/glados.py check --target .
```

Do not drop `--report-only` inside the vendored file instead: every install
vendors `.glados/ci/glados-check.gitlab-ci.yml` again with the flag, and
`check` does not report the difference, so the next reinstall (an upgrade,
say) quietly turns enforcement off.

Confirm the wiring took:

```bash
python bin/glados.py doctor --target /path/to/your/project
```

`doctor` reports whether the include is wired in: whether `.gitlab-ci.yml`
mentions it. It cannot see whether the jobs run, so look for `glados-check`
in your next merge request pipeline — a check that is declared but never
executes is exactly the failure it exists to catch.

CI enforcement is supported only for a project at the repository root. Both
jobs run `.glados/glados.py` from the repository's root, and an
`include: local:` path is read from the root too, so for a project in a
subdirectory of its repository (a monorepo package) the stanza above
includes a file that is not there, and its jobs could not find the checker.
For such a project the installer prints instead that CI enforcement is not
supported there, and `doctor` reports `CI check wired: not supported`; run
`python .glados/glados.py check --target .` in the project's directory
yourself.

## 5. Protect `glados.yaml` with CODEOWNERS

The manifest controls merge authority, decision rights, and the project
`phase:` (a one-word declaration of how careful the agent must be). Agents may
*propose* changes to it; a human should always approve them. Make that
structural:

```
# .gitlab/CODEOWNERS
/glados.yaml               @your-team-leads
/product-knowledge/steps/  @your-team-leads
/product-knowledge/canon/  @your-team-leads
```

Combine with a protected branch and approval rules requiring code owners, and
no phase relaxation merges without a named human signing off. A project
step's body can loosen a pipeline gate as surely as `glados.yaml` can, and a
canon digest decides what reviews hold a change to, so both get the same
owners. `doctor` reports whether a CODEOWNERS file exists and covers
`glados.yaml`, and each of those directories the project uses
(informational only).

## Summary

| | |
|---|---|
| **Works today** | `platform: gitlab`; all five sink kinds via `glab`; run records on the `glados/ledger` branch (`glados.py ledger save \| restore \| link`); the vendored CI include (report-only by default); `doctor` wiring and CODEOWNERS reports |
| **Coming later** | Lease files for multi-agent coordination; `verify-ledger` comparing emitted events against manifest claims; attention-tier reporting (direction, not shipped) |
| **Your responsibility** | Install and authenticate `glab` for the agent (token reachable from its shell), with push access to `glados/ledger`; add the CI `include:` to `.gitlab-ci.yml`; add the CODEOWNERS lines and approval rules |

See also: [github.md](github.md) for the GitHub equivalent,
[linear.md](linear.md) for teams that track issues in Linear, and
[../../MIGRATION.md](../../MIGRATION.md) for moving a v1 install to v2.
