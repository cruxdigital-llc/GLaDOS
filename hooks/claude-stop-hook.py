#!/usr/bin/env python3
"""GLaDOS Claude Code Stop-hook — refuse to end a session mid-run.

The compiled epilogue is an LLM promise kept at ~90% context; this hook is its
mechanical backstop. It refuses session end while a run is in flight
(`.glados/runs/current` exists) without a committed run record.

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


def in_flight_without_record(root: Path):
    """Return a reason string if the run is unfinished, else None (allow)."""
    marker = root / ".glados" / "runs" / "current"
    if not marker.exists():
        return None  # no run in flight — never block ordinary sessions

    # A record is committed when nothing under .glados/runs/ is dirty/untracked
    # (excluding the 'current' marker itself) and the marker's referenced record
    # is tracked by git.
    porcelain = _git(root, "status", "--porcelain", "--", ".glados/runs")
    dirty = []
    for line in porcelain.splitlines():
        path = line[3:].strip()
        if path.endswith("/current") or path.endswith("\\current"):
            continue
        if path.endswith(".md"):
            dirty.append(path)
    if dirty:
        return ("A GLaDOS run is in flight (.glados/runs/current is set) but its "
                "run record is not committed: " + ", ".join(sorted(dirty)) +
                ". Finish the epilogue — commit the record "
                "(chore(glados): record <workflow> run) — or clear the marker.")

    ref = ""
    try:
        ref = marker.read_text(encoding="utf-8").strip()
    except OSError:
        ref = ""
    if ref:
        record = (root / ".glados" / "runs" / ref) if not Path(ref).is_absolute() else Path(ref)
        tracked = _git(root, "ls-files", "--error-unmatch", str(record))
        if not tracked:
            return (f"A GLaDOS run is in flight but its record '{ref}' is not "
                    f"tracked/committed. Commit the run record before ending.")
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
