#!/usr/bin/env python3
"""GLaDOS Claude Code Stop-hook — refuse to end a session mid-run.

The compiled epilogue is an LLM promise kept at ~90% context; this hook is its
mechanical backstop. It refuses session end while a run is in flight
(`.glados/runs/current` or `.glados/runs/stack` exists) and its record is not
saved to the `glados/ledger` branch, where every run's record and step
artifacts live (never on a work branch). `stack` lists every run in flight,
and each listed record, with its step artifacts, must be on the ledger as it
is on disk; without a stack file, `current` alone is checked. An abandoned
run is released by deleting both markers.

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


def _repo_root(cwd: str) -> Path:
    if cwd:
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
    lines = (line.replace("\ufeff", "").strip() for line in text.splitlines())
    return [line for line in lines if line]


def in_flight_records(root: Path):
    """The records of every run in flight, outermost first; None when no run
    is in flight.

    `.glados/runs/stack` lists them: every run writes it, and a nested run
    (build-feature runs plan-feature inside itself) pushes onto it, so an
    outer run stays guarded while an inner one runs and after it ends.
    Without a stack file — an install whose preamble predates it —
    `.glados/runs/current` alone names the run. A `current` the stack does
    not list is still checked."""
    runs = root / ".glados" / "runs"
    stack, marker = runs / "stack", runs / "current"
    if not stack.exists() and not marker.exists():
        return None  # no run in flight — never block ordinary sessions
    stack_lines = _marker_lines(stack) if stack.exists() else []
    refs = list(stack_lines or [])
    if not marker.exists():
        # A stack with no current: still in flight unless the stack is empty.
        # An unreadable stack is in flight with no refs: every file is checked.
        return [] if stack_lines is None else (refs or None)
    for ref in (_marker_lines(marker) or [])[:1]:
        if ref not in refs:
            refs.append(ref)
    # An empty or unreadable `current` is still a run in flight: every file
    # under .glados/runs/ is checked.
    return refs


def _ledger_blobs(root: Path) -> dict:
    """path -> every blob the ledger holds for it, on the local glados/ledger
    branch and on each remote's copy this clone has fetched."""
    refs = ["refs/heads/" + LEDGER]
    refs += [r for r in _git(root, "for-each-ref", "--format=%(refname)",
                             "refs/remotes").split()
             if r.endswith("/" + LEDGER)]
    blobs: dict = {}
    for ref in refs:
        out = _git(root, "ls-tree", "-r", "-z", "--full-tree", ref, "--", RUNS)
        for rec in out.split("\0"):
            meta, _, path = rec.partition("\t")
            parts = meta.split()
            if len(parts) == 3 and parts[1] == "blob":
                blobs.setdefault(path, set()).add(parts[2])
    return blobs


def _files_to_check(root: Path, refs):
    """(files, missing): the repo-relative files each in-flight run owns (its
    record and its step artifacts, `<record-stem>.*`), and the records not
    on disk at all. With no readable ref, every file under .glados/runs/
    except the markers and the files this branch tracks unchanged (records
    committed before they moved to the ledger)."""
    runs = root / RUNS
    entries = sorted(runs.iterdir()) if runs.is_dir() else []

    def walk(entry):
        if entry.is_file():
            return [entry]
        return sorted(f for f in entry.rglob("*") if f.is_file())

    files, missing = [], []
    if not refs:
        tracked = set(_git(root, "ls-files", "-z", "--", RUNS).split("\0"))
        changed = set(_git(root, "diff", "--name-only", "-z", "HEAD", "--",
                           RUNS).split("\0"))
        for entry in entries:
            if entry.name in LOCAL_ONLY:
                continue
            for f in walk(entry):
                rel = f.relative_to(root).as_posix()
                if rel not in tracked or rel in changed:
                    files.append(rel)
        return files, missing
    for ref in refs:
        name = Path(ref).name
        stem = name[:-3] if name.endswith(".md") else name
        if not (runs / name).is_file():
            missing.append(f"{RUNS}/{name}")
        for entry in entries:
            if entry.name == name or entry.name.startswith(stem + "."):
                files += [f.relative_to(root).as_posix() for f in walk(entry)]
    return sorted(set(files)), missing


def in_flight_without_record(root: Path):
    """Return a reason string if a run is unfinished, else None (allow)."""
    refs = in_flight_records(root)
    if refs is None:
        return None

    # A run's trail is saved when every file it owns is on the ledger as it
    # is on disk, compared by the blob `git add` would make of it.
    files, missing = _files_to_check(root, refs)
    ledger = _ledger_blobs(root)
    shas = _git(root, "hash-object", "--stdin-paths",
                stdin="".join(f + "\n" for f in files)).split() if files else []
    hashes = dict(zip(files, shas))
    unsaved = [f for f in files if hashes.get(f) not in ledger.get(f, ())]
    unsaved += [m for m in missing if m not in ledger]
    if not unsaved:
        return None
    return ("A GLaDOS run is in flight (.glados/runs/current or "
            ".glados/runs/stack is set; the stack lists every run in flight, "
            "outermost first) but its run record is not saved to the "
            f"{LEDGER} branch: " + ", ".join(sorted(unsaved)) +
            f". Finish the epilogue — save it ({SAVE}) — or, if the run is "
            "abandoned, " + ABANDON)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError):
        event = {}
    root = _repo_root(event.get("cwd", ""))
    reason = in_flight_without_record(root)
    if reason:
        json.dump({"decision": "block", "reason": reason}, sys.stdout)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
