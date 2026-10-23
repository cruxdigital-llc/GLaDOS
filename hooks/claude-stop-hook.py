#!/usr/bin/env python3
"""GLaDOS Claude Code Stop-hook — refuse to end a session mid-run.

The compiled epilogue is an LLM promise kept at ~90% context; this hook is its
mechanical backstop. It refuses session end while a run is in flight
(`.glados/runs/current` or `.glados/runs/stack` exists) and its record is not
saved to the `glados/ledger` branch, where every run's record and step
artifacts live (never on a work branch). `stack` lists every run in flight,
and each listed record, with its step artifacts, must be on the ledger as it
is on disk, under exactly the name the marker gives, as a regular file (a
directory or a link to one or to nothing is no record). With `current` set
and no stack line (no stack file, or an empty one), nothing says which runs
enclose it, so any file under .glados/runs/ not saved blocks too. A marker
or a directory there that cannot be read blocks, since it hides which runs
are in flight. An abandoned run is released by deleting both markers.

Wire it in `.claude/settings.json`:

    {
      "hooks": {
        "Stop": [
          { "hooks": [
            { "type": "command",
              "command": "python .glados/hooks/claude-stop-hook.py" }
          ] }
        ]
      }
    }

Protocol (Claude Code Stop hook): reads a JSON event on stdin; to block the
stop, prints {"decision": "block", "reason": "..."} and exits 0. The guard is
conditional on the in-flight marker, so ordinary sessions end freely.

Dependency-free; Python 3.10+.
"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path


# The way out for an abandoned run. Either marker alone keeps the guard on
# (a stack without current is still in flight), so naming one would leave an
# agent that follows the hint blocked with the same message.
ABANDON = "delete both .glados/runs/current and .glados/runs/stack."
RUNS = ".glados/runs"
LEDGER = "glados/ledger"
# Files directly under .glados/runs/ that never leave the working tree.
LOCAL_ONLY = ("current", "stack", ".gitignore")
SAVE = "python .glados/glados.py ledger save"
# How the block message ends, before ABANDON.
FINISH = (f"Finish the epilogue — save it ({SAVE}) — or, if the run is "
          "abandoned, ")


def _repo_root(cwd: str) -> Path:
    # A cwd that is no directory (one decoded wrongly, or since removed)
    # would read both markers as absent and let the session end: fall back
    # to the process's working directory, where Claude Code runs the hook.
    if cwd and os.path.isdir(cwd):
        return Path(cwd)
    return Path.cwd()


def _git(root: Path, *args, stdin: str = "") -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), *args], input=stdin,
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=20)
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _present(path: Path) -> bool:
    """Whether a marker exists, asked of the file itself (lstat), so a marker
    that is a link to nothing is there, and then unreadable. One whose
    presence cannot be checked (a permission error on .glados/runs/) counts
    as there too. Path.exists() will not do: from Python 3.13 it reads any
    error as absent, and a guard that crashes fails OPEN; either way the
    session would end."""
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return False
    except (OSError, ValueError):
        return True
    return True


def _marker_lines(path: Path):
    """The non-empty lines of a marker file, or None when it cannot be read.

    Never raises: a guard that crashes fails OPEN. The agent writes these
    files with whatever its shell does, so a UTF-8 BOM (and, from Windows
    PowerShell 5.1 redirection, UTF-16) is normal, and a BOM left on a line
    would make a saved record look unsaved forever."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    codec = "utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    try:
        text = data.decode(codec)
    except ValueError:
        return None
    if "\0" in text:
        # Half UTF-8, half UTF-16 (PowerShell 5.1's Set-Content, then
        # `>>`) decodes to names full of NULs: no record has one.
        return None
    lines = (line.replace("\ufeff", "").strip() for line in text.splitlines())
    return [line for line in lines if line]


