# GLaDOS run-record hooks

The compiled epilogue asks each run to finalize and commit a run record before
it ends. That is a promise an LLM keeps at 90% context — these host-agent hooks
are the mechanical backstop for the three runtimes that have one. All three are
**conditional on the in-flight markers** (written by the compiled preamble at
run start, popped by the compiled epilogue, never committed): they stay silent
unless a run is actually in flight, so ordinary sessions are never disturbed.

- `.glados/runs/current` holds the filename of the innermost run in flight.
- `.glados/runs/stack` lists every run in flight, one filename per line,
  outermost first; its last line equals `current`. Runs nest: build-feature
  runs plan-feature, spec-feature, implement-feature, and verify-feature
  inside itself, and run-epic runs build-feature. A nested run pushes its
  record onto the stack and its epilogue pops it, putting the enclosing run
  back into `current`.

The guards check every record the stack lists: any listed record that is
uncommitted or untracked blocks the session end, and the message names it.
Without a `stack` file (an install compiled before it existed), they check
`current` alone, exactly as before. Either marker on its own means a run is
in flight, so to release a run you have abandoned, delete both
`.glados/runs/current` and `.glados/runs/stack`.

The guards read the markers whatever encoding the agent's shell wrote them
in: a UTF-8 byte-order mark is ignored, UTF-16 (Windows PowerShell 5.1
redirection) is decoded, and a marker they cannot read at all still counts
as a run in flight, so the uncommitted-record check runs instead of the
guard failing open.

`glados.py install` vendors the guard scripts into `.glados/hooks/` in your
repo, so the wiring snippets below reference stable, repo-local paths. The
Antigravity adapter also writes `.agents/hooks.json` for you (only if that file
does not already exist).

CI `verify-ledger` is the universal backstop that exists on every runtime — the
installer vendors the check templates into `.glados/ci/` and prints the enable
stanza; the project adds the include (GitLab) or copies the workflow file into
`.github/workflows/` (GitHub). The hooks below are per-runtime accelerators
where a blocking surface exists.

## Claude Code — Stop hook (blocks session end)

`.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "python .glados/hooks/claude-stop-hook.py" }
        ]
      }
    ]
  }
}
```

Blocks the stop with a reason (`{"decision":"block"}`) when a run is in flight
without a committed record.

## Gemini CLI — AfterAgent guard (retries the turn)

Gemini's SessionEnd cannot block; AfterAgent can (exit 2 retries the turn).
`.gemini/settings.json`:

```json
{
  "hooks": {
    "AfterAgent": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "python .glados/hooks/gemini-afteragent-guard.py" }
        ]
      }
    ]
  }
}
```

## Antigravity `agy` — Stop hook (best-effort)

`.agents/hooks.json` (written by the antigravity adapter if absent; otherwise
add the block from `agy-hooks.json` manually):

```json
{
  "hooks": {
    "glados-run-record-guard": {
      "Stop": {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "python .glados/hooks/gemini-afteragent-guard.py", "timeout": 30 }
        ]
      }
    }
  }
}
```

agy's Stop hook cannot force continuation (undocumented), so this is
best-effort: it surfaces the reason. The Antigravity IDE has no verified hook
surface — rely on CI `verify-ledger` there. Note that agy hook commands may need
**absolute paths** on some setups; adjust the vendored path if a relative one is
ignored.
