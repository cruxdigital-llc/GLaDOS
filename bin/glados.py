#!/usr/bin/env python3
"""GLaDOS v2 toolchain — a dependency-free compiler, type-checker and installer.

One file, standard library only. Floor: Python 3.10 (uses ``pathlib`` newline=
kwarg on ``write_text``, ``str.removeprefix``; no ``match`` requirement, no
third-party deps, and — deliberately — no PyYAML: a minimal YAML-subset parser
lives in the PARSER section below).

GLaDOS v2 is a compiler for team attention. Each workflow *core* is a short
markdown file describing only its distinctive work; everything cross-cutting —
the mandatory preamble/epilogue, the outcome vocabulary, module presence — is
inlined at install time from one project manifest (``glados.yaml``). This tool
is the assembler + type-checker + per-runtime emitter that does the inlining.

Subcommands (see ``--help``):
    install         compile the sources against a manifest and emit one adapter
    check           CI mode: recompute the compile and diff it against install
    doctor          staleness + wiring report (never fails)
    verify-ledger   scan git history for silent-loss candidates (report-only)
    compile-plugin  shorthand: install --mode claude-plugin --target <repo>

Sections, in order:
    1.  CONSTANTS
    2.  PARSER            — YAML subset with line-numbered errors
    3.  SOURCE MODEL      — read cores/modules/kernel/registry/presets/aliases
    4.  MANIFEST          — load + phase-preset merge with provenance
    5.  COMPILE           — assemble one compiled core from the sources
    6.  TYPE CHECKS       — the seven fatal install-time checks
    7.  ASSEMBLY REPORT
    8.  ADAPTERS          — six emitters over the SAME compiled artifacts
    9.  VENDOR + SCAFFOLD
    10. COMMANDS          — install / check / doctor / verify-ledger
    11. CLI
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


# =============================================================================
# 1. CONSTANTS
# =============================================================================

VERSION = "2.0.0"

# The fifteen v2 cores, in canonical (pipeline-ish) order. The compiler touches
# ONLY these — other .md files under src/workflows are v1 leftovers deleted at
# integration and must be ignored.
CORES = [
    "intent",
    "adopt-codebase",
    "plan-feature",
    "spec-feature",
    "implement-feature",
    "verify-feature",
    "build-feature",
    "review-mr",
    "address-review",
    "run-epic",
    "fix-bug",
    "review-codebase",
    "retrospect",
    "steward",
    "brunch",
]

# The three v2 modules. Canonical inline order (stable → byte-stable output).
MODULES = ["mr-review-panel", "evaluator-spawn", "standards-gate"]

# Phase presets name "review-panel" (the params namespace); the module file is
# "mr-review-panel". This explicit alias — NOT a silent default — keeps the
# production/baseline presets compilable. Documented so nobody has to guess.
MODULE_ALIASES = {"review-panel": "mr-review-panel"}

# The four required phase values, named in the missing-phase fatal error.
PHASES = ["nascent", "evolving", "production", "sunset"]

# Two registry-documented reader fallbacks: a read of the state key is satisfied
# when the named manifest sub-key exists, even with no enabled writer.
READER_FALLBACKS = {
    "run.active-personas": "params.review-panel.personas",
    "epic.integration-branch": "branching.default-target",
}

# Keys the compiled preamble/epilogue always write — so reading them never fails
# the readers-without-writers check.
PREAMBLE_OWNED_WRITES = ["work.base-sha", "run.record"]

# Sink kinds that make an outcome team-visible. ``ledger`` is NOT here: it is a
# valid sink only for progress/decision/observation.
TEAM_VISIBLE_SINKS = {"mr-comment", "issue", "issue-comment", "label"}
LEDGER_OK_TYPES = {"progress", "decision", "observation"}
# The full closed sink vocabulary; a channels: binding outside it is a typo.
KNOWN_SINKS = TEAM_VISIBLE_SINKS | {"ledger"}

# Merge-authority and decision strictness, STRICTEST first. "laxer = leftward"
# in the spec's own ``agent<record<escalate<forbidden`` ordering, so these lists
# read strict→lax and a lower index == stricter.
MERGE_AUTHORITY_ORDER = ["human", "agent-integration-only", "agent"]
DECISION_ORDER = ["forbidden", "escalate", "record", "agent"]

# AI Studio is a planning/review/spec surface: only advisory-safe cores get a
# paste bundle. fix-bug ships as its plan half, "fix-bug-advisory".
AISTUDIO_CORES = [
    "intent",
    "plan-feature",
    "spec-feature",
    "review-mr",
    "review-codebase",
    "retrospect",
]

INSTALL_MODES = ["claude", "claude-plugin", "direct", "gemini", "antigravity", "aistudio"]

INCLUDE_RE = re.compile(r"<!--\s*glados:include\s+(\S+?)\s*-->")

# Forbidden substrings in COMPILED core output (lint check 5).
FORBIDDEN_TOKENS = ["{{", "<!-- glados:include", "Invoke module", "OPTIMIZE_FOR"]


class Fatal(Exception):
    """A fatal, user-facing error. Message must name the file/key AND the fix."""


# =============================================================================
# 2. PARSER — a YAML subset with line-numbered errors
# =============================================================================
#
# Supported subset (enough for the restricted GLaDOS schema and no more):
#   * block maps and block lists, 2-space indentation
#   * inline flow lists: [a, b], []
#   * scalars: plain, single/double quoted, integers, true/false/null
#   * block scalars: > >- | |- (folded / literal, clip / strip chomping)
#   * comments ('# ...'), respecting quotes; '#' only starts a comment at line
#     start or after whitespace
# Anything outside the subset raises YamlError('<file>:<line>: <reason>').


class YamlError(Fatal):
    pass


def _strip_inline_comment(line: str) -> str:
    """Drop a trailing '# comment', honoring quotes and the space-before rule."""
    in_s = in_d = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d:
            if i == 0 or line[i - 1] in " \t":
                return line[:i]
    return line


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _unescape_double(s: str) -> str:
    """Minimal double-quoted-scalar escapes: \\\\ \\\" \\n \\t \\r; anything
    else keeps its backslash (lenient — the subset never emits more)."""
    out: list[str] = []
    i = 0
    escapes = {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r"}
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] in escapes:
            out.append(escapes[s[i + 1]])
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _parse_scalar(tok: str, filename: str, lineno: int):
    tok = tok.strip()
    if tok == "" or tok == "~" or tok == "null":
        return None
    if tok == "true":
        return True
    if tok == "false":
        return False
    if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
        return _unescape_double(tok[1:-1])
    if len(tok) >= 2 and tok[0] == "'" and tok[-1] == "'":
        return tok[1:-1].replace("''", "'")
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    return tok


def _split_flow_items(inner: str, filename: str, lineno: int) -> list[str]:
    """Split a flow-list body on commas, honoring quotes; reject nesting."""
    items: list[str] = []
    buf = ""
    in_s = in_d = False
    for ch in inner:
        if ch == "'" and not in_d:
            in_s = not in_s
            buf += ch
        elif ch == '"' and not in_s:
            in_d = not in_d
            buf += ch
        elif ch == "," and not in_s and not in_d:
            items.append(buf)
            buf = ""
        elif ch in "[{" and not in_s and not in_d:
            raise YamlError(f"{filename}:{lineno}: nested flow collections are "
                            f"not supported inside [...] — use a block list "
                            f"(one '- item' per line)")
        else:
            buf += ch
    if in_s or in_d:
        raise YamlError(f"{filename}:{lineno}: unterminated quote inside [...]")
    items.append(buf)
    return items


def _parse_flow_list(tok: str, filename: str, lineno: int):
    tok = tok.strip()
    if not tok.endswith("]"):
        raise YamlError(f"{filename}:{lineno}: unterminated inline list '{tok}' "
                        f"(the parser supports single-line flow lists only)")
    inner = tok[1:-1].strip()
    if inner == "":
        return []
    return [_parse_scalar(p, filename, lineno)
            for p in _split_flow_items(inner, filename, lineno)
            if p.strip() != ""]


def parse_yaml(text: str, filename: str = "<yaml>"):
    """Parse the restricted YAML subset into Python dict/list/scalar values."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    n = len(lines)

    # YAML forbids tabs in indentation; silently misreading them re-parents
    # keys (a tab-indented sub-map becomes top-level keys). Fail loudly.
    for idx, line in enumerate(lines):
        if line.strip() == "":
            continue
        lead = line[: len(line) - len(line.lstrip(" \t"))]
        if "\t" in lead:
            raise YamlError(f"{filename}:{idx + 1}: tab character in indentation "
                            f"— YAML forbids tabs; indent with 2 spaces")

    def skippable(i: int) -> bool:
        s = lines[i].strip()
        return s == "" or s.startswith("#")

    def next_meaningful(i: int) -> int:
        while i < n and skippable(i):
            i += 1
        return i

    def parse_block_scalar(i: int, parent_indent: int, style: str):
        collected: list[str] = []
        base = None
        while i < n:
            if lines[i].strip() == "":
                collected.append("")
                i += 1
                continue
            ci = _indent_of(lines[i])
            if ci <= parent_indent:
                break
            if base is None:
                base = ci
            collected.append(lines[i][base:])
            i += 1
        while collected and collected[-1] == "":
            collected.pop()
        if style[0] == ">":
            # Folded: our schema has no internal blank lines, so join on spaces.
            value = " ".join(s.strip() for s in collected)
        else:
            value = "\n".join(collected)
        if style.endswith("-"):
            value = value.rstrip("\n")
        return value, i

    def parse_map(i: int):
        i = next_meaningful(i)
        base = _indent_of(lines[i])
        result: dict = {}
        while i < n:
            if skippable(i):
                i += 1
                continue
            ci = _indent_of(lines[i])
            if ci < base:
                break
            if ci > base:
                raise YamlError(f"{filename}:{i + 1}: unexpected indent "
                                f"(expected {base} spaces, got {ci})")
            content = _strip_inline_comment(lines[i]).strip()
            if content.startswith("- "):
                raise YamlError(f"{filename}:{i + 1}: list item under a mapping")
            if ":" not in content:
                raise YamlError(f"{filename}:{i + 1}: expected 'key: value', "
                                f"got '{content}'")
            key, _, val = content.partition(":")
            key = key.strip()
            val = val.strip()
            if key in result:
                raise YamlError(f"{filename}:{i + 1}: duplicate key '{key}' — "
                                f"the earlier value would be silently "
                                f"overwritten; remove one of the definitions")
            i += 1
            if val == "":
                j = next_meaningful(i)
                if j < n and _indent_of(lines[j]) > base:
                    child = _strip_inline_comment(lines[j]).strip()
                    if child.startswith("- ") or child == "-":
                        result[key], i = parse_list(j)
                    else:
                        result[key], i = parse_map(j)
                else:
                    result[key] = None
            elif val in (">", ">-", "|", "|-", ">+", "|+"):
                result[key], i = parse_block_scalar(i, base, val)
            elif val.startswith("["):
                result[key] = _parse_flow_list(val, filename, i)
            elif val.startswith("{"):
                raise YamlError(f"{filename}:{i}: flow mapping '{{...}}' is not "
                                f"supported — use a block map (nested 2-space-"
                                f"indented 'key: value' lines)")
            else:
                result[key] = _parse_scalar(val, filename, i)
        return result, i

    def parse_list(i: int):
        i = next_meaningful(i)
        base = _indent_of(lines[i])
        result: list = []
        while i < n:
            if skippable(i):
                i += 1
                continue
            ci = _indent_of(lines[i])
            if ci < base:
                break
            if ci > base:
                raise YamlError(f"{filename}:{i + 1}: unexpected indent in list")
            content = _strip_inline_comment(lines[i]).strip()
            if not (content.startswith("- ") or content == "-"):
                break
            item = content[1:].strip()
            i += 1
            if item == "":
                j = next_meaningful(i)
                if j < n and _indent_of(lines[j]) > base:
                    child = _strip_inline_comment(lines[j]).strip()
                    if child.startswith("- ") or child == "-":
                        sub, i = parse_list(j)
                    else:
                        sub, i = parse_map(j)
                    result.append(sub)
                else:
                    result.append(None)
            elif item.startswith("["):
                result.append(_parse_flow_list(item, filename, i))
            elif item.startswith("{"):
                raise YamlError(f"{filename}:{i}: flow mapping '{{...}}' is not "
                                f"supported — use a block map (nested 2-space-"
                                f"indented 'key: value' lines)")
            else:
                result.append(_parse_scalar(item, filename, i))
        return result, i

    start = next_meaningful(0)
    if start >= n:
        return {}
    first = _strip_inline_comment(lines[start]).strip()
    value, _ = (parse_list(start) if first.startswith("- ") else parse_map(start))
    return value


