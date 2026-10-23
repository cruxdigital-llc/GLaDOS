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
    validate        type-check a project's glados.yaml (pipelines included)
                    in memory; writes nothing, needs no install
    doctor          staleness + wiring report (never fails)
    migrate         guided v1 -> v2 migration: detect, generate, convert, clean
    verify-ledger   scan git history for silent-loss candidates (report-only)
    ledger          save run records to the glados/ledger branch, restore
                    them into .glados/runs/, or print a record's ledger link
    compile-plugin  shorthand: install --mode claude-plugin --target <repo>

Sections, in order:
    1.  CONSTANTS
    2.  PARSER            — YAML subset with line-numbered errors
    3.  SOURCE MODEL      — read cores/modules/kernel/registry/presets/aliases
    4.  MANIFEST          — load + phase-preset merge with provenance
    5.  COMPILE           — assemble one compiled core from the sources
    6.  TYPE CHECKS       — the fatal install-time checks, pipelines included
    7.  ASSEMBLY REPORT
    8.  ADAPTERS          — six emitters over the SAME compiled artifacts
    9.  VENDOR + SCAFFOLD
    10. COMMANDS          — install / check / doctor / migrate / verify-ledger
                            / ledger
    11. CLI
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
from pathlib import Path


# =============================================================================
# 1. CONSTANTS
# =============================================================================

VERSION = "2.5.0"