def in_flight_records(root: Path):
    """(refs, sweep): the records of every run in flight, outermost first,
    and whether every file under .glados/runs/ that is not saved counts as
    well; None when no run is in flight.

    `.glados/runs/stack` lists them: every run writes it, its last line
    equal to `current`, and a nested run (build-feature runs plan-feature
    inside itself) pushes onto it, so an outer run stays guarded while an
    inner one runs and after it ends. A `current` the stack does not list
    is still checked. With `current` set and no stack line (no stack file,
    from a preamble that predates it or deleted by hand, or an empty one),
    nothing says which runs enclose it, so every file not saved counts,
    as 918f16a's dirty check did; so it does behind an unreadable marker."""
    runs = root / RUNS
    stack, marker = runs / "stack", runs / "current"
    has_stack, has_current = _present(stack), _present(marker)
    if not has_stack and not has_current:
        return None  # no run in flight — never block ordinary sessions
    stack_lines = _marker_lines(stack) if has_stack else []
    refs = list(stack_lines or [])
    if not has_current:
        # A stack with no current: still in flight unless the stack is empty.
        # An unreadable stack is in flight (unreadable_markers blocks on it).
        if stack_lines is None:
            return [], True
        return (refs, False) if refs else None
    for ref in (_marker_lines(marker) or [])[:1]:
        if ref not in refs:
            refs.append(ref)
    # An empty `current` is still a run in flight; an unreadable one blocks.
    return refs, not stack_lines


def unreadable_markers(root: Path) -> list:
    """The markers that exist but cannot be read or decoded. Such a marker
    hides which runs are in flight, so no run on it can be shown saved: it
    blocks, where reading it as no record at all let the session end with
    an outer run's record unsaved, or a run's record not yet written."""
    runs = root / RUNS
    return [f"{RUNS}/{name}" for name in ("stack", "current")
            if _present(runs / name) and _marker_lines(runs / name) is None]


def _prefix(root: Path) -> str:
    """``root``'s directory inside its repository, with a trailing '/' ('' at
    the top level). A project in a subdirectory (a monorepo package) keeps
    its records in its own .glados/runs/, and `ledger save` puts them on the
    ledger under this prefix; git reads --full-tree paths and
    hash-object --stdin-paths from the top level, whatever the cwd."""
    return _git(root, "rev-parse", "--show-prefix").rstrip("\r\n")


def _ledger_blobs(root: Path, prefix: str) -> dict:
    """path (from ``root``) -> every blob the ledger holds for it, on the
    local glados/ledger branch and on each remote's copy this clone has
    fetched."""
    refs = ["refs/heads/" + LEDGER]
    refs += [r for r in _git(root, "for-each-ref", "--format=%(refname)",
                             "refs/remotes").split()
             if r.endswith("/" + LEDGER)]
    blobs: dict = {}
    for ref in refs:
        out = _git(root, "ls-tree", "-r", "-z", "--full-tree", ref, "--",
                   prefix + RUNS)
        for rec in out.split("\0"):
            meta, _, path = rec.partition("\t")
            parts = meta.split()
            if len(parts) == 3 and parts[1] == "blob" and \
                    path.startswith(prefix):
                blobs.setdefault(path[len(prefix):], set()).add(parts[2])
    return blobs


def _listing(path: Path, unlistable: list) -> list:
    """A directory's entries, sorted. One that cannot be listed goes in
    ``unlistable``: nothing in it can be shown saved, so it blocks, where
    the error used to crash the guard (a non-blocking error to both
    hosts)."""
    try:
        with os.scandir(path) as it:
            return sorted(Path(entry.path) for entry in it)
    except (FileNotFoundError, NotADirectoryError):
        return []
    except OSError:
        unlistable.append(path)
        return []


# A junction's reparse tag (winnt.h). CPython's stat module defines
# IO_REPARSE_TAG_MOUNT_POINT on Windows alone, and only a Windows stat result
# has st_reparse_tag, so both are read with a default: read bare, the
# constant raised AttributeError on Linux and macOS at the first entry
# walked, and the guard crashed open.
JUNCTION = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)