# =============================================================================
# 3. SOURCE MODEL — read cores, modules, kernel fragments, registry, presets
# =============================================================================


def read_text(path: Path) -> str:
    """Read a file as UTF-8, normalizing all newlines to LF for byte stability.

    Uses utf-8-sig so a BOM (PowerShell 5.1 writes one even for `-Encoding
    utf8`) is transparent; a UTF-16 file fails with a named fix instead of a
    traceback."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Fatal(f"{path}: not valid UTF-8 ({exc.reason} at byte {exc.start}) "
                    f"— re-save the file as UTF-8; PowerShell writes UTF-16 by "
                    f"default (use `Set-Content -Encoding utf8` or your "
                    f"editor's encoding menu)")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_frontmatter(text: str, filename: str = "<md>"):
    """Return (frontmatter_dict_or_None, body). Body has its leading blank
    lines trimmed."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm_text = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1:]).lstrip("\n")
            return parse_yaml(fm_text, filename), body
    raise Fatal(f"{filename}: unterminated frontmatter — add a closing '---'")


def strip_leading_html_comment(text: str) -> str:
    """Drop a kernel fragment's leading '<!-- ... -->' authoring comment."""
    t = text.lstrip("\n")
    if t.startswith("<!--"):
        end = t.find("-->")
        if end != -1:
            return t[end + 3:].lstrip("\n")
    return text


def find_includes(text: str) -> list[str]:
    return INCLUDE_RE.findall(text)


class Source:
    """Everything the compiler reads from the GLaDOS source tree."""

    def __init__(self, root: Path):
        self.root = root
        self.src = root / "src"
        if not self.src.is_dir():
            raise Fatal(f"no src/ tree under {root} — pass --source <glados repo> "
                        f"(a vendored .glados/glados.py cannot find the sources "
                        f"on its own)")
        self.kernel = self.src / "kernel"
        self.preamble_raw = read_text(self._require(self.kernel / "preamble.md"))
        self.epilogue_raw = read_text(self._require(self.kernel / "epilogue.md"))
        self.registry = parse_yaml(
            read_text(self._require(self.kernel / "state-registry.yaml")),
            "state-registry.yaml")
        self.presets = parse_yaml(
            read_text(self._require(self.kernel / "presets" / "phases.yaml")),
            "phases.yaml")
        self.aliases = parse_yaml(
            read_text(self._require(self.kernel / "aliases.yaml")),
            "aliases.yaml").get("aliases", {})
        self.cores = {c: self._load_unit("workflows", c) for c in CORES}
        self.modules = {m: self._load_unit("modules", m) for m in MODULES}

    @staticmethod
    def _require(path: Path) -> Path:
        if not path.exists():
            raise Fatal(f"missing kernel source {path} — the GLaDOS source tree "
                        f"is incomplete; pass --source <a full glados checkout> "
                        f"or restore the file")
        return path

    def _load_unit(self, kind: str, name: str) -> dict:
        path = self.src / kind / f"{name}.md"
        if not path.exists():
            raise Fatal(f"missing {kind[:-1]} source {path} — the compiler needs "
                        f"all {len(CORES)} cores and {len(MODULES)} modules")
        fm, body = split_frontmatter(read_text(path), f"{name}.md")
        if fm is None:
            raise Fatal(f"{path}: no YAML frontmatter (needs reads/writes/emits)")
        return {
            "name": name,
            "path": path,
            "frontmatter": fm,
            "body": body,
            "reads": list(fm.get("reads") or []),
            "writes": list(fm.get("writes") or []),
            "emits": list(fm.get("emits") or []),
            "requires": list(fm.get("requires") or []),
            "description": fm.get("description", name),
        }

    # -- registry helpers -----------------------------------------------------
    def registry_keys(self) -> set[str]:
        return set((self.registry.get("keys") or {}).keys())

    def outcome_types(self) -> set[str]:
        return set(self.registry.get("outcome-types") or [])

    def manifest_keys(self) -> set[str]:
        keys = self.registry.get("keys") or {}
        return {k for k, v in keys.items() if isinstance(v, dict) and v.get("home") == "manifest"}