# The sixteen v2 cores, in canonical (pipeline-ish) order. The compiler touches
# ONLY these — other .md files under src/workflows are v1 leftovers deleted at
# integration and must be ignored. run-pipeline sits beside build-feature: it
# runs the project's own workflows (glados.yaml `pipelines:`) the way
# build-feature runs its fixed four stages.
CORES = [
    "intent",
    "adopt-codebase",
    "plan-feature",
    "spec-feature",
    "implement-feature",
    "verify-feature",
    "build-feature",
    "run-pipeline",
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

# Built-in sinks and whether each makes an outcome team-visible. Teams extend
# this set by declaring sinks under `sinks:` in glados.yaml — a declared sink is
# team-visible by default (it names an external destination people see), opt out
# with `team-visible: false`. The sink *name* set is therefore OPEN; only the
# built-ins are fixed. ``ledger`` is the one built-in that is NOT team-visible:
# it is the run record on the glados/ledger branch, valid alone only for
# progress/decision/observation.
BUILTIN_SINKS = {
    "mr-comment": True,
    "issue": True,
    "issue-comment": True,
    "label": True,
    "ledger": False,
}
# Built-in sinks that make an outcome team-visible (custom sinks are handled by
# _sink_is_team_visible, which honours their `team-visible:` declaration).
TEAM_VISIBLE_SINKS = {name for name, vis in BUILTIN_SINKS.items() if vis}
LEDGER_OK_TYPES = {"progress", "decision", "observation"}

# Merge-authority and decision strictness, STRICTEST first. "laxer = leftward"
# in the spec's own ``agent<record<escalate<forbidden`` ordering, so these lists
# read strict→lax and a lower index == stricter.
MERGE_AUTHORITY_ORDER = ["human", "agent-integration-only", "agent"]
DECISION_ORDER = ["forbidden", "escalate", "record", "agent"]

# The manifest keys whose values shape COMPILED output — the lane-1 keys.
# These, plus each pipeline's name and description (structural_projection),
# feed the manifest hash stamped into every compiled header and into
# .glados/manifest-hash, so only an edit to one of them makes `check` report a
# stale compile. Everything else in glados.yaml (channels, sinks, params,
# decisions, branching, merge-authority, platform, ...) is lane 2: compiled
# text tells the agent to read it at run time, so editing it changes behaviour
# on the next run with no reinstall — and must never make `check` fail. A key
# belongs here only if changing it changes the bytes the compiler emits:
#   phase / optimize-for   -> the optimize-for sentence in every preamble, and
#                             (phase) which preset defaults the module lists
#   default-modules / workflows -> which modules each core inlines
#   disabled-workflows     -> which cores and shims exist at all
#   sda                    -> install-time scaffolding (create-only artifacts)
# A derived projection of a lane-2 block can join the hash when it shapes
# emitted files (see structural_projection). Comments, key order, and
# whitespace never change the hash: it covers the parsed values, not bytes.
STRUCTURAL_KEYS = ["phase", "optimize-for", "default-modules", "workflows",
                   "disabled-workflows", "sda"]

# Every top-level glados.yaml key the toolchain or the compiled text reads.
# A key outside this list is almost always a typo ('chanels:') that would be
# silently ignored, so install/check print a warning naming it (doctor too).
# It is a warning, not a fatal error: rejecting unknown keys is a new rule
# and arrives in a minor release. Extend this list whenever a part of the
# toolchain starts reading a new top-level key.
KNOWN_MANIFEST_KEYS = [
    "glados", "platform", "phase", "phase-declared", "optimize-for",
    "channels", "sinks", "merge-authority", "decisions",
    "relaxation-acknowledged", "visibility-acknowledged", "branching",
    "default-modules", "workflows", "disabled-workflows", "params", "sda",
    "concurrency", "lifecycle", "pipelines", "steps", "canon",
]

# Manifest keys that are a team declaration and never a phase default. A
# preset naming one is rejected by _check_phase_invariants even when the key
# is live in glados.yaml.example (which is what the anti-inflation cap alone
# would admit). `sda:` says how the repo coordinates; `pipelines:`/`steps:`
# are the team's own process, and a preset that injected a step would add
# work nobody on the team declared. `canon:` is the team's choice of which
# books it answers to; a preset that seated one would put a work in every
# review that nobody on the team chose or summarized.
EXPLICIT_ONLY_KEYS = {
    "sda": ("SDA conformance is a team declaration, not a phase default; "
            "remove it from the preset and set 'sda: true' explicitly in "
            "glados.yaml"),
    "pipelines": ("project workflows are the team's own declaration, not a "
                  "phase default; remove it from the preset and declare "
                  "them in glados.yaml"),
    "steps": ("project steps are the team's own declaration, not a phase "
              "default; remove it from the preset and declare them in "
              "glados.yaml"),
    "canon": ("canon is the team's own choice of reference works, not a "
              "phase default; remove it from the preset and declare it in "
              "glados.yaml"),
}

# ---- project workflows: `pipelines:` and `steps:` ----------------------------
#
# A pipeline is an ordered list of steps: the built-in ones below and the
# project's own (`steps:`, bodies in product-knowledge/steps/<id>.md). No step
# is mandatory and none has a fixed position; order is validated only through
# artifacts. Each step NEEDS some kinds and PRODUCES at most one, and every
# need must come from an earlier step in the same sequence. The kinds are a
# closed set, so a new one is a compiler change, never a manifest one.
ARTIFACT_KINDS = ["plan", "shape", "spec", "change", "verification", "mr"]

# The built-in steps a sequence may name, with the contract run-pipeline's
# compiled step 2 table states (keep the two in step):
#   runs     "core" = a nested workflow run; "library" = a fragment run inside
#            run-pipeline itself (vocabulary/shape.md, open-mr.md, ...)
#   needs    artifact kinds an earlier step must produce. The brief is always
#            there, so plan-feature ("a brief") and shape ("a brief or a
#            plan") need nothing a sequence has to supply.
#   produces the artifact kind, or None (self-review's verdict lands on the MR)
#   stage    the SDA phase a row reports (sda-profile-glados-v2.1.md)
#   review   the `review:` values a step-options entry may set; empty = the
#            key is not allowed. spec-feature already runs an in-context
#            persona pass, so only `none` or `fresh-agent` add anything; the
#            stages that act on code or the MR have review loops of their own.
#   default-review  what applies when step-options says nothing
_ANY_REVIEW = ("none", "in-context", "fresh-agent")
BUILTIN_STEPS = {
    "plan-feature": {"runs": "core", "needs": (), "produces": "plan",
                     "stage": "planning", "review": _ANY_REVIEW,
                     "default-review": "none"},
    "shape": {"runs": "library", "needs": (), "produces": "shape",
              "stage": "speccing", "review": _ANY_REVIEW,
              "default-review": "in-context"},
    "spec-feature": {"runs": "core", "needs": ("plan",), "produces": "spec",
                     "stage": "speccing", "review": ("none", "fresh-agent"),
                     "default-review": "none"},
    "implement-feature": {"runs": "core", "needs": ("spec",),
                          "produces": "change", "stage": "implementing",
                          "review": (), "default-review": "none"},
    "verify-feature": {"runs": "core", "needs": ("spec", "change"),
                       "produces": "verification", "stage": "verifying",
                       "review": (), "default-review": "none"},
    "open-mr": {"runs": "library", "needs": ("change",), "produces": "mr",
                "stage": "verifying", "review": (), "default-review": "none"},
    "self-review": {"runs": "library", "needs": ("mr",), "produces": None,
                    "stage": "verifying", "review": (),
                    "default-review": "none"},
}

# Closed key and value sets. Unknown keys are fatal here (unlike unknown
# top-level manifest keys, which only warn): these declarations drive gating,
# so a misspelt `modifer: optional` must never leave a step silently required
# or a gate silently ungated.
STEP_KEYS = ["description", "kind", "stage", "produces", "audits"]
STEP_KINDS = ["produce", "gate", "change"]
STEP_STAGES = ["planning", "speccing", "implementing", "verifying"]
# What a `produce` step may declare: every kind but `change` (a `change`
# step produces it) and `mr` (only open-mr opens one).
STEP_PRODUCES = [k for k in ARTIFACT_KINDS if k not in ("change", "mr")]
PIPELINE_KEYS = ["description", "when", "sequence", "step-options"]
STEP_OPTION_KEYS = ["modifier", "when", "review", "checkpoint"]
STEP_MODIFIERS = ["required", "optional", "advisory"]
STEP_REVIEWS = list(_ANY_REVIEW)
STEP_CHECKPOINTS = ["none", "record", "human"]

# Names a step id or pipeline name may never take, beyond CORES, the aliases
# and the built-in steps, each with the reason V1's error gives: the runner
# itself (named apart from the other cores, since a pipeline named after it
# reads as the runner) and the plugin's hand-written init skill. A
# pipeline's name becomes a command in script installs, so a collision would
# shadow a real workflow.
RESERVED_STEP_NAMES = {
    "run-pipeline": "the workflow that runs pipelines",
    "init": "the Claude Code plugin's init skill",
}

# Antigravity truncates workflow descriptions at 250 characters, and a
# pipeline's description becomes its shortcut command's description.
PIPELINE_DESCRIPTION_MAX = 250

KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Where a project step's body lives, relative to the target repo.
STEPS_DIR = "product-knowledge/steps"

# ---- canon: the reference works a project holds as authoritative -----------
#
# `canon:` maps a kebab-case name to a citation (`source`), an optional `url`
# and the repo-relative path of a DIGEST: the team's own summary, one
# `## <principle-id>` section per principle. Compiled text
# (vocabulary/canon.md) tells the agent to read the digest at fixed consult
# points and never to fetch the URL during a run, so the compiler checks the
# declaration and never reads, copies or hashes a digest. Lane 2, like
# `pipelines:`: editing the block never makes the compile stale.
#
# The consult points: the workflows whose documents carry the fragment, plus
# the shape step run-pipeline runs. A project step id is a consult point too
# (check_canon adds the declared ones), because run-pipeline consults canon
# while a project step runs. implement-feature is deliberately absent: it
# builds what the spec says, and the spec already names the principles it
# relies on.
CANON_CONSULT_POINTS = ["plan-feature", "shape", "spec-feature",
                        "verify-feature", "review-mr", "review-codebase",
                        "brunch"]
# What an entry with no `applies-to` / `seats` gets. review-codebase and
# brunch are opt-in: an audit or a roundtable judging the whole codebase
# against every canon entry by default would bury the findings that matter.
CANON_DEFAULT_APPLIES_TO = ["plan-feature", "shape", "spec-feature",
                            "verify-feature", "review-mr"]
CANON_DEFAULT_SEATS = ["philosophy"]
# Closed, like the pipeline keys: `applies-to` and `seats` route a principle
# to the reviewers who apply it, so a misspelt `seat:` must never leave an
# entry silently routed by default.
CANON_ENTRY_KEYS = ["source", "url", "digest", "applies-to", "seats"]
# The standing review lenses (vocabulary/panel-roster.md), by the names a
# `seats:` list uses. The other seats are persona file stems.
STANDING_LENSES = ["uat", "adversarial", "standards", "philosophy",
                   "dead-code"]
CANON_DIR = "product-knowledge/canon"
PROJECT_PERSONAS_DIR = "product-knowledge/personas"
# Doctor's digest checks, which the template and the steward pass state too.
CANON_DIGEST_MAX_WORDS = 1000
CANON_STALE_DAYS = 180

# Directories whose files gate agent runs or weigh in reviews, so CODEOWNERS
# should cover them as it covers glados.yaml: doctor reports each one a
# project uses, with why it matters. A step body can loosen a gate as surely
# as glados.yaml can; a digest decides what reviews hold a change to.
GATING_DIRS = {
    STEPS_DIR + "/": "the step files gate pipeline runs",
    CANON_DIR + "/": "the canon digests weigh in reviews",
}

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

INSTALL_MODES = ["claude", "claude-plugin", "direct", "gemini", "antigravity", "aistudio", "pi"]

INCLUDE_RE = re.compile(r"<!--\s*glados:include\s+(\S+?)\s*-->")

# Forbidden substrings in COMPILED core output (lint check 5).
FORBIDDEN_TOKENS = ["{{", "<!-- glados:include", "Invoke module", "OPTIMIZE_FOR"]

# Backticked `params.<ns>.<key>` literals in compiled text must resolve in the
# resolved manifest (type check 8) — a dangling literal is an unbounded loop.
PARAMS_LITERAL_RE = re.compile(r"`(params\.[a-z][a-z-]*\.[a-z][a-z-]*)`")

# The marker every generated claude-plugin SKILL.md stub carries. Skill pruning
# is marker-based: only a dir whose SKILL.md contains this string is ours to
# remove — user-authored skills are structurally untouchable.
PLUGIN_STUB_MARKER = "${CLAUDE_PLUGIN_ROOT}/compiled/claude-plugin/"

# Prepended to every claude-plugin compiled core. The plugin surface compiles
# from glados.yaml.example (there is no consuming repo at compile time), so
# these artifacts must never present the example's phase-resolved policy as
# the consumer's own: the compiler stamps the phase-neutral baseline
# optimize-for instead, and this guard makes the consuming repo's manifest
# govern at run time.
#
# A plugin-only repo also has no `.glados/` tree — nothing vendored it — so
# the second paragraph maps the three vendored files compiled text points at
# (the preset table that supplies defaults for keys the manifest omits, the
# library personas, and the toolchain run-pipeline validates with) onto the
# plugin's own copies. It names exactly those three: a blanket "anything
# missing under .glados/" would also cover the run records and `.glados/runs/`
# markers, which are missing by design on a first run and must be created in
# the project, never read from the plugin. The plugin root is located
# relative to this file, never through ${CLAUDE_PLUGIN_ROOT}: that variable
# is expanded in SKILL.md stubs, not in the compiled file the agent reads.
#
# The plugin compiles from the example, whose `pipelines:`/`steps:`/`canon:`
# blocks are commented out, so it cannot compile a project's pipelines or see
# its canon; the guard names them among the keys the project's own manifest
# supplies at run time.
PLUGIN_BOOTSTRAP_GUARD = (
    "<!-- claude-plugin bootstrap guard — this artifact was compiled from\n"
    "     glados.yaml.example, not from the repo it runs in. -->\n"
    "**Bootstrap guard.** This workflow was compiled from `glados.yaml.example`,\n"
    "not this repo's manifest. Before step 1: if this repo has a `glados.yaml`,\n"
    "read it now — its `phase:`, decision rights, channels, merge authority,\n"
    "params, any project workflows and steps (`pipelines:`, `steps:`) and\n"
    "any canon (`canon:`) govern this run wherever they differ from the text\n"
    "below. If it has no `glados.yaml`, copy `glados.yaml.example` to\n"
    "`glados.yaml` (or run `/glados:init`) and set `phase:` before doing\n"
    "consequential work — do not guess a phase.\n\n"
    "**Plugin paths.** This repo may have no `.glados/` directory. Three\n"
    "read-only files then come from the plugin's own copy at the plugin root\n"
    "(two levels above this file, the directory that holds\n"
    "`compiled/claude-plugin/`): when `.glados/presets.yaml` is missing, the\n"
    "preset table is `src/kernel/presets/phases.yaml` there; when\n"
    "`.glados/personas/` is missing, the library personas are `src/personas/`\n"
    "there; and when `.glados/glados.py` is missing, the toolchain is\n"
    "`bin/glados.py` there. Project personas in `product-knowledge/personas/`\n"
    "still win a name collision. Run records and the `.glados/runs/` markers\n"
    "always live in this repo: create them here, never in the plugin.\n\n"
)

# SDA (Structured Development Artifacts) — the version header stamped on
# conformant docs and the marker that makes the prepend idempotent. The
# manifest key `sda:` is an EXPLICIT-ONLY bool (a team declaration, default
# false): phase presets may never set it (_check_phase_invariants rejects
# one that tries), and `sda: true` scaffolds the conformance artifacts at
# install time (scaffold_sda, create-only). See docs/guides/sda.md.
SDA_MARKER = "SDA: v1.0"
SDA_HEADER = f"<!-- {SDA_MARKER} -->\n\n"

# The complete v1 name sets, for legacy-cleanup and v1-detection only. v1's
# direct mode installed these under product-knowledge/{workflows,modules}/;
# only files matching these names (or their underscore variants) may be
# removed from those shared directories — never unmatched user files.
KNOWN_V1_WORKFLOWS = frozenset({
    "address-review", "adopt-codebase", "autonomous-loop", "build-feature",
    "consolidate", "establish-standards", "identify-bug", "implement-feature",
    "implement-fix", "mission", "plan-feature", "plan-fix", "plan-product",
    "recombobulate", "retrospect", "review-codebase", "review-mr", "run-epic",
    "spec-feature", "verify-feature", "verify-fix",
})
KNOWN_V1_MODULES = frozenset({
    "capabilities", "evaluator-handoff", "evaluator-spawn", "interaction-proxy",
    "mr-review-panel", "observability", "pattern-observer", "persona-context",
    "persona-review", "standards-gate",
})

# migrate: markers that identify a v2-GENERATED artifact (a compiled core's
# provenance header, or an alias shim's rename sentence). The v1 and v2 name
# sets overlap (plan-feature is both a v1 workflow and a v2 core), so the
# v1 -> v2 migrate command may treat a name-matched file as a v1 leftover
# only when its CONTENT carries no v2 marker.
V2_ARTIFACT_MARKERS = ("GLaDOS v2 compiled artifact", "workflow was renamed")

# The phase line `migrate` writes into a generated glados.yaml. It parses to
# null in the YAML subset, so the very next install still fails fast with the
# four-phase message — migrate removes the blank-page problem without ever
# choosing a phase for the team.
MIGRATE_PHASE_LINE = ("phase: # REQUIRED - pick one: " + " | ".join(PHASES)
                      + " (who gets hurt when the agent is wrong; "
                        "see MIGRATION.md)")

# Advisory (never blocking) checklists printed when an install crosses a phase
# boundary relative to the previously vendored assembly report.
PHASE_TRANSITION_CHECKLISTS = {
    "nascent": [
        "confirm there are no users left to harm — nascent relaxes nearly "
        "every default",
    ],
    "evolving": [
        "standards tree seeded (product-knowledge/standards/) so the "
        "standards-gate has teeth",
        "review cadence agreed — verdicts land on MRs and someone reads them",
    ],
    "production": [
        "smoke suite seeded and green before the first production run",
        "CI check made blocking (drop --report-only in the .glados/ci/ job)",
        "escalation sink human-visible (channels.escalation reaches a queue "
        "a human triages)",
    ],
    "sunset": [
        "build-feature and run-pipeline are disabled by the sunset preset — "
        "confirm no epic still depends on them",
        "every removal lands with a `decision` outcome visible on its "
        "MR/issue",
    ],
}


class Fatal(Exception):
    """A fatal, user-facing error. Message must name the file/key AND the fix."""


class CheckFailed(Fatal):
    """The install-time type checks failed. ``errors`` keeps each finding on
    its own so `validate` can list them; the message is the one install and
    check have always printed."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("install checks failed:\n  - "
                         + "\n  - ".join(self.errors))


# =============================================================================
# 2. PARSER — a YAML subset with line-numbered errors
# =============================================================================
#
# Supported subset (enough for the restricted GLaDOS schema and no more):
#   * block maps and block lists, 2-space indentation
#   * lists of maps: `- key: value` opens a mapping item whose later keys
#     align with `key` (as in standard YAML); bare `-` + an indented map too
#   * one-line flow lists: [a, b], [], a trailing comma
#   * scalars: plain, one-line single/double quoted (every YAML escape),
#     integers, true/false/null
#   * block scalars: > >- | |- (folded / literal, clip / strip chomping), as
#     a mapping value or a list item
#   * comments: '#' at line start or after a space, outside quotes
#
# What the parser accepts, it reads as a YAML reader does, or it refuses it.
# The agent reads glados.yaml and the preset table as YAML at run time, so a
# document the two read differently passes every check here while the run
# obeys something else. YAML syntax kept as text did exactly that:
# `&a max-cycles: true` (an anchor), `!!str max-cycles` (a tag),
# `"max\x2Dcycles"` (an escape) and a `<<:` merge key were keys no check
# reads, and YAML reads each as max-cycles. So the parser decodes every YAML
# escape and refuses anchors, aliases, tags, merge keys, explicit keys,
# reserved indicators, block-scalar indentation numbers, text after a closing
# quote, `k:v` (one plain scalar to YAML), ': ' inside an unquoted value (an
# error to YAML), a key YAML reads as a null, bool, number or date, an
# integer with a leading zero (octal to YAML 1.1), a tab outside quotes,
# lines left of the first line (it used to drop them), a line after a block
# scalar deeper than its key (it used to read that into the text), and
# characters YAML does not allow. A value YAML would type (yes, 1.5,
# 2026-10-22) stays the text it is written as; every check that wants a
# number or bool refuses it.
# Anything outside the subset raises YamlError('<file>:<line>: <reason>').


class YamlError(Fatal):
    pass


# What YAML reads a scalar's first character as when it is one of these: it
# is syntax, never text. A key may start with none of them; a value reaches
# this check only after quotes, `[`, `{`, `#` and block headers are handled.
_INDICATOR_WHAT = {
    "&": "an anchor", "!": "a tag", "*": "an alias", "%": "a directive",
    "@": "a reserved indicator", "`": "a reserved indicator",
    "?": "an explicit key", ":": "a mapping value", "-": "a list item",
    ",": "flow syntax", "[": "a flow list", "]": "flow syntax",
    "{": "a flow mapping", "}": "flow syntax", "|": "a block scalar",
    ">": "a block scalar", "#": "a comment",
}

# YAML's escapes in a double-quoted scalar (YAML 1.2 section 5.7, the set
# PyYAML reads too). Any other backslash is an error to YAML, and here.
_DQ_ESCAPES = {
    "0": "\x00", "a": "\x07", "b": "\x08", "t": "\t", "\t": "\t", "n": "\n",
    "v": "\x0b", "f": "\x0c", "r": "\r", "e": "\x1b", " ": " ", '"': '"',
    "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0", "L": "\u2028",
    "P": "\u2029",
}
_DQ_HEX = {"x": 2, "u": 4, "U": 8}

# Characters YAML does not allow in a document (a reader refuses the whole
# file), plus the three that YAML 1.1 reads as line breaks and YAML 1.2 as
# text: a reader and this parser would not agree on either.
_YAML_UNREADABLE = re.compile(
    "[^\t\n\x20-\x7e\xa0-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]"
    "|[\u2028\u2029]")

# A plain scalar YAML 1.1 or 1.2 reads as something other than text: null, a
# bool (yes/no/on/off and y/n too, in 1.1), a number in any base or with
# underscores, a float, a date. The parser reads every key as text, so
# `null:` and `~:` were two keys here and one to YAML, and `1:` and `01:`
# likewise; a key like these is refused. (A value like these stays the text
# it is written as: every check that wants a number or a bool refuses it.)
_YAML_NON_TEXT = re.compile(r"""
      ~ | null | Null | NULL
    | y | Y | yes | Yes | YES | n | N | no | No | NO
    | true | True | TRUE | false | False | FALSE | on | On | ON | off | Off | OFF
    | [-+]? [0-9][0-9_]* (?: :[0-5]?[0-9] )*
    | [-+]? 0b[01_]+ | [-+]? 0o[0-7_]+ | [-+]? 0x[0-9a-fA-F_]+
    | [-+]? (?: [0-9][0-9_]* )? \. [0-9_]* (?: [eE][-+]?[0-9]+ )?
    | [-+]? [0-9][0-9_]* [eE][-+]?[0-9]+
    | [-+]? \. (?: inf | Inf | INF ) | \. (?: nan | NaN | NAN )
    | [0-9]{4}-[0-9]{1,2}-[0-9]{1,2} (?: [Tt ].* )?
""", re.X)


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_list_line(line: str) -> bool:
    s = line.strip(" ")
    return s == "-" or s.startswith("- ")


def _comment_at(s: str, j: int) -> bool:
    """s[j] starts a comment: a '#' at the line start or after a space.
    Only a space separates tokens here: YAML readers disagree about a tab
    outside quotes (PyYAML refuses one anywhere there), so a tab stays in
    the text around it and _plain_problem refuses that text."""
    return s[j] == "#" and (j == 0 or s[j - 1] == " ")


def _strip_comment(s: str) -> str:
    """A plain scalar's text: up to a comment, trailing spaces off."""
    for j in range(len(s)):
        if _comment_at(s, j):
            return s[:j].rstrip(" ")
    return s.rstrip(" ")


def _expect_end(s: str, j: int, after: str, filename: str,
                lineno: int) -> None:
    """Only spaces, or spaces and a comment, may follow s[:j]."""
    rest = s[j:]
    tail = rest.lstrip(" ")
    if tail and not (tail[0] == "#" and len(tail) < len(rest)):
        raise YamlError(f"{filename}:{lineno}: '{tail}' after {after} — "
                        f"quote the whole value, or start a comment with a "
                        f"space and '#'")


def _scan_quoted(s: str, i: int, filename: str, lineno: int) -> int:
    """The index just past the quoted scalar that opens at s[i]: a
    backslash escapes the next character inside double quotes, and '' is
    a quote inside single quotes."""
    q = s[i]
    j = i + 1
    while j < len(s):
        if s[j] == "\\" and q == '"':
            j += 2
        elif s[j] == q:
            if q == "'" and s[j + 1:j + 2] == "'":
                j += 2
            else:
                return j + 1
        else:
            j += 1
    raise YamlError(f"{filename}:{lineno}: unterminated quote in '{s[i:]}' "
                    f"— close it on the same line (the parser reads one-line "
                    f"quoted scalars only)")


def _unescape_double(s: str, filename: str, lineno: int) -> str:
    """A double-quoted scalar's body as YAML reads it."""
    out: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        esc = s[i + 1:i + 2]
        if esc and esc in _DQ_ESCAPES:
            out.append(_DQ_ESCAPES[esc])
            i += 2
            continue
        if esc and esc in _DQ_HEX:
            width = _DQ_HEX[esc]
            digits = s[i + 2:i + 2 + width]
            if len(digits) < width or any(
                    c not in "0123456789abcdefABCDEF" for c in digits):
                raise YamlError(f"{filename}:{lineno}: '\\{esc}{digits}': "
                                f"'\\{esc}' needs {width} hex digits (as in "
                                f"'\\{esc}{'2D'.rjust(width, '0')}')")
            code = int(digits, 16)
            if code > 0x10FFFF or 0xD800 <= code <= 0xDFFF:
                raise YamlError(f"{filename}:{lineno}: '\\{esc}{digits}' is "
                                f"not a character — write the character "
                                f"itself")
            out.append(chr(code))
            i += 2 + width
            continue
        raise YamlError(f"{filename}:{lineno}: '\\{esc}' is not a YAML escape "
                        f"— write a backslash as '\\\\', or use one of YAML's "
                        f"escapes ('\\n', '\\t', '\\\"', '\\xHH', '\\uHHHH')")
    return "".join(out)


def _quoted_scalar(tok: str, filename: str, lineno: int) -> str:
    if tok[0] == '"':
        return _unescape_double(tok[1:-1], filename, lineno)
    return tok[1:-1].replace("''", "'")


def _plain_problem(text: str, role: str):
    """Why YAML would not read plain ``text`` as that text, or None."""
    if "\t" in text:
        return (f"'{text.strip()}' has a tab outside quotes, which YAML "
                f"readers do not agree on — use spaces, or quote the {role}")
    if text == "<<":
        return ("'<<' is a YAML merge key, which copies another mapping's "
                "keys in — not supported here; write each key out")
    if text == "=":
        return f"'=' is a YAML 1.1 value key, not text — quote the {role}"
    c = text[0]
    if c in _INDICATOR_WHAT and (c != "-" or text[1:2] in ("", " ", "\t")):
        return (f"'{text}' starts with '{c}', which YAML reads as "
                f"{_INDICATOR_WHAT[c]}, not text — not supported here; "
                f"write the {role} itself, quoted if the '{c}' belongs to it")
    if re.search(r":(?:[ \t]|$)", text):
        return (f"'{text}' holds ': ', which YAML reads as a mapping, not "
                f"text — quote the {role}")
    return None


def _plain_scalar(text: str, filename: str, lineno: int, role: str,
                  flow: bool = False):
    problem = _plain_problem(text, role)
    if problem is None and flow and "?" in text:
        problem = (f"'{text}' holds '?', which YAML reads as a key inside a "
                   f"flow list — quote the item")
    if problem is not None:
        raise YamlError(f"{filename}:{lineno}: {problem}")
    if text in ("~", "null"):
        return None
    if text == "true":
        return True
    if text == "false":
        return False
    # [0-9], not \d: \d and int() take other scripts' digits too (U+0663,
    # ARABIC-INDIC DIGIT THREE, reads as 3), which YAML reads as text.
    if re.fullmatch(r"-?[0-9]+", text):
        if re.fullmatch(r"-?0[0-9]+", text):
            raise YamlError(f"{filename}:{lineno}: '{text[:12]}' has a leading "
                            f"zero, which YAML 1.1 reads as an octal number — "
                            f"write it without the zero, or quote it if it "
                            f"is text")
        try:
            return int(text)
        except ValueError:
            # Python reads at most 4300 digits; the ValueError used to
            # escape as a traceback from every command, doctor included.
            raise YamlError(f"{filename}:{lineno}: the number "
                            f"'{text[:12]}...' has {len(text)} digits, more "
                            f"than can be read — write a smaller number")
    return text


def _check_key(key: str, filename: str, lineno: int, plain: bool) -> str:
    """``key`` when every reader takes it as the same text, else YamlError.
    A key holding an invisible control or format character (`\\0`, a
    zero-width space) is another key to YAML, and to every check here, but
    reads as the visible one to an agent looking at the text."""
    if key == "<<":
        raise YamlError(f"{filename}:{lineno}: '<<' is a YAML merge key, which "
                        f"copies another mapping's keys in — not supported "
                        f"here; write each key out")
    if plain:
        if key == "":
            raise YamlError(f"{filename}:{lineno}: a mapping key is empty — "
                            f"write 'key: value'")
        problem = _plain_problem(key, "key")
        if problem is None and _YAML_NON_TEXT.fullmatch(key):
            problem = (f"the key '{key}' is a null, a bool, a number or a "
                       f"date to YAML, not text — quote it (\"{key}\") if "
                       f"it is a name")
        if problem is not None:
            raise YamlError(f"{filename}:{lineno}: {problem}")
    hidden = next((c for c in key
                   if unicodedata.category(c) in ("Cc", "Cf")), None)
    if hidden is not None:
        raise YamlError(f"{filename}:{lineno}: the key {key!r} holds "
                        f"U+{ord(hidden):04X}, a character that does not "
                        f"show — write the key as plain text")
    return key


def _split_entry(s: str, filename: str, lineno: int):
    """(key, rest) when the line content ``s`` is a mapping entry as YAML
    reads it, else None (a lone scalar). The key ends at the first ':'
    followed by whitespace or the line end, outside quotes and before any
    comment: `"max-cycles": 3` is the key max-cycles, `a:b: c` the key
    a:b, and `k:v` one plain scalar. ``rest`` follows that ':'."""
    if s[:1] in ("'", '"'):
        end = _scan_quoted(s, 0, filename, lineno)
        k = end
        while k < len(s) and s[k] in " ":
            k += 1
        if s[k:k + 1] == ":" and s[k + 1:k + 2] in ("", " "):
            key = _quoted_scalar(s[:end], filename, lineno)
            return _check_key(key, filename, lineno, plain=False), s[k + 1:]
        _expect_end(s, end, "the closing quote", filename, lineno)
        return None
    for j, c in enumerate(s):
        if _comment_at(s, j):
            return None
        if c == ":" and s[j + 1:j + 2] in ("", " "):
            key = s[:j].rstrip(" ")
            return _check_key(key, filename, lineno, plain=True), s[j + 1:]
    return None


def _parse_flow_list(s: str, filename: str, lineno: int) -> list:
    """A one-line flow list opening at s[0]; only a comment may follow its
    closing ']'."""
    n = len(s)

    def blank(j: int) -> int:
        while j < n and s[j] in " ":
            j += 1
        return j

    def unterminated():
        return YamlError(f"{filename}:{lineno}: unterminated inline list "
                         f"'{s}' (the parser supports single-line flow lists "
                         f"only)")

    def nested():
        return YamlError(f"{filename}:{lineno}: nested flow collections are "
                         f"not supported inside [...] — use a block list "
                         f"(one '- item' per line)")

    items: list = []
    j = blank(1)
    if s[j:j + 1] == "]":
        _expect_end(s, j + 1, "']'", filename, lineno)
        return items
    while True:
        if j >= n or _comment_at(s, j):
            raise unterminated()
        if s[j] in "[{":
            raise nested()
        if s[j] in "\"'":
            end = _scan_quoted(s, j, filename, lineno)
            items.append(_quoted_scalar(s[j:end], filename, lineno))
            after = "the closing quote"
        else:
            end = j
            while end < n and s[end] not in ",]" and not _comment_at(s, end):
                if s[end] in "[{}":
                    raise nested()
                end += 1
            text = s[j:end].rstrip(" ")
            if not text:
                raise YamlError(f"{filename}:{lineno}: an empty item in '{s}' "
                                f"— remove the extra ','")
            items.append(_plain_scalar(text, filename, lineno, "item",
                                       flow=True))
            after = f"'{text}'"
        j = blank(end)
        if j >= n or _comment_at(s, j):
            raise unterminated()
        if s[j] == "]":
            _expect_end(s, j + 1, "']'", filename, lineno)
            return items
        if s[j] != ",":
            raise YamlError(f"{filename}:{lineno}: '{s[j:]}' after {after} "
                            f"in a flow list — quote the whole item")
        j = blank(j + 1)
        if s[j:j + 1] == "]":  # a trailing comma, as YAML allows
            _expect_end(s, j + 1, "']'", filename, lineno)
            return items


def _read_node(s: str, filename: str, lineno: int):
    """What follows `key:` or `- ` on a line, as YAML reads it: ("none",
    None) when nothing does (an indented block may follow), ("block",
    header) for a block scalar, or ("value", the value)."""
    s = s.strip(" ")
    if s == "" or s[0] == "#":
        return "none", None
    c = s[0]
    if c in "\"'":
        end = _scan_quoted(s, 0, filename, lineno)
        _expect_end(s, end, "the closing quote", filename, lineno)
        return "value", _quoted_scalar(s[:end], filename, lineno)
    if c == "[":
        return "value", _parse_flow_list(s, filename, lineno)
    if c == "{":
        raise YamlError(f"{filename}:{lineno}: flow mapping '{{...}}' is not "
                        f"supported — use a block map (nested 2-space-"
                        f"indented 'key: value' lines)")
    text = _strip_comment(s)
    if c in "|>":
        if re.fullmatch(r"[|>][+-]?", text):
            return "block", text
        raise YamlError(f"{filename}:{lineno}: block scalar header '{text}' "
                        f"is not supported — write '|', '|-', '>' or '>-' "
                        f"with no indentation number, and indent the text "
                        f"under it")
    return "value", _plain_scalar(text, filename, lineno, "value")


def parse_yaml(text: str, filename: str = "<yaml>"):
    """Parse the restricted YAML subset into Python dict/list/scalar values."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    n = len(lines)

    # YAML forbids tabs in indentation; silently misreading them re-parents
    # keys (a tab-indented sub-map becomes top-level keys). Fail loudly, on
    # a blank line too (YAML readers refuse that as well), and on any
    # character a YAML reader would refuse or read as a line break.
    for idx, line in enumerate(lines):
        bad = _YAML_UNREADABLE.search(line)
        if bad:
            raise YamlError(f"{filename}:{idx + 1}: character "
                            f"U+{ord(bad.group()):04X} is not text a YAML "
                            f"reader takes as written — remove it, or write "
                            f"it as an escape inside double quotes")
        lead = line[: len(line) - len(line.lstrip(" \t"))]
        if "\t" in lead:
            where = "on a blank line" if lead == line else "in indentation"
            raise YamlError(f"{filename}:{idx + 1}: tab character {where} "
                            f"— YAML forbids tabs; indent with 2 spaces")

    def skippable(i: int) -> bool:
        s = lines[i].strip(" \t")
        return s == "" or s.startswith("#")

    def next_meaningful(i: int) -> int:
        while i < n and skippable(i):
            i += 1
        return i

    def parse_block_scalar(i: int, parent_indent: int, style: str,
                           opener: str):
        """The block scalar whose text starts at line i, as YAML reads it.
        Its indent is its first text line's, or a blank line's above that
        when deeper (YAML takes the deepest), and the first line indented
        less ends it. That line is then read as what it is: a comment, the
        next key or item, or, deeper than ``opener`` (the key or '-' at
        ``parent_indent``), an error to YAML and here. It used to be read
        into the text with its first characters cut off, so the keys on
        it (`max-cycles: true`) vanished."""
        header = i  # 1-based: the line before i
        collected: list[str] = []
        base = None
        lead = parent_indent + 1  # deeper than the opener, at least
        blank_lead = 0            # the deepest blank line above the text
        first = 0                 # the first text line's indent
        while i < n:
            if lines[i].strip(" \t") == "":
                if base is None:
                    blank_lead = max(blank_lead, len(lines[i]))
                collected.append("")
                i += 1
                continue
            ci = _indent_of(lines[i])
            if base is None:
                first = ci
                base = max(ci, lead, blank_lead)
            if ci < base:
                break
            collected.append(lines[i][base:])
            i += 1
        after = next_meaningful(i)
        if after < n and _indent_of(lines[after]) > parent_indent:
            def spaces(k: int) -> str:
                return f"{k} space" + ("" if k == 1 else "s")
            if parent_indent < first < blank_lead:
                why = (f": a blank line above its text has "
                       f"{spaces(blank_lead)}, and YAML takes the scalar's "
                       f"indent from the deepest such line")
                fix = "remove the spaces from that blank line"
            else:
                kind = " a comment" if after != i else ""
                why = (f",{kind} indented less than its text "
                       f"({spaces(base)})")
                fix = (f"indent every line of the scalar at least "
                       f"{spaces(base)}, comments included, or outdent this "
                       f"line to a key's indent")
            raise YamlError(f"{filename}:{after + 1}: YAML refuses this "
                            f"line: the block scalar that line {header} "
                            f"opens ended at line {i + 1}{why}, and nothing "
                            f"after the scalar may sit deeper than its "
                            f"{opener} ({spaces(parent_indent)}) — {fix}")
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

    def nested_block(i: int, parent_indent: int):
        """The block an entry with nothing after its ':' (or a bare '-')
        holds: an indented map or list, else null."""
        j = next_meaningful(i)
        if j < n and _indent_of(lines[j]) > parent_indent:
            return parse_list(j) if _is_list_line(lines[j]) else parse_map(j)
        return None, i

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
            lineno = i + 1
            content = lines[i].strip(" ")
            if _is_list_line(content):
                raise YamlError(f"{filename}:{lineno}: list item under a mapping")
            entry = _split_entry(content, filename, lineno)
            if entry is None:
                raise YamlError(f"{filename}:{lineno}: expected 'key: value', "
                                f"got '{_strip_comment(content)}'")
            key, rest = entry
            if key in result:
                raise YamlError(f"{filename}:{lineno}: duplicate key '{key}' — "
                                f"the earlier value would be silently "
                                f"overwritten; remove one of the definitions")
            i += 1
            kind, value = _read_node(rest, filename, lineno)
            if kind == "none":
                result[key], i = nested_block(i, base)
            elif kind == "block":
                result[key], i = parse_block_scalar(i, base, value, "key")
            else:
                result[key] = value
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
            content = lines[i].strip(" ")
            if not _is_list_line(content):
                break
            lineno = i + 1
            item = content[1:].strip(" ")
            if item[:1] not in ("[", "{") and \
                    _split_entry(item, filename, lineno) is not None:
                # `- key: value` starts a MAPPING item (standard YAML), not
                # the string 'key: value'. The map's indent is the column of
                # `key`; following keys aligned with it continue the same
                # map, and blocks nested under them work as in any block map.
                # Blank out the dash in place and hand the line to parse_map,
                # which then sees an ordinary map starting at that column. A
                # sibling '- ' line sits left of the map's column, so
                # parse_map stops there and this loop takes the next item.
                raw_line = lines[i]
                lines[i] = raw_line[:ci] + " " + raw_line[ci + 1:]
                sub, i = parse_map(i)
                result.append(sub)
                continue
            i += 1
            kind, value = _read_node(item, filename, lineno)
            if kind == "none":
                value, i = nested_block(i, base)
            elif kind == "block":
                value, i = parse_block_scalar(i, base, value, "'-'")
            result.append(value)
        return result, i

    start = next_meaningful(0)
    if start >= n:
        return {}
    value, end = (parse_list(start) if _is_list_line(lines[start])
                  else parse_map(start))
    rest = next_meaningful(end)
    if rest < n:
        # YAML refuses a document whose later lines sit left of its first,
        # or a list followed by a key; the parser used to drop them.
        raise YamlError(f"{filename}:{rest + 1}: this line does not continue "
                        f"the document that line {start + 1} starts — indent "
                        f"every top-level key the same, from the first")
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
        # Type-validate the frontmatter fields the compiler consumes. A wrong
        # shape here otherwise surfaces as a raw AttributeError deep inside an
        # adapter (or, worse, a str silently list()-ed into characters).
        desc = fm.get("description", name)
        if not isinstance(desc, str):
            raise Fatal(f"{path}: frontmatter field 'description' must be a "
                        f"one-line string, got {type(desc).__name__} — quote it")
        lists: dict[str, list] = {}
        for field in ("reads", "writes", "emits", "requires"):
            val = fm.get(field)
            if val is None:
                lists[field] = []
            elif isinstance(val, str):
                raise Fatal(f"{path}: frontmatter field '{field}' must be a "
                            f"list of strings, got the bare string '{val}' — "
                            f"write [{val}] or a '- item' block list")
            elif isinstance(val, list) and all(isinstance(x, str) for x in val):
                lists[field] = list(val)
            else:
                raise Fatal(f"{path}: frontmatter field '{field}' must be a "
                            f"list of strings — got {val!r}")
        return {
            "name": name,
            "path": path,
            "frontmatter": fm,
            "body": body,
            "reads": lists["reads"],
            "writes": lists["writes"],
            "emits": lists["emits"],
            "requires": lists["requires"],
            "description": desc,
        }

    # -- registry helpers -----------------------------------------------------
    def registry_keys(self) -> set[str]:
        return set((self.registry.get("keys") or {}).keys())

    def outcome_types(self) -> set[str]:
        return set(self.registry.get("outcome-types") or [])

    def manifest_keys(self) -> set[str]:
        keys = self.registry.get("keys") or {}
        return {k for k, v in keys.items() if isinstance(v, dict) and v.get("home") == "manifest"}

    def human_written_keys(self) -> set[str]:
        """Keys a person writes: every manifest key, plus a repo key marked
        `writer: human` (the canon digests). Reading one never needs an
        enabled workflow to write it: the digest readers do not depend on
        steward, which also refreshes the digests, being enabled."""
        keys = self.registry.get("keys") or {}
        return self.manifest_keys() | {
            k for k, v in keys.items()
            if isinstance(v, dict) and v.get("writer") == "human"}


def include_fragment(source: Source, rel: str, _stack: tuple, seen: set) -> str:
    if rel in _stack:
        chain = " -> ".join(_stack + (rel,))
        raise Fatal(f"glados:include cycle: {chain} — remove one of the "
                    f"includes to break the loop")
    if len(_stack) > 16:
        raise Fatal(f"glados:include recursion too deep at '{rel}' (chain: "
                    f"{' -> '.join(_stack)}) — flatten the fragment nesting")
    root = source.src.resolve()
    path = (source.src / rel).resolve()
    if not path.is_relative_to(root):
        raise Fatal(f"glados:include escapes the source tree: '{rel}' resolves "
                    f"to {path}, outside {root} — includes must stay within "
                    f"src/")
    if not path.exists():
        raise Fatal(f"dangling glados:include '{rel}' — no file at {path}; add "
                    f"the fragment or remove the directive")
    frag = read_text(path)
    if rel in seen:
        # Already inlined earlier in THIS document. A fragment reaches one
        # core by more than one route whenever a workflow includes it and so
        # does a module the workflow seats; inlining it twice made the one
        # document a panelist reads as its whole brief longer without making
        # it more correct.
        #
        # What replaces the second copy is a pointer, not nothing. The text
        # around an include was written to introduce it, and a site that
        # silently vanishes leaves that text introducing whatever happens to
        # come next — in 2.3.1 an evaluator brief said "the rules below,
        # copied verbatim" over a blank line and the next heading. The pointer
        # names the fragment by its heading, so every lead-in still has a
        # referent however the document happened to be assembled.
        #
        # Which copy survives is decided by emission order, documented at
        # ``compile_core``: the first one emitted.
        return _pointer_to(rel, frag)
    seen.add(rel)
    return resolve_includes(source, frag, _stack + (rel,), seen=seen)


def _pointer_to(rel: str, frag: str) -> str:
    """One line naming a fragment that is already in the document."""
    heading = re.search(r"^#{1,6}\s+(.+?)\s*$", frag, re.MULTILINE)
    name = heading.group(1) if heading else Path(rel).stem
    return f"*(See **{name}**, earlier in this document.)*"


def resolve_includes(source: Source, text: str, _stack: tuple = (), *,
                     seen: set) -> str:
    """Inline every ``glados:include`` in ``text``.

    ``seen`` is required and scopes de-duplication to one compiled document:
    pass a fresh set per core and share it across that core's body and its
    modules. There is deliberately no "inline everything" mode — every
    compiled document de-duplicates, and a default that silently did not
    would be the path nothing tests.
    """
    return INCLUDE_RE.sub(
        lambda m: include_fragment(source, m.group(1), _stack, seen), text
    )


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
    # An unknown value compares as "not laxer". That is safe only because
    # run_type_checks rejects a decision value outside DECISION_ORDER as a
    # fatal error of its own — without that check a typo ('agnet') would
    # slip past the relaxation check silently.
    try:
        return order.index(a) > order.index(b)
    except ValueError:
        return False


def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise Fatal(f"no manifest at {path} — copy glados.yaml.example to "
                    f"{path.name} in your repo root and edit it")
    return parse_manifest(read_text(path), path.name)


def parse_manifest(text: str, name: str) -> dict:
    raw = parse_yaml(text, name)
    if not isinstance(raw, dict):
        raise Fatal(f"{name}: the top level must be a mapping of "
                    f"'key: value' lines, got a {type(raw).__name__} — start "
                    f"from glados.yaml.example")
    return raw


def _require_name_list(value, where: str, origin: str, what: str) -> None:
    """Fail with a named fix unless ``value`` is None or a list of names.

    These lists (disabled-workflows, default-modules, workflows.<core>,
    channels.<outcome>, relaxation-acknowledged) feed set lookups long before
    the type checks run. The parser reads `- name: value` as a MAPPING item,
    as standard YAML does, so a stray colon would otherwise surface as an
    unhashable-dict TypeError instead of a sentence naming the key. A
    non-string scalar item (a number) stays legal here: it is hashable, and
    the token checks name it as an unknown workflow/module/sink."""
    if value is None:
        return
    if not isinstance(value, list):
        raise Fatal(f"{origin}: {where}: must be a list of {what} names — got "
                    f"{value!r}; write '[a, b]' or one '- name' per line")
    for idx, item in enumerate(value, 1):
        if isinstance(item, dict):
            shown = ", ".join(
                f"{k}: {'' if v is None else _fmt(v)}".rstrip()
                for k, v in item.items())
            raise Fatal(f"{origin}: {where}: item {idx} is a mapping "
                        f"('{shown}') — write one {what} name per '- ' line; "
                        f"'- name: value' is a mapping in YAML")
        if isinstance(item, list):
            raise Fatal(f"{origin}: {where}: item {idx} is a nested list "
                        f"({_fmt(item)}) — write one {what} name per item")


def resolve_manifest(raw: dict, presets: dict, manifest_name: str,
                     table_name: str = "phases.yaml") -> Resolved:
    phase = raw.get("phase")
    if phase is None:
        raise Fatal(f"{manifest_name}: required key 'phase:' is missing — set it "
                    f"to one of: {', '.join(PHASES)}")
    if phase not in PHASES:
        raise Fatal(f"{manifest_name}: phase '{phase}' is not valid — use one of: "
                    f"{', '.join(PHASES)}")

    plabel = f"phase:{phase}"
    # The layers are iterated below, so a layer out of shape (`baseline: 5`,
    # `decisions: [agent]`) escaped as an AttributeError or TypeError
    # traceback; it is a Fatal naming the table and the layer.
    for name, label in (("baseline", "baseline"), (phase, plabel)):
        layer = presets.get(name)
        if layer is not None and not isinstance(layer, dict):
            raise Fatal(f"{table_name}: '{name}:' must be a mapping of the "
                        f"keys it sets — got {layer!r}")
        for key in ("channels", "decisions", "params"):
            val = (layer or {}).get(key)
            if val is not None and not isinstance(val, dict):
                raise Fatal(f"{table_name} ({label}): {key}: must be a "
                            f"mapping of one 'name: value' line per entry — "
                            f"got {val!r}")
    baseline = presets.get("baseline") or {}
    preset = presets.get(phase) or {}
    r = Resolved()
    r.phase = phase
    r.raw = raw

    def layer_scalar(key: str):
        val, prov = baseline.get(key), "baseline"
        if key in preset:
            val, prov = preset[key], plabel
        if key in raw:
            val, prov = raw[key], "explicit"
        r.values[key] = val
        r.provenance[key] = prov

    # disabled-workflows layers like the scalars (an explicit list replaces the
    # preset list wholesale — [] re-enables everything a preset disabled), so a
    # phase preset CAN flip workflow existence (sunset unloads build-feature).
    for key in ("optimize-for", "merge-authority", "default-modules",
                "disabled-workflows"):
        layer_scalar(key)

    # channels + decisions: per-leaf layering
    for group in ("channels", "decisions"):
        if raw.get(group) is not None and not isinstance(raw.get(group), dict):
            raise Fatal(f"{manifest_name}: '{group}:' must be a mapping of "
                        f"one 'name: value' line per leaf — got "
                        f"{raw.get(group)!r}")
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

    # Shapes the compiler iterates or hashes before any type check runs. A
    # wrong shape here used to escape as a TypeError/AttributeError traceback
    # (and a hard exit from `check --report-only`, which never hard-exits);
    # it must be a Fatal naming the key. The origin names where the value
    # came from, so a malformed preset is not blamed on the manifest.
    def origin(key: str) -> str:
        prov = r.provenance.get(key, "explicit")
        return manifest_name if prov == "explicit" else f"{table_name} ({prov})"

    opt = r.values.get("optimize-for")
    if opt is not None and not isinstance(opt, str):
        raise Fatal(f"{origin('optimize-for')}: optimize-for: must be one "
                    f"sentence of text — got {opt!r}")
    for key, what in (("default-modules", "module"),
                      ("disabled-workflows", "workflow")):
        _require_name_list(r.values.get(key), key, origin(key), what)
    for leaf, sinks in r.values["channels"].items():
        _require_name_list(sinks, f"channels.{leaf}",
                           origin(f"channels.{leaf}"), "sink")
    for key in ("workflows", "params"):
        if raw.get(key) is not None and not isinstance(raw.get(key), dict):
            raise Fatal(f"{manifest_name}: '{key}:' must be a mapping of one "
                        f"'name: value' line per entry — got {raw.get(key)!r}")
    for wf, mods in (raw.get("workflows") or {}).items():
        _require_name_list(mods, f"workflows.{wf}", manifest_name, "module")
    _require_name_list(raw.get("relaxation-acknowledged"),
                       "relaxation-acknowledged", manifest_name, "key")

    # params: deep-ish merge (baseline<phase<explicit), review-panel.max-cycles tracked
    params: dict = {}
    for layer, label in ((baseline, "baseline"), (preset, plabel), (raw, "explicit")):
        for ns, cfg in (layer.get("params") or {}).items():
            params.setdefault(ns, {})
            if isinstance(cfg, dict):
                for k, v in cfg.items():
                    params[ns][k] = v
                    r.provenance[f"params.{ns}.{k}"] = label
            elif cfg is not None:
                # Merging skips it, so `pipeline: 5` would leave the
                # inherited bound in force without a word.
                where = (manifest_name if label == "explicit"
                         else f"{table_name} ({label})")
                raise Fatal(f"{where}: params.{ns}: must be a mapping of one "
                            f"'key: value' line per parameter (such as "
                            f"'max-cycles: 3') — got {cfg!r}")
    r.values["params"] = params

    # pass-through explicit-only keys. `sinks:` is project-declared like
    # branching: presets never set it (it is not in the anti-inflation
    # allowlist), and its bodies are freeform config the agent interprets at
    # run time — the compiler only checks structure and referential integrity.
    #
    # `pipelines:` and `steps:` are the same kind of key: the team's own
    # declarations (EXPLICIT_ONLY_KEYS), read live by run-pipeline. The
    # compiler checks them (check_pipelines) and emits one shortcut command
    # per pipeline, but compiles none of their contents into a core.
    # `canon:` too: read live at the consult points, checked by check_canon,
    # never compiled (a digest's text never enters an installed file).
    for key in ("platform", "phase", "branching", "workflows", "sinks",
                "visibility-acknowledged", "relaxation-acknowledged",
                "pipelines", "steps", "canon"):
        if key in raw:
            r.values[key] = raw[key]
            r.provenance[key] = "explicit"

    # sda: EXPLICIT-ONLY bool, default false. Conformance is a team
    # declaration, not a phase default — a preset naming it is rejected by
    # _check_phase_invariants; here only the manifest's own word counts.
    sda = raw.get("sda", False)
    if not isinstance(sda, bool):
        raise Fatal(f"{manifest_name}: key 'sda' must be a bool — got "
                    f"{sda!r}; write 'sda: true' or 'sda: false' (SDA "
                    f"conformance is declared, never implied)")
    r.values["sda"] = sda
    r.provenance["sda"] = "explicit" if "sda" in raw else "default"

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


def structural_projection(raw: dict) -> dict:
    """The lane-1 slice of a parsed manifest: exactly what the compiled output
    depends on. ``{key: raw[key]}`` for every STRUCTURAL_KEYS entry the
    manifest SETS; an absent key is left out.

    Absent and an explicit null must hash differently, because
    resolve_manifest treats them differently: an absent key takes the phase
    preset's value, while `default-modules:` with no value overrides the
    preset with null (no modules). Projecting `raw.get(key)` hashed both as
    None, so switching between them changed the compiled cores without
    moving the hash (check reported drift, doctor said "current").

    Derived projections of lane-2 blocks join here when they shape emitted
    files — under their own key, never the whole block. Today that is
    `pipelines:`: each pipeline's name and description shape the shortcut
    command script installs emit for it, so they are hashed, while its
    `when:`, `sequence:` and `step-options:` (and every `steps:` entry) stay
    live: run-pipeline reads them at run time, and editing them never makes
    the compile stale. Same present-keys rule: an absent block adds nothing.
    `canon:` shapes no emitted file at all (no shim, no compiled text), so
    nothing of it is projected.
    """
    proj = {key: raw[key] for key in STRUCTURAL_KEYS if key in raw}
    if "pipelines" in raw:
        proj["pipelines"] = _pipeline_name_projection(raw["pipelines"])
    return proj


def _pipeline_name_projection(pipelines):
    """``{name: description}`` of a `pipelines:` block — exactly what the
    per-pipeline shims are built from. A malformed block (the type checks
    report it) still projects to something hashable instead of raising."""
    if not isinstance(pipelines, dict):
        return None
    return {name: (cfg.get("description") if isinstance(cfg, dict) else None)
            for name, cfg in pipelines.items()}


def structural_hash(raw: dict) -> str:
    """sha256 of the canonical JSON of the structural projection. Sorted keys
    and fixed separators make it independent of key order, comments and
    whitespace in glados.yaml; only a changed structural VALUE moves it."""
    canonical = json.dumps(structural_projection(raw), sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def manifest_hash_of(path: Path) -> str:
    """Parse the manifest at ``path`` and hash its structural keys.

    This hash is what every compiled header and .glados/manifest-hash carry,
    and what `check` compares. It used to hash the whole file, which made
    every lane-2 edit (a sink, a channel, a param) fail `check` as a stale
    compile — the opposite of the lane-2 promise. A parse error raises the
    parser's Fatal (file:line plus the fix)."""
    return structural_hash(load_manifest(path))


def unknown_manifest_keys(raw: dict) -> list[str]:
    """Top-level manifest keys nothing reads, in manifest order."""
    return [k for k in raw if k not in KNOWN_MANIFEST_KEYS]


# `params` keys a release stopped reading, each with why. A manifest that
# still sets one resolves (it is only a value nothing reads), but a team that
# tuned it would otherwise get no signal that the tuning does nothing, and
# the assembly report would list it as a live setting.
RETIRED_PARAMS = {
    "pipeline.max-stalled-cycles": (
        "retired in 2.5 (v3): the first stalled check parks the step for a "
        "person, so no stall count is read"),
}


def retired_params(raw: dict) -> list[str]:
    """The retired `params.<ns>.<key>` paths the manifest sets, in order."""
    found = []
    params = raw.get("params")
    for ns, cfg in (params.items() if isinstance(params, dict) else ()):
        for k in (cfg if isinstance(cfg, dict) else ()):
            if f"{ns}.{k}" in RETIRED_PARAMS:
                found.append(f"{ns}.{k}")
    return found


def read_params(source) -> set[str]:
    """Every `<ns>.<key>` under params: that something reads: named in the
    workflow sources (`params.<ns>.<key>`), or set by a preset."""
    paths = set()
    for f in source.src.rglob("*.md"):
        paths.update(m.group(1) for m in re.finditer(
            r"params\.([a-z][a-z-]*\.[a-z][a-z-]*)", read_text(f)))
    for layer in source.presets.values():
        params = layer.get("params") if isinstance(layer, dict) else None
        for ns, cfg in (params.items() if isinstance(params, dict) else ()):
            paths.update(f"{ns}.{k}" for k in
                         (cfg if isinstance(cfg, dict) else ()))
    return paths


def unread_params(raw: dict, read: set) -> list[str]:
    """The `params.<ns>.<key>` paths the manifest sets that nothing reads
    (`max_cycles`, `run-pipeline.max-cycles`): a tightening that silently
    does nothing while the inherited bound stays in force."""
    params = raw.get("params")
    return [f"{ns}.{k}"
            for ns, cfg in (params.items() if isinstance(params, dict) else ())
            for k in (cfg if isinstance(cfg, dict) else ())
            if f"{ns}.{k}" not in read and f"{ns}.{k}" not in RETIRED_PARAMS]


def manifest_warnings(raw: dict, manifest_name: str,
                      source=None) -> list[str]:
    """Non-fatal findings about the manifest itself (never block an install).
    Unknown top-level keys, each named with the known set so a typo is one
    glance from its fix; retired `params` keys, each with why; and, given
    the source, `params` keys nothing reads."""
    known = ", ".join(KNOWN_MANIFEST_KEYS)
    read = read_params(source) if source is not None else None
    return [f"{manifest_name}: unknown top-level key '{k}' is ignored — check "
            f"the spelling (known keys: {known})"
            for k in unknown_manifest_keys(raw)] + [
            f"{manifest_name}: params.{path} is {RETIRED_PARAMS[path]}; "
            f"remove it" for path in retired_params(raw)] + [
            f"{manifest_name}: params.{path} is read by nothing, so it "
            f"changes nothing — check the spelling (read: "
            f"{', '.join(sorted(read))})"
            for path in (unread_params(raw, read) if read is not None
                         else ())]


def _print_warnings(warnings: list[str]) -> None:
    for w in warnings:
        print(f"glados: warning: {w}", file=sys.stderr)


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
    # One set for the whole document, so a fragment the core body and a
    # module both include is inlined once rather than once per route.
    #
    # EMISSION ORDER IS LOAD-BEARING. The body is resolved before its modules,
    # and de-duplication keeps the first copy emitted, so a fragment the
    # workflow includes for itself is the one that survives and a module's
    # copy becomes a pointer. Reorder these and every document still compiles
    # and still reads correctly — pointers name their fragment — but the
    # full text moves into whichever module happens to come first.
    seen: set = set()
    core_body = resolve_includes(source, core["body"], seen=seen).strip("\n")

    parts = [preamble, header, core_body]
    for m in modules:
        parts.append(
            resolve_includes(source, source.modules[m]["body"], seen=seen).strip("\n")
        )
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
        # Non-fatal findings (manifest_warnings and any later warning rules).
        # install/check print them; they never fail a command.
        self.warnings: list[str] = []


def compile_all(source: Source, r: Resolved, manifest_hash: str) -> Compilation:
    return Compilation(source, r, manifest_hash)


# =============================================================================
# 6. TYPE CHECKS — the fatal install-time checks
# =============================================================================


def _sinks_map(r: Resolved) -> dict:
    """The manifest's sinks: block as a dict, coerced to {} when malformed (a
    non-mapping is reported by run_type_checks; the helpers must not crash on it
    before that error surfaces)."""
    sinks = r.values.get("sinks")
    return sinks if isinstance(sinks, dict) else {}


def _declared_sinks(r: Resolved) -> set[str]:
    """Every sink name a channels: binding may reference: the built-ins plus
    whatever the manifest declares under sinks:."""
    return set(BUILTIN_SINKS) | set(_sinks_map(r).keys())


def _sink_is_team_visible(name: str, r: Resolved) -> bool:
    """Does delivery to this sink satisfy the team-visibility invariant? A
    built-in keeps its fixed classification (ledger is the only quiet one); a
    project-declared sink must say so itself.

    Fails CLOSED. run_type_checks requires `team-visible` on every declared
    sink, so a missing key here means the manifest did not pass checks (a
    --report-only run, or a malformed body reported separately) — and the safe
    reading of "we do not know whether anyone sees this" is that nobody
    does."""
    if name in BUILTIN_SINKS:
        return BUILTIN_SINKS[name]
    cfg = _sinks_map(r).get(name)
    if not isinstance(cfg, dict):
        return False
    return cfg.get("team-visible") is True


def run_type_checks(source: Source, comp: Compilation,
                    target: Path | None = None) -> list[str]:
    """Return a list of fatal error strings (empty == passes).

    ``target`` is the repo being installed into, when there is one: the few
    checks that read project files (a project step's body) run only then.
    Non-fatal findings are appended to ``comp.warnings``."""
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
    writers: set[str] = (set(PREAMBLE_OWNED_WRITES)
                         | source.human_written_keys())
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

    # ---- (2) sink bindings + zero-sink emits --------------------------------
    channels = r.values.get("channels") or {}
    sinks_cfg = r.values.get("sinks")
    vis_ack = r.values.get("visibility-acknowledged")
    # Validate the sinks: block shape. Sink *bodies* are freeform config the
    # agent interprets at run time (channel, format, grouping, threads, …); the
    # compiler checks only that a declaration is a mapping and that an explicit
    # team-visible: is a bool — never the meaning of the other keys.
    if sinks_cfg is not None and not isinstance(sinks_cfg, dict):
        errors.append("sinks: must be a mapping of sink-name -> config (e.g. "
                      "'slack:\\n    channel: \"#reviews\"')")
        sinks_cfg = {}
    for name, cfg in (sinks_cfg or {}).items():
        if cfg is not None and not isinstance(cfg, dict):
            errors.append(f"sinks.{name}: must be a mapping (e.g. 'channel: ...') "
                          f"or empty — got {cfg!r}")
        elif isinstance(cfg, dict) and "team-visible" in cfg:
            # A built-in's visibility is fixed in BUILTIN_SINKS, and
            # _sink_is_team_visible never consults the body for one. Accepting
            # the key would install clean and change nothing — precisely the
            # silent no-op this checker exists to prevent. Say so instead.
            if name in BUILTIN_SINKS:
                fixed = "team-visible" if BUILTIN_SINKS[name] else "record-only"
                errors.append(f"sinks.{name}.team-visible: '{name}' is a built-in "
                              f"sink and its visibility is fixed ({fixed}); the "
                              f"key would be ignored — remove it, or declare a "
                              f"differently-named sink you own")
            elif not isinstance(cfg["team-visible"], bool):
                errors.append(f"sinks.{name}.team-visible: must be true or false — "
                              f"got {cfg['team-visible']!r}")
        elif name not in BUILTIN_SINKS:
            # The dangerous direction. Opening the sink vocabulary means a
            # name nobody recognises can be bound in channels:, and a body
            # that says nothing about visibility used to satisfy the
            # team-visibility invariant by default — so an outcome no human
            # ever sees passed the check that exists to prevent exactly that.
            # A project-declared sink states its visibility or it does not
            # install.
            errors.append(f"sinks.{name}: a project-declared sink must state "
                          f"`team-visible: true` or `team-visible: false` — "
                          f"without it, binding an outcome to '{name}' would "
                          f"satisfy the team-visibility check by default")
    declared = _declared_sinks(r)
    # channels: the outcome-type on the left must be real; each sink on the
    # right must be DECLARED (built-in or named in sinks:). A typo is silent
    # visibility loss — the referential-integrity check catches it statically
    # without the sink vocabulary being a closed enum.
    for otype in sorted(channels.keys()):
        if otype not in outcome_types:
            errors.append(f"channels.{otype}: not a registered outcome type — "
                          f"use one of {', '.join(sorted(outcome_types))}")
        for s in (channels.get(otype) or []):
            if s not in declared:
                errors.append(f"channels.{otype}: sink '{s}' is not declared — "
                              f"declare it under sinks: in glados.yaml, or fix "
                              f"the typo (declared: {', '.join(sorted(declared))})")
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
        if any(_sink_is_team_visible(s, r) for s in sinks):
            continue
        if vis_ack == "ledger-only":
            continue
        errors.append(f"outcome '{otype}' has no team-visible sink "
                      f"(has {sinks}); bind a team-visible sink under "
                      f"channels.{otype} (built-in: "
                      f"{', '.join(sorted(TEAM_VISIBLE_SINKS))}), declare one in "
                      f"sinks:, or confess with 'visibility-acknowledged: ledger-only'")

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

    # ---- (6b) decision values ------------------------------------------------
    errors.extend(decision_value_errors(r))

    # ---- (7) alias-map integrity -------------------------------------------
    for alias, aliased in source.aliases.items():
        if alias in CORES:
            errors.append(f"aliases.yaml: alias '{alias}' shadows the real core "
                          f"of the same name — its shim would overwrite the "
                          f"compiled core; remove the alias (aliases exist only "
                          f"for dead v1 names)")
        if aliased not in CORES:
            errors.append(f"aliases.yaml: alias '{alias}' -> '{aliased}' is not a "
                          f"real core — fix the target or add the core")

    # ---- (8) dotted params literals resolve ---------------------------------
    errors.extend(unresolved_params_errors(comp))

    # ---- (8b) loop bounds are whole numbers ----------------------------------
    errors.extend(loop_bound_errors(r))

    # ---- (9) project workflows: pipelines + steps ----------------------------
    # Lane 2 by design (run-pipeline reads them live), but they decide which
    # steps gate a change, so they are checked wherever the compiler runs:
    # install, check, and `validate` (which run-pipeline itself calls before
    # its first step). The warnings never fail anything.
    pc = check_pipelines(source, r, comp.enabled, target)
    errors.extend(pc.errors)
    for w in pc.warnings:
        if w not in comp.warnings:
            comp.warnings.append(w)

    # ---- (10) canon ------------------------------------------------------------
    # Lane 2 as well (read live at each consult point), but `applies-to` and
    # `seats` route principles to reviewers, so a misspelt consult point or
    # seat is an error wherever the compiler runs. A digest not written yet
    # is only a warning: a team may declare an entry before writing it.
    cc = check_canon(source, r, target)
    errors.extend(cc.errors)
    for w in cc.warnings:
        if w not in comp.warnings:
            comp.warnings.append(w)

    return errors


def decision_value_errors(r: Resolved) -> list[str]:
    """Check (6b). Leaf NAMES under decisions: are open (a project names its
    own decision points), but every VALUE must be one of the four classes
    the preamble's decision-rights table defines, and merge-authority one of
    its three. A misspelt value has no defined behaviour at run time, and
    _is_laxer would wave it through the relaxation check. effective-config
    runs it on the table a run reads too, which validate does not."""
    errors = []
    for leaf, val in sorted((r.values.get("decisions") or {}).items()):
        if val not in DECISION_ORDER:
            prov = r.provenance.get(f"decisions.{leaf}", "baseline")
            errors.append(f"decisions.{leaf}: '{val}' is not a decision class "
                          f"— use one of agent | record | escalate | "
                          f"forbidden (value from {prov})")
    val = r.values.get("merge-authority")
    if val not in MERGE_AUTHORITY_ORDER:
        prov = r.provenance.get("merge-authority", "baseline")
        errors.append(f"merge-authority: {val!r} is not a merge authority — "
                      f"use one of {' | '.join(MERGE_AUTHORITY_ORDER)} "
                      f"(value from {prov})")
    return errors


def unresolved_params_errors(comp: Compilation) -> list[str]:
    """Check (8). Compiled text tells the agent to resolve
    `params.<ns>.<key>` from glados.yaml at run time; a literal with no
    resolved value is a safety bound that resolves to nothing (an unbounded
    loop, a missing roster). effective-config runs it on the configuration
    a run obeys too, whose preset table validate does not read."""
    errors = []
    params = comp.resolved.values.get("params") or {}
    for c, text in comp.cores.items():
        for lit in sorted(set(PARAMS_LITERAL_RE.findall(text))):
            _, ns, key = lit.split(".")
            if (params.get(ns) or {}).get(key) is None:
                errors.append(f"compiled {c}: references `{lit}` but the "
                              f"resolved manifest has no value for it — set it "
                              f"under params: in glados.yaml or a phase-preset "
                              f"baseline")
    return errors


def _loop_bound_problem(val):
    """What is wrong with ``val`` as a loop bound, or None for a whole number
    of 1 or more. YAML's `true` is a bool, which Python counts as an int, so
    it is refused before the int test."""
    if isinstance(val, bool):
        return f"got {_fmt(val)}"
    if isinstance(val, int):
        return None if val >= 1 else f"got {val}"
    if isinstance(val, str):
        return f"got the text '{val}'"
    return f"got {_fmt(val)}"


def loop_bound_errors(r: Resolved) -> list[str]:
    """Every `params.<ns>.max-…` key bounds a loop (*Loop bounds*), whichever
    layer set it. Text, true/false, a list or a number below 1 is no count
    an agent can stop at. An absent value is check (8)'s; a retired key is
    read by nothing."""
    errors = []
    for ns, cfg in sorted((r.values.get("params") or {}).items()):
        for key, val in sorted(cfg.items()):
            if (not key.startswith("max-") or val is None
                    or f"{ns}.{key}" in RETIRED_PARAMS):
                continue
            problem = _loop_bound_problem(val)
            if problem:
                prov = r.provenance.get(f"params.{ns}.{key}", "baseline")
                errors.append(f"params.{ns}.{key}: must be a whole number of "
                              f"1 or more (it bounds a loop) — {problem} "
                              f"(value from {prov}); write a plain integer "
                              f"such as 3, with no quotes or decimal point")
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
            if key in EXPLICIT_ONLY_KEYS:
                # In the manifest schema but EXPLICIT-ONLY: a team
                # declaration, never a phase default.
                errors.append(f"phases.yaml: preset '{pname}' sets '{key}' — "
                              f"{EXPLICIT_ONLY_KEYS[key]}")
            elif key not in allowed:
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


# ---- (9) project workflows: `pipelines:` + `steps:` --------------------------
#
# One rule set, run wherever the compiler sees a manifest: install and check
# (with the target, so step bodies are checked too), `glados.py validate`,
# and, summarized as a checklist, run-pipeline's own step 2 for runs with no
# Python. Errors (V1-V10 in the design notes):
#   V1  ids are kebab-case and collide with nothing (a workflow, an alias, a
#       built-in step, run-pipeline, init, or each other)
#   V2  a sequence is a non-empty list of known ids with no repeats
#   V3  every need of a step is produced by an earlier step; a step that
#       always runs (required or advisory) needs a producer that always runs
#   V4  a gate audits at least one step that runs before it (the latest one)
#   V5  closed key and value sets; step-options only for steps in the
#       sequence; `when:` only with (and required by) `modifier: optional`
#   V6  `review:` only where the step takes it (BUILTIN_STEPS)
#   V7  a used project step has a body file with no frontmatter (target only)
#   V8  nested workflows a sequence uses are enabled
#   V9  decisions.pipeline-discretion is a decision class (check 6b)
#   V10 a pipeline description fits in 250 characters
# Warnings: an MR opened with no verification before it (W1), a declared
# step no pipeline uses (W2), and pipelines declared while run-pipeline is
# disabled (V8's advisory half).


def _kind_phrase(kind: str) -> str:
    """'a spec', 'an MR' — artifact kinds as a sentence names them."""
    return "an MR" if kind == "mr" else f"a {kind}"


def _name_list_problem(value, what: str = "step id"):
    """Why ``value`` is not a list of names, or None. The collecting twin of
    _require_name_list: the pipeline checks report every problem at once
    rather than stopping at the first."""
    if not isinstance(value, list):
        return (f"must be a list of {what}s — got {_fmt(value)}; write "
                f"'[a, b]' or one '- {what}' per line")
    for idx, item in enumerate(value, 1):
        if isinstance(item, dict):
            shown = ", ".join(
                f"{k}: {'' if v is None else _fmt(v)}".rstrip()
                for k, v in item.items())
            return (f"item {idx} is a mapping ('{shown}') — write one {what} "
                    f"per '- ' line; '- name: value' is a mapping in YAML")
        if not isinstance(item, str):
            return f"item {idx} ({_fmt(item)}) is not a {what}"
    return None


def _prose_problem(value):
    """Why ``value`` is not one line of prose, or None. Absent (or blank) is
    'required'; a value the YAML subset read as something else (`when:
    true`, `description: 5`) is named as such, because "required" sends the
    user looking for a key they did write."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "required"
    if not isinstance(value, str):
        read_as = ("a list" if isinstance(value, list) else
                   "a mapping" if isinstance(value, dict) else
                   "a number or a boolean")
        return (f"must be one line of prose — got {_fmt(value)}, which YAML "
                f"reads as {read_as}; quote it if you meant text")
    return None


def _option(opts: dict, key: str, values, default):
    """A step option's value when it is valid, else the default (an
    invalid one is already an error; the row still renders)."""
    return opts.get(key) if opts.get(key) in values else default


class PipelineCheck:
    """What check_pipelines found: fatal errors, warnings, and each
    pipeline's resolved rows (defaults applied), which the assembly report
    renders."""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.steps: dict = {}        # step id -> normalized declaration
        self.pipelines: dict = {}    # name -> {"description", "when", "rows"}


def _step_producers(kind: str, steps: dict) -> list[str]:
    """Every built-in or declared step that produces ``kind``."""
    names = [s for s, b in BUILTIN_STEPS.items() if b["produces"] == kind]
    for sid, d in steps.items():
        if d.get("kind") == "change" and kind == "change":
            names.append(sid)
        elif d.get("kind") == "produce" and d.get("produces") == kind:
            names.append(sid)
    return names


def check_pipelines(source: Source, r: Resolved, enabled: list[str],
                    target: Path | None = None) -> PipelineCheck:
    """Check the manifest's `steps:` and `pipelines:` blocks (P3).

    Never raises on a malformed block: every shape problem becomes an error
    string naming the key and the fix, so `check --report-only` and doctor
    keep their never-crash contracts. ``target`` enables V7, the one rule
    that reads project files."""
    pc = PipelineCheck()
    raw_steps = r.values.get("steps")
    raw_pipes = r.values.get("pipelines")
    if raw_steps is None and raw_pipes is None:
        return pc
    if raw_steps is not None and not isinstance(raw_steps, dict):
        pc.errors.append(f"steps: must be a mapping of step id -> "
                         f"declaration (description, kind, stage, ...) — "
                         f"got {_fmt(raw_steps)}")
        raw_steps = None
    if raw_pipes is not None and not isinstance(raw_pipes, dict):
        pc.errors.append(f"pipelines: must be a mapping of pipeline name -> "
                         f"declaration (description, when, sequence, ...) — "
                         f"got {_fmt(raw_pipes)}")
        raw_pipes = None
    raw_steps = raw_steps or {}
    raw_pipes = raw_pipes or {}
    err = pc.errors.append

    # V1: one namespace. A pipeline name becomes a command beside the cores
    # and alias shims in every script install, and a step id names a file a
    # sequence runs, so neither may shadow anything GLaDOS ships.
    taken: dict[str, str] = {}
    for name in CORES:
        taken[name] = "a GLaDOS workflow"
    for name in source.aliases:
        taken[name] = "a v1 alias (src/kernel/aliases.yaml)"
    for name in BUILTIN_STEPS:
        taken[name] = "a built-in step"
    taken.update(RESERVED_STEP_NAMES)
    builtin_list = ", ".join(BUILTIN_STEPS)

    def check_name(where: str, name) -> bool:
        if not isinstance(name, str) or not KEBAB_RE.match(name):
            err(f"{where}: '{name}' is not kebab-case — use lowercase "
                f"letters, digits and single hyphens (e.g. backend-feature)")
            return False
        if name in taken:
            err(f"{where}: '{name}' is {taken[name]} — pick another name; "
                f"step ids and pipeline names may not reuse a workflow, an "
                f"alias, a built-in step, run-pipeline or init")
            return False
        return True

    # ---- steps ---------------------------------------------------------------
    for sid, decl in raw_steps.items():
        where = f"steps.{sid}"
        valid_name = check_name(where, sid)
        if sid in raw_pipes:
            err(f"{where}: a pipeline has the same name — step ids and "
                f"pipeline names share one namespace; rename one of them")
        norm = {"kind": None, "stage": None, "produces": None, "audits": [],
                "description": None, "valid-name": valid_name}
        pc.steps[sid] = norm
        if not isinstance(decl, dict):
            err(f"{where}: must be a mapping with description, kind and "
                f"stage — got {_fmt(decl)}")
            continue
        for key in decl:
            if key not in STEP_KEYS:
                err(f"{where}.{key}: unknown key — a step takes "
                    f"{', '.join(STEP_KEYS)} (these drive gating, so a typo "
                    f"is an error, not a warning)")
        desc = decl.get("description")
        problem = _prose_problem(desc)
        if problem:
            err(f"{where}.description: {problem} — one line saying what the "
                f"step does")
        else:
            norm["description"] = desc
        kind = decl.get("kind")
        if kind not in STEP_KINDS:
            err(f"{where}.kind: "
                + ("required" if kind is None else f"'{_fmt(kind)}' is not a step kind")
                + f" — one of {' | '.join(STEP_KINDS)}")
            kind = None
        norm["kind"] = kind
        stage = decl.get("stage")
        if stage not in STEP_STAGES:
            err(f"{where}.stage: "
                + ("required" if stage is None else f"'{_fmt(stage)}' is not a stage")
                + f" — one of {' | '.join(STEP_STAGES)} (where the step sits "
                  f"for SDA and boards)")
        else:
            norm["stage"] = stage
        if "produces" in decl and kind is not None:
            produces = decl.get("produces")
            if kind != "produce":
                err(f"{where}.produces: only a produce step declares what it "
                    f"produces — a change step always produces a change and a "
                    f"gate produces nothing; remove the key")
            elif produces not in STEP_PRODUCES:
                err(f"{where}.produces: '{_fmt(produces)}' is not an artifact "
                    f"a step can declare — one of {' | '.join(STEP_PRODUCES)}")
            else:
                norm["produces"] = produces
        audits = decl.get("audits")
        if kind == "gate":
            if audits is None or audits == []:
                err(f"{where}.audits: a gate must name the steps it may audit "
                    f"(built-in or declared step ids), e.g. [shape, "
                    f"spec-feature]")
            else:
                problem = _name_list_problem(audits)
                if problem:
                    err(f"{where}.audits: {problem}")
                else:
                    for a in audits:
                        if a == sid:
                            err(f"{where}.audits: a gate cannot audit itself")
                        elif a not in BUILTIN_STEPS and a not in raw_steps:
                            err(f"{where}.audits: '{a}' is neither a built-in "
                                f"step ({builtin_list}) nor declared under "
                                f"steps: — fix the typo or declare it")
                        else:
                            norm["audits"].append(a)
        elif "audits" in decl and kind is not None:
            err(f"{where}.audits: only a gate audits — remove the key, or "
                f"make the step kind: gate")

    # ---- pipelines -----------------------------------------------------------
    used: set[str] = set()
    for name, cfg in raw_pipes.items():
        where = f"pipelines.{name}"
        check_name(where, name)
        if not isinstance(cfg, dict):
            err(f"{where}: must be a mapping with description, when and "
                f"sequence — got {_fmt(cfg)}")
            continue
        for key in cfg:
            if key not in PIPELINE_KEYS:
                err(f"{where}.{key}: unknown key — a pipeline takes "
                    f"{', '.join(PIPELINE_KEYS)}")
        desc = cfg.get("description")
        problem = _prose_problem(desc)
        if problem:
            err(f"{where}.description: {problem} — one line; it becomes the "
                f"pipeline's shortcut command description")
            desc = None
        elif len(_one_line(desc)) > PIPELINE_DESCRIPTION_MAX:
            err(f"{where}.description: {len(_one_line(desc))} characters — "
                f"keep it to {PIPELINE_DESCRIPTION_MAX} or fewer (it becomes "
                f"the shortcut command's description, and Antigravity "
                f"truncates longer ones)")
        when = cfg.get("when")
        problem = _prose_problem(when)
        if problem:
            err(f"{where}.when: {problem} — the prose run-pipeline matches a "
                f"brief against when nobody names a pipeline")
            when = None

        # V2: the sequence itself.
        seq = cfg.get("sequence")
        sound = True
        if seq is None or seq == []:
            err(f"{where}.sequence: required and not empty — the step ids to "
                f"run, in order")
            seq, sound = [], False
        else:
            problem = _name_list_problem(seq)
            if problem:
                err(f"{where}.sequence: {problem}")
                seq, sound = [], False
        in_seq: set[str] = set()
        clean: list[str] = []
        for sid in seq:
            if sid in in_seq:
                err(f"{where}.sequence: '{sid}' appears twice — a step runs "
                    f"once per pipeline; a second pass over an artifact is a "
                    f"revise cycle, which the step's modifier already bounds")
                sound = False
                continue
            in_seq.add(sid)
            if sid not in BUILTIN_STEPS and sid not in raw_steps:
                err(f"{where}.sequence: '{sid}' is neither a built-in step "
                    f"({builtin_list}) nor declared under steps: — fix the "
                    f"typo or declare it")
                sound = False
                continue
            # V8: a nested workflow the sequence runs must be installed.
            if sid in CORES and sid not in enabled:
                err(f"{where}.sequence: '{sid}' is a workflow "
                    f"disabled-workflows turns off — re-enable it or remove "
                    f"it from the sequence")
            clean.append(sid)
            used.add(sid)

        # V5 + V6: per-step options.
        opts = cfg.get("step-options")
        if opts is not None and not isinstance(opts, dict):
            err(f"{where}.step-options: must be a mapping of step id -> "
                f"options (modifier, when, review, checkpoint) — got "
                f"{_fmt(opts)}")
            opts = None
        opts = opts or {}
        for sid, o in opts.items():
            ow = f"{where}.step-options.{sid}"
            if sid not in in_seq:
                err(f"{ow}: '{sid}' is not in this pipeline's sequence — "
                    f"options apply only to steps the sequence runs")
                continue
            if o is None:
                continue
            if not isinstance(o, dict):
                err(f"{ow}: must be a mapping (modifier, when, review, "
                    f"checkpoint) — got {_fmt(o)}")
                continue
            for key in o:
                if key not in STEP_OPTION_KEYS:
                    err(f"{ow}.{key}: unknown key — step options are "
                        f"{', '.join(STEP_OPTION_KEYS)}")
            modifier = o.get("modifier", "required")
            if modifier not in STEP_MODIFIERS:
                err(f"{ow}.modifier: '{_fmt(modifier)}' — one of "
                    f"{' | '.join(STEP_MODIFIERS)}")
            for key, allowed_values in (("review", STEP_REVIEWS),
                                        ("checkpoint", STEP_CHECKPOINTS)):
                if key in o and o[key] not in allowed_values:
                    err(f"{ow}.{key}: '{_fmt(o[key])}' — one of "
                        f"{' | '.join(allowed_values)}")
            if "when" in o:
                if modifier != "optional":
                    err(f"{ow}.when: only an optional step takes when: (the "
                        f"agent evaluates it to decide whether the step "
                        f"runs) — set modifier: optional or remove when:")
                elif _prose_problem(o["when"]):
                    err(f"{ow}.when: {_prose_problem(o['when'])} — prose "
                        f"saying when the step applies")
            elif modifier == "optional":
                err(f"{ow}: modifier: optional needs a when: saying when the "
                    f"step applies — the agent evaluates it, and records that "
                    f"evaluation when it skips the step")
            if "review" in o and o["review"] in STEP_REVIEWS:
                allowed = (BUILTIN_STEPS[sid]["review"] if sid in BUILTIN_STEPS
                           else _ANY_REVIEW)
                if not allowed:
                    err(f"{ow}.review: {sid} takes no review: setting — it "
                        f"acts on the code or the MR, which have review loops "
                        f"of their own")
                elif o["review"] not in allowed:
                    err(f"{ow}.review: {sid} takes only "
                        f"{' | '.join(allowed)} — it already runs an "
                        f"in-context persona pass of its own")

        # Rows, defaults applied (what the step table and report show).
        rows: list[dict] = []
        for sid in clean:
            o = opts.get(sid) if isinstance(opts.get(sid), dict) else {}
            if sid in BUILTIN_STEPS:
                b = BUILTIN_STEPS[sid]
                runs = "nested workflow" if b["runs"] == "core" else "library step"
                needs, produces = list(b["needs"]), b["produces"]
                default_review, is_gate, candidates = b["default-review"], False, []
            else:
                st = pc.steps.get(sid, {})
                kind = st.get("kind")
                runs = f"project {kind}" if kind else "project step"
                needs = []
                produces = ("change" if kind == "change" else
                            st.get("produces") if kind == "produce" else None)
                default_review = "in-context" if kind == "gate" else "none"
                is_gate, candidates = kind == "gate", st.get("audits", [])
            rows.append({
                "id": sid, "runs": runs, "needs": needs, "produces": produces,
                "modifier": _option(o, "modifier", STEP_MODIFIERS, "required"),
                "review": _option(o, "review", STEP_REVIEWS, default_review),
                "checkpoint": _option(o, "checkpoint", STEP_CHECKPOINTS, "none"),
                "when": o.get("when"), "gate": is_gate,
                "candidates": candidates, "audits": None,
            })

        # V3 + V4 + W1, through artifacts. Skipped when the sequence itself
        # is broken: a typo'd id would otherwise cascade into "nothing
        # produces a spec" errors that hide the one real mistake.
        if sound:
            producers: dict[str, list[dict]] = {}
            for i, row in enumerate(rows):
                always = row["modifier"] != "optional"
                for kind in row["needs"]:
                    prods = producers.get(kind, [])
                    if not prods:
                        err(f"{where}: '{row['id']}' needs "
                            f"{_kind_phrase(kind)}, but no step before it in "
                            f"the sequence produces one — put one of "
                            f"{', '.join(_step_producers(kind, pc.steps))} "
                            f"earlier")
                    elif always and all(p["modifier"] == "optional"
                                        for p in prods):
                        names = ", ".join(f"'{p['id']}'" for p in prods)
                        verb = "is" if len(prods) == 1 else "are"
                        err(f"{where}: '{row['id']}' needs "
                            f"{_kind_phrase(kind)}, but its only earlier "
                            f"producer {names} {verb} optional — the run could "
                            f"reach it with nothing to work on; make a producer "
                            f"required or advisory, or make '{row['id']}' "
                            f"optional too")
                if row["gate"] and row["candidates"]:
                    earlier = [rows[j] for j in range(i)
                               if rows[j]["id"] in row["candidates"]]
                    if not earlier:
                        err(f"{where}: gate '{row['id']}' audits "
                            f"[{', '.join(row['candidates'])}], but none of "
                            f"them runs before it in this sequence — move the "
                            f"gate after one of them, or add the step it "
                            f"should audit to its audits:")
                    else:
                        row["audits"] = earlier[-1]["id"]
                        if always and all(e["modifier"] == "optional"
                                          for e in earlier):
                            names = ", ".join(f"'{e['id']}'" for e in earlier)
                            err(f"{where}: gate '{row['id']}' can audit only "
                                f"optional steps before it ({names}) — the run "
                                f"could reach it with nothing to audit; make "
                                f"one of them required or advisory, or make "
                                f"the gate optional too")
                if row["produces"]:
                    producers.setdefault(row["produces"], []).append(row)
            ids = [row["id"] for row in rows]
            if "open-mr" in ids:
                before = rows[:ids.index("open-mr")]
                if not any(row["produces"] == "verification" for row in before):
                    pc.warnings.append(
                        f"pipelines.{name}: opens an MR with no verification "
                        f"step; the MR description will say so")
        pc.pipelines[name] = {"description": desc, "when": when, "rows": rows}

    # W2 + V8's advisory half.
    for sid in raw_steps:
        if sid not in used:
            pc.warnings.append(f"steps.{sid}: declared but no pipeline uses "
                               f"it — add it to a sequence or remove it")
    if raw_pipes and "run-pipeline" not in enabled:
        pc.warnings.append(f"pipelines: declared, but run-pipeline is "
                           f"disabled {_disabled_by(r)} — no pipeline can run "
                           f"until it is re-enabled, and each pipeline's "
                           f"shortcut command says so")

    # V7: the body of every project step a pipeline runs. Only kebab-case
    # ids reach the filesystem, so an id can never point outside the steps
    # directory. The name is matched against the directory listing, not
    # through is_file(): on a case-insensitive disk (Windows, macOS) `S.md`
    # would pass for step `s` here and then be missing on a Linux CI runner.
    if target is not None:
        steps_dir = target / STEPS_DIR
        try:
            listed = ({p.name for p in steps_dir.iterdir() if p.is_file()}
                      if steps_dir.is_dir() else set())
        except OSError:
            listed = set()
        for sid in sorted(used):
            if sid in BUILTIN_STEPS or not pc.steps.get(sid, {}).get("valid-name"):
                continue
            rel = f"{STEPS_DIR}/{sid}.md"
            body = steps_dir / f"{sid}.md"
            if body.name not in listed:
                twin = next((n for n in sorted(listed)
                             if n.lower() == body.name.lower()), None)
                if twin:
                    err(f"steps.{sid}: the body is {STEPS_DIR}/{twin}, but "
                        f"the step needs {rel} — rename the file to match "
                        f"the id's case (a case-sensitive checkout, such as "
                        f"Linux CI, will not find it)")
                    continue
                err(f"steps.{sid}: no body at {rel} — write what the step "
                    f"produces or checks there (plain markdown, no "
                    f"frontmatter); run-pipeline escalates rather than "
                    f"improvise a missing step")
                continue
            try:
                text = read_text(body)
            except Fatal as exc:
                err(f"steps.{sid}: {exc}")
                continue
            first = next((l.strip() for l in text.split("\n") if l.strip()), "")
            if first == "---":
                err(f"steps.{sid}: {rel} starts with YAML frontmatter — a "
                    f"step is declared in glados.yaml under steps:, so the "
                    f"body file holds only the body; remove the --- block")
    return pc


# ---- (10) canon: `canon:` ------------------------------------------------------
#
# The declaration is checked; the digests are not read (beyond whether the
# file exists). Errors:
#   - the block is a mapping keyed by kebab-case name; a list of `- name:`
#     items is the commonest wrong shape and is named as such
#   - an entry is a mapping of CANON_ENTRY_KEYS only, with `source` and
#     `digest` required
#   - `digest` is a repo-relative path that stays inside the repo, lexically
#     and (target known) after symlinks resolve
#   - `applies-to` names consult points: CANON_CONSULT_POINTS, or a step id
#     declared under `steps:`
#   - `seats` names standing lenses or personas: the library's, and (target
#     known) the project's product-knowledge/personas/*.md. With no target a
#     name that is neither a lens nor a library persona may be a project
#     persona, so it is let through rather than guessed at.
# Warnings (target known): the digest does not exist yet, or exists under a
# name that differs in case.


class CanonCheck:
    """What check_canon found: fatal errors, warnings, and each entry
    normalized (defaults applied), which the assembly report renders."""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        # name -> {"source", "url", "digest", "applies-to", "seats",
        #          "default-applies-to", "default-seats"}
        self.entries: dict = {}


def canon_digest_problem(digest):
    """Why ``digest`` is not a safe repo-relative path, or None.

    Lexical, so it holds before anything touches the filesystem: a URL or
    other URI (`https:`, `file:`), an absolute path (POSIX, a drive letter,
    a UNC share, a home directory) or a `..` that climbs above the repo root
    is refused. Agents and doctor read the digest at this path, and a path
    that leaves the repo would make them read a file no reviewer of the repo
    can see."""
    if not isinstance(digest, str) or not digest.strip():
        return ("required — the digest's path relative to the repo root, "
                "e.g. product-knowledge/canon/<name>.md")
    p = digest.strip().replace("\\", "/")
    # A scheme is two or more characters before the colon, so a drive letter
    # (`C:`) keeps the absolute-path message below.
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]+:", p):
        return (f"'{digest}' is a URL — the digest is a file in the repo "
                f"(conventionally {CANON_DIR}/<name>.md); put the address "
                f"under url:")
    if p.startswith("/") or p.startswith("~") or re.match(r"^[A-Za-z]:", p):
        return (f"'{digest}' is an absolute path — write it relative to the "
                f"repo root, e.g. product-knowledge/canon/<name>.md")
    depth = 0
    for seg in p.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            depth -= 1
            if depth < 0:
                return (f"'{digest}' climbs out of the repo — a digest lives "
                        f"in the repo, where every reviewer reads the same "
                        f"text (conventionally {CANON_DIR}/<name>.md)")
        else:
            depth += 1
    if depth == 0:
        return f"'{digest}' names the repo root, not a file"
    return None


def _canon_list(entry: dict, key: str, where: str, what: str, err):
    """The validated list under ``key``, or None when the key is absent or
    the value is unusable (the error is already reported)."""
    if key not in entry:
        return None
    value = entry[key]
    if value is None or value == []:
        err(f"{where}.{key}: empty — remove the key to take the default, or "
            f"name at least one {what}")
        return None
    problem = _name_list_problem(value, what)
    if problem:
        err(f"{where}.{key}: {problem}")
        return None
    return list(dict.fromkeys(value))


def check_canon(source: Source, r: Resolved,
                target: Path | None = None) -> CanonCheck:
    """Check the manifest's `canon:` block (C1). Never raises: every shape
    problem becomes an error string naming the key and the fix, so `check
    --report-only` and doctor keep their never-crash contracts. ``target``
    enables the checks that read project files (project personas, whether
    each digest exists)."""
    cc = CanonCheck()
    block = r.values.get("canon")
    if block is None:
        return cc
    err = cc.errors.append
    if isinstance(block, list):
        err("canon: must be a mapping keyed by each work's name, not a list "
            "— write 'clean-architecture:' with its keys indented under it, "
            "with no leading '- '")
        return cc
    if not isinstance(block, dict):
        err(f"canon: must be a mapping of name -> entry (source, digest, "
            f"...) — got {_fmt(block)}")
        return cc

    steps = r.values.get("steps")
    step_ids = ([s for s in steps if isinstance(s, str)]
                if isinstance(steps, dict) else [])
    pipelines = r.values.get("pipelines")
    pipeline_names = set(pipelines) if isinstance(pipelines, dict) else set()
    points = CANON_CONSULT_POINTS + [s for s in step_ids
                                     if s not in CANON_CONSULT_POINTS]
    points_text = ", ".join(CANON_CONSULT_POINTS) + (
        f", or a step declared under steps: ({', '.join(step_ids)})"
        if step_ids else ", or the id of a step declared under steps:")
    library = sorted(p.stem for p in (source.src / "personas").glob("*.md"))
    project = None
    if target is not None:
        pdir = target / PROJECT_PERSONAS_DIR
        try:
            project = (sorted(p.stem for p in pdir.iterdir()
                              if p.is_file() and p.suffix == ".md")
                       if pdir.is_dir() else [])
        except OSError:
            project = []

    for name, entry in block.items():
        where = f"canon.{name}"
        if not isinstance(name, str) or not KEBAB_RE.match(name):
            err(f"{where}: '{name}' is not kebab-case — use lowercase "
                f"letters, digits and single hyphens (it is the first half "
                f"of every citation, canon:<name>#<principle-id>)")
        if not isinstance(entry, dict):
            err(f"{where}: must be a mapping with source and digest — got "
                f"{_fmt(entry)}")
            continue
        for key in entry:
            if key not in CANON_ENTRY_KEYS:
                err(f"{where}.{key}: unknown key — a canon entry takes "
                    f"{', '.join(CANON_ENTRY_KEYS)} (these route principles "
                    f"to reviewers, so a typo is an error, not a warning)")
        src = entry.get("source")
        if not isinstance(src, str) or not src.strip():
            err(f"{where}.source: required — the citation a person would "
                f"use to find the work, e.g. \"Robert C. Martin, Clean "
                f"Architecture (2017)\" (double-quote it: ' #' starts a "
                f"comment)")
            src = None
        url = entry.get("url")
        if "url" in entry and (not isinstance(url, str) or not url.strip()):
            err(f"{where}.url: must be the work's web address, or leave the "
                f"key out — got {_fmt(url)}")
            url = None
        digest = entry.get("digest")
        problem = canon_digest_problem(digest)
        if problem:
            err(f"{where}.digest: {problem}")
            digest = None
        else:
            digest = digest.strip().replace("\\", "/")

        applies = _canon_list(entry, "applies-to", where, "consult point", err)
        for a in applies or []:
            if a in points:
                continue
            if a in pipeline_names:
                err(f"{where}.applies-to: '{a}' is a pipeline, not a consult "
                    f"point — name the steps in it where the entry applies "
                    f"({points_text})")
            else:
                err(f"{where}.applies-to: '{a}' is not a consult point — use "
                    f"{points_text}")

        seats = _canon_list(entry, "seats", where, "seat", err)
        for s in seats or []:
            if s in STANDING_LENSES or s in library:
                continue
            if project is None:
                continue                # may be a project persona: unseen
            if s in project:
                continue
            twin = next((p for p in project if p.lower() == s.lower()), None)
            if twin:
                err(f"{where}.seats: the persona file is "
                    f"{PROJECT_PERSONAS_DIR}/{twin}.md, but the seat names "
                    f"'{s}' — match the file's case (a case-sensitive "
                    f"checkout, such as Linux CI, will not find it)")
                continue
            err(f"{where}.seats: '{s}' is neither a standing lens "
                f"({', '.join(STANDING_LENSES)}) nor a persona — a library "
                f"persona ({', '.join(library)}) or a project one at "
                f"{PROJECT_PERSONAS_DIR}/{s}.md")

        if digest and target is not None:
            _check_canon_digest_file(cc, where, digest, target)

        cc.entries[name] = {
            "source": src, "url": url, "digest": digest,
            "applies-to": applies or list(CANON_DEFAULT_APPLIES_TO),
            "seats": seats or list(CANON_DEFAULT_SEATS),
            "default-applies-to": "applies-to" not in entry,
            "default-seats": "seats" not in entry,
        }
    return cc


def _canon_digest_resolve_problem(target: Path, digest: str):
    """(what is wrong, the fix) when the digest path, followed through any
    symlinks or junctions, leaves the repo or cannot be followed at all;
    None when it stays inside. Shared by check_canon and doctor, which both
    promise never to raise."""
    try:
        inside = (target / digest).resolve().is_relative_to(target.resolve())
    except RuntimeError:
        # Python 3.10 to 3.12 raise RuntimeError on a symlink or junction
        # loop (3.13 returns the path unresolved; the caller's is-a-file
        # check catches it there).
        return ("is a symlink loop", "point it at the digest file")
    except (OSError, ValueError):
        inside = False
    if not inside:
        return ("resolves outside the repo (through a symlink)",
                "keep the digest itself in the repo")
    return None


def _check_canon_digest_file(cc: CanonCheck, where: str, digest: str,
                             target: Path) -> None:
    """Whether a lexically safe digest path is a readable file in the repo.
    Missing is a warning (declare first, write next); a path that resolves
    outside the repo through a symlink, loops, names a directory, or is a
    link to nothing is an error; a path that matches only by case is a
    warning."""
    path = target / digest
    problem = _canon_digest_resolve_problem(target, digest)
    if problem:
        cc.errors.append(f"{where}.digest: {digest} {problem[0]} — "
                         f"{problem[1]}")
        return
    if path.is_dir():
        cc.errors.append(f"{where}.digest: {digest} is a directory — name the "
                         f"digest file, e.g. {CANON_DIR}/<name>.md")
        return
    # Walk the declared path one part at a time against the real directory
    # listings, so a part that matches only by case is caught at any depth:
    # a case-insensitive checkout (Windows, macOS) opens it silently, and a
    # case-sensitive one (Linux CI) reports the digest missing.
    parts: list[str] = []
    for seg in digest.split("/"):       # lexically normal; never climbs out
        if seg == "..":
            if parts:
                parts.pop()
        elif seg not in ("", "."):
            parts.append(seg)
    on_disk, cur, case_only = [], target, False
    for part in parts:
        try:
            listed = ({p.name for p in cur.iterdir()} if cur.is_dir()
                      else set())
        except OSError:
            listed = set()
        if part in listed:
            name = part
        else:
            name = next((n for n in sorted(listed)
                         if n.lower() == part.lower()), None)
            if name is None:
                on_disk = None
                break
            case_only = True
        on_disk.append(name)
        cur = cur / name
    if on_disk is not None and case_only:
        cc.warnings.append(f"{where}.digest: the path on disk is "
                           f"{'/'.join(on_disk)}, but the entry names "
                           f"{digest} — match the case (a case-sensitive "
                           f"checkout, such as Linux CI, will not find it)")
        return
    if on_disk is not None:
        if not path.is_file():
            cc.errors.append(f"{where}.digest: {digest} is listed in its "
                             f"directory but cannot be opened as a file (a "
                             f"broken symlink, or a symlink loop) — point "
                             f"it at the digest file")
        return
    cc.warnings.append(f"{where}.digest: {digest} does not exist yet — write "
                       f"it from the CANON.md template "
                       f"(.glados/src/templates/CANON.md, or "
                       f"src/templates/CANON.md under the plugin root); "
                       f"until then every consult point reports it missing")


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
    for key in ("phase", "platform", "sda", "merge-authority", "optimize-for",
                "default-modules", "disabled-workflows"):
        if key in r.values and r.values[key] is not None:
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
            prov = r.provenance.get(path, 'baseline')
            if f"{ns}.{k}" in RETIRED_PARAMS:
                prov += "; retired, read by nothing"
            out.append(f"| {path} | {_fmt(cfg[k])} | ({prov}) |")
    for leaf in sorted((r.values.get("branching") or {}).keys()):
        out.append(f"| branching.{leaf} | {_fmt(r.values['branching'][leaf])} | "
                   f"(explicit) |")
    out.append("")

    out.append("## Sinks")
    out.append("")
    out.append("Where outcomes land, and whether delivery counts as team-visible. "
               "Built-ins are always available; a project may declare more under "
               "`sinks:` (bodies are freeform config the agent interprets at run "
               "time). Runtime delivery is verified — a bound sink that fails "
               "to receive its outcome escalates, whatever the other sinks got.")
    out.append("")
    out.append("| Sink | Team-visible | Config | Source |")
    out.append("|------|--------------|--------|--------|")
    declared_sinks = _sinks_map(r)
    for name in sorted(BUILTIN_SINKS):
        vis = "yes" if _sink_is_team_visible(name, r) else "no (record-only)"
        # A built-in the manifest configured is still explicitly configured;
        # reporting it as plain "built-in" hides the one row a reader checks.
        src = "built-in (explicit config)" if declared_sinks.get(name) else "built-in"
        out.append(f"| {name} | {vis} | {_fmt(declared_sinks.get(name) or {})} | "
                   f"{src} |")
    for name in sorted(declared_sinks):
        if name in BUILTIN_SINKS:
            continue
        vis = "yes" if _sink_is_team_visible(name, r) else "no (record-only)"
        out.append(f"| {name} | {vis} | {_fmt(declared_sinks.get(name) or {})} | "
                   f"(explicit) |")
    out.append("")

    out.extend(_canon_report(source, comp))

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

    out.extend(_pipelines_report(source, comp))

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

    if r.values.get("sda"):
        out.append("## SDA conformance")
        out.append("")
        out.append("`sda: true` — the install scaffolds these artifacts "
                   "(create-only, never clobbered):")
        out.append("")
        out.append("- `claims.md` (repo root) — the SDA claims file")
        out.append("- `product-knowledge/SPEC_LOG.md` — the SDA work-unit log")
        out.append("- `SDA: v1.0` headers on an existing "
                   "`product-knowledge/ROADMAP.md` and `PROJECT_STATUS.md`")
        out.append("- `product-knowledge/standards/sda-*.md` — the versioned "
                   "standard and profile docs")
        out.append("")
    return "\n".join(out)


def _pipelines_report(source: Source, comp: Compilation) -> list[str]:
    """The `## Pipelines` section: each declared pipeline as the step table
    run-pipeline will write (defaults applied), which artifact each gate
    audits, the project steps, and the pipeline warnings. Declarations only:
    run-pipeline reads the blocks live, so this records what they said at
    install (the report is presence-checked, never byte-compared). Absent
    when the manifest declares neither block."""
    r = comp.resolved
    if not r.values.get("pipelines") and not r.values.get("steps"):
        return []
    pc = check_pipelines(source, r, comp.enabled)
    out = ["## Pipelines", "",
           "Project workflows declared under `pipelines:` and run by "
           "`run-pipeline`, with the project's own steps declared under "
           "`steps:` (bodies in `product-knowledge/steps/`). run-pipeline "
           "reads these declarations live at every run; this section records "
           "what they said at install. Script installs also carry one "
           "shortcut command per pipeline.", ""]
    if "run-pipeline" not in comp.enabled:
        out += [f"**run-pipeline is disabled** {_disabled_by(comp.resolved)}: "
                f"none of these pipelines can run until it is re-enabled.", ""]
    for name, p in pc.pipelines.items():
        out.append(f"### `{name}`")
        out.append("")
        if p["description"]:
            out.append(_fmt_cell(_one_line(p["description"])))
            out.append("")
        if p["when"]:
            out.append(f"When: {_fmt_cell(_one_line(p['when']))}")
            out.append("")
        out.append("| # | Step | Runs as | Modifier | Review | Checkpoint | "
                   "Audits |")
        out.append("|---|------|---------|----------|--------|------------|"
                   "--------|")
        for i, row in enumerate(p["rows"], 1):
            audits = f"`{row['audits']}`" if row["audits"] else ""
            out.append(f"| {i} | {row['id']} | {row['runs']} | "
                       f"{row['modifier']} | {row['review']} | "
                       f"{row['checkpoint']} | {audits} |")
        out.append("")
    if pc.steps:
        out.append("### Project steps")
        out.append("")
        out.append("| Step | Kind | Stage | Produces | Audits | Body |")
        out.append("|------|------|-------|----------|--------|------|")
        for sid, st in pc.steps.items():
            out.append(f"| {sid} | {st.get('kind') or '?'} | "
                       f"{st.get('stage') or '?'} | "
                       f"{st.get('produces') or ''} | "
                       f"{', '.join(st.get('audits') or [])} | "
                       f"`{STEPS_DIR}/{sid}.md` |")
        out.append("")
    out.append("### Warnings")
    out.append("")
    if pc.warnings:
        out.extend(f"- {_fmt_cell(w)}" for w in pc.warnings)
    else:
        out.append("_None._")
    out.append("")
    return out


def _canon_report(source: Source, comp: Compilation) -> list[str]:
    """The `## Canon` section: one row per declared entry (name, source,
    digest path, applies-to, seats, defaults marked). Declarations only: a
    digest's content never enters the report, as it never enters compiled
    text, and the report is presence-checked, so editing the block makes
    nothing stale. Absent when the manifest declares no canon."""
    block = comp.resolved.values.get("canon")
    if not isinstance(block, dict) or not block:
        return []
    cc = check_canon(source, comp.resolved)
    out = ["## Canon", "",
           "Reference works declared under `canon:`. At each consult point "
           "its `applies-to` names, an agent reads the entry's digest, never "
           "its URL, and routes it to the seats named here. This section "
           "records the declarations at install, never a digest's content.",
           "",
           "| Name | Source | Digest | Applies to | Seats |",
           "|------|--------|--------|------------|-------|"]

    def listed(values, default):
        return ", ".join(values) + (" (default)" if default else "")

    for name, e in cc.entries.items():
        digest = f"`{e['digest']}`" if e["digest"] else "?"
        out.append(f"| {name} | {_fmt_cell(_one_line(e['source'] or '?'))} | "
                   f"{digest} | "
                   f"{listed(e['applies-to'], e['default-applies-to'])} | "
                   f"{listed(e['seats'], e['default-seats'])} |")
    out.append("")
    return out


def _fmt_cell(s: str) -> str:
    """One markdown-table-safe cell. A pipe ends the cell early and a newline
    ends the ROW, so a multi-line value — the normal shape of a freeform sink
    body the agent interprets at run time — has to be summarized rather than
    inlined, or it tears the table apart. Single-line values pass through with
    only pipes escaped, so a long-but-flat entry like optimize-for still reads
    in full."""
    lines = s.splitlines()
    if len(lines) <= 1:
        return s.replace("|", "\\|")
    head = lines[0].strip().replace("|", "\\|")
    if len(head) > 60:
        head = head[:60].rstrip()
    return f"{head}… ({len(lines)} lines)"


def _fmt(val) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, list):
        return "[" + ", ".join(str(v) for v in val) + "]"
    if isinstance(val, dict):
        return "{" + ", ".join(f"{k}: {_fmt(v)}" for k, v in val.items()) + "}"
    if isinstance(val, str):
        return _fmt_cell(val)
    return str(val)


# =============================================================================
# 8. ADAPTERS — six emitters over the SAME compiled artifacts
# =============================================================================
#
# Each adapter is a pure function returning a plan: {relpath: (kind, data)}
# where kind is 'text' (LF str) or 'bytes'. install applies the plan then runs
# directory-scoped cleanup; check recomputes the plan and diffs it.


def _alias_targets(source: Source, comp: "Compilation") -> dict[str, tuple[str, bool]]:
    """Alias -> (target, enabled). Every alias is always emitted: a shim whose
    target is disabled must SAY so — a silently vanished alias makes the model
    reconstruct the v1 workflow from training data, the exact ungoverned ghost
    the aliases exist to prevent. (Alias-map integrity guarantees every target
    is a real core name.)"""
    return {a: (t, t in comp.cores) for a, t in source.aliases.items()}


def _disabled_by(r: Resolved) -> str:
    """Where the effective `disabled-workflows` list came from, as the end
    of a sentence "<workflow> is disabled ...". A phase preset can disable a
    workflow (sunset unloads build-feature and run-pipeline) with no
    `disabled-workflows:` line in glados.yaml, and naming that key sent
    people looking for a line that is not there."""
    prov = r.provenance.get("disabled-workflows", "explicit")
    if prov.startswith("phase:"):
        return (f"by the {prov.split(':', 1)[1]} phase preset (glados.yaml "
                f"sets no `disabled-workflows:`; an explicit list there that "
                f"leaves it out re-enables it)")
    if prov == "baseline":
        return ("by GLaDOS's baseline preset (an explicit "
                "`disabled-workflows:` list in glados.yaml that leaves it out "
                "re-enables it)")
    return "in this project's glados.yaml (`disabled-workflows:`)"


def _disabled_alias_body(alias: str, target: str, comp: Compilation) -> str:
    """Shim body for an alias whose target core is disabled in the manifest."""
    return (f"The `{alias}` workflow was renamed to `{target}`, which is "
            f"disabled {_disabled_by(comp.resolved)}. "
            f"Do not reconstruct it from memory — ask a maintainer to "
            f"re-enable it or pick a different workflow.\n")


# ---- per-pipeline shims ------------------------------------------------------
#
# Every declared pipeline gets a shortcut command in the script modes
# (claude, direct, gemini, antigravity, pi), named after the pipeline and
# modelled on the alias shims: a pointer that runs run-pipeline with the
# pipeline named, so `/glados:backend-feature <brief>` is the same run as
# `/glados:run-pipeline backend-feature <brief>`. Only a pipeline's name and
# description shape a shim, which is why exactly those two are hashed
# (structural_projection). The files land in each mode's owned directory, so
# a removed pipeline's shim is cleaned at the next install. claude-plugin
# and aistudio emit none: the plugin is compiled once from GLaDOS's own
# example, and AI Studio cannot run a pipeline.


def _pipeline_shims(comp: Compilation) -> list[tuple[str, str]]:
    """(name, one-line description) for every declared pipeline. Adapters
    run only after the type checks pass, but this stays defensive anyway."""
    pipelines = comp.resolved.values.get("pipelines")
    if not isinstance(pipelines, dict):
        return []
    out: list[tuple[str, str]] = []
    for name, cfg in pipelines.items():
        desc = cfg.get("description") if isinstance(cfg, dict) else None
        out.append((name, _one_line(desc) if isinstance(desc, str)
                    else f"Run the {name} project workflow"))
    return out


def _pipeline_shim_body(comp: Compilation, name: str, runner: str,
                        invoke: str | None) -> str:
    """The pointer a pipeline's shortcut command carries. ``runner`` names
    the installed run-pipeline file; ``invoke`` is the mode's spelling of
    the run-pipeline command (None where the mode has no invocation
    syntax)."""
    if "run-pipeline" not in comp.cores:
        return (f"`{name}` is a project workflow declared under `pipelines:` "
                f"in glados.yaml, but run-pipeline, the workflow that runs "
                f"it, is disabled {_disabled_by(comp.resolved)}. Do not "
                f"reconstruct it from memory — ask a maintainer to re-enable "
                f"run-pipeline or pick a different workflow.\n")
    same = f" This is the same run as `{invoke} {name} <brief>`." if invoke else ""
    given = "this command" if invoke else "this file"
    return (f"`{name}` is a project workflow declared under `pipelines:` in "
            f"glados.yaml. Run it with the run-pipeline workflow: read and "
            f"follow `{runner}`, with `{name}` as the first word of its "
            f"arguments and the brief you were given with {given} as the "
            f"rest.{same}\n")


# ---- claude -----------------------------------------------------------------

def adapter_claude(source: Source, comp: Compilation) -> dict:
    plan: dict = {}
    base = ".claude/commands/glados"
    for c in comp.enabled:
        plan[f"{base}/{c}.md"] = ("text", comp.cores[c])
    for alias, (target, enabled) in _alias_targets(source, comp).items():
        body = (f"The `{alias}` workflow was renamed. Run `/glados:{target}` "
                f"instead.\n" if enabled else _disabled_alias_body(alias, target, comp))
        plan[f"{base}/{alias}.md"] = ("text", body)
    for name, desc in _pipeline_shims(comp):
        body = _pipeline_shim_body(comp, name, f"{base}/run-pipeline.md",
                                   "/glados:run-pipeline")
        plan[f"{base}/{name}.md"] = ("text", f"---\ndescription: "
                                     f"{_yaml_quote(desc)}\n---\n\n{body}")
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
            f"`{PLUGIN_STUB_MARKER}{c}.md`.\n")
    for alias, (target, enabled) in _alias_targets(source, comp).items():
        if enabled:
            desc = _yaml_quote(f"(renamed) the '{alias}' workflow is now '{target}'")
            body = (f"`{alias}` was renamed to `{target}`. Read and follow "
                    f"`{PLUGIN_STUB_MARKER}{target}.md`.\n")
        else:
            desc = _yaml_quote(f"(renamed) the '{alias}' workflow is now "
                               f"'{target}', which is disabled in this project")
            # Still a generated stub: carries the marker (as the not-installed
            # compiled path) so marker-based pruning can retire it later.
            body = (f"`{alias}` was renamed to `{target}`, which is disabled "
                    f"in this project's glados.yaml (`disabled-workflows:`) — "
                    f"`{PLUGIN_STUB_MARKER}{target}.md` is not installed. Do "
                    f"not reconstruct it from memory; ask a maintainer to "
                    f"re-enable it or pick a different workflow.\n")
        plan[f"skills/{alias}/SKILL.md"] = ("text",
            f"---\ndescription: {desc}\n---\n\n{body}")
    return plan


# ---- direct -----------------------------------------------------------------

def adapter_direct(source: Source, comp: Compilation) -> dict:
    plan: dict = {}
    for c in comp.enabled:
        plan[f"product-knowledge/glados/{c}.md"] = ("text", comp.cores[c])
    # Direct mode has no invocation syntax — shims point at the target FILE.
    for alias, (target, enabled) in _alias_targets(source, comp).items():
        body = (f"The `{alias}` workflow was renamed. Read and follow "
                f"`product-knowledge/glados/{target}.md` instead.\n"
                if enabled else _disabled_alias_body(alias, target, comp))
        plan[f"product-knowledge/glados/{alias}.md"] = ("text", body)
    for name, _desc in _pipeline_shims(comp):
        plan[f"product-knowledge/glados/{name}.md"] = ("text", _pipeline_shim_body(
            comp, name, "product-knowledge/glados/run-pipeline.md", None))
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
    for alias, (target, enabled) in _alias_targets(source, comp).items():
        if enabled:
            desc = f"(renamed) {alias} is now {target}"
            body = f"The `{alias}` workflow was renamed. Run `/glados:{target}` instead.\n"
        else:
            desc = f"(renamed) {alias} is now {target} — disabled here"
            body = _disabled_alias_body(alias, target, comp)
        toml = (f"description = {_toml_basic(desc)}\n"
                f"prompt = {_toml_multiline(body)}\n")
        plan[f"{base}/{alias}.toml"] = ("text", toml)
    for name, desc in _pipeline_shims(comp):
        # The runner is the run-pipeline command's TOML, whose prompt is the
        # compiled workflow.
        body = _pipeline_shim_body(comp, name, f"{base}/run-pipeline.toml",
                                   "/glados:run-pipeline")
        plan[f"{base}/{name}.toml"] = ("text",
            f"description = {_toml_basic(desc)}\n"
            f"prompt = {_toml_multiline(body)}\n")
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
    for alias, (target, enabled) in _alias_targets(source, comp).items():
        if enabled:
            desc = _yaml_quote(_agy_description(f"(renamed) {alias} is now {target}"))
            shim = f"The `{alias}` workflow was renamed. Run `/glados-{target}` instead.\n"
        else:
            desc = _yaml_quote(_agy_description(
                f"(renamed) {alias} is now {target} — disabled here"))
            shim = _disabled_alias_body(alias, target, comp)
        body = f"---\ndescription: {desc}\n---\n\n{shim}"
        plan[f"{base}/glados-{alias}.md"] = ("text", body)
    for name, desc in _pipeline_shims(comp):
        shim = _pipeline_shim_body(comp, name, f"{base}/glados-run-pipeline.md",
                                   "/glados-run-pipeline")
        plan[f"{base}/glados-{name}.md"] = ("text",
            f"---\ndescription: {_yaml_quote(_agy_description(desc))}\n"
            f"---\n\n{shim}")
    return plan


# ---- pi ---------------------------------------------------------------------

# pi (pi.dev) prompt templates substitute shell-style argument placeholders in
# the template text. A compiled core must not contain one, or pi would rewrite
# the workflow; the adapter refuses rather than ship a silently altered core.
_PI_PLACEHOLDER = re.compile(r"\$\{(\d+|ARGUMENTS|@)[:}]|\$(ARGUMENTS|@|\d)")
_PI_ARGS_TRAILER = ("\n\n## Invocation arguments\n\n"
                    "${ARGUMENTS:-(none given — ask if the workflow needs them)}\n")


def _pi_template(desc: str, body: str, rel: str) -> str:
    hit = _PI_PLACEHOLDER.search(body)
    if hit:
        raise Fatal(f"pi adapter: {rel} contains '{hit.group(0)}', which pi "
                    f"would substitute as a prompt-template argument")
    return f"---\ndescription: {desc}\n---\n\n{body}{_PI_ARGS_TRAILER}"


def adapter_pi(source: Source, comp: Compilation) -> dict:
    """Prompt templates in .pi/prompts/ — run `/glados-fix-bug` in pi.

    pi loads only direct .md children of a prompt directory, so the namespace
    is a `glados-` filename prefix (as in antigravity), not a subdirectory.
    """
    plan: dict = {}
    base = ".pi/prompts"
    for c in comp.enabled:
        rel = f"{base}/glados-{c}.md"
        desc = _yaml_quote(_one_line(source.cores[c]["description"]))
        plan[rel] = ("text", _pi_template(desc, comp.cores[c], rel))
    for alias, (target, enabled) in _alias_targets(source, comp).items():
        rel = f"{base}/glados-{alias}.md"
        if enabled:
            desc = _yaml_quote(f"(renamed) {alias} is now {target}")
            shim = f"The `{alias}` workflow was renamed. Run `/glados-{target}` instead.\n"
        else:
            desc = _yaml_quote(f"(renamed) {alias} is now {target} — disabled here")
            shim = _disabled_alias_body(alias, target, comp)
        plan[rel] = ("text", f"---\ndescription: {desc}\n---\n\n{shim}")
    for name, desc in _pipeline_shims(comp):
        # A real prompt template, trailer included: the brief arrives as the
        # template's arguments. The runner it points at is a template too,
        # and read as a file (not run as a command) its own trailer is the
        # raw placeholder, whose default text says no arguments were given.
        # The shim says which Invocation arguments section counts.
        rel = f"{base}/glados-{name}.md"
        shim = _pipeline_shim_body(comp, name, f"{base}/glados-run-pipeline.md",
                                   "/glados-run-pipeline")
        if "run-pipeline" in comp.cores:
            shim += ("\nThat file is itself a prompt template: ignore its "
                     "closing `## Invocation arguments` section, which is an "
                     "unexpanded placeholder when the file is read. The "
                     "brief is in the `## Invocation arguments` section at "
                     "the end of this command.\n")
        plan[rel] = ("text", _pi_template(_yaml_quote(desc), shim, rel))
    return plan


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
        "- You cannot read `glados.yaml` here. Only its optimize-for sentence "
        "was compiled in (see the compile stamp in the provenance header); "
        "every other key a step resolves comes from the copy the operator "
        "pastes with the repo context. If a step needs `glados.yaml` and it "
        "was not pasted, ask for it rather than guess. A key the pasted "
        "manifest leaves unset takes its default from the preset table, "
        "`.glados/presets.yaml`: ask for that file too when you need it.\n"
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
   current `glados.yaml` and `.glados/presets.yaml`, the relevant files, the
   issue text — as your first user message.
4. Run. The model emits `=== WRITE FILE: ... ===` and `=== RUN: ... ===`
   blocks; you (the operator) apply them to the repo and save the run record
   to the ledger (`python .glados/glados.py ledger save`).

## Saved-prompt setup

Save the prompt (System Instructions + run settings) to reuse the workflow. AI
Studio autosaves prompts to your Google Drive.

## Data-governance note

Pasting proprietary repo content into free-tier AI Studio may expose it to
product-improvement use. Confirm your tier's data policy before pasting private
code. The api-runner path (paid API key) is the governed alternative.

## Staleness rule

These bundles are compiled from `glados.yaml`. `MANIFEST.md` records the
compile hash each bundle was built against; it covers the structural keys only
(phase, optimize-for, default-modules, workflows, disabled-workflows, sda, and
the names and descriptions of any pipelines), so re-run `glados.py install
--mode aistudio` whenever one of those changes or GLaDOS is upgraded. The live
keys (channels, decisions, merge-authority, params, sinks, branching, canon)
are not baked in and do not move the hash: paste the current `glados.yaml`
with the repo context so the model sees them, together with
`.glados/presets.yaml`, where the model looks up the default of any key the
manifest leaves unset. When it declares `canon:`, paste the digest files the
workflow consults too: the bundles tell the model to read a digest, never to
fetch the work itself.
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

    # Alias shims are pointer stubs, not bundles (they never join MANIFEST.md).
    # AI Studio has no invocation syntax, so bodies point at bundle FILES.
    for alias, (target, enabled) in _alias_targets(source, comp).items():
        rel = f"{base}/bundles/{alias}.aistudio.md"
        if not enabled:
            plan[rel] = ("text", _disabled_alias_body(alias, target, comp))
            continue
        if target in AISTUDIO_CORES:
            bundle_target = target
        elif target == "fix-bug":
            bundle_target = "fix-bug-advisory"
        else:
            bundle_target = None
        if bundle_target:
            body = (f"The `{alias}` workflow was renamed. Paste "
                    f"`bundles/{bundle_target}.aistudio.md` instead.\n")
        else:
            body = (f"The `{alias}` workflow was renamed to `{target}`, which "
                    f"is execution-heavy and ships no AI Studio bundle — run "
                    f"it from a full install mode (claude / gemini / direct) "
                    f"instead.\n")
        plan[rel] = ("text", body)

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
    "pi": adapter_pi,
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
    "pi": [".pi/prompts"],                 # scoped to glados-*.md, see cleanup
}

# Vendored subtrees EVERY mode owns. Cleaned like OWNED_DIRS so a renamed
# source/persona/hook does not linger and skew the self-contained vendored
# checker. Deliberately excludes .glados/runs/ (run records are user history,
# and no install plans a file there) and the .glados/ root files (always
# re-planned).
VENDOR_OWNED_DIRS = [".glados/src", ".glados/ci", ".glados/hooks",
                     ".glados/personas"]


# =============================================================================
# 9. VENDOR + SCAFFOLD
# =============================================================================


VENDORED_HOOKS = ["claude-stop-hook.py", "gemini-afteragent-guard.py",
                  "agy-hooks.json"]

# The two CI backstop templates, vendored to .glados/ci/ by every install mode
# (decision 9c: the backstop exists everywhere; platform: only selects which
# enable stanza the installer prints).
CI_TEMPLATES = ["glados-check.gitlab-ci.yml", "glados-check.github-actions.yml"]


def vendor_plan(source: Source, manifest_hash: str, report: str) -> dict:
    """Files vendored into <target>/.glados/, identical for every mode. The
    self-copy, presets and source tree must byte-match their sources; vendoring
    src/ makes the vendored checker self-contained (`.glados/glados.py check`
    needs no --source — _resolve_source finds `.glados/src/`)."""
    plan: dict = {}
    self_path = source.root / "bin" / "glados.py"
    if not self_path.exists():
        # A vendored .glados/ source tree carries the compiler at its root.
        self_path = source.root / "glados.py"
    if not self_path.exists():
        raise Fatal(f"cannot find glados.py under {source.root} (tried bin/ "
                    f"and the root) — the source tree is incomplete; pass "
                    f"--source <a full glados checkout>")
    presets_bytes = (source.kernel / "presets" / "phases.yaml").read_bytes()
    plan[".glados/glados.py"] = ("bytes", self_path.read_bytes())
    plan[".glados/presets.yaml"] = ("bytes", presets_bytes)
    plan[".glados/manifest-hash"] = ("text", manifest_hash + "\n")
    plan[".glados/assembly-report.md"] = ("text", report)
    # Vendor the full source tree so the CI backstop can recompute the compile
    # from the repo alone (self-contained check), plus the manifest example the
    # anti-inflation cap reads.
    for f in sorted(source.src.rglob("*")):
        if f.is_file():
            rel = f.relative_to(source.src).as_posix()
            plan[f".glados/src/{rel}"] = ("bytes", f.read_bytes())
    example = source.root / "glados.yaml.example"
    if example.exists():
        plan[".glados/glados.yaml.example"] = ("bytes", example.read_bytes())
    # Vendor the CI templates so MIGRATION step 5's "add the include" has a
    # real, repo-local file to include/copy.
    for name in CI_TEMPLATES:
        src = source.root / "ci" / name
        if src.exists():
            plan[f".glados/ci/{name}"] = ("bytes", src.read_bytes())
    # Vendor the SDA standard/profile docs. scaffold_sda copies these into a
    # consuming project, and without them `install` on an `sda: true` repo
    # dies with "pass --source <a full glados checkout>" — which made the
    # vendored tree self-contained for `check` but not for `install`, so the
    # one command a consumer needs to pick up a re-vendor could not be run
    # from the repo it was vendored into.
    sda_docs = source.root / "docs" / "standards"
    if sda_docs.is_dir():
        for f in sorted(sda_docs.glob("sda-*.md")):
            plan[f".glados/docs/standards/{f.name}"] = ("bytes", f.read_bytes())
    # Vendor the run-record guard scripts (and the agy hooks block of record)
    # so emitted hook references resolve.
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
    """Create-only product-knowledge skeleton; NEVER deletes user content.
    `steps/` holds the bodies of the project's own pipeline steps
    (glados.yaml `steps:`), one `<step-id>.md` each; `canon/` holds the
    digests of the works declared under `canon:` (src/templates/CANON.md is
    the template, vendored under .glados/src/)."""
    created: list[str] = []
    pk = target / "product-knowledge"
    for sub in ("observations", "standards", "philosophies", "personas",
                "steps", "canon"):
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


def _prepend_sda_header(path: Path) -> bool:
    """Idempotently prepend the `SDA: v1.0` version header; True if written.

    read_text validates the encoding first (UTF-16 dies with the named fix
    instead of mojibake); the write is a byte-level prepend so the user's own
    bytes — CRLF endings included — survive untouched after the header."""
    if SDA_MARKER in read_text(path):
        return False
    raw = path.read_bytes().removeprefix(b"\xef\xbb\xbf")
    path.write_bytes(SDA_HEADER.encode("utf-8") + raw)
    return True


def _require_sda_template(source: Source, tmpl: Path) -> Path:
    if not tmpl.exists():
        raise Fatal(f"sda: true but the source tree is missing {tmpl} — pass "
                    f"--source <a full glados checkout> and re-run install")
    return tmpl


def _scaffold_spec_log(target: Path, source: Source, today: str) -> bool:
    """Create product-knowledge/SPEC_LOG.md from the template, dated today
    (the scaffold_sda date-fill precedent). Create-only; True when written."""
    spec_log = target / "product-knowledge" / "SPEC_LOG.md"
    if spec_log.exists():
        return False
    tmpl = _require_sda_template(source, source.src / "templates" / "SPEC_LOG.md")
    spec_log.parent.mkdir(parents=True, exist_ok=True)
    spec_log.write_text(read_text(tmpl).replace("YYYY-MM-DD", today),
                        encoding="utf-8", newline="\n")
    return True


def scaffold_sda(target: Path, source: Source) -> list[str]:
    """Create-only SDA conformance artifacts, run when the manifest sets
    `sda: true`. Never clobbers: existing files win, and the version-header
    prepend is marker-checked (idempotent). Returns repo-relative paths of
    what THIS run created/stamped — the vendored assembly report lists the
    artifact set instead, so re-installs stay byte-identical."""
    created: list[str] = []
    today = datetime.date.today().isoformat()

    def rel(p: Path) -> str:
        return p.relative_to(target).as_posix()

    # 1. claims.md at the repo root, from the template, dated today.
    claims = target / "claims.md"
    if not claims.exists():
        tmpl = _require_sda_template(source, source.src / "templates" / "CLAIMS.md")
        claims.write_text(read_text(tmpl).replace("YYYY-MM-DD", today),
                          encoding="utf-8", newline="\n")
        created.append(rel(claims))

    # 2. product-knowledge/SPEC_LOG.md — the SDA work-unit log the compiled
    #    epilogue appends to (per the standard's work-unit-log format).
    if _scaffold_spec_log(target, source, today):
        created.append(rel(target / "product-knowledge" / "SPEC_LOG.md"))

    # 3. Version headers on the roadmap/status docs IF they exist and lack
    #    one. Never creates the docs themselves — a missing roadmap is the
    #    team's call, not the installer's.
    for name in ("ROADMAP.md", "PROJECT_STATUS.md"):
        doc = target / "product-knowledge" / name
        if doc.is_file() and _prepend_sda_header(doc):
            created.append(rel(doc) + " (SDA header)")

    # 4. The versioned standard + profile docs, copied byte-identically
    #    (install_file fidelity) into the repo's own standards tree.
    docs = sorted((source.root / "docs" / "standards").glob("sda-*.md"))
    if not docs:
        raise Fatal(f"sda: true but no docs/standards/sda-*.md under "
                    f"{source.root} — pass --source <a full glados checkout> "
                    f"and re-run install")
    for doc in docs:
        dest = target / "product-knowledge" / "standards" / doc.name
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(doc.read_bytes())
            created.append(rel(dest))
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


def _remove_tree_files(root: Path, target: Path) -> list[str]:
    """Remove every file under root and prune the emptied directories (root
    included). Returns target-relative paths of the removed files. Only ever
    called on trees GLaDOS owns outright (v1 layouts, converted specs/ dirs)."""
    removed: list[str] = []
    entries = sorted(root.rglob("*"), reverse=True)
    for f in entries:
        if f.is_file():
            _force_unlink(f)
            removed.append(str(f.relative_to(target)))
    for d in entries + [root]:
        if d.is_dir():
            try:
                d.rmdir()
            except OSError:
                pass
    return removed


def _cleanup_owned(target: Path, mode: str, plan: dict, source: Source,
                   comp: Compilation) -> list[str]:
    """Directory-scoped stale-file removal, porting the bash cleanup semantics."""
    removed: list[str] = []
    planned = {str(Path(rel)) for rel in plan}

    for owned in OWNED_DIRS.get(mode, []) + VENDOR_OWNED_DIRS:
        d = target / owned
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file():
                continue
            rel = str(f.relative_to(target))
            if (mode, owned) in (("antigravity", ".agents/workflows"),
                                 ("pi", ".pi/prompts")) \
                    and not f.name.startswith("glados-"):
                continue  # only glados-*.md are ours in these shared dirs
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


def _v1_stem_match(stem: str, names: frozenset) -> bool:
    """A file stem names a known v1 unit, in dash or underscore spelling."""
    return stem in names or stem.replace("_", "-") in names


def _cleanup_v1_legacy(target: Path, mode: str) -> list[str]:
    """Per-mode removal of v1-era layouts the current mode supersedes.

    - gemini: v1's install_gemini fully owned `.gemini/skills/glados/`; the
      whole tree goes.
    - direct: v1 shared `product-knowledge/{workflows,modules}/` with user
      content, so only files whose basenames (or underscore variants) match
      the known v1 workflow/module name sets are removed — never unmatched
      user files. The dirs are removed only if that leaves them empty.
    """
    removed: list[str] = []
    if mode == "gemini":
        root = target / ".gemini" / "skills" / "glados"
        if root.is_dir():
            removed.extend(_remove_tree_files(root, target))
    if mode == "direct":
        for sub, names in (("workflows", KNOWN_V1_WORKFLOWS),
                           ("modules", KNOWN_V1_MODULES)):
            d = target / "product-knowledge" / sub
            if not d.is_dir():
                continue
            for f in sorted(d.glob("*.md")):
                if _v1_stem_match(f.stem, names):
                    _force_unlink(f)
                    removed.append(str(f.relative_to(target)))
            try:
                d.rmdir()  # only succeeds when nothing user-owned remains
            except OSError:
                pass
    return removed


def _resolve_source(args) -> Source:
    if getattr(args, "source", None):
        return Source(Path(args.source).resolve())
    here = Path(__file__).resolve().parent
    # Disambiguate on the GLaDOS source *shape* (src/kernel/), not the mere
    # presence of a src/ dir: a target repo with its own top-level src/ would
    # otherwise shadow the vendored .glados/src/. For bin/glados.py the repo
    # root (here.parent) has src/kernel/ and wins; for a vendored
    # .glados/glados.py, here.parent is the consuming repo (whose unrelated
    # src/ has no kernel/) so it falls through to here (.glados/), which does.
    # A vendored copy tries its own .glados/ FIRST: a consuming repo can
    # have a src/kernel/ of its own (an OS project's kernel sources), and
    # resolving to it failed every vendored check and validate, which
    # run-pipeline runs before its first step.
    order = (here, here.parent) if here.name == ".glados" else (here.parent, here)
    for cand in order:
        if (cand / "src" / "kernel").is_dir():
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
    # Computed before anything can fail: when resolution or a type check
    # fails, a misspelt top-level key ('sinsk:') is often the cause, so the
    # warnings ride on the Fatal (exc.warnings) for install/check to print —
    # together with any the type checks added (an unused step is often the
    # other half of a misspelt sequence id).
    warnings = manifest_warnings(raw, manifest_path.name, source)
    comp = None
    try:
        resolved = resolve_manifest(raw, source.presets, manifest_path.name)
        if mode == "claude-plugin":
            # Never bake the example manifest's phase-resolved optimize-for
            # into artifacts every plugin consumer runs: stamp the
            # phase-neutral baseline sentence, and prepend the bootstrap
            # guard to every core so the consuming repo's own glados.yaml
            # governs at run time.
            resolved.values["optimize-for"] = (
                source.presets.get("baseline") or {}).get("optimize-for")
            resolved.provenance["optimize-for"] = "baseline (claude-plugin is phase-neutral)"
        # The structural hash of the manifest already parsed above (identical
        # to manifest_hash_of(manifest_path), without a second parse).
        manifest_hash = structural_hash(raw)
        comp = compile_all(source, resolved, manifest_hash)
        comp.warnings.extend(warnings)
        if mode == "claude-plugin":
            for name in list(comp.cores):
                comp.cores[name] = PLUGIN_BOOTSTRAP_GUARD + comp.cores[name]
        # The target is the project only in the modes that compile its own
        # manifest; the plugin compiles the example inside GLaDOS itself, so
        # there are no project files (step bodies) to check.
        errors = run_type_checks(source, comp,
                                 None if mode == "claude-plugin" else target)
        if errors:
            raise CheckFailed(errors)
    except Fatal as exc:
        exc.warnings = list(comp.warnings) if comp is not None else warnings
        raise
    return comp, manifest_hash


def cmd_install(args) -> int:
    source = _resolve_source(args)
    target = Path(args.target).resolve()
    mode = args.mode
    if mode not in ADAPTERS:
        raise Fatal(f"unknown mode '{mode}' — one of: {', '.join(INSTALL_MODES)}")
    if not target.is_dir():
        raise Fatal(f"target directory does not exist: {target}")

    # A target full of v1 leftovers but no manifest is a migration half-start:
    # hint at the prefilled path before load_manifest raises its Fatal.
    if mode != "claude-plugin" and not (target / "glados.yaml").exists() \
            and _has_v1_leftovers(target):
        print("glados: v1 GLaDOS files detected but no glados.yaml — this "
              "looks like a v1 -> v2 migration; run `glados.py migrate "
              "--target <repo>` to generate the manifest and convert specs/ "
              "history, then set phase: and re-run install (MIGRATION.md "
              "documents the details)", file=sys.stderr)

    try:
        comp, manifest_hash = _prepare_compilation(source, target, mode)
    except Fatal as exc:
        # Warnings first, then main() prints the error: an unknown key is
        # most useful exactly when the install fails.
        _print_warnings(getattr(exc, "warnings", []))
        raise
    _print_warnings(comp.warnings)
    report = build_assembly_report(source, comp)

    # Read the previously vendored report BEFORE the plan overwrites it, so a
    # phase change can print its advisory transition checklist.
    prev_report = None
    prev_report_path = target / ".glados" / "assembly-report.md"
    if prev_report_path.exists():
        try:
            prev_report = read_text(prev_report_path)
        except Fatal:
            prev_report = None

    plan = ADAPTERS[mode](source, comp)
    plan.update(vendor_plan(source, manifest_hash, report))
    _write_plan(target, plan)
    removed = _cleanup_owned(target, mode, plan, source, comp)
    removed += _cleanup_v1_legacy(target, mode)

    scaffolded: list[str] = []
    sda_scaffolded: list[str] = []
    sda_on = bool(comp.resolved.values.get("sda")) and mode != "claude-plugin"
    if mode not in ("claude-plugin",):
        scaffolded = scaffold_product_knowledge(target, source)
        if sda_on:
            sda_scaffolded = scaffold_sda(target, source)

    if mode == "claude-plugin":
        _regenerate_plugin_skills(target, source, comp)

    if mode == "antigravity":
        _emit_agy_hooks(target, source)

    # The plugin build's target is GLaDOS itself, not a project.
    runs_excluded = mode != "claude-plugin" and _exclude_runs_at(target)

    print(f"glados: installed mode '{mode}' into {target}")
    print(f"glados: {len(comp.enabled)} cores, manifest {manifest_hash[:12]}…")
    if runs_excluded:
        print(f"glados: added {runs_excluded} to the clone's git exclude file "
              f"— run records go to the {LEDGER_BRANCH} branch, never in a "
              f"commit")
    if removed:
        print(f"glados: cleaned {len(removed)} stale file(s): {', '.join(removed)}")
    if scaffolded:
        print(f"glados: scaffolded {len(scaffolded)} product-knowledge file(s)")
    if sda_scaffolded:
        print(f"glados: sda: true — scaffolded {', '.join(sda_scaffolded)}")
    elif sda_on:
        print("glados: sda: true — all conformance artifacts already present")
    advisory = _phase_transition_advisory(prev_report, comp.resolved.phase)
    if advisory:
        print(advisory)
    try:
        ci_wired = _ci_check_wired(target)
    except Fatal:
        ci_wired = False
    if not ci_wired:
        print(_ci_enable_stanza(comp.resolved.values.get("platform")))
    print()
    print(report)
    print(f"glados: assembly report written to .glados/assembly-report.md")
    return 0


def _has_v1_leftovers(target: Path) -> bool:
    """Cheap detection of a v1 GLaDOS install in the target tree."""
    if (target / ".gemini" / "skills" / "glados").is_dir():
        return True
    for sub, names in (("workflows", KNOWN_V1_WORKFLOWS),
                       ("modules", KNOWN_V1_MODULES)):
        d = target / "product-knowledge" / sub
        if d.is_dir():
            for f in d.glob("*.md"):
                if _v1_stem_match(f.stem, names):
                    return True
    cmds = target / ".claude" / "commands"
    if cmds.is_dir():
        for name in KNOWN_V1_WORKFLOWS:
            if (cmds / f"{name}.md").is_file() or \
                    (cmds / f"{name.replace('-', '_')}.md").is_file():
                return True
    return False


def _phase_transition_advisory(prev_report, new_phase: str):
    """Advisory-only checklist when the phase differs from the previously
    vendored assembly report. Never blocks; returns None when not a transition."""
    if not prev_report:
        return None
    m = re.search(r"^- phase: `([a-z]+)`", prev_report, re.M)
    if not m:
        return None
    old = m.group(1)
    if old == new_phase or old not in PHASES or new_phase not in PHASES:
        return None
    lines = [f"glados: phase transition {old} -> {new_phase} — advisory "
             f"checklist (nothing here blocks the install):"]
    for item in PHASE_TRANSITION_CHECKLISTS.get(new_phase, []):
        lines.append(f"  [ ] {item}")
    if PHASES.index(new_phase) < PHASES.index(old):
        lines.append("  [ ] backward move — say why in the MR that changes "
                     "glados.yaml")
    return "\n".join(lines)


def _ci_enable_stanza(platform) -> str:
    """The one-paste instruction wiring the vendored CI backstop, selected by
    the manifest's platform: key (both templates are always vendored)."""
    gitlab = ("glados: CI backstop vendored to .glados/ci/ — enable it in "
              ".gitlab-ci.yml:\n"
              "    include:\n"
              "      - local: '.glados/ci/glados-check.gitlab-ci.yml'")
    # .github/workflows/ first: a repository with no workflow yet lacks it,
    # and `cp` failed as printed. Two lines, as Windows PowerShell 5.1 has
    # no `&&`.
    github = ("glados: CI backstop vendored to .glados/ci/ — enable it with:\n"
              "    mkdir -p .github/workflows\n"
              "    cp .glados/ci/glados-check.github-actions.yml "
              ".github/workflows/glados-check.yml")
    if platform == "github":
        return github
    if platform == "gitlab":
        return gitlab
    return gitlab + "\n" + github