def _is_link(st) -> bool:
    """A symbolic link, or a Windows junction, which lstat reports as a
    directory: walked into, a junction back to .glados/runs/ looped until
    the path grew too long or, with long paths on, until Python's recursion
    limit crashed the guard open."""
    return stat.S_ISLNK(st.st_mode) or \
        getattr(st, "st_reparse_tag", 0) == JUNCTION


def _walk(entry: Path, unlistable: list) -> list:
    """Every file at or under ``entry``, walked by hand: rglob skips a
    directory it cannot read without a word. A link is never followed into
    a directory. A link to a file counts as one; os.path.isfile answers
    False for one whose target cannot be reached, where Path.is_file()
    raised on Python 3.10 to 3.12 (a link into a directory this user may
    not search; on Windows a junction to a directory it was denied) and
    the guard crashed open."""
    try:
        st = os.lstat(entry)
    except FileNotFoundError:
        return []
    except OSError:
        unlistable.append(entry)
        return []
    if _is_link(st):
        return [entry] if os.path.isfile(entry) else []
    if stat.S_ISDIR(st.st_mode):
        return [f for child in _listing(entry, unlistable)
                for f in _walk(child, unlistable)]
    return [entry] if stat.S_ISREG(st.st_mode) else []


def _not_a_record(entry: Path):
    """What the entry under a record's name is instead of a record, or None
    when it is one: a regular file, once links are followed. A directory, or
    a link to one or to nothing, holds no record to check, and counting it
    as the record let a run end with none."""
    try:
        mode = os.stat(entry).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return "a link to nothing"
    except (OSError, ValueError):
        return "an entry that cannot be read"
    if stat.S_ISREG(mode):
        return None
    if not stat.S_ISDIR(mode):
        return "not a regular file"
    try:
        linked = _is_link(os.lstat(entry))
    except OSError:
        linked = False
    return "a link to a directory" if linked else "a directory"


def _files_to_check(root: Path, refs, sweep: bool):
    """(files, missing, not_records, unlistable): the repo-relative files
    each in-flight run owns (its record and its step artifacts,
    `<record-stem>.*`), and with ``sweep`` every file under .glados/runs/
    except the markers and the files this branch tracks unchanged (records
    committed before they moved to the ledger); the records a marker names
    that are not on disk under exactly that name; (path, what it is) for
    each record name whose entry is no record (_not_a_record); and the
    directories that could not be listed."""
    runs = root / RUNS
    unlistable: list = []
    entries = _listing(runs, unlistable)
    files, missing = [], []
    if sweep:
        tracked = set(_git(root, "ls-files", "-z", "--", RUNS).split("\0"))
        # --relative: from ``root``, as ls-files and `rel` are, not from
        # the top level, for a project in a subdirectory.
        changed = set(_git(root, "diff", "--name-only", "--relative", "-z",
                           "HEAD", "--", RUNS).split("\0"))
        for entry in entries:
            if entry.name in LOCAL_ONLY:
                continue
            for f in _walk(entry, unlistable):
                rel = f.relative_to(root).as_posix()
                if rel not in tracked or rel in changed:
                    files.append(rel)
    names = {entry.name: entry for entry in entries}
    not_records: list = []
    for ref in refs:
        name = Path(ref).name
        stem = name[:-3] if name.endswith(".md") else name
        # Exactly that name. On Windows and macOS `Outer.md` (on Windows,
        # `outer.md.` too) opens outer.md, but no entry below matches it,
        # so the run would be checked as having no files at all.
        if name not in names:
            missing.append(f"{RUNS}/{name}")
        elif (what := _not_a_record(names[name])) is not None:
            not_records.append((f"{RUNS}/{name}", what))
        for entry in entries:
            if entry.name == name or entry.name.startswith(stem + "."):
                files += [f.relative_to(root).as_posix()
                          for f in _walk(entry, unlistable)]
    shown = sorted({p.relative_to(root).as_posix() for p in unlistable})
    return (sorted(set(files)), missing, list(dict.fromkeys(not_records)),
            shown)


