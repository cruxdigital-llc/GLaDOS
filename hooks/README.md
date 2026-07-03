# GLaDOS run-record hooks

The compiled epilogue asks each run to finalize and commit a run record before
it ends. That is a promise an LLM keeps at 90% context — these host-agent hooks
are the mechanical backstop for the three runtimes that have one. All three are
**conditional on the in-flight marker** `.glados/runs/current`: they stay silent
unless a run is actually in flight, so ordinary sessions are never disturbed.

`glados.py install` vendors the guard scripts into `.glados/hooks/` in your
repo, so the wiring snippets below reference stable, repo-local paths. The
Antigravity adapter also writes `.agents/hooks.json` for you (only if that file
does not already exist).

CI `verify-ledger` is the universal backstop that exists on every runtime; the
hooks below are per-runtime accelerators where a blocking surface exists.

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
