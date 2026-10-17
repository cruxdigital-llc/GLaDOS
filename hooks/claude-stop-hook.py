#!/usr/bin/env python3
"""GLaDOS Claude Code Stop-hook — refuse to end a session mid-run.

The compiled epilogue is an LLM promise kept at ~90% context; this hook is its
mechanical backstop. It refuses session end while a run is in flight
(`.glados/runs/current` or `.glados/runs/stack` exists) without a committed
run record. `stack` lists every run in flight, and each listed record must be
committed; without a stack file, `current` alone is checked. An abandoned
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


def _repo_root(cwd: str) -> Path:
    if cwd:
        return Path(cwd)
    return Path.cwd()


def _git(root: Path, *args) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), *args],
                             capture_output=True, text=True, timeout=20)
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _marker_lines(path: Path):
    """The non-empty lines of a marker file, or None when it cannot be read.

    Never raises: a guard that crashes fails OPEN. The agent writes these
    files with whatever its shell does, so a UTF-8 BOM (and, from Windows
    PowerShell 5.1 redirection, UTF-16) is normal, and a BOM left on a line
    would make a committed record look untracked forever."""
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
        # An unreadable stack is in flight with no refs: the dirty check runs.
        return [] if stack_lines is None else (refs or None)
    for ref in (_marker_lines(marker) or [])[:1]:
        if ref not in refs:
            refs.append(ref)
    # An empty or unreadable `current` is still a run in flight: the dirty
    # check applies.
    return refs


def in_flight_without_record(root: Path):
    """Return a reason string if a run is unfinished, else None (allow)."""
    refs = in_flight_records(root)
    if refs is None:
        return None

    # A record is committed when nothing under .glados/runs/ is dirty/untracked
    # (excluding the two marker files) and every in-flight record the markers
    # name is tracked by git.
    porcelain = _git(root, "status", "--porcelain", "--untracked-files=all", "--", ".glados/runs")
    dirty = []
    for line in porcelain.splitlines():
        path = line[3:].strip()
        if path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] in ("current", "stack"):
            continue
        if path.endswith(".md"):
            dirty.append(path)
    if dirty:
        return ("A GLaDOS run is in flight (.glados/runs/current or "
                ".glados/runs/stack is set) but its run record is not "
                "committed: " + ", ".join(sorted(dirty)) +
                ". Finish the epilogue — commit the record "
                "(chore(glados): record <workflow> run) — or, if the run is "
                "abandoned, " + ABANDON)

    untracked = []
    for ref in refs:
        record = (root / ".glados" / "runs" / ref) if not Path(ref).is_absolute() else Path(ref)
        if not _git(root, "ls-files", "--error-unmatch", str(record)):
            untracked.append(ref)
    if untracked:
        names = ", ".join(f"'{r}'" for r in untracked)
        return (f"A GLaDOS run is in flight but its record {names} is not "
                f"tracked/committed (.glados/runs/stack lists every run in "
                f"flight, outermost first). Commit the run record before "
                f"ending, or, if the run is abandoned, " + ABANDON)
    return None


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