def _regenerate_plugin_skills(target: Path, source: Source, comp: Compilation) -> None:
    """Prune stale skills/ dirs (keeping init), leave user skills untouched.

    Pruning is marker-based, not name-based: a dir is ours to remove only when
    its SKILL.md contains the generated-stub marker every stub emitted by
    adapter_claude_plugin carries. User skills lack the marker, so they are
    structurally untouchable — no name list to maintain, and a retired core or
    alias is pruned automatically."""
    skills = target / "skills"
    if not skills.is_dir():
        return
    keep = set(comp.enabled) | set(source.aliases) | {"init"}
    for d in sorted(skills.iterdir()):
        if not d.is_dir() or d.name in keep:
            continue
        skill_md = d / "SKILL.md"
        if not skill_md.is_file():
            continue  # not a stub layout — leave it alone
        try:
            text = read_text(skill_md)
        except Fatal:
            continue  # unreadable = not provably ours — leave it alone
        if PLUGIN_STUB_MARKER not in text:
            continue  # user-authored skill — never touch
        for f in sorted(d.rglob("*"), reverse=True):
            if f.is_file():
                _force_unlink(f)
        try:
            d.rmdir()
        except OSError:
            pass


def _read_agy_hooks_block(source: Source) -> str:
    """hooks/agy-hooks.json is the single file of record for the antigravity
    hooks block (vendored to .glados/hooks/ with the guard scripts). Missing
    or invalid is a broken source tree, never a silent skip."""
    path = source.root / "hooks" / "agy-hooks.json"
    if not path.exists():
        raise Fatal(f"missing {path} — hooks/agy-hooks.json is the file of "
                    f"record for the antigravity hooks block; restore it")
    try:
        data = json.loads(read_text(path))
    except ValueError as exc:
        raise Fatal(f"{path}: invalid JSON ({exc}) — fix the file of record")
    return json.dumps(data, indent=2) + "\n"