def include_fragment(source: Source, rel: str, _stack: tuple = ()) -> str:
    if rel in _stack:
        chain = " -> ".join(_stack + (rel,))
        raise Fatal(f"glados:include cycle: {chain} — remove one of the "
                    f"includes to break the loop")
    if len(_stack) > 16:
        raise Fatal(f"glados:include recursion too deep at '{rel}' (chain: "
                    f"{' -> '.join(_stack)}) — flatten the fragment nesting")
    path = source.src / rel
    if not path.exists():
        raise Fatal(f"dangling glados:include '{rel}' — no file at {path}; add "
                    f"the fragment or remove the directive")
    frag = read_text(path)
    return resolve_includes(source, frag, _stack + (rel,))


def resolve_includes(source: Source, text: str, _stack: tuple = ()) -> str:
    return INCLUDE_RE.sub(lambda m: include_fragment(source, m.group(1), _stack), text)


# =============================================================================
# 4. MANIFEST — load, merge phase presets with provenance
# =============================================================================


class Resolved:
    """A resolved manifest plus per-leaf provenance and relaxation bookkeeping."""

    def __init__(self):
        self.values: dict = {}
        self.provenance: dict[str, str] = {}   # leaf-path -> baseline|phase:X|explicit
        self.relaxed_phase: list[str] = []      # keys where phase is laxer than baseline
        self.phase = ""
        self.raw: dict = {}


def _is_laxer(order: list[str], a, b) -> bool:
    try:
        return order.index(a) > order.index(b)
    except ValueError:
        return False


def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise Fatal(f"no manifest at {path} — copy glados.yaml.example to "
                    f"{path.name} in your repo root and edit it")
    return parse_yaml(read_text(path), path.name)


def resolve_manifest(raw: dict, presets: dict, manifest_name: str) -> Resolved:
    phase = raw.get("phase")
    if phase is None:
        raise Fatal(f"{manifest_name}: required key 'phase:' is missing — set it "
                    f"to one of: {', '.join(PHASES)}")
    if phase not in PHASES:
        raise Fatal(f"{manifest_name}: phase '{phase}' is not valid — use one of: "
                    f"{', '.join(PHASES)}")

    baseline = presets.get("baseline") or {}
    preset = presets.get(phase) or {}
    r = Resolved()
    r.phase = phase
    r.raw = raw
    plabel = f"phase:{phase}"

    def layer_scalar(key: str):
        val, prov = baseline.get(key), "baseline"
        if key in preset:
            val, prov = preset[key], plabel
        if key in raw:
            val, prov = raw[key], "explicit"
        r.values[key] = val
        r.provenance[key] = prov

    for key in ("optimize-for", "merge-authority", "default-modules"):
        layer_scalar(key)

    # channels + decisions: per-leaf layering
    for group in ("channels", "decisions"):
        merged: dict = {}
        for leaf, val in (baseline.get(group) or {}).items():
            merged[leaf] = val
            r.provenance[f"{group}.{leaf}"] = "baseline"
        for leaf, val in (preset.get(group) or {}).items():
            merged[leaf] = val
            r.provenance[f"{group}.{leaf}"] = plabel
        for leaf, val in (raw.get(group) or {}).items():
            merged[leaf] = val
            r.provenance[f"{group}.{leaf}"] = "explicit"
        r.values[group] = merged

    # params: deep-ish merge (baseline<phase<explicit), review-panel.max-cycles tracked
    params: dict = {}
    for layer, label in ((baseline, "baseline"), (preset, plabel), (raw, "explicit")):
        for ns, cfg in (layer.get("params") or {}).items():
            params.setdefault(ns, {})
            if isinstance(cfg, dict):
                for k, v in cfg.items():
                    params[ns][k] = v
                    r.provenance[f"params.{ns}.{k}"] = label
    r.values["params"] = params

    # pass-through explicit-only keys
    for key in ("platform", "phase", "branching", "workflows", "visibility-acknowledged",
                "relaxation-acknowledged", "disabled-workflows"):
        if key in raw:
            r.values[key] = raw[key]
            r.provenance[key] = "explicit"

    # RELAXED(phase): a value whose resolved provenance is the phase preset AND
    # that is laxer than the strict baseline. An explicit override (provenance
    # 'explicit') is NOT phase-derived, so it clears the marker.
    if r.provenance.get("merge-authority") == plabel and _is_laxer(
            MERGE_AUTHORITY_ORDER, r.values.get("merge-authority"),
            baseline.get("merge-authority")):
        r.relaxed_phase.append("merge-authority")
    for leaf, val in (r.values.get("decisions") or {}).items():
        if r.provenance.get(f"decisions.{leaf}") == plabel and _is_laxer(
                DECISION_ORDER, val, (baseline.get("decisions") or {}).get(leaf)):
            r.relaxed_phase.append(leaf)

    return r


def resolved_subkey_exists(r: Resolved, dotted: str) -> bool:
    """Does e.g. 'branching.default-target' or 'params.review-panel.personas'
    exist (non-empty) in the resolved manifest?"""
    node = r.values
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return node is not None and node != [] and node != {}


def manifest_hash_of(path: Path) -> str:
    return hashlib.sha256(read_text(path).encode("utf-8")).hexdigest()


# =============================================================================
# 5. COMPILE — assemble one compiled core from the sources
# =============================================================================


def effective_modules(source: Source, core_name: str, r: Resolved) -> list[str]:
    """workflows[wf] (or default-modules if absent) ∪ core.requires, aliased,
    deduped, in canonical order."""
    workflows = r.values.get("workflows") or {}
    if core_name in workflows and workflows[core_name] is not None:
        base = list(workflows[core_name])
    else:
        base = list(r.values.get("default-modules") or [])
    requires = source.cores[core_name]["requires"]
    chosen = set()
    for m in base + requires:
        chosen.add(MODULE_ALIASES.get(m, m))
    return [m for m in MODULES if m in chosen]


def provenance_header(core_name: str, manifest_hash: str, modules: list[str]) -> str:
    mods = ", ".join(modules) if modules else "none"
    return (
        "<!-- GLaDOS v2 compiled artifact — generated by glados.py; "
        "edit the source, not this file.\n"
        f"     workflow: {core_name}\n"
        f"     glados-version: {VERSION}\n"
        f"     manifest-sha256: {manifest_hash}\n"
        f"     modules-inlined: {mods}\n"
        f"     compile-source: src/workflows/{core_name}.md\n"
        "-->"
    )


def compile_core(source: Source, core_name: str, r: Resolved, manifest_hash: str) -> str:
    core = source.cores[core_name]
    modules = effective_modules(source, core_name, r)

    optimize_for = r.values.get("optimize-for") or ""
    preamble = strip_leading_html_comment(source.preamble_raw)
    preamble = preamble.replace("{{OPTIMIZE_FOR}}", optimize_for).strip("\n")
    epilogue = strip_leading_html_comment(source.epilogue_raw).strip("\n")

    header = provenance_header(core_name, manifest_hash, modules)
    core_body = resolve_includes(source, core["body"]).strip("\n")

    parts = [preamble, header, core_body]
    for m in modules:
        parts.append(resolve_includes(source, source.modules[m]["body"]).strip("\n"))
    parts.append(epilogue)
    return "\n\n".join(parts) + "\n"


class Compilation:
    """The mode-independent compiled artifacts for one (source, manifest)."""

    def __init__(self, source: Source, r: Resolved, manifest_hash: str):
        self.source = source
        self.resolved = r
        self.manifest_hash = manifest_hash
        self.enabled = [c for c in CORES
                        if c not in set(r.values.get("disabled-workflows") or [])]
        self.cores = {c: compile_core(source, c, r, manifest_hash) for c in self.enabled}
        self.modules_for = {c: effective_modules(source, c, r) for c in self.enabled}


def compile_all(source: Source, r: Resolved, manifest_hash: str) -> Compilation:
    return Compilation(source, r, manifest_hash)


# =============================================================================
# 6. TYPE CHECKS — the seven fatal install-time checks
# =============================================================================


