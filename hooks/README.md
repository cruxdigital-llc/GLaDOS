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
  inside itself, run-pipeline runs its built-in stages the same way, and
  run-epic runs build-feature or run-pipeline for each ticket. A nested run
  pushes its record onto the stack and its epilogue pops it, putting the
  enclosing run back into `current`.

The guards check every record the stack lists, with its step artifacts
(`<record-stem>.*`): any such file that is not on the ledger as it is on
disk (compared with the local `glados/ledger` branch and every fetched
remote copy of it) blocks the session end, and the message names it and the
command that saves it, `python .glados/glados.py ledger save` (in a
plugin-only repo, which has no `.glados/glados.py`, run the plugin's own
`bin/glados.py ledger save`). A marker names a record by its exact file
name: one that differs in case, which still opens the file on Windows and
macOS, blocks and says so. A record is a regular file: a directory under its
name, or a link (on Windows, a junction too) to a directory or to nothing,
blocks and says what it is, whatever the ledger holds under that name. A
link to a file passes that check, but `ledger save` saves no link under
`.glados/runs/` and walks into none, so a record that is a link blocks as
not saved until the file itself replaces it (unless the ledger already
holds, under the record's name, the content it links to). A step
artifact linked to a file blocks the same way; one linked to a directory,
or to what this user cannot reach, counts as no file, as `ledger save`
walks into no link. With `current` set
and no line in `stack` (no stack file, from an install compiled before it
existed or deleted by hand, or an empty one), nothing says which runs
enclose `current`, so they check its files and every file under
`.glados/runs/` that is not saved, as the guards did before records moved to
the ledger.
`current` on its own, even empty, means a run is in flight, and so does a
`stack` with a line in it, so to release a run you have abandoned, delete
both `.glados/runs/current` and `.glados/runs/stack`.

The guards read `.glados/runs/` in the directory the agent runs in. For a
project in a subdirectory of its repository (a monorepo package), run the
agent there: the guards then look for its records on the ledger under that
subdirectory's path, which is where `ledger save` puts them.

The guards read the markers whatever encoding the agent's shell wrote them
in: a UTF-8 byte-order mark is ignored, UTF-16 (Windows PowerShell 5.1
redirection) is decoded. A marker that exists but cannot be read or
decoded (a file half UTF-8, half UTF-16, from `Set-Content` then `>>`,
counts too) hides which runs are in flight, so it blocks the session end
even when every file under `.glados/runs/` is saved, naming the marker and
any unsaved file there, until it is rewritten as text or both markers are
deleted. So does a marker that is not a regular file (a link to nothing, a
FIFO, a device such as `/dev/null`), and so does a
directory that cannot be listed (a permission error), until this user can
read it again: `.glados/runs/` itself, or a directory in it that could hold
a file the guards check (a listed run's `<record-stem>.*`, or any, with
`current` set and no line in `stack`). A file there that the guards cannot
look at, or that git cannot read (one another program holds open, say),
blocks the same way, named as one that "cannot be listed or read". On
Windows the guards and `ledger save` reach a file whose full path is 260
characters or more (a step artifact deep under `<stem>.evidence/`) even
with long paths off, Windows' default: they use its `\\?\` form and run git
with `core.longpaths`.

The guards run on Linux, macOS and Windows alike. The snippets below call
`python`, as does the `.agents/hooks.json` the Antigravity adapter writes;
where only `python3` is on the PATH (macOS, or Debian and Ubuntu without
`python-is-python3`), write `python3` there. To Claude Code and Gemini CLI
a hook command that cannot start is a non-blocking error, so the guard
would not run and the session would end.

`glados.py install` vendors the guard scripts into `.glados/hooks/` in your
repo, so the wiring snippets below reference stable, repo-local paths. The
Antigravity adapter also writes `.agents/hooks.json` for you (only if that file
does not already exist).

CI `verify-ledger` is the universal backstop that exists on every runtime — the
installer vendors the check templates into `.glados/ci/` and prints the enable
stanza; the project adds the include (GitLab) or copies the workflow file into
`.github/workflows/` (GitHub). That is for a project at the repository root
only: CI enforcement is not supported for a project in a subdirectory of its
repository, where the hooks are the only mechanical check. The hooks below
are per-runtime accelerators where a blocking surface exists.

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

Blocks the stop with a reason (`{"decision":"block"}`) when any run in
flight (the current one, or one enclosing it on the stack) lacks a saved
record, or when a marker or `.glados/runs/` exists but cannot be read, as
above. An event it cannot parse, one that is not a JSON object, or none at
all (the hook started with no stdin) still gets the check, in the process's
working directory. The Gemini/agy guard below does the same.

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

## pi — extension, not a settings hook

pi has no settings-file hooks. The run-record guard (the pi equivalent of
`claude-stop-hook.py`) is a pi extension; Crux ships it in its `cruxcode` pi
package. It does not yet read `.glados/runs/stack` as the scripts here do.
Without it, rely on CI `verify-ledger`.