def _emit_agy_hooks(target: Path, source: Source) -> None:
    """Write .agents/hooks.json ONLY if absent; never clobber a user's file."""
    hooks = target / ".agents" / "hooks.json"
    block = _read_agy_hooks_block(source)
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
    if (target / ".pi/prompts").is_dir() and \
            any((target / ".pi/prompts").glob("glados-*.md")):
        modes.append("pi")
    return modes


# Planned files `check` requires to EXIST but never byte-compares. The
# assembly report is an informational record of the last install: it renders
# live lane-2 values (channels, sinks, params, decisions, branching), so it
# legitimately goes stale on every lane-2 edit, and byte-checking it made
# those edits fail `check` — the opposite of the lane-2 promise. Doctor says
# when it predates later edits.
CHECK_PRESENCE_ONLY = {".glados/assembly-report.md"}


def _installed_drift(source: Source, target: Path, mode: str,
                     comp: Compilation, manifest_hash: str,
                     report: str) -> list[tuple[str, str]]:
    """(relpath, problem) for every planned file of ``mode`` that is missing
    or differs from a fresh render. Files in CHECK_PRESENCE_ONLY need only
    exist. Shared by `check` (each pair is a failure) and `doctor` (which
    must know whether anything besides the report is stale before saying
    nothing is)."""
    plan = ADAPTERS[mode](source, comp)
    plan.update(vendor_plan(source, manifest_hash, report))
    out: list[tuple[str, str]] = []
    for rel, (kind, data) in plan.items():
        path = target / rel
        if not path.exists():
            out.append((rel, "missing installed file"))
            continue
        if rel in CHECK_PRESENCE_ONLY:
            continue
        if kind == "bytes":
            drift = path.read_bytes() != data
        else:
            drift = read_text(path) != data
        if drift:
            out.append((rel, "drift in installed file"))
    return out


