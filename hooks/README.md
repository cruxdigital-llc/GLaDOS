# GLaDOS run-record hooks

The compiled epilogue asks each run to finalize its run record and save it,
with its step artifacts, to the `glados/ledger` branch before it ends (records
never go on a work branch, so a merge request's diff is the change). That is a
promise an LLM keeps at 90% context — these host-agent hooks are the
mechanical backstop for the three runtimes that have one. All three are
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

The guards check every record the stack lists, with its step artifacts
(`<record-stem>.*`): any such file that is not on the ledger as it is on disk
(compared with the local `glados/ledger` branch and every fetched remote copy
of it) blocks the session end, and the message names it and the command that
saves it, `python .glados/glados.py ledger save`. A marker names a record by
its exact file name: one that differs in case, which still opens the file
on Windows and macOS, blocks and says so. With `current` set and no line in
`stack` (no stack file, from an install compiled before it existed or
deleted by hand, or an empty one), nothing says which runs enclose
`current`, so they check its files and every file under `.glados/runs/`
that is not saved, as the guards did before records moved to the ledger.
Either marker on its own means a run is in flight, so to release a run you
have abandoned, delete both `.glados/runs/current` and `.glados/runs/stack`.

The guards read the markers whatever encoding the agent's shell wrote them
in: a UTF-8 byte-order mark is ignored, UTF-16 (Windows PowerShell 5.1
redirection) is decoded. A marker that exists but cannot be read or
decoded hides which runs are in flight, so it blocks the session end even
when every file under `.glados/runs/` is saved, naming the marker and any
unsaved file there, until it is rewritten as text or both markers are
deleted. So does a marker that is a link to nothing, and so does
`.glados/runs/` or a directory in it that cannot be listed (a permission
error), until this user can read it again.

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
without a saved record.

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