def run_type_checks(source: Source, comp: Compilation) -> list[str]:
    """Return a list of fatal error strings (empty == passes)."""
    r = comp.resolved
    errors: list[str] = []
    enabled = set(comp.enabled)

    # Enabled modules = union of effective modules across enabled cores.
    enabled_modules: set[str] = set()
    for c in comp.enabled:
        enabled_modules.update(comp.modules_for[c])

    units_cores = [source.cores[c] for c in comp.enabled]
    units_modules = [source.modules[m] for m in sorted(enabled_modules)]
    all_units = units_cores + units_modules

    registry_keys = source.registry_keys()
    outcome_types = source.outcome_types()

    # ---- (4) unknown tokens -------------------------------------------------
    for u in all_units:
        for tok in u["reads"] + u["writes"]:
            if tok not in registry_keys:
                errors.append(f"{u['name']}: '{tok}' in reads/writes is not a "
                              f"registered state key — add it to "
                              f"src/kernel/state-registry.yaml or fix the typo")
        for tok in u["emits"]:
            if tok not in outcome_types:
                errors.append(f"{u['name']}: emits '{tok}', not an outcome-type — "
                              f"use one of {', '.join(sorted(outcome_types))}")

    # ---- (1) readers without writers ---------------------------------------
    writers: set[str] = set(PREAMBLE_OWNED_WRITES) | source.manifest_keys()
    for u in all_units:
        writers.update(u["writes"])
    readers: dict[str, list[str]] = {}
    for u in all_units:
        for key in u["reads"]:
            readers.setdefault(key, []).append(u["name"])
    for key, who in readers.items():
        if key in writers:
            continue
        fallback = READER_FALLBACKS.get(key)
        if fallback and resolved_subkey_exists(r, fallback):
            continue
        fix = (f"enable a workflow that writes it, or set manifest '{fallback}'"
               if fallback else "enable a workflow that writes it")
        errors.append(f"state key '{key}' is read by [{', '.join(sorted(set(who)))}] "
                      f"but no enabled writer covers it — {fix}")

    # ---- (2) zero-sink emits ------------------------------------------------
    channels = r.values.get("channels") or {}
    vis_ack = r.values.get("visibility-acknowledged")
    # channels: typos are silent visibility loss — validate both sides of the
    # binding against the closed vocabularies first.
    for otype in sorted(channels.keys()):
        if otype not in outcome_types:
            errors.append(f"channels.{otype}: not a registered outcome type — "
                          f"use one of {', '.join(sorted(outcome_types))}")
        for s in (channels.get(otype) or []):
            if s not in KNOWN_SINKS:
                errors.append(f"channels.{otype}: unknown sink '{s}' — sinks "
                              f"are: {', '.join(sorted(KNOWN_SINKS))}")
    emitted: set[str] = set()
    for u in all_units:
        emitted.update(u["emits"])
    for otype in sorted(emitted):
        sinks = channels.get(otype) or []
        if not sinks:
            errors.append(f"outcome '{otype}' is emitted but bound to no sink in "
                          f"channels: — add a sink under channels.{otype}")
            continue
        if otype in LEDGER_OK_TYPES:
            continue
        if any(s in TEAM_VISIBLE_SINKS for s in sinks):
            continue
        if vis_ack == "ledger-only":
            continue
        errors.append(f"outcome '{otype}' has no team-visible sink "
                      f"(has {sinks}); bind one of "
                      f"{sorted(TEAM_VISIBLE_SINKS)} under channels.{otype}, or "
                      f"confess with 'visibility-acknowledged: ledger-only'")

    # ---- (3) requires satisfied --------------------------------------------
    # First: every module/workflow token the manifest names must exist. A typo
    # here otherwise SILENTLY drops the module from the compiled output —
    # exactly the v1 "mode that stops shipping modules" bug.
    workflows = r.values.get("workflows") or {}
    for tok in (r.values.get("default-modules") or []):
        if MODULE_ALIASES.get(tok, tok) not in MODULES:
            errors.append(f"default-modules: unknown module '{tok}' — modules "
                          f"are: {', '.join(MODULES)} (a typo here silently "
                          f"drops the module from every workflow)")
    for wf, mods in sorted(workflows.items()):
        if wf not in CORES:
            errors.append(f"workflows.{wf}: unknown workflow — cores are: "
                          f"{', '.join(CORES)}")
            continue
        for tok in (mods or []):
            if MODULE_ALIASES.get(tok, tok) not in MODULES:
                errors.append(f"workflows.{wf}: unknown module '{tok}' — "
                              f"modules are: {', '.join(MODULES)} (a typo here "
                              f"silently drops the module from the workflow)")
    for wf in (r.values.get("disabled-workflows") or []):
        if wf not in CORES:
            errors.append(f"disabled-workflows: unknown workflow '{wf}' — "
                          f"cores are: {', '.join(CORES)} (a typo here leaves "
                          f"the workflow enabled)")
    for c in comp.enabled:
        req = [MODULE_ALIASES.get(m, m) for m in source.cores[c]["requires"]]
        for m in req:
            if m not in MODULES:
                errors.append(f"{c}: requires unknown module '{m}'")
                continue
            if c in workflows and workflows[c] is not None:
                listed = [MODULE_ALIASES.get(x, x) for x in workflows[c]]
                if m not in listed:
                    errors.append(f"workflows.{c} must list required module "
                                  f"'{m}' — add it to the {c} module list in "
                                  f"the manifest")

    # ---- (5) forbidden-content lint on compiled output ---------------------
    for c, text in comp.cores.items():
        for tok in FORBIDDEN_TOKENS:
            if tok in text:
                errors.append(f"compiled {c}: contains forbidden token '{tok}' — "
                              f"an unresolved include/placeholder slipped through")

    # ---- (6) phase invariants ----------------------------------------------
    errors.extend(_check_phase_invariants(source, r))

    # ---- (7) alias-map integrity -------------------------------------------
    for alias, target in source.aliases.items():
        if alias in CORES:
            errors.append(f"aliases.yaml: alias '{alias}' shadows the real core "
                          f"of the same name — its shim would overwrite the "
                          f"compiled core; remove the alias (aliases exist only "
                          f"for dead v1 names)")
        if target not in CORES:
            errors.append(f"aliases.yaml: alias '{alias}' -> '{target}' is not a "
                          f"real core — fix the target or add the core")

    return errors


def _check_phase_invariants(source: Source, r: Resolved) -> list[str]:
    errors: list[str] = []

    # anti-inflation: a preset may only set keys present in glados.yaml.example
    # (+ the preset-native optimize-for).
    example_path = source.root / "glados.yaml.example"
    allowed = {"optimize-for"}
    if example_path.exists():
        allowed |= set(parse_yaml(read_text(example_path), "glados.yaml.example").keys())
    for pname, preset in source.presets.items():
        if not isinstance(preset, dict):
            continue
        for key in preset.keys():
            if key not in allowed:
                errors.append(f"phases.yaml: preset '{pname}' sets '{key}', which "
                              f"is not a glados.yaml schema key — presets may only "
                              f"spell existing defaults (anti-inflation cap)")

    # explicit keys laxer than the phase preset require relaxation-acknowledged
    raw = r.raw
    phase = r.phase
    preset = source.presets.get(phase) or {}
    baseline = source.presets.get("baseline") or {}
    acked = set(raw.get("relaxation-acknowledged") or [])

    if "merge-authority" in raw:
        floor = preset.get("merge-authority", baseline.get("merge-authority"))
        if _is_laxer(MERGE_AUTHORITY_ORDER, raw["merge-authority"], floor) \
                and "merge-authority" not in acked:
            errors.append(f"merge-authority '{raw['merge-authority']}' is laxer than "
                          f"phase '{phase}' ('{floor}') — add 'merge-authority' to "
                          f"relaxation-acknowledged: in the manifest to confess it")
    for leaf, val in (raw.get("decisions") or {}).items():
        floor = (preset.get("decisions") or {}).get(
            leaf, (baseline.get("decisions") or {}).get(leaf))
        if _is_laxer(DECISION_ORDER, val, floor) and leaf not in acked:
            errors.append(f"decision '{leaf}: {val}' is laxer than phase '{phase}' "
                          f"('{floor}') — add '{leaf}' to relaxation-acknowledged: "
                          f"in the manifest to confess it")

    return errors


# =============================================================================
# 7. ASSEMBLY REPORT
# =============================================================================


