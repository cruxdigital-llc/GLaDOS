# Using GLaDOS with Linear

GLaDOS is a library of engineering workflows for AI coding agents. You install
it into a project workspace, and it compiles a set of slash commands (for
example `/glados:build-feature`) tailored to that project's configuration file,
`glados.yaml` (called the **manifest**). Many teams keep code on GitHub or
GitLab but track work in [Linear](https://linear.app). This guide is the
honest version of how that combination works — including what GLaDOS does
*not* do for you.

## There is no `platform: linear`

The manifest's `platform:` key supports exactly two documented values:

```yaml
platform: gitlab            # gitlab | github
```

That key answers one question: *which git host holds this project's merge
requests, pipelines, and default issue tracker*, so workflows know which CLI
to reach for (`glab` or `gh`). Linear is not a git host, so it is not a
`platform:` value. (The compiler does not currently hard-reject other
strings, but nothing reads an undocumented value — the workflows would have
no defined CLI and the installer's CI instructions fall back to printing both
git-host variants. Keep `platform:` set to your actual git host.)

## How Linear enters: the boundary of responsibility

GLaDOS defines *contracts*, not integrations. The manifest's `channels:`
section routes each **outcome type** (a kind of result a workflow produces —
a review verdict, a discovered bug, an escalation) to one or more **sinks**
(places the team can see it). The sink vocabulary is closed:

- `mr-comment` — a comment on the open merge request / pull request
- `issue` — a new ticket in the project's issue tracker
- `issue-comment` — a comment on an existing ticket
- `label` — a label applied to the MR/PR or ticket
- `ledger` — a committed file under `.glados/runs/` in the repo

Notice what `issue` does *not* say: it does not say "GitHub issue" or "GitLab
issue". GLaDOS never wires a platform API itself — the **agent brings its own
hands**. If your agent has Linear tooling (typically the
[Linear MCP server](https://linear.app/docs/mcp)), it can satisfy every
issue-kind sink by creating and commenting on Linear issues, exactly as a
`gh`-equipped agent satisfies them with GitHub issues.

## A worked configuration

Manifest — note that `platform:` stays on the git host, because verdicts
still belong on the code review:

```yaml
platform: github            # your git host — MRs/PRs and CI live here

channels:
  progress:    [ledger]
  verdict:     [mr-comment]   # review results stay on the PR, next to the code
  escalation:  [issue]        # → Linear (see agent instructions below)
  bug:         [issue]        # → Linear
  decision:    [ledger]
  observation: [ledger]
```

Then tell the agent — in your project's agent instructions file (`CLAUDE.md`,
`GEMINI.md`, or equivalent) — how to execute issue-kind sinks:

```markdown
## Issue tracker

This project tracks issues in Linear (team ENG), not GitHub issues.
When a GLaDOS channel binds an outcome to the `issue` or `issue-comment`
sink, use the Linear MCP tools: create the issue in team ENG, apply the
`agent-filed` label, and paste the resulting Linear URL into the run
record so the ledger links to it.
```

That is the whole integration: the manifest routes *what* must be visible,
your instructions file says *where* the tracker lives, and the agent's own
Linear tooling does the posting. Install as usual:

```bash
python bin/glados.py install --mode claude --target /path/to/your/project
```

(`--mode claude` targets Claude Code; other modes: `claude-plugin`, `direct`,
`gemini` for Gemini CLI — Google's open-source terminal agent, `antigravity`
for Google Antigravity — Google's agentic IDE, CLI `agy`, antigravity.google
— and `aistudio` for Google AI Studio, aistudio.google.com.)

## What is NOT automated — plainly

- **GLaDOS never calls the Linear API.** No sink is hardwired to Linear; the
  routing works only if the agent actually has Linear tooling connected and
  authenticated. Set up the Linear MCP server yourself and verify the agent
  can create a test issue before trusting the channel.
- **The installer cannot type-check Linear wiring.** The install-time check
  verifies every emitted outcome type has a team-visible sink *kind* bound —
  it cannot verify Linear credentials exist or that issues really land.
- **`glados doctor` does not inspect Linear.** It reports git-host CI wiring
  and CODEOWNERS coverage; it has no view into your Linear workspace.
- **The CI backstop checks the repo, not the tracker.** `.glados/ci/`
  templates recompute the compile and scan the run ledger; they do not verify
  that a `bug` outcome produced a Linear issue.
- **Code review stays on the git host.** `mr-comment` verdicts have no Linear
  equivalent — the review conversation belongs on the MR/PR, and pointing
  `verdict:` away from it would need an explicit confession
  (`visibility-acknowledged`) to pass the installer.
- **No agent Linear tooling = manual posting.** On runtimes without hands,
  workflows emit the issue title/body text and a human (or a runner script)
  creates the Linear issue.

## Summary

| | |
|---|---|
| **Works today** | `platform: github` or `gitlab` + issue-kind sinks satisfied by the agent's own Linear MCP tooling, directed by your agent instructions file; Linear URLs recorded in the run ledger |
| **Coming in v2.1–v2.2** | Nothing Linear-specific is planned; v2.1's issue-claim lease backend (humans assigning tickets act as leases) targets the git host's tracker, not Linear |
| **Your responsibility** | Connect and authenticate the Linear MCP for the agent; write the tracker instructions in `CLAUDE.md`; spot-check that filed outcomes actually appear in Linear — no GLaDOS check will catch a silent Linear failure |

See also: [github.md](github.md) / [gitlab.md](gitlab.md) for the git-host
setup this guide builds on.