def _installed_version(target: Path) -> str | None:
    """The GLaDOS version that built the install at ``target``: the VERSION
    line of its vendored .glados/glados.py. None when there is no vendored
    copy or it carries no VERSION line."""
    try:
        text = (target / ".glados" / "glados.py").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    m = re.search(r'^VERSION = "([^"]+)"', text, re.M)
    return m.group(1) if m else None


def _version_skew(target: Path) -> str | None:
    """When the install at ``target`` was built by another GLaDOS version
    than this one, the sentence that says so; else None.

    A hash mismatch then proves nothing about glados.yaml: 2.5 changed the
    manifest hash from the whole file to its structural keys, so the first
    2.5 check of an untouched 2.4 install mismatches, and blaming "a
    structural key changed" sends the user hunting for an edit nobody made.
    The cause is the version, and the fix is the same reinstall."""
    installed = _installed_version(target)
    if installed is None or installed == VERSION:
        return None
    return (f"this install was built by GLaDOS {installed} and this is "
            f"GLaDOS {VERSION} — re-run install with {VERSION} to upgrade it "
            f"(its own .glados/glados.py checks it as it stands)")


def cmd_check(args) -> int:
    target = Path(args.target).resolve()
    report_only = args.report_only
    problems: list[str] = []

    # An unreadable/unresolvable source must not hard-exit a --report-only run:
    # it becomes a reported problem, and enforcing mode still fails cleanly.
    source = None
    try:
        source = _resolve_source(args)
    except Fatal as exc:
        problems.append(f"cannot resolve the GLaDOS source tree: {exc}")

    modes = _detect_modes(target)
    if not modes:
        # Deliberately fatal even under --report-only. Every install mode this
        # detects lands in a directory a project may gitignore, so in CI, on a
        # fresh clone, "no install detected" is the normal shape of a repo
        # whose compiled artifacts never travel — and returning 0 for it turns
        # the drift check, the manifest-hash check, and every type check into
        # a job that passes without reading anything. A checker that cannot
        # see the thing it checks reports that, loudly, in both modes.
        problems.append(
            f"no GLaDOS install detected under {target} — nothing was "
            f"checked. Install modes live in directories that are commonly "
            f"gitignored (.claude/, .gemini/); commit one install mode so "
            f"this job has an artifact to verify, or run check where the "
            f"install actually is")
        _emit_check(problems, report_only)
        return 1

    # manifest hash: recompute vs vendored
    try:
        hash_path = target / ".glados" / "manifest-hash"
        manifest_path = target / "glados.yaml"
        if not manifest_path.exists() and modes == ["claude-plugin"]:
            manifest_path = target / "glados.yaml.example"
        if hash_path.exists() and manifest_path.exists():
            vendored = read_text(hash_path).strip()
            current = manifest_hash_of(manifest_path)
            skew = _version_skew(target)
            if skew:
                # The compiled headers carry glados-version, so a version
                # change always drifts every installed file too; this line
                # says why, and a hash mismatch then proves nothing about
                # glados.yaml.
                problems.append(f"stale compile: {skew}")
            elif vendored != current:
                problems.append(f"stale compile: a structural glados.yaml key "
                                f"({', '.join(STRUCTURAL_KEYS)}, or a "
                                f"pipelines: name or description) changed since "
                                f"install — manifest-hash {vendored[:12]}… != "
                                f"current {current[:12]}…; re-run glados install")
    except Fatal as exc:
        problems.append(f"cannot compare manifest hash: {exc}")

    warnings: list[str] = []
    for mode in (modes if source is not None else []):
        try:
            comp, manifest_hash = _prepare_compilation(source, target, mode)
        except Fatal as exc:
            problems.append(f"[{mode}] {exc}")
            # A failing mode still reports its manifest warnings: a misspelt
            # top-level key is often the cause of the failure itself.
            warnings += [w for w in getattr(exc, "warnings", [])
                         if w not in warnings]
            continue
        warnings += [w for w in comp.warnings if w not in warnings]
        report = build_assembly_report(source, comp)
        for rel, why in _installed_drift(source, target, mode, comp,
                                         manifest_hash, report):
            problems.append(f"[{mode}] {why}: {rel}")

    _print_warnings(warnings)
    _emit_check(problems, report_only)
    if report_only:
        return 0
    return 1 if problems else 0


def cmd_validate(args) -> int:
    """Type-check a project's glados.yaml without installing anything.

    Loads <target>/glados.yaml, resolves it against the source presets,
    compiles in memory (claude mode: the compile is mode-independent, and it
    is a mode that sees the project's own files) and runs every type check,
    the pipeline rules with the step-body checks included. Prints errors and
    warnings, writes nothing, and exits 1 on any error.

    It needs no install, so a plugin-only repo can run it, from the plugin's
    own `bin/glados.py` (_resolve_source finds `src/` beside `bin/`) or from
    a pinned GLaDOS checkout in CI. run-pipeline calls it before its first
    step, from the GLaDOS that compiled the running workflow."""
    source = _resolve_source(args)
    target = Path(args.target).resolve()
    if not target.is_dir():
        raise Fatal(f"target directory does not exist: {target}")
    try:
        comp, _ = _prepare_compilation(source, target, "claude")
    except CheckFailed as exc:
        _print_warnings(getattr(exc, "warnings", []))
        print(f"glados validate: FAIL — {len(exc.errors)} error(s) in "
              f"{target / 'glados.yaml'}")
        for e in exc.errors:
            print(f"  - {e}")
        return 1
    except Fatal as exc:
        _print_warnings(getattr(exc, "warnings", []))
        print(f"glados validate: FAIL — {target / 'glados.yaml'}")
        print(f"  - {exc}")
        return 1
    _print_warnings(comp.warnings)
    pipes = comp.resolved.values.get("pipelines") or {}
    steps = comp.resolved.values.get("steps") or {}
    print(f"glados validate: OK — {target / 'glados.yaml'} passes every "
          f"check ({len(pipes)} pipeline(s), {len(steps)} project step(s), "
          f"{len(comp.warnings)} warning(s))")
    return 0


# ---- effective-config ---------------------------------------------------------
#
# A run obeys glados.yaml layered over the preset table (baseline < phase <
# explicit), not glados.yaml alone: a bound or decision class the manifest
# leaves out comes from the table. Pinning only glados.yaml's blob let such a
# value change mid-run unseen — a re-vendored or edited .glados/presets.yaml,
# a plugin update, a toolchain whose layering moved. run-pipeline pins this
# digest of the resolved values beside the blobs; a resumed run takes the
# fresh one from the branch the work targets with --ref.

RUN_PRESETS = ".glados/presets.yaml"