def build_assembly_report(source: Source, comp: Compilation) -> str:
    r = comp.resolved
    out: list[str] = []
    out.append("# GLaDOS assembly report")
    out.append("")
    out.append(f"- phase: `{r.phase}`")
    out.append(f"- manifest sha256: `{comp.manifest_hash}`")
    out.append(f"- glados version: {VERSION}")
    out.append(f"- enabled cores: {len(comp.enabled)} / {len(CORES)}")
    out.append("")

    out.append("## Resolved manifest keys")
    out.append("")
    out.append("| Key | Value | Provenance |")
    out.append("|-----|-------|------------|")
    for key in ("phase", "platform", "merge-authority", "optimize-for",
                "default-modules"):
        if key in r.values:
            out.append(f"| {key} | {_fmt(r.values[key])} | "
                       f"({r.provenance.get(key, 'baseline')}) |")
    for group in ("channels", "decisions"):
        for leaf in sorted((r.values.get(group) or {}).keys()):
            path = f"{group}.{leaf}"
            out.append(f"| {path} | {_fmt(r.values[group][leaf])} | "
                       f"({r.provenance.get(path, 'baseline')}) |")
    for ns, cfg in sorted((r.values.get("params") or {}).items()):
        for k in sorted(cfg.keys()):
            path = f"params.{ns}.{k}"
            out.append(f"| {path} | {_fmt(cfg[k])} | "
                       f"({r.provenance.get(path, 'baseline')}) |")
    for leaf in sorted((r.values.get("branching") or {}).keys()):
        out.append(f"| branching.{leaf} | {_fmt(r.values['branching'][leaf])} | "
                   f"(explicit) |")
    out.append("")

    out.append(f"## RELAXED(phase) markers: {len(r.relaxed_phase)}")
    out.append("")
    if r.relaxed_phase:
        out.append("Values the phase preset relaxes below the strict baseline:")
        out.append("")
        for key in r.relaxed_phase:
            val = (r.values.get("decisions") or {}).get(key, r.values.get(key))
            out.append(f"- RELAXED(phase) `{key}` = `{_fmt(val)}`")
    else:
        out.append("_None — the phase preset is no laxer than baseline._")
    out.append("")

    out.append("## Per-workflow assembly")
    out.append("")
    for c in comp.enabled:
        mods = comp.modules_for[c]
        incs = find_includes(source.cores[c]["body"])
        for m in mods:
            incs += find_includes(source.modules[m]["body"])
        seen: list[str] = []
        for inc in incs:
            if inc not in seen:
                seen.append(inc)
        out.append(f"- **{c}** — core + modules[{', '.join(mods) or 'none'}] + "
                   f"fragments[{', '.join(seen) or 'none'}]")
    out.append("")

    out.append("## Waived / acknowledged confessions")
    out.append("")
    confessions = False
    for key in ("visibility-acknowledged", "relaxation-acknowledged"):
        if key in r.raw:
            confessions = True
            out.append(f"- `{key}: {_fmt(r.raw[key])}`")
    if not confessions:
        out.append("_None._")
    out.append("")
    return "\n".join(out)


def _fmt(val) -> str:
    if isinstance(val, list):
        return "[" + ", ".join(str(v) for v in val) + "]"
    return str(val)


# =============================================================================
# 8. ADAPTERS — six emitters over the SAME compiled artifacts
# =============================================================================
#
# Each adapter is a pure function returning a plan: {relpath: (kind, data)}
# where kind is 'text' (LF str) or 'bytes'. install applies the plan then runs
# directory-scoped cleanup; check recomputes the plan and diffs it.


def _alias_targets(source: Source, comp: "Compilation") -> dict[str, str]:
    """Alias -> target, skipping any alias whose target core is disabled."""
    return {a: t for a, t in source.aliases.items() if t in comp.cores}


# ---- claude -----------------------------------------------------------------

def adapter_claude(source: Source, comp: Compilation) -> dict:
    plan: dict = {}
    base = ".claude/commands/glados"
    for c in comp.enabled:
        plan[f"{base}/{c}.md"] = ("text", comp.cores[c])
    for alias, target in _alias_targets(source, comp).items():
        plan[f"{base}/{alias}.md"] = ("text",
            f"The `{alias}` workflow was renamed. Run `/glados:{target}` instead.\n")
    return plan


# ---- claude-plugin (repo-side) ---------------------------------------------

def adapter_claude_plugin(source: Source, comp: Compilation) -> dict:
    plan: dict = {}
    for c in comp.enabled:
        plan[f"compiled/claude-plugin/{c}.md"] = ("text", comp.cores[c])
        desc = _yaml_quote(source.cores[c]["description"])
        plan[f"skills/{c}/SKILL.md"] = ("text",
            f"---\ndescription: {desc}\n---\n\n"
            f"Read and follow the compiled workflow at "
            f"`${{CLAUDE_PLUGIN_ROOT}}/compiled/claude-plugin/{c}.md`.\n")
    for alias, target in _alias_targets(source, comp).items():
        desc = _yaml_quote(f"(renamed) the '{alias}' workflow is now '{target}'")
        plan[f"skills/{alias}/SKILL.md"] = ("text",
            f"---\ndescription: {desc}\n---\n\n"
            f"`{alias}` was renamed to `{target}`. Read and follow "
            f"`${{CLAUDE_PLUGIN_ROOT}}/compiled/claude-plugin/{target}.md`.\n")
    return plan


# ---- direct -----------------------------------------------------------------

def adapter_direct(source: Source, comp: Compilation) -> dict:
    plan: dict = {}
    for c in comp.enabled:
        plan[f"product-knowledge/glados/{c}.md"] = ("text", comp.cores[c])
    return plan


# ---- gemini -----------------------------------------------------------------

def _toml_multiline(s: str) -> str:
    """Emit s as a TOML multi-line string, byte-preserving under tomllib.

    Preferred form is the literal '''…''' (no escaping to get wrong). When the
    content itself contains ''' — a Python triple-quote in a code example —
    fall back to a basic \"\"\"…\"\"\" string with backslash/quote escaping."""
    if "'''" not in s and s.endswith("\n"):
        return "'''\n" + s + "'''"
    esc = s.replace("\\", "\\\\").replace('"', '\\"')
    return '"""\n' + esc + '"""'


def _toml_basic(s: str) -> str:
    """Single-line TOML basic string; newlines/tabs become escapes."""
    esc = (s.replace("\\", "\\\\").replace('"', '\\"')
           .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"))
    return '"' + esc + '"'


def _one_line(s: str) -> str:
    """Collapse newlines/whitespace runs: descriptions are menu one-liners."""
    return " ".join(s.split())


def _yaml_quote(s: str) -> str:
    """One-line, double-quoted YAML scalar for emitted frontmatter. Collapses
    newlines/runs of whitespace so a block-scalar description cannot break the
    frontmatter of a generated SKILL.md / workflow file."""
    s = _one_line(s)
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def adapter_gemini(source: Source, comp: Compilation) -> dict:
    plan: dict = {}
    base = ".gemini/commands/glados"
    for c in comp.enabled:
        desc = _one_line(source.cores[c]["description"])
        toml = (f"description = {_toml_basic(desc)}\n"
                f"prompt = {_toml_multiline(comp.cores[c])}\n")
        plan[f"{base}/{c}.toml"] = ("text", toml)
    for alias, target in _alias_targets(source, comp).items():
        desc = f"(renamed) {alias} is now {target}"
        body = f"The `{alias}` workflow was renamed. Run `/glados:{target}` instead.\n"
        toml = (f"description = {_toml_basic(desc)}\n"
                f"prompt = {_toml_multiline(body)}\n")
        plan[f"{base}/{alias}.toml"] = ("text", toml)
    return plan


# ---- antigravity ------------------------------------------------------------

def _agy_description(text: str) -> str:
    """Antigravity caps workflow description frontmatter at 250 chars."""
    text = text.replace("\n", " ").strip()
    return text[:247] + "..." if len(text) > 250 else text


def adapter_antigravity(source: Source, comp: Compilation) -> dict:
    plan: dict = {}
    base = ".agents/workflows"
    for c in comp.enabled:
        desc = _yaml_quote(_agy_description(source.cores[c]["description"]))
        body = f"---\ndescription: {desc}\n---\n\n{comp.cores[c]}"
        plan[f"{base}/glados-{c}.md"] = ("text", body)
    for alias, target in _alias_targets(source, comp).items():
        desc = _yaml_quote(_agy_description(f"(renamed) {alias} is now {target}"))
        body = (f"---\ndescription: {desc}\n---\n\n"
                f"The `{alias}` workflow was renamed. Run `/glados-{target}` instead.\n")
        plan[f"{base}/glados-{alias}.md"] = ("text", body)
    return plan


AGY_HOOKS_BLOCK = {
    "hooks": {
        "glados-run-record-guard": {
            "Stop": {
                "matcher": "",
                "hooks": [{
                    "type": "command",
                    # Reuses the shared run-record guard vendored into .glados/hooks/.
                    "command": "python .glados/hooks/gemini-afteragent-guard.py",
                    "timeout": 30,
                }],
            }
        }
    }
}


# ---- aistudio ---------------------------------------------------------------

def _aistudio_preamble(title: str, advisory: bool) -> str:
    banner = ("\n> **Advisory mode.** This is an execution-heavy workflow; in "
              "AI Studio it plans and reviews only. Do not treat emitted commands "
              "as run — a human or the api-runner applies them.\n") if advisory else ""
    return (
        f"# GLaDOS v2 — {title} (AI Studio edition)\n"
        "\n"
        "## Runtime contract (read first)\n"
        "\n"
        "You are running in Google AI Studio. You have NO file, git, or "
        "GitLab/GitHub access; the human operator (or the api-runner script) is "
        "your hands. Emit exact artifacts; they apply them.\n"
        "\n"
        "- When a step writes a file, emit a fenced block headed "
        "`=== WRITE FILE: <repo-relative-path> ===` with the full contents.\n"
        "- When a step performs a git/platform action, emit the exact command "
        "in a fenced block headed `=== RUN: ===`.\n"
        "- glados.yaml could not be read at runtime; its values were inlined at "
        "compile time (see the compile stamp in the provenance header). If the "
        "pasted repo context contradicts them, warn the operator.\n"
        "- End EVERY response with the `## Before ending this run` epilogue "
        "checklist as a mandatory response suffix; if you cannot complete it, "
        "say so explicitly rather than omitting it.\n"
        f"{banner}"
        "\n"
        "---\n"
    )


AISTUDIO_README = """# GLaDOS on Google AI Studio — paste kit + API runner

AI Studio has no filesystem, no plugin/skill/command surface, and no lifecycle
hooks. It is a **planning / review / spec** surface. This kit ships the
advisory-safe workflows as self-contained paste bundles plus a Gemini
Interactions API runner for unattended read-mostly routines.

## Paste flow

1. Open a new prompt in AI Studio.
2. Paste the contents of `bundles/<workflow>.aistudio.md` into the **System
   Instructions** field.
3. Paste (or attach from Drive) the repo context the workflow needs — the
   relevant files, the issue text — as your first user message.
4. Run. The model emits `=== WRITE FILE: ... ===` and `=== RUN: ... ===`
   blocks; you (the operator) apply them to the repo and commit the run record.

## Saved-prompt setup

Save the prompt (System Instructions + run settings) to reuse the workflow. AI
Studio autosaves prompts to your Google Drive.

## Data-governance note

Pasting proprietary repo content into free-tier AI Studio may expose it to
product-improvement use. Confirm your tier's data policy before pasting private
code. The api-runner path (paid API key) is the governed alternative.

## Staleness rule

These bundles inline `glados.yaml` values at compile time. Re-run
`glados.py install --mode aistudio` whenever the manifest changes; `MANIFEST.md`
records the compile hash each bundle was built against.
"""

AISTUDIO_RUN_RECORD_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "GLaDOS run record (AI Studio structured-output form)",
    "type": "object",
    "required": ["workflow", "outcome", "run_record", "epilogue_completed"],
    "properties": {
        "workflow": {"type": "string"},
        "outcome": {"type": "string"},
        "decisions": {"type": "array", "items": {"type": "object"}},
        "emitted_outcomes": {"type": "array", "items": {"type": "string"}},
        "write_file_blocks": {"type": "array", "items": {"type": "object"}},
        "run_command_blocks": {"type": "array", "items": {"type": "string"}},
        "run_record": {
            "type": "string",
            "description": "Full markdown body for .glados/runs/<id>.md",
        },
        "epilogue_completed": {"type": "boolean"},
    },
    "additionalProperties": True,
}

