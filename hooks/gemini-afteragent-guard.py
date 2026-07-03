#!/usr/bin/env python3
"""GLaDOS run-record guard for Gemini CLI (AfterAgent) and Antigravity agy (Stop).

Gemini CLI has no blocking session-end hook — SessionEnd is best-effort. The
blocking equivalent is AfterAgent: exit 2 makes the CLI retry the turn with the
stderr text as the reason, so an agent that tried to finish without committing
its run record is pushed to keep going. Antigravity's agy reuses this same
script from its Stop hook (best-effort there — agy cannot force continuation).

The guard is CONDITIONAL on the in-flight marker (`.glados/runs/current`): it
must stay silent on ordinary turns, or interactive use becomes unbearable.

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


def _git(root: Path, *args) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), *args],
                             capture_output=True, text=True, timeout=20)
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def in_flight_without_record(root: Path):
    marker = root / ".glados" / "runs" / "current"
    if not marker.exists():
        return None  # conditional-on-marker: silent on ordinary turns
    porcelain = _git(root, "status", "--porcelain", "--", ".glados/runs")
    dirty = []
    for line in porcelain.splitlines():
        path = line[3:].strip()
        if path.endswith("/current") or path.endswith("\\current"):
            continue
        if path.endswith(".md"):
            dirty.append(path)
    if dirty:
        return ("A GLaDOS run is in flight but its run record is uncommitted: "
                + ", ".join(sorted(dirty)) +
                ". Commit it (chore(glados): record <workflow> run) before finishing.")
    ref = ""
    try:
        ref = marker.read_text(encoding="utf-8").strip()
    except OSError:
        ref = ""
    if ref:
        record = (root / ".glados" / "runs" / ref) if not Path(ref).is_absolute() else Path(ref)
        if not _git(root, "ls-files", "--error-unmatch", str(record)):
            return (f"A GLaDOS run is in flight but its record '{ref}' is not "
                    f"committed. Commit the run record before finishing.")
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