def _blob_text(data: bytes, name: str) -> str:
    """A blob's bytes as read_text reads a file: UTF-8, a BOM allowed, LF."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Fatal(f"{name}: not valid UTF-8 ({exc.reason} at byte "
                    f"{exc.start}) — re-save the file as UTF-8")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def run_configuration(source: Source, target: Path, ref=None):
    """(resolved, where): the configuration a run in ``target`` obeys and
    where it was read. glados.yaml is layered over the preset table the
    preamble names, `.glados/presets.yaml`, else this toolchain's own (the
    plugin's path mapping). With ``ref``, each is read as that commit has
    it; a table the commit does not track is read from the working tree,
    as the run reads it."""
    git = sha = None
    if ref is None:
        raw = load_manifest(target / "glados.yaml")
        where = "glados.yaml"
    else:
        git = _LedgerGit(target)
        sha = git.rev(ref)
        if sha is None:
            raise Fatal(f"--ref {ref}: not a commit in {target}")
        proc = git.run("cat-file", "blob", f"{sha}:./glados.yaml", check=False)
        if proc.returncode != 0:
            raise Fatal(f"{ref} has no glados.yaml in {target} — a run there "
                        f"has no manifest to obey")
        raw = parse_manifest(_blob_text(proc.stdout, f"{ref}:glados.yaml"),
                             "glados.yaml")
        where = f"glados.yaml at {ref}"
    table, table_where = None, f"{RUN_PRESETS} at {ref}"
    if sha is not None:
        proc = git.run("cat-file", "blob", f"{sha}:./{RUN_PRESETS}",
                       check=False)
        if proc.returncode == 0:
            table = parse_yaml(_blob_text(proc.stdout, table_where),
                               "presets.yaml")
    if table is None and (target / RUN_PRESETS).is_file():
        table, table_where = (parse_yaml(read_text(target / RUN_PRESETS),
                                         "presets.yaml"), RUN_PRESETS)
    if table is None:
        table = source.presets
        table_where = (source.kernel / "presets" / "phases.yaml").as_posix()
    if not isinstance(table, dict):
        raise Fatal(f"{table_where}: the preset table must be a mapping of "
                    f"'baseline:' and one entry per phase")
    return (resolve_manifest(raw, table, "glados.yaml", table_where),
            f"{where} over {table_where}")


def effective_config_digest(r: Resolved) -> str:
    """sha256 of the canonical JSON of every resolved value (bounds,
    decision classes, merge authority, channels and the rest) as layering
    left them: only a change to what a run obeys moves it."""
    canonical = json.dumps(r.values, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cmd_effective_config(args) -> int:
    """Print the digest run-pipeline pins: the configuration a run obeys,
    inherited bounds and decision rights included. A bound no loop could
    stop at is refused, not pinned: one that is not a whole number of 1 or
    more, and one a workflow this configuration enables references but the
    table leaves absent or null (validate resolves against the toolchain's
    table, not the one the run reads). So is a decision class or merge
    authority the table misspells."""
    source = _resolve_source(args)
    target = Path(args.target).resolve()
    if not target.is_dir():
        raise Fatal(f"target directory does not exist: {target}")
    r, where = run_configuration(source, target, args.ref)
    comp = compile_all(source, r, structural_hash(r.raw))
    errors = (unresolved_params_errors(comp) + loop_bound_errors(r)
              + decision_value_errors(r))
    if errors:
        print(f"glados effective-config: FAIL — {where}")
        skew = _version_skew(target)
        if skew:
            # Before the reinstall the run's table is the old version's,
            # which lacks keys this version's workflows read, and each error
            # below says to set them in glados.yaml: a value there would
            # override the preset from then on.
            print(f"  - {skew}. Until then {RUN_PRESETS} is GLaDOS "
                  f"{_installed_version(target)}'s table: what it lacks below "
                  f"is the reinstall's to supply, not glados.yaml's")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"glados effective-config: {effective_config_digest(r)} — {where} "
          f"(phase: {r.phase})")
    return 0


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
    try:
        if hash_path.exists() and manifest_path.exists():
            vendored = read_text(hash_path).strip()
            current = manifest_hash_of(manifest_path)
            skew = _version_skew(target)
            state = ("current" if vendored == current else
                     f"STALE — {skew}" if skew else
                     "STALE — a structural key changed; re-run install")
            print(f"  manifest hash: {state} ({current[:12]}…)")
        else:
            print("  manifest hash: not vendored (no .glados/manifest-hash)")
    except Fatal as exc:
        print(f"  manifest hash: UNREADABLE — {exc}")

    print(_assembly_report_doctor_line(source, target, modes))

    try:
        if _ci_check_wired(target):
            print("  CI check wired: yes")
        else:
            print("  CI check wired: no — enable the vendored template under "
                  ".glados/ci/ (see the install output)")
    except Fatal as exc:
        print(f"  CI check wired: UNREADABLE — {exc}")

    hooks = []
    if (target / ".claude" / "settings.json").exists():
        try:
            data = json.loads(read_text(target / ".claude" / "settings.json"))
            if "hooks" in data:
                hooks.append("claude")
        except (ValueError, OSError, Fatal):
            pass
    if (target / ".agents" / "hooks.json").exists():
        hooks.append("antigravity")
    if (target / ".gemini" / "settings.json").exists():
        hooks.append("gemini")
    print(f"  run-record hooks: {', '.join(hooks) if hooks else '(none installed)'}")

    # CODEOWNERS on glados.yaml — informational: agents propose phase changes,
    # humans approve them; a covered manifest makes that structural.
    found = None
    for rel in ("CODEOWNERS", ".github/CODEOWNERS", ".gitlab/CODEOWNERS",
                "docs/CODEOWNERS"):
        if (target / rel).is_file():
            found = rel
            break
    # The directories whose files gate runs (a project step's body can
    # loosen a gate as surely as glados.yaml can), reported once the project
    # uses them.
    gating = _gating_dirs_in_use(target, manifest_path)
    if found is None:
        print("  CODEOWNERS: none found — consider one covering glados.yaml"
              + "".join(f" and {g}" for g in gating)
              + " (agents propose phase changes; humans approve"
              + "".join(f"; {GATING_DIRS[g]}" for g in gating)
              + ")")
    else:
        try:
            owners = read_text(target / found)
        except Fatal:
            owners = ""
        mentions = "glados.yaml" in owners
        print(f"  CODEOWNERS: {found} "
              + ("covers glados.yaml" if mentions else
                 "does not mention glados.yaml — consider protecting phase "
                 "changes"))
        for gdir in gating:
            print(f"  CODEOWNERS: {found} "
                  + (f"covers {gdir}" if _codeowners_cover(owners, gdir) else
                     f"has no pattern found covering {gdir} — "
                     f"{GATING_DIRS[gdir]}; consider the same owners as "
                     f"glados.yaml"))

    if manifest_path.exists():
        try:
            raw = load_manifest(manifest_path)
        except Fatal as exc:
            print(f"  phase: UNREADABLE — {exc}")
        else:
            declared = raw.get("phase-declared")
            print(f"  phase: {raw.get('phase')} "
                  f"(declared: {declared or 'undated — add phase-declared:'})")
            unknown = unknown_manifest_keys(raw)
            if unknown:
                print(f"  manifest keys: unknown top-level key(s) "
                      f"{', '.join(unknown)} — ignored; known keys: "
                      f"{', '.join(KNOWN_MANIFEST_KEYS)}")
            else:
                print("  manifest keys: all known")
            for key in ("visibility-acknowledged", "relaxation-acknowledged"):
                if key in raw:
                    print(f"  confession restated: {key}: {_fmt(raw[key])}")
            for line in _sda_doctor_lines(target, raw):
                print(line)
            for line in _canon_doctor_lines(target, raw):
                print(line)

    print("glados doctor: informational only — never fails")
    return 0


def _gating_dirs_in_use(target: Path, manifest_path: Path) -> list[str]:
    """GATING_DIRS entries this project uses: the manifest declares the
    matching block (`steps:`, `canon:`), or the directory holds a markdown
    file. Never raises."""
    declared: set = set()
    try:
        if manifest_path.exists():
            declared = set(load_manifest(manifest_path))
    except Fatal:
        pass
    used: list[str] = []
    for gdir in GATING_DIRS:
        key = gdir.rstrip("/").rsplit("/", 1)[-1]          # steps, canon, ...
        d = target / gdir
        if key in declared or (d.is_dir() and any(d.glob("*.md"))):
            used.append(gdir)
    return used


def _codeowners_cover(owners: str, gdir: str) -> bool:
    """Does a CODEOWNERS pattern cover ``gdir``: the directory itself, a
    directory above it, or files under it (`/product-knowledge/steps/*.md`)?
    Follows the gitignore anchoring rule: a pattern with a slash at the start
    or in the middle is relative to the repo root, one without (`steps/`) or
    led by `**/` matches at any depth. The root catch-all `*` does not count,
    as it does not for the glados.yaml line. A pattern-level reading, not a
    full gitignore-style matcher: other globs are not expanded."""
    parts = gdir.strip("/").split("/")
    full = "/".join(parts)
    # anchored: the directory and each one above it, from the repo root;
    # anywhere: every run of path segments, for patterns that float.
    anchored = {"/".join(parts[:i]) for i in range(1, len(parts) + 1)}
    anywhere = {"/".join(parts[i:j]) for i in range(len(parts))
                for j in range(i + 1, len(parts) + 1)}
    tails = {"/".join(parts[i:]) for i in range(len(parts))}
    for line in owners.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        raw = line.split()[0]
        floats = raw.startswith("**/")
        if floats:
            raw = raw[3:]
        floats = floats or not (raw.startswith("/")
                                or "/" in raw.strip("/"))
        pattern = raw.strip("/")
        for suffix in ("/**", "/*"):
            if pattern.endswith(suffix):
                pattern = pattern[:-len(suffix)]
        if pattern in ("", "*", "**"):
            continue
        names, roots = (anywhere, tails) if floats else (anchored, {full})
        if pattern in names or any(pattern.startswith(r + "/") for r in roots):
            return True
    return False


def _assembly_report_doctor_line(source: Source, target: Path,
                                 modes: list[str]) -> str:
    """Whether the vendored assembly report matches a fresh render.

    `check` no longer byte-compares the report (CHECK_PRESENCE_ONLY): it
    renders lane-2 values, so it goes stale on every lane-2 edit without
    anything being wrong. Doctor still says so, because a reader of the report
    deserves to know it shows the manifest as of the last install.

    "Nothing is stale" is a claim, so it is checked before it is printed: the
    report also differs when the GLaDOS source changed (a newer VERSION, a
    preset edit) or after a structural edit the hash cannot see, and then
    the compiled files drift too. Every planned file is byte-compared as
    `check` does (_installed_drift), and the informational wording is used
    only when the report is the only thing that differs.

    Never raises: doctor never fails, so any error while rendering (not only
    a Fatal) becomes the "could not render" line."""
    path = target / ".glados" / "assembly-report.md"
    if not path.exists():
        return "  assembly report: not vendored (no .glados/assembly-report.md)"
    if not modes:
        return "  assembly report: present (no install mode detected to compare)"
    try:
        vendored = read_text(path)
    except Fatal as exc:
        return f"  assembly report: UNREADABLE — {exc}"
    fresh: list[str] = []
    hashes: set[str] = set()
    drifted: set[str] = set()
    for mode in modes:
        try:
            comp, manifest_hash = _prepare_compilation(source, target, mode)
            report = build_assembly_report(source, comp)
            drift = _installed_drift(source, target, mode, comp,
                                     manifest_hash, report)
        except Exception as exc:  # deliberately broad: doctor never fails
            text = str(exc)
            first = text.splitlines()[0] if text else type(exc).__name__
            if isinstance(exc, CheckFailed) and exc.errors:
                # The first line is only "install checks failed:".
                more = len(exc.errors) - 1
                first = exc.errors[0] + (f"; and {more} more" if more else "")
            elif not isinstance(exc, Fatal):
                first = f"{type(exc).__name__}: {first}"
            return (f"  assembly report: could not render a fresh copy to "
                    f"compare ({first}) — run check for details")
        fresh.append(report)
        hashes.add(manifest_hash)
        drifted.update(rel for rel, _ in drift)
    if vendored in fresh:
        return "  assembly report: current"
    hash_path = target / ".glados" / "manifest-hash"
    try:
        vendored_hash = read_text(hash_path).strip() if hash_path.exists() else ""
    except (Fatal, OSError):
        vendored_hash = ""
    skew = _version_skew(target)
    if vendored_hash and vendored_hash not in hashes:
        if skew:
            return f"  assembly report: {skew}"
        return ("  assembly report: predates later glados.yaml edits, "
                "including a structural one — re-run install")
    if drifted:
        return (f"  assembly report: differs from a fresh render and "
                f"{len(drifted)} installed file(s) drift — "
                + (skew or "re-run install (glados.py check lists them)"))
    return ("  assembly report: the assembly report predates later glados.yaml "
            "edits; re-run install to refresh it — informational, nothing is "
            "stale")


def _sda_doctor_lines(target: Path, raw: dict) -> list[str]:
    """Informational sda status: the declared value plus whether each
    scaffolded conformance artifact exists. Never raises."""
    sda = raw.get("sda", False)
    if not isinstance(sda, bool):
        return [f"  sda: INVALID — {sda!r} is not a bool; write 'sda: true' "
                f"or 'sda: false'"]
    if not sda:
        return ["  sda: false (SDA conformance not declared)"]
    lines = ["  sda: true (explicit) — scaffolded artifacts:"]
    lines.append("    - claims.md: "
                 + ("present" if (target / "claims.md").is_file()
                    else "missing — re-run install"))
    spec_log = target / "product-knowledge" / "SPEC_LOG.md"
    lines.append("    - product-knowledge/SPEC_LOG.md: "
                 + ("present" if spec_log.is_file()
                    else "missing — re-run install"))
    for name in ("ROADMAP.md", "PROJECT_STATUS.md"):
        doc = target / "product-knowledge" / name
        if not doc.is_file():
            lines.append(f"    - product-knowledge/{name}: absent (the header "
                         f"is added only when the file exists)")
            continue
        try:
            has = SDA_MARKER in read_text(doc)
        except Fatal:
            has = False
        lines.append(f"    - product-knowledge/{name}: SDA header "
                     + ("present" if has else "missing — re-run install"))
    std_dir = target / "product-knowledge" / "standards"
    n_std = len(list(std_dir.glob("sda-*.md"))) if std_dir.is_dir() else 0
    lines.append(f"    - product-knowledge/standards/sda-*.md: "
                 + (f"{n_std} doc(s) present" if n_std
                    else "missing — re-run install"))
    return lines


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def _canon_doctor_lines(target: Path, raw: dict, today=None) -> list[str]:
    """Informational canon status: per declared entry, whether its digest
    exists, its age (`retrieved:` older than CANON_STALE_DAYS), its length
    (over about CANON_DIGEST_MAX_WORDS words, frontmatter and HTML comments
    left out, so the template's unfinished guidance comment does not count)
    and whether it was drafted from recall. The digests are read here, and
    only here, because doctor reports on the project's files; nothing it
    reads is printed beyond these facts. Never raises."""
    try:
        block = raw.get("canon")
        if block is None:
            return ["  canon: none declared"]
        if not isinstance(block, dict):
            return ["  canon: INVALID — the block must be a mapping keyed by "
                    "name (run check for details)"]
        today = today or datetime.date.today()
        lines = [f"  canon: {len(block)} "
                 f"{'entry' if len(block) == 1 else 'entries'} declared — "
                 f"digests:"]
        for name, entry in block.items():
            try:
                status = _canon_digest_status(target, entry, today)
            except Exception as exc:  # one bad digest never hides the rest
                status = (f"could not inspect the digest "
                          f"({type(exc).__name__}: {exc})")
            lines.append(f"    - {name}: {status}")
        return lines
    except Exception as exc:  # deliberately broad: doctor never fails
        return [f"  canon: could not inspect the digests "
                f"({type(exc).__name__}: {exc})"]


def _canon_digest_status(target: Path, entry, today) -> str:
    digest = entry.get("digest") if isinstance(entry, dict) else None
    if canon_digest_problem(digest):
        return "no usable digest path (run check for details)"
    rel = digest.strip().replace("\\", "/")
    path = target / rel
    problem = _canon_digest_resolve_problem(target, rel)
    if problem:
        return f"{rel} {problem[0]} (run check for details)"
    if path.is_dir():
        return f"{rel} is a directory (run check for details)"
    if not path.is_file():
        try:
            listed = path.name in {p.name for p in path.parent.iterdir()}
        except OSError:
            listed = False
        if listed:                      # a broken symlink, or a loop
            return (f"{rel} cannot be opened as a file (run check for "
                    f"details)")
        return (f"{rel} missing — write it from the CANON.md template; every "
                f"consult point reports it missing until then")
    try:
        text = read_text(path)
    except Fatal as exc:
        return f"{rel} cannot be read — {str(exc).splitlines()[0]}"
    try:
        fm, body = split_frontmatter(text, rel)
    except Fatal as exc:
        return f"{rel} has unreadable frontmatter — {str(exc).splitlines()[0]}"
    fm = fm if isinstance(fm, dict) else {}
    notes: list[str] = []
    retrieved = fm.get("retrieved")
    age = None
    try:
        age = (today - datetime.date.fromisoformat(str(retrieved))).days
    except ValueError:
        notes.append(f"no `retrieved:` date (YYYY-MM-DD) in its frontmatter"
                     if retrieved is None else
                     f"`retrieved: {retrieved}` is not a date (YYYY-MM-DD)")
    if age is not None and age < 0:
        notes.append(f"`retrieved: {retrieved}` is in the future — a typo "
                     f"there hides the digest's age")
    elif age is not None and age > CANON_STALE_DAYS:
        notes.append(f"retrieved {retrieved}, {age} days ago (over "
                     f"{CANON_STALE_DAYS}) — the steward pass re-fetches a "
                     f"URL source; re-read a book and update the digest")
    words = len(_HTML_COMMENT_RE.sub(" ", body).split())
    if words > CANON_DIGEST_MAX_WORDS:
        notes.append(f"{words} words (keep a digest under about "
                     f"{CANON_DIGEST_MAX_WORDS:,}: the principles that change "
                     f"decisions here, not a chapter-by-chapter summary)")
    if fm.get("drafted-from") == "recall":
        notes.append("drafted from recall — advisory only until a person "
                     "checks it against the source and sets "
                     "`drafted-from: source`")
    if notes:
        return f"{rel} — " + "; ".join(notes)
    return f"{rel} ok (retrieved {retrieved}, {words} words)"


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
            # git writes UTF-8; the locale's codec (cp1252 on Windows)
            # cannot decode every byte of it, and stdout came back None.
            out = subprocess.run(["git", "-C", str(target), *a],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace",
                                 timeout=30)
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
    feature_branches = [b for b in branches
                        if b and b not in ("main", "master", LEDGER_BRANCH)]

    # Records live on the ledger branch, so a clone without it has none to
    # count: say so rather than report a silent loss. GitHub's checkout with
    # fetch-depth 0 brings every branch; the GitLab job fetches it first.
    ledger_refs = [r for r in git("for-each-ref", "--format=%(refname)",
                                  "refs/heads", "refs/remotes").split()
                   if r == LEDGER_REF or r.endswith("/" + LEDGER_BRANCH)]
    if ledger_refs:
        print(f"  ledger branch: {', '.join(ledger_refs)}")
    else:
        print(f"  ledger branch: {LEDGER_BRANCH} is not in this clone — fetch "
              f"it to count the run records that live there")
    print(f"  run-record commits (chore(glados): record …): {record_commits}")
    print(f"  feature/other branches: {len(feature_branches)}")
    print(f"  MR-less verdict/review commits (silent-loss candidates): "
          f"{len(verdict_commits)}")
    for v in verdict_commits[:20]:
        print(f"    - {v}")
    if record_commits == 0 and feature_branches and ledger_refs:
        print("  WARNING: agent-authored branches exist with zero run records — "
              "this is the class-B silent loss verify-ledger exists to surface")

    # A work branch carries the change, never the run's records (epilogue
    # step 4). Compared with the merge-base of the branch it targets: an
    # explicit --base, else the merge request's diff base in GitLab CI, else
    # the pull request's base branch in GitHub Actions. Records committed
    # before they moved to the ledger are history and are not listed: only
    # the commits this branch adds count.
    base = getattr(args, "base", None) \
        or os.environ.get("CI_MERGE_REQUEST_DIFF_BASE_SHA") \
        or (f"origin/{os.environ['GITHUB_BASE_REF']}"
            if os.environ.get("GITHUB_BASE_REF") else None)
    if not base:
        print("  run records on this branch: not checked (no base to compare "
              "with — pass --base <target branch>)")
    else:
        mb = git("merge-base", base, "HEAD").strip()
        if not mb:
            print(f"  run records on this branch: not checked ({base} is not "
                  f"in this clone)")
        else:
            # Paths from the target, so a project in a subdirectory of its
            # repository is read like one at the top level.
            added = [p for p in git("diff", "--name-only", "--relative",
                                    "--diff-filter=AM", mb, "HEAD", "--",
                                    RUNS_DIR).split("\n")
                     if p and p != RUNS_IGNORE_FILE]
            print(f"  run records this branch commits (since {base}): "
                  f"{len(added)}")
            for p in added[:20]:
                print(f"    - {p}")
            if len(added) > 20:
                print(f"    … and {len(added) - 20} more")
            if added:
                print(f"  WARNING: run records belong on {LEDGER_BRANCH}, not "
                      f"in a merge request's diff — save them with `glados.py "
                      f"ledger save` and leave them out of the branch")
    print("glados verify-ledger: report-only")
    return 0


# ---- ledger -----------------------------------------------------------------
#
# `glados.py ledger save | restore | link` moves run records between the
# working tree and the `glados/ledger` branch. Every run's record and step
# artifacts live on that branch and never on a work branch, so a merge
# request's diff is the change (epilogue step 4). Agents still read and
# write them under `.glados/runs/`, which the clone's exclude file keeps out
# of every branch's commits (_ensure_runs_ignored). Records an older GLaDOS
# committed to a branch stay there: nothing here rewrites history.
#
# save builds its commit in a temporary index, so the checked-out branch,
# the real index and the working tree's tracked files are never touched,
# moves refs/heads/glados/ledger with a compare-and-swap, and pushes it. It
# never force-pushes. When another session pushed meanwhile, its commit
# becomes a parent of ours: a file one side changed takes that side, and a
# file both changed is merged keeping both sides' lines (`git merge-file
# --union`), with a warning naming it. A local copy that is an earlier
# version of the ledger's is refreshed, never written back over it. The
# version of each file this working tree last synced with the ledger is
# kept in the git dir (LEDGER_SYNC_FILE): it is the base those merges
# compare against, and how a stale copy is told from an edited one.

LEDGER_BRANCH = "glados/ledger"
LEDGER_REF = "refs/heads/" + LEDGER_BRANCH
RUNS_DIR = ".glados/runs"
RUNS_IGNORE_FILE = RUNS_DIR + "/.gitignore"
# Files directly under RUNS_DIR that never leave the working tree: the
# in-flight markers, and an ignore file a project may keep there.
RUNS_LOCAL_ONLY = frozenset({"current", "stack", ".gitignore"})
# The line every ledger command puts in the clone's exclude file.
RUNS_EXCLUDE = "/" + RUNS_DIR + "/*"
LEDGER_SYNC_FILE = "glados-ledger.json"
LEDGER_PUSH_ATTEMPTS = 5
LEDGER_DEFAULT_MESSAGE = "chore(glados): record runs"
# Network commands never wait on a credential prompt nobody will answer.
_LEDGER_NET_ENV = {"GIT_TERMINAL_PROMPT": "0"}


def _first_line(data) -> str:
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[0] if lines else "no output"


class _LedgerGit:
    """git, run in one repository's top level; bytes in and out. ``runs`` is
    the project's runs directory, repository-relative: RUNS_DIR for a
    project at the top level, `packages/app/.glados/runs` for one in a
    subdirectory, and the path its records take on the ledger."""

    def __init__(self, root: Path, runs: str = RUNS_DIR):
        self.root = root
        self.runs = runs
        # The project's directory, repository-relative with a trailing '/'
        # ('' at the top level).
        self.prefix = runs[:-len(RUNS_DIR)]

    def run(self, *args, input=None, env=None, check=True):
        full_env = None
        if env:
            full_env = dict(os.environ)
            full_env.update(env)
        if isinstance(input, str):
            # A path's bytes, as os.fsencode gives them: on Linux a file
            # name need not be UTF-8 (caf\xe9.txt), and os.scandir hands
            # such a byte back as a lone surrogate, which strict UTF-8
            # refused with a traceback. On Windows, surrogatepass makes a
            # name git cannot find, a clean error.
            input = input.encode("utf-8", "surrogatepass" if os.name == "nt"
                                 else "surrogateescape")
        try:
            proc = subprocess.run(["git", "-C", str(self.root), *args],
                                  input=input, capture_output=True,
                                  env=full_env, timeout=300)
        except (OSError, subprocess.SubprocessError) as exc:
            raise Fatal(f"git {args[0]} could not run ({exc}) — the run ledger "
                        f"needs git on PATH")
        if check and proc.returncode != 0:
            raise Fatal(f"git {' '.join(args[:2])} failed: "
                        f"{_first_line(proc.stderr)}")
        return proc

    def out(self, *args, **kw) -> str:
        return self.run(*args, **kw).stdout.decode("utf-8", "replace").strip()

    def rev(self, ref):
        proc = self.run("rev-parse", "--verify", "--quiet", ref + "^{commit}",
                        check=False)
        sha = proc.stdout.decode("ascii", "replace").strip()
        return sha if proc.returncode == 0 and sha else None

    def is_ancestor(self, a: str, b: str) -> bool:
        return self.run("merge-base", "--is-ancestor", a, b,
                        check=False).returncode == 0


def _ledger_open(target, search: bool = True) -> _LedgerGit:
    """The repository holding ``target``, and the project's own runs
    directory in it: `.glados/runs` under the nearest directory, from
    ``target`` up to the top level, that holds glados.yaml or `.glados/`
    (with ``search`` false, under ``target`` itself), else the top level's.
    A project in a subdirectory of its repository (a monorepo package)
    keeps its records there, and its ledger paths keep the subdirectory, so
    two projects in one repository never share one. The commands used to
    read only the top level's, so such a project saved and restored
    nothing."""
    probe = _LedgerGit(Path(target))
    proc = probe.run("rev-parse", "--show-toplevel", "--show-prefix",
                     check=False)
    out = proc.stdout.decode("utf-8", "replace").split("\n")
    top = out[0].strip()
    if proc.returncode != 0 or not top:
        raise Fatal(f"{Path(target).resolve()} is not inside a git repository "
                    f"— the run ledger is the {LEDGER_BRANCH} branch of the "
                    f"project's repository")
    parts = [p for p in (out[1] if len(out) > 1 else "").split("/") if p]
    if search:
        here = Path(target).resolve()
        while parts and not (os.path.isfile(here / "glados.yaml")
                             or os.path.isdir(here / ".glados")):
            parts.pop()
            here = here.parent
    return _LedgerGit(Path(top), "".join(p + "/" for p in parts) + RUNS_DIR)


def _exclude_line(runs: str) -> str:
    """The exclude-file line that keeps everything under ``runs`` out of
    commits: anchored at the top level, glob characters in a directory
    name escaped. RUNS_EXCLUDE for a top-level project."""
    return "/" + re.sub(r"([\\*?\[])", r"\\\1", runs) + "/*"


def _ensure_runs_ignored(git: _LedgerGit, write: bool = True) -> str:
    """Add the project's line (_exclude_line) to the clone's exclude file
    (`info/exclude` in the common git dir), so nothing a run writes under
    its `.glados/runs/` reaches a commit. That file holds on every branch
    and in every worktree. An ignore file inside `.glados/runs/` would not:
    with a branch that tracks it and one that lacks it, a checkout either
    aborts over an untracked copy or deletes the tracked one, leaving every
    record open to `git add -A`. Every run starts with `ledger restore`
    (preamble step 1), and install and migrate write it too
    (_exclude_runs_at), so a clone has the line before it has a record.
    Returns the line when it was missing, else ''; ``write`` false only
    checks.

    The file is read as git reads it, as bytes (a UTF-8 BOM skipped), and
    the line goes in as UTF-8. Windows PowerShell 5.1 writes `>` as UTF-16
    and Add-Content in the ANSI code page: read as UTF-8 text, either
    raised UnicodeDecodeError, a traceback in install, save and restore.
    A file this user cannot write is named on stderr instead."""
    line = _exclude_line(git.runs)
    want = line.encode("utf-8")
    rel = Path(git.out("rev-parse", "--git-path", "info/exclude"))
    path = rel if rel.is_absolute() else git.root / rel
    try:
        data = path.read_bytes() if os.path.isfile(path) else b""
    except OSError:
        data = b""
    if want in (ln.strip() for ln in
                data.removeprefix(b"\xef\xbb\xbf").split(b"\n")):
        return ""
    if not write:
        return line
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as fh:
            fh.write((b"" if data.endswith(b"\n") or not data else b"\n")
                     + b"# glados: run records live on the glados/ledger "
                       b"branch\n" + want + b"\n")
    except OSError as exc:
        print(f"glados: could not add {line} to {path} "
              f"({exc.strerror or exc}): add that line by hand, or a commit "
              f"of everything can take the run records", file=sys.stderr)
        return ""
    return line


def _exclude_runs_at(target: Path, write: bool = True) -> str:
    """_ensure_runs_ignored for install and migrate, which run before any
    `ledger` command and are followed by committing `.glados/`: migrate
    converts history into records there, and a clone upgraded from a
    GLaDOS that kept records on the branch may hold untracked ones. For
    ``target``'s own `.glados/runs/`, at the repository's top level or in a
    subdirectory of it; outside a repository it does nothing. Returns the
    line when it was missing, else ''."""
    try:
        return _ensure_runs_ignored(_ledger_open(target, search=False), write)
    except (Fatal, OSError):
        return ""


def _ledger_held_by(git: _LedgerGit):
    """(path, main) of the worktree that has the ledger branch checked out,
    if any, ``main`` true for the repository's main working tree (listed
    first), which `git worktree remove` cannot remove: moving the branch
    under it would leave that checkout showing the save as an undone
    change."""
    path, seen = None, 0
    for line in git.out("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
            seen += 1
        elif line.strip() == "branch " + LEDGER_REF:
            return path or "a worktree", seen == 1
    return None


def _ledger_remote(git: _LedgerGit, name: str):
    return name if name in git.out("remote").split() else None


def _ledger_tracking(remote: str) -> str:
    return f"refs/remotes/{remote}/{LEDGER_BRANCH}"


def _ledger_fetch(git: _LedgerGit, remote: str):
    """Fetch the remote's ledger into its remote-tracking ref. None when that
    worked or the remote has no ledger yet; otherwise why it failed."""
    proc = git.run("fetch", "--quiet", "--no-tags", remote,
                   f"+{LEDGER_REF}:{_ledger_tracking(remote)}",
                   env=_LEDGER_NET_ENV, check=False)
    if proc.returncode == 0:
        return None
    err = proc.stderr.decode("utf-8", "replace")
    if "couldn't find remote ref" in err.lower():
        return None
    return _first_line(err)


def _ledger_tree(git: _LedgerGit, commit, prefix=None) -> dict:
    """path -> (mode, blob sha) for every file in ``commit`` (under
    ``prefix`` when given); {} for no commit."""
    if not commit:
        return {}
    args = ["ls-tree", "-r", "-z", "--full-tree", commit]
    if prefix:
        args += ["--", prefix]
    tree: dict = {}
    for rec in git.run(*args).stdout.split(b"\0"):
        if not rec:
            continue
        meta, _, path = rec.partition(b"\t")
        mode, kind, sha = meta.decode("ascii").split()
        if kind == "blob":
            tree[path.decode("utf-8", "surrogateescape")] = (mode, sha)
    return tree


def _runs_relative(path: str, runs: str = RUNS_DIR) -> str:
    return path[len(runs) + 1:] if path.startswith(runs + "/") else path


def _runs_local_only(path: str, runs: str = RUNS_DIR) -> bool:
    rel = _runs_relative(path, runs)
    return "/" not in rel and rel in RUNS_LOCAL_ONLY


# A junction's reparse tag (winnt.h). CPython's stat module defines
# IO_REPARSE_TAG_MOUNT_POINT on Windows alone, and only a Windows stat result
# has st_reparse_tag, so both are read with a default: read bare, the
# constant raised AttributeError on Linux and macOS, and save crashed at the
# first file it walked.
_JUNCTION = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)


def _is_link(st: os.stat_result) -> bool:
    """A symbolic link, or a Windows junction, which is_symlink() does not
    report and lstat calls a directory."""
    return (stat.S_ISLNK(st.st_mode)
            or getattr(st, "st_reparse_tag", 0) == _JUNCTION)


def _runs_walk(entry: Path, top: bool = False) -> list[Path]:
    """The regular files at or under ``entry``, walked by hand. A link or a
    junction under it is neither saved nor walked into, as the guards walk
    .glados/runs/: rglob took a junction for a directory, so one back to
    .glados/runs/ saved outer.loop/outer.loop/... copies, and one to a
    directory outside the repository saved its files. With ``top``,
    ``entry`` itself is followed, as the guards list .glados/runs/ through
    a link (a named path arrives resolved, so only the runs directory can
    be one)."""
    try:
        st = os.stat(entry) if top else os.lstat(entry)
    except OSError:
        return []
    if not top and _is_link(st):
        return []
    if stat.S_ISREG(st.st_mode):
        return [entry]
    if not stat.S_ISDIR(st.st_mode):
        return []
    try:
        with os.scandir(entry) as it:
            children = sorted(Path(e.path) for e in it)
    except OSError:
        return []
    return [f for child in children for f in _runs_walk(child)]


def _runs_files(root: Path, sub: str = RUNS_DIR,
                runs: str = RUNS_DIR) -> list[str]:
    """Repo-relative paths of the regular files under ``sub`` (a path under
    the project's runs directory ``runs``), the local-only ones left out."""
    out = []
    for f in _runs_walk(root / sub, top=True):
        rel = f.relative_to(root).as_posix()
        if not _runs_local_only(rel, runs):
            out.append(rel)
    return out


def _hash_files(git: _LedgerGit, paths, write=False) -> dict:
    """path -> the blob sha `git add` would give it (the path's filters and
    line-ending rules applied)."""
    paths = list(paths)
    if not paths:
        return {}
    args = ["hash-object"] + (["-w"] if write else []) + ["--stdin-paths"]
    shas = git.out(*args, input="".join(p + "\n" for p in paths)).split()
    if len(shas) != len(paths):
        raise Fatal("git hash-object returned a different number of hashes "
                    "than paths — a path under .glados/runs/ has a newline in "
                    "its name; rename it")
    return dict(zip(paths, shas))


def _path_history(git: _LedgerGit, commits, path: str) -> set:
    """Every blob the ledger has held at ``path`` in the history of
    ``commits``."""
    commits = [c for c in dict.fromkeys(commits) if c]
    if not commits:
        return set()
    out = git.run("log", "-m", "--format=", "--raw", "--no-abbrev",
                  "--no-renames", *commits, "--", path,
                  check=False).stdout.decode("utf-8", "replace")
    blobs = set()
    for line in out.splitlines():
        if line.startswith(":"):
            for sha in line.split("\t", 1)[0].split()[2:4]:
                if sha.strip("0"):
                    blobs.add(sha)
    return blobs


def _ledger_sync_path(git: _LedgerGit) -> Path:
    p = Path(git.out("rev-parse", "--git-path", LEDGER_SYNC_FILE))
    return p if p.is_absolute() else git.root / p


def _ledger_sync_load(git: _LedgerGit) -> dict:
    try:
        data = json.loads(_ledger_sync_path(git).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _ledger_sync_store(git: _LedgerGit, data: dict) -> None:
    path = _ledger_sync_path(git)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=0, sort_keys=True),
                       encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    except OSError:
        pass  # the sync file only sharpens merges; losing it loses nothing


def _blob_bytes(git: _LedgerGit, sha: str) -> bytes:
    return git.run("cat-file", "blob", sha).stdout


def _union_merge(git: _LedgerGit, base, ours: str, theirs: str):
    """The blob of a line merge of ``ours`` and ``theirs`` from ``base``
    (None: no common version) that keeps both sides' lines where they
    conflict; None for binary content, which cannot be merged by line."""
    blobs = [_blob_bytes(git, ours), _blob_bytes(git, base) if base else b"",
             _blob_bytes(git, theirs)]
    if any(b"\0" in b for b in blobs):
        return None
    with tempfile.TemporaryDirectory(prefix="glados-ledger-") as td:
        names = []
        for label, data in zip(("ours", "base", "theirs"), blobs):
            f = Path(td) / label
            f.write_bytes(data)
            names.append(str(f))
        proc = git.run("merge-file", "-p", "--union", *names, check=False)
        if proc.returncode != 0:
            return None
        merged = proc.stdout
    return git.out("hash-object", "-w", "--stdin", input=merged)


def _tree_name_clashes(tree) -> list:
    """(file, path) for each path in ``tree`` under a directory that a file
    in ``tree`` names. One git tree cannot hold both: written together, git
    keeps the directory and drops the file without a word."""
    out = []
    for p in sorted(tree):
        parts = p.split("/")
        for i in range(1, len(parts)):
            above = "/".join(parts[:i])
            if above in tree:
                out.append((above, p))
    return out


def _ledger_clash_note(pairs, remote) -> str:
    """Why two ledgers were not merged, and the way out, for each (path in
    this clone, path on ``remote``) that a file and a directory share."""
    names = ", ".join(sorted({min(pair, key=len) for pair in pairs}))
    return ("; ".join(f"{here} here and {there} on {remote}"
                      for here, there in pairs)
            + f" cannot both be on the ledger, where a file and a directory "
              f"cannot share a name, so this clone's {LEDGER_BRANCH} is not "
              f"merged with {remote}'s, and neither copy is dropped. Rename "
              f"{names} in this clone to a name the ledger does not use, put "
              f"the rename on this clone's ledger (`ledger save --no-push "
              f"<old> <new>`), then run `ledger save` to merge and push")


def _ledger_integrate(git: _LedgerGit, local, remote_tip, notes: list,
                      refused: list):
    """(parents, tree) of the ledger a save builds on: this clone's ledger
    and the remote's, merged when they diverged, so that neither side's
    saves are lost. A merge that would hold a file and a directory under
    one name is refused, and this clone's ledger is built on alone: each
    (path here, path there) goes in ``refused``. Merged into one dict, git
    kept the directory and dropped the file, so one side's record left the
    ledger without a word."""
    if local and remote_tip and local != remote_tip \
            and not git.is_ancestor(local, remote_tip):
        if git.is_ancestor(remote_tip, local):
            return [local], _ledger_tree(git, local)
        mb = git.run("merge-base", local, remote_tip,
                     check=False).stdout.decode("ascii").strip() or None
        base_t = _ledger_tree(git, mb)
        ours_t = _ledger_tree(git, local)
        theirs_t = _ledger_tree(git, remote_tip)
        merged = dict(theirs_t)
        merge_notes: list = []
        for p in sorted(set(base_t) | set(ours_t)):
            b, o, t = base_t.get(p), ours_t.get(p), theirs_t.get(p)
            if o == b or o == t:
                continue                    # ours left it alone, or agrees
            if t == b:                      # only this clone changed it
                if o is None:
                    merged.pop(p, None)
                else:
                    merged[p] = o
                continue
            if o is None:                   # removed here, edited there
                continue
            if t is None:                   # edited here, removed there
                merged[p] = o
                continue
            sha = _union_merge(git, b[1] if b else None, o[1], t[1])
            merged[p] = (o[0], sha or o[1])
            merge_notes.append(
                f"{p}: changed here and by another session; "
                + ("merged keeping both sides' lines — check it reads right"
                   if sha else "binary, so this clone's copy is kept and the "
                   "other is in the ledger's history"))
        clashes = _tree_name_clashes(merged)
        if clashes:
            # Exactly one of each pair is the remote's: each tree alone is
            # a git tree, which holds no such pair.
            refused += [(f, d) if f not in theirs_t else (d, f)
                        for f, d in clashes]
            return [local], ours_t
        notes += merge_notes
        notes.append("this clone's earlier saves were merged with saves "
                     "another session pushed")
        return [remote_tip, local], merged
    tip = remote_tip if remote_tip and (not local or local == remote_tip
                                        or git.is_ancestor(local, remote_tip)) \
        else local
    return ([tip] if tip else []), _ledger_tree(git, tip)


def _ledger_arg_paths(git: _LedgerGit, args_paths) -> list[str]:
    """Each argument as a repo-relative path under the project's runs
    directory: as given from the current directory, from the project's
    directory, from the repo root, or as a name inside that runs
    directory."""
    out = []
    top = git.root.resolve()
    project = git.root / git.prefix
    for arg in args_paths:
        cand = Path(arg)
        options = [cand] if cand.is_absolute() else \
            [Path.cwd() / cand, project / cand, git.root / cand,
             project / RUNS_DIR / cand]
        chosen = None
        for opt in options:
            try:
                rel = opt.resolve().relative_to(top).as_posix()
            except ValueError:
                continue
            if rel != git.runs and not rel.startswith(git.runs + "/"):
                continue
            if os.path.exists(opt):
                chosen = rel
                break
            chosen = chosen or rel
        if chosen is None:
            raise Fatal(f"{arg}: not under {git.runs}/ — the ledger holds run "
                        f"records and step artifacts only")
        out.append(chosen)
    return out


def _ledger_name_clash(entries: dict, updates: dict, path: str):
    """The note for a path new to the ledger whose name a file or a
    directory the ledger keeps already takes, or None. Both in one tree,
    git keeps the directory and drops the file without a word, so a record
    replaced by a directory left the ledger while save named only what it
    added."""
    def kept(p):
        return p in entries and not (p in updates and updates[p] is None)
    parts = path.split("/")
    for i in range(1, len(parts)):
        above = "/".join(parts[:i])
        if kept(above):
            return (f"{path}: the ledger has a file at {above}; left off the "
                    f"ledger, where a file and a directory cannot share a "
                    f"name — rename one of them")
    if any(p.startswith(path + "/") and kept(p) for p in entries):
        return (f"{path}: the ledger has a directory there; left off the "
                f"ledger, where a file and a directory cannot share a name "
                f"— rename one of them")
    return None


def _dot_git_at(path: str):
    """The part of ``path`` up to its first `.git` component (any case), or
    None. git keeps no such path in a tree: written anyway, it was left out
    with only an "Ignoring path" warning."""
    parts = path.split("/")
    for i, part in enumerate(parts):
        if part.lower() == ".git":
            return "/".join(parts[:i + 1])
    return None


def _ledger_plan_local(git, root, entries, sync, explicit, history, notes):
    """What the working tree's files change on the ledger tree ``entries``.

    Returns (updates, refresh, synced): ``updates`` maps a path to its new
    (mode, sha), or None to remove it; ``refresh`` maps a path to the blob to
    write back over the local copy; ``synced`` is the version each path now
    shares with the ledger.

    With no explicit paths, every file under the project's runs directory
    is considered except those this branch tracks unchanged (records
    committed before they moved to the ledger stay the branch's own). An
    explicit path that no longer exists removes it, and everything under
    it, from the ledger."""
    head = _ledger_tree(git, git.rev("HEAD"), git.runs)
    updates: dict = {}
    refresh: dict = {}
    synced: dict = {}
    if explicit is None:
        files = _runs_files(root, git.runs, git.runs)
    else:
        files = []
        for rel in explicit:
            if _runs_local_only(rel, git.runs):
                continue
            # Only a path that is not there is gone. Path.exists() raised
            # on Python 3.10 to 3.12 for a path this user cannot reach, and
            # from 3.13 answers False, so the file left the ledger.
            try:
                os.stat(root / rel)
            except (FileNotFoundError, NotADirectoryError):
                pass
            except (OSError, ValueError) as exc:
                why = getattr(exc, "strerror", None) or exc
                notes.append(f"{rel}: cannot be read here ({why}); left on "
                             f"the ledger as it is")
                continue
            else:
                files += _runs_files(root, rel, git.runs)
                continue
            gone = [p for p in entries
                    if p == rel or p.startswith(rel.rstrip("/") + "/")]
            for p in gone:
                updates[p] = None
                synced[p] = None
            if not gone:
                notes.append(f"{rel}: neither here nor on the ledger")
    # A repository kept among a run's step artifacts: git holds no path
    # with a .git component, and save once named each such file saved and
    # recorded it as synced, so restore then deleted it as compacted away.
    dot_git: dict = {}
    for p in files:
        at = _dot_git_at(p)
        if at:
            dot_git.setdefault(at, []).append(p)
    if dot_git:
        files = [p for p in files if not _dot_git_at(p)]
        for at, under in sorted(dot_git.items()):
            shown = at if under == [at] else at + "/"
            notes.append(f"{shown}: left off the ledger ({len(under)} "
                         f"file(s)), as git holds no path with a .git "
                         f"component — keep that repository as an archive "
                         f"(`git bundle`, a tarball) instead")
    hashes = _hash_files(git, files)
    changed = []
    for p in files:
        w = hashes[p]
        if explicit is None and head.get(p, (None, None))[1] == w:
            continue
        t = entries.get(p, (None, None))[1]
        if w == t:
            synced[p] = t
            continue
        changed.append(p)
    _hash_files(git, changed, write=True)    # a merge reads them as blobs
    for p in changed:
        w = hashes[p]
        t = entries.get(p, (None, None))[1]
        known = sync.get(p)
        if t is None and known == w and not _path_history(git, history, p):
            # Synced with a ledger this clone no longer has (`git branch -D
            # glados/ledger` after a --no-push save, a reset): no ledger
            # here removed it, so it is new, not "removed there".
            known = None
        # An earlier version: the ledger moved on and this copy did not.
        # Once this tree has synced the path, only that version is stale:
        # any other content, an earlier text put back included, is an edit.
        if w == known or (known is None
                          and w in _path_history(git, history, p)):
            if t:
                refresh[p] = t
                synced[p] = t
                notes.append(f"{p}: this copy was an earlier version of the "
                             f"ledger's; refreshed from the ledger")
            else:
                notes.append(f"{p}: the ledger removed it, and this copy is an "
                             f"earlier version; left off the ledger")
            continue
        if t is None:
            clash = _ledger_name_clash(entries, updates, p)
            if clash:
                notes.append(clash)
                continue
            updates[p] = ("100644", w)
            synced[p] = w
            continue
        base = known or head.get(p, (None, None))[1]
        if base == t:                      # only this copy changed
            updates[p] = (entries[p][0], w)
            synced[p] = w
            continue
        # Both changed since this copy's base (or, with no base, two files
        # that took the same name): keep both sides' lines.
        merged = _union_merge(git, base, w, t)
        if merged:
            updates[p] = (entries[p][0], merged)
            refresh[p] = merged
            synced[p] = merged
            notes.append(f"{p}: changed here and on the ledger; merged keeping "
                         f"both sides' lines — check it reads right")
        else:
            updates[p] = (entries[p][0], w)
            synced[p] = w
            notes.append(f"{p}: changed here and on the ledger, and cannot be "
                         f"merged by line; this copy is saved, the other is in "
                         f"the ledger's history")
    return updates, refresh, synced


def _ledger_write_tree(git: _LedgerGit, tree: dict) -> str:
    """Write ``tree`` (path -> (mode, sha)) as a git tree through a temporary
    index, leaving the repository's own index alone. A file and a directory
    under one name stop the save: git would keep the directory and drop the
    file without a word (the merge and the plan keep such pairs out; this
    is the last line).

    core.protectNTFS is off for this index alone, which is never checked
    out: on Windows git leaves out of an index, with only a warning, any
    path Windows cannot hold as a file (? * : " < > |, a trailing period, a
    device name such as aux), so a save there dropped such a record that a
    clone on Linux or macOS had put on the ledger. core.protectHFS (on by
    default on macOS) is off for the same reason.

    The tree written is checked against ``tree``: a path git leaves out
    (a .git component, which _ledger_plan_local keeps out, or any other)
    stops the save rather than leaving the ledger without a word."""
    for f, d in _tree_name_clashes(tree)[:1]:
        raise Fatal(f"{f} and {d} cannot both be on the ledger, where a file "
                    f"and a directory cannot share a name; nothing was saved "
                    f"— rename one of them, then save again")
    with tempfile.TemporaryDirectory(prefix="glados-ledger-") as td:
        env = {"GIT_INDEX_FILE": str(Path(td) / "index")}
        git.run("read-tree", "--empty", env=env)
        if tree:
            info = b"".join(f"{mode} {sha}\t".encode("ascii")
                            + path.encode("utf-8", "surrogateescape") + b"\0"
                            for path, (mode, sha) in sorted(tree.items()))
            git.run("-c", "core.protectNTFS=false", "-c",
                    "core.protectHFS=false", "update-index", "-z",
                    "--index-info", input=info, env=env)
        sha = git.out("write-tree", env=env)
    listed = git.run("ls-tree", "-r", "-z", "--name-only", sha).stdout
    lost = sorted(set(tree) - {p.decode("utf-8", "surrogateescape")
                               for p in listed.split(b"\0") if p})
    if lost:
        more = f" and {len(lost) - 1} more" if len(lost) > 1 else ""
        raise Fatal(f"git left {lost[0]}{more} out of the ledger's tree; "
                    f"nothing was saved — rename it, then save again")
    return sha


def _ledger_apply_refresh(git: _LedgerGit, refresh: dict) -> dict:
    """Write each refreshed blob over the local copy. Returns path -> why
    for each copy that could not be written: one read-only, or in a
    directory this user cannot write (a container running as root made
    it, say). That write had no try, and it runs after the save's commit
    and before its push: every save stopped there with a traceback, so
    nothing reached the remote."""
    failed = {}
    for p, sha in refresh.items():
        f = git.root / p
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(_blob_bytes(git, sha))
        except OSError as exc:
            failed[p] = exc.strerror or str(exc)
    return failed


def _remote_web_base(url: str):
    """https://host/group/project for an http(s), ssh or scp-style remote
    URL; None for a local path or anything else."""
    url = url.strip()
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", url):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https", "ssh", "git", "git+ssh",
                                "ssh+git"):
            return None
        host, path = parts.hostname, parts.path
        scheme = "http" if parts.scheme == "http" else "https"
    else:
        m = re.match(r"^(?:[^@/]+@)?([^:/]+):(.+)$", url)
        if not m or len(m.group(1)) == 1:      # C:/... is a Windows path
            return None
        host, path, scheme = m.group(1), m.group(2), "https"
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not host or not path:
        return None
    return f"{scheme}://{host}/{path}"


