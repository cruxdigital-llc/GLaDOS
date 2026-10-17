#!/usr/bin/env python3
"""GLaDOS run-record guard for Gemini CLI (AfterAgent) and Antigravity agy (Stop).

Gemini CLI has no blocking session-end hook — SessionEnd is best-effort. The
blocking equivalent is AfterAgent: exit 2 makes the CLI retry the turn with the
stderr text as the reason, so an agent that tried to finish without committing
its run record is pushed to keep going. Antigravity's agy reuses this same
script from its Stop hook (best-effort there — agy cannot force continuation).

The guard is CONDITIONAL on the in-flight markers (`.glados/runs/current` and
`.glados/runs/stack`; either one means a run is in flight): it must stay
silent on ordinary turns, or interactive use becomes unbearable. Every record
the stack lists must be committed; without a stack file, `current` alone is
checked. An abandoned run is released by deleting both markers.

Wire it in `.gemini/settings.json`:

    {
      "hooks": {
        "AfterAgent": [
          { "matcher": "",
            "hooks": [
              { "type": "command",
                "command": "python .glados/hooks/gemini-afteragent-guard.py" }
            ] }
        ]
      }
    }

Behavior: reads the event JSON on stdin (both runtimes pass JSON). When a run is
in flight without a committed record, prints the reason to stderr and exits 2;
otherwise exits 0. Dependency-free; Python 3.10+.
"""

import json
import subprocess
import sys
from pathlib import Path

# The way out for an abandoned run. Either marker alone keeps the guard on
# (a stack without current is still in flight), so naming one would leave an
# agent that follows the hint blocked with the same message.
ABANDON = "delete both .glados/runs/current and .glados/runs/stack."


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
    is in flight. `.glados/runs/stack` lists them (every run writes it; a
    nested run pushes onto it); without it (an older preamble),
    `.glados/runs/current` alone names the run. A `current` the stack does
    not list is still checked."""
    runs = root / ".glados" / "runs"
    stack, marker = runs / "stack", runs / "current"
    if not stack.exists() and not marker.exists():
        return None  # conditional-on-marker: silent on ordinary turns
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
    refs = in_flight_records(root)
    if refs is None:
        return None
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
                ".glados/runs/stack is set) but its run record is "
                "uncommitted: " + ", ".join(sorted(dirty)) +
                ". Commit it (chore(glados): record <workflow> run) before "
                "finishing, or, if the run is abandoned, " + ABANDON)
    untracked = []
    for ref in refs:
        record = (root / ".glados" / "runs" / ref) if not Path(ref).is_absolute() else Path(ref)
        if not _git(root, "ls-files", "--error-unmatch", str(record)):
            untracked.append(ref)
    if untracked:
        names = ", ".join(f"'{r}'" for r in untracked)
        return (f"A GLaDOS run is in flight but its record {names} is not "
                f"committed (.glados/runs/stack lists every run in flight, "
                f"outermost first). Commit the run record before finishing, "
                f"or, if the run is abandoned, " + ABANDON)
    return None


def main() -> int:
    try:
        json.load(sys.stdin)
    except (ValueError, OSError):
        pass
    root = Path.cwd()
    reason = in_flight_without_record(root)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