def in_flight_without_record(root: Path):
    """Return a reason string if a run is unfinished, else None (allow)."""
    found = in_flight_records(root)
    if found is None:
        return None
    refs, sweep = found

    # A run's trail is saved when every file it owns is on the ledger as it
    # is on disk, compared by the blob `git add` would make of it. Behind an
    # unreadable marker every file under .glados/runs/ is listed.
    unreadable = unreadable_markers(root)
    files, missing, not_records, unlistable = _files_to_check(
        root, refs, sweep or bool(unreadable))
    prefix = _prefix(root)
    ledger = _ledger_blobs(root, prefix)
    shas = _git(root, "hash-object", "--stdin-paths",
                stdin="".join(prefix + f + "\n" for f in files)
                ).split() if files else []
    hashes = dict(zip(files, shas))
    absent = list(dict.fromkeys(m for m in missing if m not in ledger))
    # A record name whose entry is no record is unsaved, whatever the
    # ledger holds under it: the run has no record on disk to save.
    unsaved = sorted(set(f for f in files
                         if hashes.get(f) not in ledger.get(f, ()))
                     | set(absent) | {path for path, _ in not_records})
    if unreadable or unlistable:
        problems = ([" and ".join(unreadable) + " cannot be read or "
                     "decoded as UTF-8 or UTF-16 text"] if unreadable else [])
        problems += ([" and ".join(unlistable) + " cannot be listed"]
                     if unlistable else [])
        fixes = ([f"rewrite {'them' if len(unreadable) > 1 else 'it'} "
                  "as text (stack: each run's record filename, "
                  "one per line, outermost first; current: the innermost "
                  "one's)"] if unreadable else [])
        fixes += ([f"give this user read access to {RUNS}/ and all in it"]
                  if unlistable else [])
        fixes.append(f"save every record ({SAVE})")
        fix = (", ".join(fixes[:-1]) + (", and " if len(fixes) > 2 else
                                        " and ") + fixes[-1])
        listed = (f"; not saved to the {LEDGER} branch: "
                  + ", ".join(unsaved)) if unsaved else ""
        return ("A GLaDOS run is in flight, but " + "; ".join(problems)
                + ", so which runs are in flight, and whether each one's "
                "record is saved, is unknown" + listed + ". "
                + fix[0].upper() + fix[1:] + "; or, if the run is "
                "abandoned, " + ABANDON)
    if not unsaved:
        return None
    reason = ("A GLaDOS run is in flight (.glados/runs/current or "
              ".glados/runs/stack is set; the stack lists every run in "
              "flight, outermost first) but its run record is not saved to "
              f"the {LEDGER} branch: " + ", ".join(unsaved) + ".")
    if absent:
        reason += (" A marker names " + ", ".join(absent) + ", but no file "
                   "has exactly the name: write that record, or correct "
                   "the marker line to the file's name, case included.")
    for path, what in not_records:
        reason += (f" {path} is {what}, not a record file: put the record "
                   "file there under that name, or correct the marker line "
                   "to the record's name.")
    return reason + " " + FINISH + ABANDON


def main() -> int:
    # Claude Code writes the event in UTF-8. Read as text, stdin decodes in
    # the locale's codec, the ANSI code page on Windows until Python 3.15:
    # a cwd with an ë in it became a path that does not exist, and the
    # guard allowed. json.loads finds UTF-8 (BOM or not), -16 or -32 in
    # the bytes themselves.
    try:
        event = json.loads(sys.stdin.buffer.read())
    except (ValueError, OSError, AttributeError):
        event = {}
    # Valid JSON that is not an object (null, a list), or a cwd that is
    # not text, crashed here: exit 1 is a non-blocking error, so the
    # session ended. Fall back to the process cwd, as for no cwd.
    cwd = event.get("cwd") if isinstance(event, dict) else None
    root = _repo_root(cwd if isinstance(cwd, str) else "")
    reason = in_flight_without_record(root)
    if reason:
        json.dump({"decision": "block", "reason": reason}, sys.stdout)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