def _ledger_link_base(git: _LedgerGit, remote):
    """The web prefix a ledger file's path is appended to, or None when the
    remote has no web address this can derive. GitHub (glados.yaml
    `platform: github`, or a github host) puts blobs under /blob/, GitLab
    under /-/blob/."""
    if not remote:
        return None
    url = git.run("remote", "get-url", remote, check=False).stdout.decode(
        "utf-8", "replace")
    base = _remote_web_base(url)
    if not base:
        return None
    platform = None
    manifest = git.root / git.prefix / "glados.yaml"
    if os.path.isfile(manifest):
        try:
            platform = load_manifest(manifest).get("platform")
        except Fatal:
            platform = None
    if platform not in ("github", "gitlab"):
        platform = "github" if "github" in base.split("/")[2] else "gitlab"
    blob = "blob" if platform == "github" else "-/blob"
    return f"{base}/{blob}/{LEDGER_BRANCH}/"


def _ledger_link(prefix, path: str) -> str:
    if prefix:
        return prefix + urllib.parse.quote(path, safe="/",
                                           errors="surrogateescape")
    return f"{LEDGER_BRANCH}:{path}"


def cmd_ledger_save(args) -> int:
    git = _ledger_open(args.target)
    _ensure_runs_ignored(git)
    held = _ledger_held_by(git)
    if held:
        where, main = held
        fix = (f"switch it to another branch (`git -C \"{where}\" switch "
               f"<branch>`); it is the repository's main working tree, which "
               f"`git worktree remove` cannot remove" if main else
               f"remove that worktree (`git worktree remove \"{where}\"`)")
        raise Fatal(f"{LEDGER_BRANCH} is checked out at {where}, and saving "
                    f"would move it under that checkout — {fix}, then save "
                    f"again")
    remote = None
    if not args.no_push:
        remote = _ledger_remote(git, args.remote)
        if remote is None and args.remote != "origin":
            raise Fatal(f"no git remote named '{args.remote}' — pass --remote "
                        f"<name>, or --no-push to save locally only")
    explicit = _ledger_arg_paths(git, args.paths) if args.paths else None
    sync = _ledger_sync_load(git)
    notes: list = []
    fetch_error = _ledger_fetch(git, remote) if remote else None
    saved: set = set()
    removed: set = set()
    committed = pushed = False
    push_error = None
    new = None
    refused: list = []
    for _attempt in range(LEDGER_PUSH_ATTEMPTS):
        local = git.rev(LEDGER_REF)
        remote_tip = git.rev(_ledger_tracking(remote)) if remote else None
        refused.clear()
        parents, entries = _ledger_integrate(git, local, remote_tip, notes,
                                             refused)
        history = [c for c in (*parents, local) if c]
        updates, refresh, synced = _ledger_plan_local(
            git, git.root, entries, sync, explicit, history, notes)
        tree = dict(entries)
        for p, val in updates.items():
            if val is None:
                tree.pop(p, None)
            else:
                tree[p] = val
        tip = parents[0] if parents else None
        if not parents and not tree:
            new = None                        # no ledger, nothing to save
        else:
            tree_sha = _ledger_write_tree(git, tree)
            if len(parents) == 1 and \
                    git.out("rev-parse", tip + "^{tree}") == tree_sha:
                new = tip                     # nothing new to commit
            else:
                parent_args = []
                for p in parents:
                    parent_args += ["-p", p]
                new = git.out("commit-tree", tree_sha, *parent_args,
                              "-m", args.message or LEDGER_DEFAULT_MESSAGE)
                moved = git.run("update-ref", "-m", "glados ledger save",
                                LEDGER_REF, new, local or "", check=False)
                if moved.returncode != 0:
                    continue                  # another save moved it: redo
        committed = True
        saved |= {p for p, v in updates.items() if v is not None}
        removed |= {p for p, v in updates.items() if v is None}
        for p, why in _ledger_apply_refresh(git, refresh).items():
            # The copy keeps its sync entry, the version it still holds, so
            # the next save tries again and never takes it for an edit to
            # put back over the ledger's.
            synced.pop(p, None)
            refreshed = (f"{p}: this copy was an earlier version of the "
                         f"ledger's; refreshed from the ledger")
            notes[:] = [n for n in notes if n != refreshed]
            notes.append(f"{p}: the ledger's newer copy could not be written "
                         f"here ({why}); this copy is left as it was — make "
                         f"it writable, then run `ledger restore` or save "
                         f"again")
        for p, sha in synced.items():
            if sha is None:
                sync.pop(p, None)
            else:
                sync[p] = sha
        _ledger_sync_store(git, sync)
        if refused:
            # The merge was refused, so this commit is on this clone's
            # ledger alone. If it moved that ledger (a rename of the
            # clashing name among it), merge again, saving nothing more:
            # a named path that is gone would remove the remote's file of
            # that name from the merge.
            if new != local and explicit != []:
                explicit = []
                continue
            break
        if not remote or not new or new == remote_tip:
            break
        proc = git.run("push", "--quiet", remote, f"{new}:{LEDGER_REF}",
                       env=_LEDGER_NET_ENV, check=False)
        if proc.returncode == 0:
            git.run("update-ref", _ledger_tracking(remote), new, check=False)
            pushed = True
            break
        err = proc.stderr.decode("utf-8", "replace")
        # "[remote rejected]" is a hook or a protected branch saying no,
        # which another fetch does not change, unless the remote lost the
        # ref's lock to a push that landed after it advertised its refs.
        # That, and the rest, mean the remote moved on since the fetch.
        lost_race = any(m in err for m in ("cannot lock ref", "but expected",
                                           "failed to update ref"))
        if lost_race or ("[remote rejected]" not in err and (
                "[rejected]" in err or "fetch first" in err
                or "non-fast-forward" in err)):
            # Another session pushed first: take its saves and merge again.
            fetch_error = _ledger_fetch(git, remote)
            if fetch_error is None:
                continue
        push_error = fetch_error or _first_line(err)
        break
    else:
        if not committed:
            raise Fatal(f"{LEDGER_REF} kept moving under this save through "
                        f"{LEDGER_PUSH_ATTEMPTS} attempts — another process is "
                        f"saving in this clone; save again once it is done")
        push_error = (f"the remote {LEDGER_BRANCH} kept moving through "
                      f"{LEDGER_PUSH_ATTEMPTS} attempts")

    prefix = _ledger_link_base(git, remote or _ledger_remote(git, "origin"))
    saved, removed = sorted(saved), sorted(removed)
    if saved or removed:
        print(f"glados ledger: saved {len(saved)} file(s)"
              + (f", removed {len(removed)}" if removed else "")
              + f" to {LEDGER_BRANCH} at {new[:12]}")
        for p in saved[:20]:
            print(f"  {p} -> {_ledger_link(prefix, p)}")
        if len(saved) > 20:
            print(f"  … and {len(saved) - 20} more")
        for p in removed[:20]:
            print(f"  removed {p}")
    else:
        # A save with no file of its own may still commit a merge of this
        # clone's ledger with the remote's, or push earlier saves: the lines
        # below say so, so this one speaks only of files.
        print("glados ledger: no new or changed file to save"
              + (f"; {LEDGER_BRANCH} is at {new[:12]}" if new else ""))
    for note in dict.fromkeys(notes):    # a retry repeats a note
        print(f"glados ledger: {note}")
    if pushed:
        print(f"glados ledger: pushed {LEDGER_BRANCH} to {remote}")
    elif refused:
        print(f"glados ledger: saved locally, NOT pushed to {remote}: "
              f"{_ledger_clash_note(refused, remote)}. Record this in the "
              f"run record.", file=sys.stderr)
        return 1
    elif remote and push_error:
        print(f"glados ledger: saved locally, NOT pushed to {remote}: "
              f"{push_error}. Record this in the run record; the next "
              f"`ledger save` pushes it.", file=sys.stderr)
        return 1
    elif not remote and not args.no_push:
        print("glados ledger: no 'origin' remote — saved locally only")
    return 0


def _ledger_select(tree: dict, names,
                   runs: str = RUNS_DIR) -> tuple[dict, list]:
    """The ledger files a name picks: the record itself and its step
    artifacts, `<record-stem>.*`, in the project's runs directory."""
    keep: dict = {}
    unmatched = []
    for name in names:
        rel = _runs_relative(name.replace("\\", "/").removeprefix("./"))
        rel = _runs_relative(rel, runs)
        stem = rel[:-3] if rel.endswith(".md") else rel
        hits = {p: v for p, v in tree.items()
                if _runs_relative(p, runs) == rel
                or _runs_relative(p, runs).startswith(stem + ".")
                or _runs_relative(p, runs).startswith(stem + "/")}
        if not hits:
            unmatched.append(name)
        keep.update(hits)
    return keep, unmatched


# What Windows cannot hold in a file name, as Git for Windows judges it: a
# ledger saved on Linux or macOS can have such names.
_WIN_BAD_CHARS = frozenset('<>:"|?*\\') | {chr(c) for c in range(32)}
_WIN_DEVICES = frozenset({"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                          *(f"COM{i}" for i in range(1, 10)),
                          *(f"LPT{i}" for i in range(1, 10))})


def _unholdable_here(p: str) -> bool:
    """Whether this platform cannot hold the ledger path ``p`` under its own
    name. Windows: a name with < > : " | ? * or a backslash or a control
    character in it, one that ends in a space or a period, or a device
    name, with or without an extension. Written anyway, one raised and
    restore crashed, and a ':' wrote an alternate data stream of an empty
    file, which the next save put on the ledger. Windows and macOS: a name
    that is not UTF-8."""
    if os.name != "nt" and sys.platform != "darwin":
        return False
    # A name saved on Linux that is not UTF-8 (_ledger_tree decodes it with
    # surrogateescape): neither NTFS nor APFS holds it under that name.
    if any("\ud800" <= c <= "\udfff" for c in p):
        return True
    if os.name != "nt":
        return False
    for part in p.split("/"):
        if any(c in _WIN_BAD_CHARS for c in part):
            return True
        if part.endswith((" ", ".")):
            return True
        if part.split(".")[0].rstrip(" ").upper() in _WIN_DEVICES:
            return True
    return False


def _ledger_name_taken(root: Path, p: str):
    """What in the working tree takes the name the ledger file ``p`` needs,
    or None: anything but a file at ``p`` (a directory), or anything but a
    directory at one of its parents (a file). Written over, either raised,
    and restore crashed (both ledgers' files, or a directory put where a
    saved record was). os.path answers False where Path's methods raised
    on Python 3.10 to 3.12 (a name too long for this file system)."""
    parts = p.split("/")
    for i in range(1, len(parts)):
        above = root / "/".join(parts[:i])
        if os.path.lexists(above) and not os.path.isdir(above):
            return f"{'/'.join(parts[:i])} is a file"
    f = root / p
    if os.path.lexists(f) and not os.path.isfile(f):
        return f"{p} is a directory" if os.path.isdir(f) else \
            f"{p} is not a regular file"
    return None