AISTUDIO_RUNNER = '''#!/usr/bin/env python3
"""GLaDOS AI Studio api-runner — stdlib only.

Runs a compiled AI Studio bundle as the system instruction against the Gemini
Interactions API (GA June 2026), gathering context files from argv and writing
the model output beside the run ledger. Requires GEMINI_API_KEY in the env.

    python run_workflow.py bundles/plan-feature.aistudio.md context1.md context2.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = ("https://generativelanguage.googleapis.com/v1beta/"
            "models/{model}:generateContent")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: run_workflow.py <bundle.md> [context-file ...]", file=sys.stderr)
        return 2
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not set — export it (or use Vertex ADC) before "
              "running a scheduled GLaDOS workflow on the Gemini API.", file=sys.stderr)
        return 1

    bundle = Path(sys.argv[1]).read_text(encoding="utf-8")
    context = ""
    for ctx in sys.argv[2:]:
        context += f"\\n\\n=== FILE: {ctx} ===\\n" + Path(ctx).read_text(encoding="utf-8")

    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
    payload = {
        "system_instruction": {"parts": [{"text": bundle}]},
        "contents": [{"role": "user", "parts": [{"text": context or "(no context)"}]}],
    }
    url = ENDPOINT.format(model=model) + f"?key={api_key}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:  # pragma: no cover - network
        print(f"Gemini API request failed: {exc}", file=sys.stderr)
        return 1

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        print(json.dumps(data, indent=2))
        return 1

    runs = Path(".glados/runs")
    runs.mkdir(parents=True, exist_ok=True)
    out = runs / "aistudio-latest.md"
    out.write_text(text, encoding="utf-8", newline="\\n")
    print(text)
    print(f"\\n[written to {out}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

AISTUDIO_SCHEDULE = """# Scheduling GLaDOS on the Gemini API

"Scheduled GLaDOS on AI Studio" means "scheduled GLaDOS on the Gemini API": the
runner gathers repo context, calls the model, and applies the output itself.

## cron (Linux/macOS)

    0 7 * * 1  cd /path/to/repo && GEMINI_API_KEY=... \\
        python glados/adapters/aistudio/api-runner/run_workflow.py \\
        glados/adapters/aistudio/bundles/retrospect.aistudio.md CHANGELOG.md

## Windows Task Scheduler

    schtasks /Create /SC WEEKLY /D MON /TR "python run_workflow.py ..." /ST 07:00

## GitLab CI (scheduled pipeline)

    glados-retrospect:
      rule: if: $CI_PIPELINE_SOURCE == "schedule"
      script:
        - python glados/adapters/aistudio/api-runner/run_workflow.py \\
            glados/adapters/aistudio/bundles/retrospect.aistudio.md
"""


def adapter_aistudio(source: Source, comp: Compilation) -> dict:
    plan: dict = {}
    base = "glados/adapters/aistudio"
    bundle_rows: list[tuple[str, str]] = []

    def emit_bundle(bundle_name: str, core_name: str, title: str, advisory: bool):
        if core_name not in comp.cores:
            return
        text = _aistudio_preamble(title, advisory) + "\n" + comp.cores[core_name]
        rel = f"{base}/bundles/{bundle_name}.aistudio.md"
        plan[rel] = ("text", text)
        bundle_rows.append((bundle_name, f"bundles/{bundle_name}.aistudio.md"))

    for c in AISTUDIO_CORES:
        emit_bundle(c, c, source.cores[c]["description"], advisory=False)
    emit_bundle("fix-bug-advisory", "fix-bug",
                "Fix Bug (plan/triage only)", advisory=True)

    plan[f"{base}/README.md"] = ("text", AISTUDIO_README)

    manifest_md = ["# GLaDOS AI Studio bundles", "",
                   f"Compile hash: `{comp.manifest_hash}`", "",
                   "| Workflow | Bundle | Compile hash |",
                   "|----------|--------|--------------|"]
    for name, rel in bundle_rows:
        manifest_md.append(f"| {name} | {rel} | `{comp.manifest_hash}` |")
    manifest_md.append("")
    plan[f"{base}/MANIFEST.md"] = ("text", "\n".join(manifest_md))

    plan[f"{base}/schemas/run_record.schema.json"] = (
        "text", json.dumps(AISTUDIO_RUN_RECORD_SCHEMA, indent=2) + "\n")
    plan[f"{base}/api-runner/run_workflow.py"] = ("text", AISTUDIO_RUNNER)
    plan[f"{base}/api-runner/schedule.example.md"] = ("text", AISTUDIO_SCHEDULE)
    return plan


ADAPTERS = {
    "claude": adapter_claude,
    "claude-plugin": adapter_claude_plugin,
    "direct": adapter_direct,
    "gemini": adapter_gemini,
    "antigravity": adapter_antigravity,
    "aistudio": adapter_aistudio,
}


# Directory prefixes each mode fully owns (for stale-file cleanup). A file under
# one of these prefixes that the current plan does not emit is a stale leftover.
OWNED_DIRS = {
    "claude": [".claude/commands/glados"],
    "claude-plugin": ["compiled/claude-plugin"],
    "direct": ["product-knowledge/glados"],
    "gemini": [".gemini/commands/glados"],
    "antigravity": [".agents/workflows"],   # scoped to glados-*.md, see cleanup
    "aistudio": ["glados/adapters/aistudio/bundles"],
}


# =============================================================================
# 9. VENDOR + SCAFFOLD
# =============================================================================


VENDORED_HOOKS = ["claude-stop-hook.py", "gemini-afteragent-guard.py"]


def vendor_plan(source: Source, manifest_hash: str, report: str) -> dict:
    """Files vendored into <target>/.glados/, identical for every mode. The
    self-copy and presets must byte-match their sources."""
    plan: dict = {}
    self_bytes = (source.root / "bin" / "glados.py").read_bytes()
    presets_bytes = (source.kernel / "presets" / "phases.yaml").read_bytes()
    plan[".glados/glados.py"] = ("bytes", self_bytes)
    plan[".glados/presets.yaml"] = ("bytes", presets_bytes)
    plan[".glados/manifest-hash"] = ("text", manifest_hash + "\n")
    plan[".glados/assembly-report.md"] = ("text", report)
    # Vendor the run-record guard scripts so emitted hook references resolve.
    for name in VENDORED_HOOKS:
        src = source.root / "hooks" / name
        if src.exists():
            plan[f".glados/hooks/{name}"] = ("bytes", src.read_bytes())
    # Vendor the library persona definitions. Panels resolve a named persona
    # from the project's product-knowledge/personas/ first, then fall back to
    # this vendored library — without it, no install mode ships a persona.
    personas = source.src / "personas"
    if personas.is_dir():
        for f in sorted(personas.glob("*.md")):
            plan[f".glados/personas/{f.name}"] = ("bytes", f.read_bytes())
    return plan


def scaffold_product_knowledge(target: Path, source: Source) -> list[str]:
    """Create-only product-knowledge skeleton; NEVER deletes user content."""
    created: list[str] = []
    pk = target / "product-knowledge"
    for sub in ("observations", "standards", "philosophies"):
        d = pk / sub
        keep = d / ".gitkeep"
        if not keep.exists():
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.write_text("", encoding="utf-8", newline="\n")
            created.append(str(keep.relative_to(target)))
    status = pk / "PROJECT_STATUS.md"
    tmpl = source.src / "templates" / "PROJECT_STATUS.md"
    if not status.exists() and tmpl.exists():
        status.parent.mkdir(parents=True, exist_ok=True)
        status.write_text(read_text(tmpl), encoding="utf-8", newline="\n")
        created.append(str(status.relative_to(target)))
    return created


# =============================================================================
# 10. COMMANDS
# =============================================================================


def _write_one(path: Path, kind: str, data) -> None:
    if kind == "bytes":
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8", newline="\n")


def _write_plan(target: Path, plan: dict) -> None:
    for rel, (kind, data) in plan.items():
        path = target / rel
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_one(path, kind, data)
        except PermissionError:
            # Windows: an overwrite of a read-only leftover raises. The file is
            # inside a glados-owned dir, so clearing the attribute is in
            # contract; only a second failure is fatal.
            try:
                path.chmod(0o644)
                _write_one(path, kind, data)
            except OSError as exc:
                raise Fatal(f"cannot write {path}: {exc} — clear the read-only "
                            f"attribute (attrib -R) or delete the file, then "
                            f"re-run install")
        except OSError as exc:
            raise Fatal(f"cannot write {path}: {exc} — a conflicting "
                        f"file/directory is in the way; move it aside and "
                        f"re-run install")


def _force_unlink(path: Path) -> None:
    try:
        path.unlink()
    except PermissionError:
        try:
            path.chmod(0o644)
            path.unlink()
        except OSError as exc:
            raise Fatal(f"cannot remove stale file {path}: {exc} — clear the "
                        f"read-only attribute (attrib -R) or delete it by "
                        f"hand, then re-run install")


def _cleanup_owned(target: Path, mode: str, plan: dict, source: Source,
                   comp: Compilation) -> list[str]:
    """Directory-scoped stale-file removal, porting the bash cleanup semantics."""
    removed: list[str] = []
    planned = {str(Path(rel)) for rel in plan}

    for owned in OWNED_DIRS.get(mode, []):
        d = target / owned
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file():
                continue
            rel = str(f.relative_to(target))
            if mode == "antigravity" and not f.name.startswith("glados-"):
                continue  # only glados-*.md are ours under .agents/workflows
            if rel not in planned:
                _force_unlink(f)
                removed.append(rel)

    # claude: migrate old top-level (un-namespaced) command files, porting
    # cleanup_old_toplevel — remove name-matching files from the parent dir.
    if mode == "claude":
        parent = target / ".claude" / "commands"
        expected = [f"{c}.md" for c in comp.enabled] + \
                   [f"{a}.md" for a in source.aliases]
        for name in expected:
            for variant in (name, name.replace("-", "_")):
                stale = parent / variant
                if stale.is_file():
                    _force_unlink(stale)
                    removed.append(str(stale.relative_to(target)))
    return removed


def _resolve_source(args) -> Source:
    if getattr(args, "source", None):
        return Source(Path(args.source).resolve())
    here = Path(__file__).resolve().parent
    # bin/glados.py -> repo root is parent; vendored .glados/glados.py has no src
    for cand in (here.parent, here):
        if (cand / "src").is_dir():
            return Source(cand)
    raise Fatal("could not locate the GLaDOS source tree — pass --source <repo>")


def _prepare_compilation(source: Source, target: Path, mode: str):
    """Load the manifest for this mode, resolve it, compile, run checks."""
    if mode == "claude-plugin":
        manifest_path = target / "glados.yaml.example"
        if not manifest_path.exists():
            manifest_path = source.root / "glados.yaml.example"
    else:
        manifest_path = target / "glados.yaml"
    raw = load_manifest(manifest_path)
    resolved = resolve_manifest(raw, source.presets, manifest_path.name)
    manifest_hash = manifest_hash_of(manifest_path)
    comp = compile_all(source, resolved, manifest_hash)
    errors = run_type_checks(source, comp)
    if errors:
        raise Fatal("install checks failed:\n  - " + "\n  - ".join(errors))
    return comp, manifest_hash


def cmd_install(args) -> int:
    source = _resolve_source(args)
    target = Path(args.target).resolve()
    mode = args.mode
    if mode not in ADAPTERS:
        raise Fatal(f"unknown mode '{mode}' — one of: {', '.join(INSTALL_MODES)}")
    if not target.is_dir():
        raise Fatal(f"target directory does not exist: {target}")

    comp, manifest_hash = _prepare_compilation(source, target, mode)
    report = build_assembly_report(source, comp)

    plan = ADAPTERS[mode](source, comp)
    plan.update(vendor_plan(source, manifest_hash, report))
    _write_plan(target, plan)
    removed = _cleanup_owned(target, mode, plan, source, comp)

    scaffolded: list[str] = []
    if mode not in ("claude-plugin",):
        scaffolded = scaffold_product_knowledge(target, source)

    if mode == "claude-plugin":
        _regenerate_plugin_skills(target, source, comp)

    if mode == "antigravity":
        _emit_agy_hooks(target)

    print(f"glados: installed mode '{mode}' into {target}")
    print(f"glados: {len(comp.enabled)} cores, manifest {manifest_hash[:12]}…")
    if removed:
        print(f"glados: cleaned {len(removed)} stale file(s): {', '.join(removed)}")
    if scaffolded:
        print(f"glados: scaffolded {len(scaffolded)} product-knowledge file(s)")
    print()
    print(report)
    print(f"glados: assembly report written to .glados/assembly-report.md")
    return 0


def _regenerate_plugin_skills(target: Path, source: Source, comp: Compilation) -> None:
    """Prune stale skills/ dirs (keeping init), leave user skills untouched."""
    skills = target / "skills"
    if not skills.is_dir():
        return
    keep = set(comp.enabled) | set(source.aliases) | {"init"}
    # Known GLaDOS names we are allowed to remove (v1 + v2), never user skills.
    known = keep | {
        "mission", "plan-product", "autonomous-loop", "identify-bug", "plan-fix",
        "implement-fix", "verify-fix", "consolidate", "establish-standards",
        "recombobulate", "implement-feature", "verify-feature", "spec-feature",
        "review-mr", "review-codebase", "run-epic", "build-feature",
        "address-review", "adopt-codebase", "retrospect",
    }
    for d in sorted(skills.iterdir()):
        if d.is_dir() and d.name not in keep and d.name in known:
            for f in sorted(d.rglob("*"), reverse=True):
                if f.is_file():
                    _force_unlink(f)
            try:
                d.rmdir()
            except OSError:
                pass


def _emit_agy_hooks(target: Path) -> None:
    """Write .agents/hooks.json ONLY if absent; never clobber a user's file."""
    hooks = target / ".agents" / "hooks.json"
    block = json.dumps(AGY_HOOKS_BLOCK, indent=2) + "\n"
    if hooks.exists():
        print("glados: .agents/hooks.json exists — add this glados block manually:\n"
              + block)
    else:
        hooks.parent.mkdir(parents=True, exist_ok=True)
        hooks.write_text(block, encoding="utf-8", newline="\n")


def _detect_modes(target: Path) -> list[str]:
    modes: list[str] = []
    if (target / ".claude/commands/glados").is_dir():
        modes.append("claude")
    if (target / "product-knowledge/glados").is_dir():
        modes.append("direct")
    if (target / ".gemini/commands/glados").is_dir():
        modes.append("gemini")
    if (target / ".agents/workflows").is_dir() and \
            any((target / ".agents/workflows").glob("glados-*.md")):
        modes.append("antigravity")
    if (target / "glados/adapters/aistudio").is_dir():
        modes.append("aistudio")
    if (target / "compiled/claude-plugin").is_dir():
        modes.append("claude-plugin")
    return modes


def cmd_check(args) -> int:
    source = _resolve_source(args)
    target = Path(args.target).resolve()
    report_only = args.report_only
    problems: list[str] = []

    modes = _detect_modes(target)
    if not modes:
        problems.append(f"no GLaDOS install detected under {target}")
        _emit_check(problems, report_only)
        return 0 if report_only else 1

    # manifest hash: recompute vs vendored
    hash_path = target / ".glados" / "manifest-hash"
    manifest_path = target / "glados.yaml"
    if not manifest_path.exists() and modes == ["claude-plugin"]:
        manifest_path = target / "glados.yaml.example"
    if hash_path.exists() and manifest_path.exists():
        vendored = read_text(hash_path).strip()
        current = manifest_hash_of(manifest_path)
        if vendored != current:
            problems.append(f"stale compile: manifest-hash {vendored[:12]}… != "
                            f"current {current[:12]}… — re-run glados install")

    for mode in modes:
        try:
            comp, manifest_hash = _prepare_compilation(source, target, mode)
        except Fatal as exc:
            problems.append(f"[{mode}] {exc}")
            continue
        report = build_assembly_report(source, comp)
        plan = ADAPTERS[mode](source, comp)
        plan.update(vendor_plan(source, manifest_hash, report))
        for rel, (kind, data) in plan.items():
            path = target / rel
            if not path.exists():
                problems.append(f"[{mode}] missing installed file: {rel}")
                continue
            if kind == "bytes":
                drift = path.read_bytes() != data
            else:
                drift = read_text(path) != data
            if drift:
                problems.append(f"[{mode}] drift in installed file: {rel}")

    _emit_check(problems, report_only)
    if report_only:
        return 0
    return 1 if problems else 0


def _emit_check(problems: list[str], report_only: bool) -> None:
    if not problems:
        print("glados check: OK — no drift, checks pass, manifest hash current")
        return
    header = "glados check: report-only" if report_only else "glados check: FAIL"
    print(header)
    for p in problems:
        print(f"  - {p}")


def cmd_doctor(args) -> int:
    source = _resolve_source(args)
    target = Path(args.target).resolve()
    print(f"glados doctor — {target}")

    modes = _detect_modes(target)
    print(f"  installed modes: {', '.join(modes) if modes else '(none)'}")

    hash_path = target / ".glados" / "manifest-hash"
    manifest_path = target / "glados.yaml"
    if not manifest_path.exists():
        manifest_path = target / "glados.yaml.example"
    if hash_path.exists() and manifest_path.exists():
        vendored = read_text(hash_path).strip()
        current = manifest_hash_of(manifest_path)
        state = "current" if vendored == current else "STALE — re-run install"
        print(f"  manifest hash: {state} ({current[:12]}…)")
    else:
        print("  manifest hash: not vendored (no .glados/manifest-hash)")

    if _ci_check_wired(target):
        print("  CI check wired: yes")
    else:
        print("  CI check wired: no — add the glados-check CI template and "
              "reference it (see ci/)")

    hooks = []
    if (target / ".claude" / "settings.json").exists():
        try:
            data = json.loads(read_text(target / ".claude" / "settings.json"))
            if "hooks" in data:
                hooks.append("claude")
        except (ValueError, OSError):
            pass
    if (target / ".agents" / "hooks.json").exists():
        hooks.append("antigravity")
    if (target / ".gemini" / "settings.json").exists():
        hooks.append("gemini")
    print(f"  run-record hooks: {', '.join(hooks) if hooks else '(none installed)'}")

    if manifest_path.exists():
        raw = load_manifest(manifest_path)
        declared = raw.get("phase-declared")
        print(f"  phase: {raw.get('phase')} "
              f"(declared: {declared or 'undated — add phase-declared:'})")
        for key in ("visibility-acknowledged", "relaxation-acknowledged"):
            if key in raw:
                print(f"  confession restated: {key}: {_fmt(raw[key])}")

    print("glados doctor: informational only — never fails")
    return 0


def _ci_check_wired(target: Path) -> bool:
    gitlab = target / ".gitlab-ci.yml"
    if gitlab.exists() and "glados" in read_text(gitlab):
        return True
    wf_dir = target / ".github" / "workflows"
    if wf_dir.is_dir():
        for f in wf_dir.glob("*.yml"):
            if "glados.py check" in read_text(f):
                return True
    return False


def cmd_verify_ledger(args) -> int:
    target = Path(args.target).resolve()
    print(f"glados verify-ledger (report-only) — {target}")

    def git(*a):
        try:
            out = subprocess.run(["git", "-C", str(target), *a],
                                 capture_output=True, text=True, timeout=30)
            return out.stdout if out.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""

    log = git("log", "--all", "--format=%H%x09%s", "-n", "200")
    if not log.strip():
        print("  no git history reachable (not a repo, or empty) — nothing to scan")
        return 0

    record_commits = 0
    verdict_commits: list[str] = []
    for line in log.strip().split("\n"):
        sha, _, subject = line.partition("\t")
        if subject.startswith("chore(glados): record"):
            record_commits += 1
        low = subject.lower()
        if any(w in low for w in ("verdict", "review", "escalat")):
            verdict_commits.append(f"{sha[:10]} {subject}")

    branches = git("branch", "--format=%(refname:short)").strip().split("\n")
    feature_branches = [b for b in branches if b and b not in ("main", "master")]

    print(f"  run-record commits (chore(glados): record …): {record_commits}")
    print(f"  feature/other branches: {len(feature_branches)}")
    print(f"  MR-less verdict/review commits (silent-loss candidates): "
          f"{len(verdict_commits)}")
    for v in verdict_commits[:20]:
        print(f"    - {v}")
    if record_commits == 0 and feature_branches:
        print("  WARNING: agent-authored branches exist with zero run records — "
              "this is the class-B silent loss verify-ledger exists to surface")
    print("glados verify-ledger: report-only in v2.0.0")
    return 0


def cmd_compile_plugin(args) -> int:
    source = _resolve_source(args)
    repo = Path(args.target).resolve() if args.target else source.root
    ns = argparse.Namespace(source=str(source.root), target=str(repo),
                            mode="claude-plugin")
    return cmd_install(ns)


# =============================================================================
# 11. CLI
# =============================================================================


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="glados.py",
        description="GLaDOS v2 compiler / type-checker / installer.")
    p.add_argument("--version", action="version", version=f"glados {VERSION}")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("install", help="compile + emit one adapter")
    pi.add_argument("--target", required=True)
    pi.add_argument("--mode", required=True, choices=INSTALL_MODES)
    pi.add_argument("--source")
    pi.set_defaults(func=cmd_install)

    pc = sub.add_parser("check", help="CI mode: recompute + diff installed files")
    pc.add_argument("--target", default=".")
    pc.add_argument("--source")
    pc.add_argument("--report-only", action="store_true")
    pc.set_defaults(func=cmd_check)

    pd = sub.add_parser("doctor", help="staleness + wiring report (never fails)")
    pd.add_argument("--target", required=True)
    pd.add_argument("--source")
    pd.set_defaults(func=cmd_doctor)

    pv = sub.add_parser("verify-ledger", help="scan git for silent-loss candidates")
    pv.add_argument("--target", required=True)
    pv.add_argument("--report-only", action="store_true")
    pv.set_defaults(func=cmd_verify_ledger)

    pp = sub.add_parser("compile-plugin",
                        help="shorthand: install --mode claude-plugin --target <repo>")
    pp.add_argument("--target")
    pp.add_argument("--source")
    pp.set_defaults(func=cmd_compile_plugin)
    return p


def main(argv=None) -> int:
    # Legacy Windows consoles (cp850/cp437) cannot encode the em dashes and
    # ellipses in reports; never let a print() kill an install that already
    # wrote files.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Fatal as exc:
        print(f"glados: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