def cmd_ledger_restore(args) -> int:
    git = _ledger_open(args.target)
    _ensure_runs_ignored(git)
    remote = _ledger_remote(git, args.remote)
    fetch_error = _ledger_fetch(git, remote) if remote else None
    if fetch_error:
        print(f"glados ledger: could not fetch {LEDGER_BRANCH} from {remote} "
              f"({fetch_error}); restoring from this clone's copy",
              file=sys.stderr)
    local = git.rev(LEDGER_REF)
    remote_tip = git.rev(_ledger_tracking(remote)) if remote else None
    if not local and not remote_tip:
        print(f"glados ledger: no {LEDGER_BRANCH} branch yet — nothing to "
              f"restore")
        return 0
    notes: list = []
    if local and remote_tip and local != remote_tip \
            and not git.is_ancestor(local, remote_tip) \
            and not git.is_ancestor(remote_tip, local):
        ours_t = _ledger_tree(git, local, git.runs)
        tree = {**_ledger_tree(git, remote_tip, git.runs), **ours_t}
        clashes = [(f, d) if f in ours_t else (d, f)
                   for f, d in _tree_name_clashes(tree)]
        if clashes:
            notes.append(_ledger_clash_note(clashes, remote))
        else:
            notes.append("this clone's ledger has saves the remote lacks; "
                         "the next `ledger save` merges and pushes them")
    else:
        src = remote_tip if remote_tip and (
            not local or git.is_ancestor(local, remote_tip)) else local
        tree = _ledger_tree(git, src, git.runs)
    tree = {p: v for p, v in tree.items()
            if not _runs_local_only(p, git.runs)}
    sync = _ledger_sync_load(git)
    # A file this tree synced that the ledger no longer has (steward
    # compacted it elsewhere): the local copy goes too when it is the synced
    # version, so a compacted record is not read, or compacted, again.
    gone = {p: None for p in sync
            if p not in tree and p.startswith(git.runs + "/")}
    if args.names:
        tree, unmatched = _ledger_select(tree, args.names, git.runs)
        gone, _ = _ledger_select(gone, args.names, git.runs)
        for name in unmatched:
            notes.append(f"{name}: no file on the ledger matches it")
    head = _ledger_tree(git, git.rev("HEAD"), git.runs)
    # os.path, never Path.is_file(): on Python 3.10 to 3.12 that raised for
    # a ledger name this file system cannot hold (a component over 255
    # bytes, which a Windows clone can save), and restore wrote nothing.
    present = [p for p in tree if os.path.isfile(git.root / p)]
    hashes = _hash_files(git, present)
    on_disk = [p for p in gone
               if p not in head and os.path.isfile(git.root / p)]
    history = [c for c in (local, remote_tip) if c]
    removed = []
    for p, w in _hash_files(git, on_disk).items():
        if w == sync.get(p) and not _path_history(git, history, p):
            # Synced with a ledger this clone no longer has (`git branch -D
            # glados/ledger` after a --no-push save, a reset): no ledger
            # here removed it. Deleted, it was the record's only copy. It
            # stays, and the next save puts it back on the ledger.
            sync.pop(p, None)
            continue
        if w == sync.get(p):
            try:
                (git.root / p).unlink()
            except OSError as exc:
                # It keeps its sync entry: the next restore tries again.
                why = exc.strerror or exc
                notes.append(f"{p}: the ledger no longer has it, but this "
                             f"copy could not be removed ({why}); remove it "
                             f"by hand, or make it writable and restore "
                             f"again")
                continue
            removed.append(p)
    for p in gone:
        if p in removed or not os.path.exists(git.root / p):
            sync.pop(p, None)
    written, refreshed, kept, tracked = [], [], [], 0
    for p, (_mode, sha) in sorted(tree.items()):
        if _unholdable_here(p):
            # It stays on the ledger: save removes only a path it is named.
            notes.append(f"{p}: not restored, as this platform cannot hold "
                         f"its name; it stays on the ledger — rename it in a "
                         f"clone on Linux, which holds any name")
            continue
        w = hashes.get(p)
        if w == sha:
            sync[p] = sha
            continue
        if p in head:
            # The branch's own copy, committed before records moved to the
            # ledger: never overwritten, so the branch shows no change.
            tracked += 1
            continue
        if w is None:
            taken = _ledger_name_taken(git.root, p)
            if taken:
                notes.append(f"{p}: not restored, as {taken} here, where a "
                             f"file and a directory cannot share a name — "
                             f"rename one of them")
                continue
            written.append(p)
        elif w == sync.get(p) or (p not in sync and
                                  w in _path_history(git, history, p)):
            refreshed.append(p)
        else:
            kept.append(p)
            continue
        f = git.root / p
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(_blob_bytes(git, sha))
        except OSError as exc:
            # A path too long for this platform, say: the rest still come.
            for listed in (written, refreshed):
                if p in listed:
                    listed.remove(p)
            notes.append(f"{p}: not restored ({exc.strerror or exc}); it "
                         f"stays on the ledger")
            continue
        sync[p] = sha
    _ledger_sync_store(git, sync)
    print(f"glados ledger: restored {len(written)} file(s) from "
          f"{LEDGER_BRANCH}"
          + (f", refreshed {len(refreshed)} older copies" if refreshed else "")
          + (f", removed {len(removed)} the ledger no longer has"
             if removed else ""))
    for p in kept:
        notes.append(f"{p}: kept this copy, which has changes the ledger "
                     f"lacks; `ledger save` merges them")
    if tracked:
        notes.append(f"{tracked} file(s) this branch tracks differ from the "
                     f"ledger's copy and were left as the branch has them "
                     f"(`git show {LEDGER_BRANCH}:<path>` reads the ledger's)")
    for note in notes:
        print(f"glados ledger: {note}")
    return 0


def cmd_ledger_link(args) -> int:
    git = _ledger_open(args.target)
    prefix = _ledger_link_base(git, _ledger_remote(git, args.remote))
    for rel in _ledger_arg_paths(git, args.paths):
        print(_ledger_link(prefix, rel))
    return 0


# ---- migrate ----------------------------------------------------------------
#
# `glados.py migrate --target <repo>` — the guided v1 -> v2 path. Four steps:
# DETECT (v1 layouts, specs/ dirs, SDA artifacts; suggest the install mode),
# GENERATE (glados.yaml from the example — platform auto-detected, sda from
# the artifacts, phase left as a REQUIRED human edit), CONVERT (each specs/
# dir becomes a create-only .glados/runs/ digest record, kept out of commits
# by the clone's exclude file; SPEC_LOG rows when sda), REPORT (next steps +
# counts). Non-destructive by default and idempotent; --dry-run prints the
# full plan and writes nothing; --clean removes the converted specs/ dirs and
# the detected v1 layouts. Touches nothing outside specs/, the v1
# GLaDOS-owned layouts, glados.yaml, .glados/, product-knowledge/SPEC_LOG.md
# and the exclude file's one line.


def _is_v2_artifact(path: Path) -> bool:
    """True when the file is provably v2-generated — or unreadable (an
    unreadable file is not provably a v1 leftover, so it is left alone,
    the same stance as plugin-skill pruning)."""
    try:
        text = read_text(path)
    except Fatal:
        return True
    return any(m in text for m in V2_ARTIFACT_MARKERS)


def _detect_v1_layouts(target: Path) -> dict[str, list[Path]]:
    """The v1 command layouts present, keyed by the v2 install mode that
    supersedes each. Only files provably v1 GLaDOS-owned are listed: a known
    v1 name (or its underscore variant) carrying no v2 artifact marker —
    the v1/v2 name overlap makes the content check load-bearing."""
    layouts: dict[str, list[Path]] = {}

    claude: list[Path] = []
    cmds = target / ".claude" / "commands"
    if cmds.is_dir():
        for f in sorted(cmds.glob("*.md")):   # v1 un-namespaced commands
            if _v1_stem_match(f.stem, KNOWN_V1_WORKFLOWS):
                claude.append(f)
        namespaced = cmds / "glados"
        if namespaced.is_dir():               # v1 content under the v2 dir
            for f in sorted(namespaced.glob("*.md")):
                if _v1_stem_match(f.stem, KNOWN_V1_WORKFLOWS) \
                        and not _is_v2_artifact(f):
                    claude.append(f)
    if claude:
        layouts["claude"] = claude

    gem = target / ".gemini" / "skills" / "glados"
    if gem.is_dir():                          # tree fully owned by v1
        layouts["gemini"] = sorted(f for f in gem.rglob("*") if f.is_file())

    agy: list[Path] = []
    for base in (".agents", ".agent"):
        d = target / base / "workflows"
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            stem = f.stem.removeprefix("glados-")
            if _v1_stem_match(stem, KNOWN_V1_WORKFLOWS) \
                    and not _is_v2_artifact(f):
                agy.append(f)
    if agy:
        layouts["antigravity"] = agy

    direct: list[Path] = []
    for sub, names in (("workflows", KNOWN_V1_WORKFLOWS),
                       ("modules", KNOWN_V1_MODULES)):
        d = target / "product-knowledge" / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            if _v1_stem_match(f.stem, names):
                direct.append(f)
    if direct:
        layouts["direct"] = direct
    return layouts


def _suggest_mode(layouts: dict):
    """The install mode the follow-up should use, from the detected layouts."""
    for mode in ("claude", "gemini", "antigravity", "direct"):
        if mode in layouts:
            return mode
    return None


def _detect_sda_artifacts(target: Path) -> list[str]:
    """The v1 SDA conformance artifacts present (prefills `sda: true`)."""
    found: list[str] = []
    if (target / "claims.md").is_file():
        found.append("claims.md")
    if (target / "product-knowledge" / "SPEC_LOG.md").is_file():
        found.append("product-knowledge/SPEC_LOG.md")
    for name in ("ROADMAP.md", "PROJECT_STATUS.md"):
        doc = target / "product-knowledge" / name
        if doc.is_file():
            try:
                if SDA_MARKER in read_text(doc):
                    found.append(f"product-knowledge/{name} (SDA header)")
            except Fatal:
                pass
    return found


def _detect_platform(target: Path):
    """platform: for the generated manifest, from the origin remote host —
    gitlab.com -> gitlab, github.com -> github; anything else (self-hosted,
    no remote, no git) -> None, leaving the example default plus a TODO."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(target), "remote", "get-url", "origin"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    url = proc.stdout.strip()
    if proc.returncode != 0 or not url:
        return None
    m = re.search(r"(?:@|://)(?:[^/@]+@)?([^/:]+)", url)
    host = (m.group(1) if m else url).lower()
    if host == "gitlab.com" or host.endswith(".gitlab.com"):
        return "gitlab"
    if host == "github.com" or host.endswith(".github.com"):
        return "github"
    return None


def _generated_manifest(example_text: str, platform, sda: bool) -> str:
    """glados.yaml content for a migrating repo: the example verbatim except
    platform: auto-filled, sda: set from detection, phase: left as the
    REQUIRED-edit line (parses to null, so install still fails fast until a
    human chooses), and the example's explicit `decisions:` overrides plus
    its `relaxation-acknowledged:` confession commented out. The example's
    decision values are written for its own `phase: evolving`; carried into
    a manifest whose phase a human picks LATER, they would fail the install
    for a stricter phase (production/sunset) with relaxation errors the team
    never chose. Commented out, the chosen phase's preset governs and every
    phase installs cleanly. Line-level edits only — the output stays inside
    the YAML subset the tool's own parser accepts."""
    out: list[str] = []
    done = {"phase": False, "platform": False, "sda": False}
    in_decisions = False
    for line in example_text.split("\n"):
        if in_decisions:
            if line.startswith("  ") and line.strip():
                out.append("# " + line)
                continue
            in_decisions = False
        if not done["phase"] and line.startswith("phase:"):
            out.append(MIGRATE_PHASE_LINE)
            done["phase"] = True
        elif not done["platform"] and line.startswith("platform:"):
            if platform:
                out.append(f"platform: {platform}            # gitlab | github "
                           f"(auto-detected from the origin remote)")
            else:
                out.append(line + "  # TODO(migrate): could not auto-detect "
                                  "from a git origin remote - verify")
            done["platform"] = True
        elif not done["sda"] and line.startswith("sda:"):
            out.append("sda: true" if sda else line)
            done["sda"] = True
        elif line.startswith("decisions:"):
            out.append("# NOTE(migrate): the example's explicit decision "
                       "overrides are commented out")
            out.append("# so whichever phase: you pick governs them (see the "
                       "presets in")
            out.append("# .glados/presets.yaml after install). Uncomment a "
                       "line only to override")
            out.append("# your phase deliberately - a laxer value then needs "
                       "relaxation-acknowledged.")
            out.append("# " + line)
            in_decisions = True
        elif line.startswith("relaxation-acknowledged:"):
            out.append("# " + line)
        else:
            out.append(line)
    missing = [k for k, ok in done.items() if not ok]
    if missing:
        raise Fatal(f"glados.yaml.example has no top-level "
                    f"{', '.join(missing)} line(s) — cannot generate a "
                    f"migrated glados.yaml from it; pass --source <a v2 "
                    f"glados checkout with the current example>")
    return "\n".join(out)


def _check_generated_manifest_phases(source: Source, text: str) -> None:
    """Generate-time self-check: the generated manifest must resolve with NO
    phase-invariant errors under EVERY phase — 'fill phase:, run install' is
    the guided path's contract, and a pre-seeded value laxer than the phase
    a human picks later would break it. Fails fast at generate time instead
    of at the user's install."""
    raw = parse_yaml(text, "glados.yaml (generated)")
    for phase in PHASES:
        trial = dict(raw)
        trial["phase"] = phase
        resolved = resolve_manifest(trial, source.presets,
                                    "glados.yaml (generated)")
        errors = _check_phase_invariants(source, resolved)
        if errors:
            raise Fatal("the generated glados.yaml would fail install under "
                        f"phase '{phase}':\n  - " + "\n  - ".join(errors)
                        + "\nglados.yaml.example and the phase presets have "
                          "drifted apart — fix the example (this is a GLaDOS "
                          "source bug, not a problem with your repo)")


def _existing_manifest_report(raw: dict, source: Source, platform,
                              sda_artifacts: list[str]) -> list[str]:
    """Report-only differences for a pre-existing glados.yaml (never edited)."""
    lines: list[str] = []
    if raw.get("phase") in (None, ""):
        lines.append("phase: unset — set it to one of: " + ", ".join(PHASES)
                     + " before running install")
    if platform and raw.get("platform") not in (None, platform):
        lines.append(f"platform: manifest says '{raw.get('platform')}' but the "
                     f"origin remote looks like {platform} — verify")
    if sda_artifacts and raw.get("sda") is not True:
        lines.append("sda: SDA artifacts detected ("
                     + ", ".join(sda_artifacts)
                     + ") but the manifest does not set 'sda: true' — "
                     "consider declaring it")
    example = source.root / "glados.yaml.example"
    if example.exists():
        ex_keys = parse_yaml(read_text(example), "glados.yaml.example").keys()
        absent = sorted(k for k in ex_keys if k not in raw)
        if absent:
            lines.append("keys in glados.yaml.example not present here "
                         "(informational): " + ", ".join(absent))
    if not lines:
        lines.append("no differences worth reporting")
    return lines


_SPEC_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[-_]+(.*))?$")


def _git_last_commit_date(target: Path, rel: str):
    """YYYY-MM-DD of the last commit touching rel, else None. History, never
    wall clock — a re-run derives the same date."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(target), "log", "-1", "--format=%cs", "--", rel],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    line = proc.stdout.strip().split("\n")[0].strip() if proc.stdout.strip() else ""
    return line if re.fullmatch(r"\d{4}-\d{2}-\d{2}", line) else None


def _spec_dirs(target: Path) -> list[Path]:
    specs = target / "specs"
    if not specs.is_dir():
        return []
    return sorted(d for d in specs.iterdir() if d.is_dir())


def _spec_identity(target: Path, d: Path):
    """(date, date_source, slug) for one specs/ dir: date from the YYYY-MM-DD
    dirname prefix, else from git history of the dir, else None."""
    m = _SPEC_DATE_RE.match(d.name)
    if m:
        date, date_src = m.group(1), "from the directory name"
        rest = m.group(2) or ""
    else:
        date = _git_last_commit_date(target, f"specs/{d.name}")
        date_src = ("from git history" if date
                    else "unknown - no dirname date prefix and no git history")
        rest = d.name
    slug = re.sub(r"[^A-Za-z0-9.-]+", "-", rest.replace("_", "-")).strip("-.")
    return date, date_src, slug or "spec"


def _spec_excerpt(readme: Path):
    """First heading + last ~10 lines of a spec dir's README.md, or None."""
    if not readme.is_file():
        return None
    try:
        text = read_text(readme)
    except Fatal:
        return None
    lines = [l.rstrip() for l in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return None
    tail = lines[-10:]
    while tail and tail[0] == "":
        tail.pop(0)
    heading = next((l for l in lines if l.startswith("#")), None)
    parts: list[str] = []
    if heading is not None and heading not in tail:
        parts += [heading, "", "[...]", ""]
    parts += tail
    return "\n".join(parts)


def _spec_record_body(d: Path, date, date_src: str) -> str:
    """The digest run record one converted specs/ dir becomes."""
    name = d.name
    lines = [f"# Migrated spec: {name}", ""]
    lines.append(f"- Converted from `specs/{name}/` by `glados.py migrate` "
                 f"(v1 -> v2).")
    lines.append(f"- Date: {date or 'unknown'} ({date_src}).")
    lines.append(f"- The full history lives in git: `git log -- specs/{name}` "
                 f"— the specs/ tree can be deleted after migration "
                 f"(migrate --clean does it).")
    excerpt = _spec_excerpt(d / "README.md")
    if excerpt is None:
        lines += ["", f"_No README.md in `specs/{name}/` — no excerpt._"]
    else:
        lines += ["", f"## Excerpt (from `specs/{name}/README.md`)", "", excerpt]
    return "\n".join(lines) + "\n"


def _insert_spec_log_rows(path: Path, rows: list[str]) -> None:
    """Insert work-unit rows just under the table header separator (the log
    is newest-first); with no recognizable table, append them at the end."""
    lines = read_text(path).split("\n")
    idx = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and "-" in s \
                and set(s) <= set("|-: "):
            idx = i + 1
            break
    if idx is None:
        while lines and lines[-1] == "":
            lines.pop()
        lines += rows + [""]
    else:
        lines[idx:idx] = rows
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _migrate_clean(target: Path, layouts: dict, conversions: list) -> list[str]:
    """--clean: remove converted specs/ dirs (record on disk == converted)
    and the exact v1 files detection named; the fully v1-owned gemini/direct
    layouts go through the same _cleanup_v1_legacy the installer uses."""
    removed: list[str] = []
    for c in conversions:
        if c["path"].exists() and c["dir"].is_dir():
            removed += _remove_tree_files(c["dir"], target)
    specs = target / "specs"
    if specs.is_dir():
        try:
            specs.rmdir()   # only when every spec dir was converted + removed
        except OSError:
            pass
    for f in layouts.get("claude", []):
        if f.is_file():
            _force_unlink(f)
            removed.append(str(f.relative_to(target)))
    namespaced = target / ".claude" / "commands" / "glados"
    if namespaced.is_dir():
        try:
            namespaced.rmdir()   # keeps a dir that still has v2/user files
        except OSError:
            pass
    for f in layouts.get("antigravity", []):
        if f.is_file():
            _force_unlink(f)
            removed.append(str(f.relative_to(target)))
    for base in (".agents", ".agent"):
        d = target / base / "workflows"
        if d.is_dir():
            try:
                d.rmdir()
            except OSError:
                pass
    removed += _cleanup_v1_legacy(target, "gemini")
    removed += _cleanup_v1_legacy(target, "direct")
    return removed


def _this_script() -> str:
    """This script's path as the user can type it here: relative to the
    working directory when under it (`bin/glados.py` from a GLaDOS
    checkout), else absolute; quoted when it holds a space. migrate's next
    steps said `python glados.py`, which runs from no directory a user is
    in: the checkout has bin/glados.py, the project .glados/glados.py."""
    me = Path(__file__).resolve()
    try:
        shown = me.relative_to(Path.cwd().resolve()).as_posix()
    except (ValueError, OSError):
        shown = me.as_posix()
    return f'"{shown}"' if " " in shown else shown


def cmd_migrate(args) -> int:
    target = Path(args.target).resolve()
    if not target.is_dir():
        raise Fatal(f"target directory does not exist: {target}")
    source = _resolve_source(args)
    dry = bool(args.dry_run)

    def act(verb: str) -> str:
        return f"would {verb}" if dry else verb

    def posix(p: Path) -> str:
        return p.relative_to(target).as_posix()

    print(f"glados migrate — {target}"
          + (" (dry-run: nothing is written)" if dry else ""))

    # -- 1. DETECT ------------------------------------------------------------
    layouts = _detect_v1_layouts(target)
    spec_dirs = _spec_dirs(target)
    sda_artifacts = _detect_sda_artifacts(target)
    suggested = _suggest_mode(layouts)
    platform = _detect_platform(target)

    print("\n== detected ==")
    if layouts:
        for mode, paths in layouts.items():
            print(f"  v1 layout [{mode}]: {len(paths)} file(s)")
            for p in paths:
                print(f"    - {posix(p)}")
    else:
        print("  v1 command layouts: none found")
    if spec_dirs:
        print(f"  specs/ directories: {len(spec_dirs)}")
        for d in spec_dirs:
            print(f"    - specs/{d.name}")
    else:
        print("  specs/ directories: none found")
    print("  SDA artifacts: "
          + (", ".join(sda_artifacts) if sda_artifacts else "none found"))
    if suggested:
        others = [m for m in layouts if m != suggested]
        print(f"  suggested install mode: {suggested}"
              + (f" (v1 layouts also found for: {', '.join(others)})"
                 if others else ""))
    else:
        print("  suggested install mode: none detected — pick one of: "
              + ", ".join(INSTALL_MODES))

    # -- 2. GENERATE glados.yaml (never overwrite) ------------------------------
    print("\n== manifest ==")
    gy = target / "glados.yaml"
    files_generated = 0
    phase_unset = True
    if gy.exists():
        raw = load_manifest(gy)
        sda_val = raw.get("sda", False)
        if not isinstance(sda_val, bool):
            raise Fatal(f"{gy.name}: key 'sda' must be a bool — got {sda_val!r}; "
                        f"write 'sda: true' or 'sda: false'")
        sda_effective = sda_val
        phase_unset = raw.get("phase") in (None, "")
        print("  glados.yaml: present — never overwritten (report-only):")
        for line in _existing_manifest_report(raw, source, platform,
                                              sda_artifacts):
            print(f"    - {line}")
    else:
        sda_effective = bool(sda_artifacts)
        example = source.root / "glados.yaml.example"
        if not example.exists():
            raise Fatal(f"cannot generate glados.yaml: no glados.yaml.example "
                        f"under {source.root} — pass --source <a full glados "
                        f"checkout>")
        text = _generated_manifest(read_text(example), platform, sda_effective)
        _check_generated_manifest_phases(source, text)  # any phase must install
        print(f"  glados.yaml: absent — {act('generate from glados.yaml.example')}:")
        if platform:
            print(f"    - platform: {platform} (auto-detected from the origin "
                  f"remote)")
        else:
            print("    - platform: gitlab (example default; no gitlab.com/"
                  "github.com origin remote found — a TODO comment marks the "
                  "line)")
        print(f"    - sda: {'true' if sda_effective else 'false'}"
              + (" (SDA artifacts detected)" if sda_effective else ""))
        print("    - phase: left REQUIRED — install fails fast until a human "
              "picks one")
        print("    - decisions: example overrides commented out — your phase's "
              "preset governs (uncomment to override)")
        if not dry:
            gy.write_text(text, encoding="utf-8", newline="\n")
        files_generated += 1

    # -- 3. CONVERT specs/ ------------------------------------------------------
    print("\n== convert specs/ ==")
    # Before any record exists, so committing the migrated tree takes none
    # and `ledger save` finds them all.
    excluded = _exclude_runs_at(target, write=not dry)
    if excluded:
        print(f"  .git/info/exclude: {act(f'add {excluded}')} (run "
              f"records go to the {LEDGER_BRANCH} branch, never in a commit)")
    conversions: list[dict] = []
    for d in spec_dirs:
        date, date_src, slug = _spec_identity(target, d)
        rec_name = f"{date or 'undated'}-migrated-{slug}.md"
        rec_path = target / ".glados" / "runs" / rec_name
        existed = rec_path.exists()
        conversions.append({"dir": d, "date": date, "path": rec_path,
                            "rel": f".glados/runs/{rec_name}",
                            "existed": existed})
        if existed:
            print(f"  specs/{d.name}/ -> .glados/runs/{rec_name} "
                  f"(record exists — kept)")
            continue
        print(f"  specs/{d.name}/ -> .glados/runs/{rec_name} ({act('create')})")
        if not dry:
            rec_path.parent.mkdir(parents=True, exist_ok=True)
            rec_path.write_text(_spec_record_body(d, date, date_src),
                                encoding="utf-8", newline="\n")
        files_generated += 1
    if not spec_dirs:
        print("  nothing to convert")

    rows_added = 0
    if conversions and sda_effective:
        spec_log = target / "product-knowledge" / "SPEC_LOG.md"
        existing_text = read_text(spec_log) if spec_log.exists() else ""
        pending = [c for c in conversions
                   if c["path"].name not in existing_text]
        pending.sort(key=lambda c: c["date"] or "", reverse=True)  # newest first
        rows = [f"| {c['date'] or 'undated'} | migrate | specs/{c['dir'].name} "
                f"| migrated | {c['rel']} |" for c in pending]
        if rows:
            if not spec_log.exists():
                print(f"  product-knowledge/SPEC_LOG.md: "
                      f"{act('create from the template')}")
                if not dry:
                    _scaffold_spec_log(target, source,
                                       datetime.date.today().isoformat())
                files_generated += 1
            print(f"  product-knowledge/SPEC_LOG.md: "
                  f"{act(f'append {len(rows)} work-unit row(s)')}")
            if not dry:
                _insert_spec_log_rows(spec_log, rows)
            rows_added = len(rows)
        else:
            print("  product-knowledge/SPEC_LOG.md: every migrated row already "
                  "present")
    elif conversions:
        print("  SPEC_LOG rows: skipped (sda is not true)")

    # -- --clean / cleanup report -----------------------------------------------
    print("\n== cleanup ==")
    if args.clean:
        if dry:
            for c in conversions:
                print(f"  would remove specs/{c['dir'].name}/ (converted)")
            for mode, paths in layouts.items():
                for p in paths:
                    print(f"  would remove {posix(p)} (v1 {mode} layout)")
            if not conversions and not layouts:
                print("  nothing to clean")
        else:
            removed = _migrate_clean(target, layouts, conversions)
            for rel in removed:
                print("  removed " + rel.replace("\\", "/"))
            if not removed:
                print("  nothing to clean")
    else:
        if conversions or layouts:
            print("  nothing removed (non-destructive default); removable once "
                  "migrated:")
            for c in conversions:
                print(f"    - specs/{c['dir'].name}/ (converted to {c['rel']})")
            for mode, paths in layouts.items():
                for p in paths:
                    print(f"    - {posix(p)} (v1 {mode} layout)")
            print("  note: `install --mode <m>` cleans the v1 layout of its own "
                  "mode; `migrate --clean` removes all of the above")
        else:
            print("  nothing to clean")

    # -- 4. NEXT STEPS + counts ---------------------------------------------------
    print("\n== next steps ==")
    steps: list[str] = []
    if phase_unset:
        steps.append("edit glados.yaml — set phase: (one of: "
                     + ", ".join(PHASES) + ")")
    me = _this_script()
    steps.append(f"python {me} install --mode {suggested or '<mode>'} "
                 f"--target {target}")
    steps.append("commit the migrated tree")
    if conversions:
        steps.append(f"save the converted records to the {LEDGER_BRANCH} "
                     f"branch: python {me} ledger save --target {target}")
    if not args.clean:
        steps.append(f"re-run: python {me} migrate --target {target} "
                     f"--clean (removes the converted specs/ dirs and v1 "
                     f"layouts)")
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")

    converted = sum(1 for c in conversions if not c["existed"])
    if dry:
        print(f"\nglados migrate (dry-run): would convert {converted} spec "
              f"dir(s), generate {files_generated} file(s), append "
              f"{rows_added} SPEC_LOG row(s)")
    else:
        print(f"\nglados migrate: {converted} spec dir(s) converted, "
              f"{files_generated} file(s) generated, {rows_added} SPEC_LOG "
              f"row(s) appended")
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

    pval = sub.add_parser(
        "validate",
        help="type-check the target's glados.yaml, pipelines and steps "
             "included, in memory: writes nothing, needs no install, exits 1 "
             "on any error")
    pval.add_argument("--target", default=".")
    pval.add_argument("--source")
    pval.set_defaults(func=cmd_validate)

    pe = sub.add_parser(
        "effective-config",
        help="print the digest of the configuration a run obeys: the "
             "target's glados.yaml layered over the preset table "
             "(.glados/presets.yaml, else this toolchain's), inherited "
             "bounds and decision rights included. run-pipeline pins it")
    pe.add_argument("--target", default=".")
    pe.add_argument("--source")
    pe.add_argument("--ref",
                    help="read glados.yaml and the preset table as this "
                         "commit has them (a resumed run passes the branch "
                         "its work targets)")
    pe.set_defaults(func=cmd_effective_config)

    pd = sub.add_parser("doctor", help="staleness + wiring report (never fails)")
    pd.add_argument("--target", required=True)
    pd.add_argument("--source")
    pd.set_defaults(func=cmd_doctor)

    pm = sub.add_parser(
        "migrate",
        help="guided v1 -> v2 migration: detect v1 layouts, generate "
             "glados.yaml (phase left for a human), convert specs/ history "
             "to run records — non-destructive and idempotent by default")
    pm.add_argument("--target", required=True)
    pm.add_argument("--source")
    pm.add_argument("--dry-run", action="store_true",
                    help="print the full migration plan; write nothing")
    pm.add_argument("--clean", action="store_true",
                    help="after successful conversion, remove the converted "
                         "specs/ dirs and the detected v1 command layouts")
    pm.set_defaults(func=cmd_migrate)

    pv = sub.add_parser("verify-ledger", help="scan git for silent-loss candidates")
    pv.add_argument("--target", required=True)
    pv.add_argument("--report-only", action="store_true")
    pv.add_argument("--base",
                    help="the branch this one targets: list the run records "
                         "this branch commits since their merge-base (CI "
                         "supplies it on merge requests and pull requests)")
    pv.set_defaults(func=cmd_verify_ledger)

    pl = sub.add_parser(
        "ledger",
        help="move run records between .glados/runs/ and the glados/ledger "
             "branch, which holds every run's record and step artifacts "
             "so no work branch does")
    lsub = pl.add_subparsers(dest="ledger_command", required=True)
    ls_ = lsub.add_parser(
        "save",
        help="commit records onto glados/ledger without touching the "
             "checked-out branch, the index or tracked files, merging what "
             "another session pushed, then push it. With no paths: every "
             "file under .glados/runs/ the ledger lacks or holds older, "
             "except files this branch tracks unchanged. A path that no "
             "longer exists is removed from the ledger. Exits 1 when the "
             "push fails; the commit is kept and the next save pushes it")
    ls_.add_argument("paths", nargs="*")
    ls_.add_argument("--target", default=".")
    ls_.add_argument("--remote", default="origin")
    ls_.add_argument("-m", "--message",
                     help=f"commit message (default: "
                          f"'{LEDGER_DEFAULT_MESSAGE}')")
    ls_.add_argument("--no-push", action="store_true",
                     help="commit locally only; a later save pushes it")
    ls_.set_defaults(func=cmd_ledger_save)
    lr = lsub.add_parser(
        "restore",
        help="fetch glados/ledger and copy its records into .glados/runs/: "
             "every one, or the named records with their step artifacts. "
             "Never overwrites a copy with changes the ledger lacks, or a "
             "file this branch tracks")
    lr.add_argument("names", nargs="*")
    lr.add_argument("--target", default=".")
    lr.add_argument("--remote", default="origin")
    lr.set_defaults(func=cmd_ledger_restore)
    lk = lsub.add_parser(
        "link",
        help="print the web link of each path's copy on glados/ledger, for "
             "a merge request description or an outcome")
    lk.add_argument("paths", nargs="+")
    lk.add_argument("--target", default=".")
    lk.add_argument("--remote", default="origin")
    lk.set_defaults(func=cmd_ledger_link)

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
