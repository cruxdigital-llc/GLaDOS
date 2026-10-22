#!/usr/bin/env python3
"""GLaDOS v2 self-test — stdlib unittest, no third-party deps.

Run from the repo root (or anywhere):  python tests/run_tests.py

Compiles every adapter over the fixtures and exercises the type-checker,
cleanup, determinism, drift detection and the runtime artifacts. A mode that
stops shipping modules — v1's flagship bug — fails this build.
"""

import argparse
import contextlib
import datetime
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unicodedata
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GLADOS_PY = REPO / "bin" / "glados.py"
FIXTURE = REPO / "tests" / "fixture-project"
LEGACY = REPO / "tests" / "fixtures-legacy"
EXAMPLE = REPO / "glados.yaml.example"


def _load_module():
    spec = importlib.util.spec_from_file_location("glados_mod", GLADOS_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


glados = _load_module()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def run_cli(*args, env=None):
    """Invoke the real CLI in a subprocess; return (returncode, stdout+stderr)."""
    proc = subprocess.run(
        [sys.executable, str(GLADOS_PY), *[str(a) for a in args]],
        capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout + proc.stderr


def tmpdir(prefix="glados-test-"):
    d = Path(tempfile.mkdtemp(prefix=prefix))
    return d


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def make_target(manifest_text=None, from_example=True):
    """A fresh install target with a glados.yaml."""
    d = tmpdir()
    if manifest_text is not None:
        write(d / "glados.yaml", manifest_text)
    elif from_example:
        shutil.copyfile(EXAMPLE, d / "glados.yaml")
    return d


def make_plugin_target():
    """A plugin-mode target: needs glados.yaml.example present."""
    d = tmpdir("glados-plugin-")
    shutil.copyfile(EXAMPLE, d / "glados.yaml.example")
    return d


def install(mode, target, extra=(), source=None, env=None):
    return run_cli("install", "--mode", mode, "--target", target,
                   "--source", source or REPO, *extra, env=env)


def make_doctored_source():
    """A private copy of the GLaDOS source tree that tests may mutate."""
    d = tmpdir("glados-src-")
    shutil.copytree(REPO / "src", d / "src")
    shutil.copytree(REPO / "bin", d / "bin",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(REPO / "hooks", d / "hooks",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(REPO / "ci", d / "ci")
    shutil.copyfile(EXAMPLE, d / "glados.yaml.example")
    return d


def all_files(root: Path):
    return sorted(p for p in root.rglob("*") if p.is_file())


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class TestCompile(unittest.TestCase):

    def test_compile_all_modes_no_dangling(self):
        """All seven modes compile with zero unresolved includes/placeholders."""
        forbidden = ["{{", "<!-- glados:include"]
        for mode in ["claude", "direct", "gemini", "antigravity", "aistudio", "pi"]:
            with self.subTest(mode=mode):
                t = make_target()
                rc, out = install(mode, t)
                self.assertEqual(rc, 0, f"{mode} install failed:\n{out}")
                self._scan(t, mode, forbidden)
        # plugin mode is repo-side
        with self.subTest(mode="claude-plugin"):
            t = make_plugin_target()
            rc, out = install("claude-plugin", t)
            self.assertEqual(rc, 0, f"plugin install failed:\n{out}")
            self._scan(t / "compiled", "claude-plugin", forbidden)

    def _scan(self, root, mode, forbidden):
        # Scan only emitted adapter artifacts, never the vendored compiler/presets
        # (which legitimately contain the token strings) or copied sources.
        skip_dirs = {".glados", "src", "bin", "hooks"}
        checked = 0
        for f in all_files(root):
            if any(part in skip_dirs for part in f.relative_to(root).parts):
                continue
            if f.suffix not in (".md", ".toml"):
                continue
            text = read(f)
            checked += 1
            for tok in forbidden:
                self.assertNotIn(tok, text, f"{mode}: '{tok}' in {f.name}")
        self.assertGreater(checked, 0, f"{mode}: no artifacts scanned")

    def test_toml_roundtrip(self):
        """Gemini TOML parses with tomllib; prompt carries the epilogue text."""
        t = make_target()
        rc, out = install("gemini", t)
        self.assertEqual(rc, 0, out)
        toml_path = t / ".gemini" / "commands" / "glados" / "build-feature.toml"
        data = tomllib.loads(read(toml_path))
        self.assertIn("description", data)
        self.assertIn("prompt", data)
        self.assertIn("Before ending this run", data["prompt"])   # epilogue
        self.assertIn("Before doing anything else", data["prompt"])  # preamble
        # an alias TOML states the rename
        alias = t / ".gemini" / "commands" / "glados" / "plan-fix.toml"
        adata = tomllib.loads(read(alias))
        self.assertIn("fix-bug", adata["prompt"])

    def test_plugin_cores_phase_neutral_with_bootstrap_guard(self):
        """claude-plugin compiles from glados.yaml.example, so its cores must
        not bake the example's phase-resolved optimize-for: they carry the
        phase-neutral baseline sentence plus a bootstrap guard deferring to
        the consuming repo's own glados.yaml."""
        t = make_plugin_target()
        rc, out = install("claude-plugin", t)
        self.assertEqual(rc, 0, out)
        for core in (t / "compiled" / "claude-plugin").glob("*.md"):
            text = read(core)
            self.assertTrue(text.startswith("<!-- claude-plugin bootstrap guard"),
                            f"{core.name}: missing bootstrap guard")
            self.assertIn("Optimize for doing no harm", text, core.name)
            # the example's evolving-phase sentence must NOT be baked in
            self.assertNotIn("Optimize for velocity with a memory", text,
                             f"{core.name}: example's phase leaked into plugin")

    def test_determinism(self):
        """Two installs of the same mode produce byte-identical trees."""
        for mode in ("claude", "direct", "gemini", "antigravity", "aistudio",
                     "pi", "claude-plugin"):
            with self.subTest(mode=mode):
                if mode == "claude-plugin":
                    a, b = make_plugin_target(), make_plugin_target()
                else:
                    a, b = make_target(), make_target()
                self.assertEqual(install(mode, a)[0], 0)
                self.assertEqual(install(mode, b)[0], 0)
                fa = {f.relative_to(a).as_posix(): f for f in all_files(a)}
                fb = {f.relative_to(b).as_posix(): f for f in all_files(b)}
                self.assertEqual(set(fa), set(fb), "file sets differ")
                for rel in fa:
                    self.assertEqual(fa[rel].read_bytes(), fb[rel].read_bytes(),
                                     f"bytes differ for {rel}")


class TestTypeChecks(unittest.TestCase):

    def test_missing_phase_fatal(self):
        t = make_target("glados: 2\nplatform: gitlab\n")
        rc, out = install("direct", t)
        self.assertEqual(rc, 1)
        self.assertIn("phase", out)
        for value in ("nascent", "evolving", "production", "sunset"):
            self.assertIn(value, out, "fatal message must name the four phases")

    def test_reader_without_writer_fails(self):
        # Disable run-epic (the only writer of epic.integration-branch) and omit
        # branching.default-target (its documented fallback): build-feature still
        # reads epic.integration-branch, so the read is genuinely uncovered.
        manifest = (
            "glados: 2\nplatform: gitlab\nphase: evolving\n"
            "disabled-workflows: [run-epic]\n"
            "channels:\n  progress: [ledger]\n  verdict: [mr-comment]\n"
            "  escalation: [issue]\n  bug: [issue]\n  decision: [ledger]\n"
            "  observation: [ledger]\n"
            "branching:\n  feature: \"feat/<slug>\"\n"
            "  epic-integration: \"feature/<epic-slug>\"\n"
            "default-modules: [standards-gate]\n")
        t = make_target(manifest)
        rc, out = install("direct", t)
        self.assertEqual(rc, 1, out)
        self.assertIn("epic.integration-branch", out)
        self.assertIn("build-feature", out)

    def test_reader_without_writer_passes_with_fallback(self):
        # Same as above but WITH branching.default-target: the fallback covers it.
        manifest = (
            "glados: 2\nplatform: gitlab\nphase: evolving\n"
            "disabled-workflows: [run-epic]\n"
            "channels:\n  progress: [ledger]\n  verdict: [mr-comment]\n"
            "  escalation: [issue]\n  bug: [issue]\n  decision: [ledger]\n"
            "  observation: [ledger]\n"
            "branching:\n  feature: \"feat/<slug>\"\n  default-target: main\n"
            "default-modules: [standards-gate]\n")
        t = make_target(manifest)
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)

    def test_zero_sink_emit_fails(self):
        text = read(EXAMPLE).replace("  verdict:     [mr-comment]",
                                     "  verdict:     [ledger]")
        t = make_target(text)
        rc, out = install("direct", t)
        self.assertEqual(rc, 1, out)
        self.assertIn("verdict", out)
        self.assertIn("team-visible", out)

    def test_zero_sink_emit_passes_with_confession(self):
        text = read(EXAMPLE).replace("  verdict:     [mr-comment]",
                                     "  verdict:     [ledger]")
        text += "\nvisibility-acknowledged: ledger-only\n"
        t = make_target(text)
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)

    def test_relaxation_confession_required(self):
        manifest = (
            "glados: 2\nplatform: gitlab\nphase: production\n"
            "merge-authority: agent\n"
            "branching:\n  feature: \"feat/<slug>\"\n  default-target: main\n")
        t = make_target(manifest)
        rc, out = install("direct", t)
        self.assertEqual(rc, 1, out)
        self.assertIn("merge-authority", out)
        self.assertIn("relaxation-acknowledged", out)

    def test_relaxation_confession_accepted(self):
        manifest = (
            "glados: 2\nplatform: gitlab\nphase: production\n"
            "merge-authority: agent\n"
            "relaxation-acknowledged: [merge-authority]\n"
            "branching:\n  feature: \"feat/<slug>\"\n  default-target: main\n")
        t = make_target(manifest)
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)

    def test_alias_integrity(self):
        source = glados.Source(REPO)
        for alias, target in source.aliases.items():
            self.assertIn(target, glados.CORES, f"{alias} -> {target} not a core")
        # a doctored bad alias is caught by the checker
        r = glados.resolve_manifest(
            glados.load_manifest(EXAMPLE), source.presets, "glados.yaml.example")
        comp = glados.compile_all(source, r, "deadbeef")
        source.aliases["bogus-alias"] = "not-a-core"
        errors = glados.run_type_checks(source, comp)
        self.assertTrue(any("bogus-alias" in e for e in errors), errors)


class TestReporting(unittest.TestCase):

    def test_assembly_report_provenance(self):
        # nascent, with no explicit overrides, is phase-derived and laxer than
        # baseline — the report must show RELAXED(phase) markers and provenance.
        manifest = ("glados: 2\nplatform: gitlab\nphase: nascent\n"
                    "branching:\n  feature: \"feat/<slug>\"\n"
                    "  default-target: main\n")
        t = make_target(manifest)
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("RELAXED(phase) markers:", report)
        # count must be > 0 for nascent
        line = [l for l in report.splitlines() if "RELAXED(phase) markers:" in l][0]
        count = int(line.rsplit(":", 1)[1].strip())
        self.assertGreater(count, 0, report)
        self.assertIn("RELAXED(phase) `merge-authority`", report)
        self.assertIn("(phase:nascent)", report)   # provenance tag
        self.assertIn("(explicit)", report)        # branching came from manifest

    def test_check_detects_drift(self):
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        rc, _ = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, "clean install should pass check")
        # hand-edit an installed compiled file
        core = t / "product-knowledge" / "glados" / "intent.md"
        core.write_text(read(core) + "\nHAND EDIT\n", encoding="utf-8", newline="\n")
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, "drift must fail check")
        self.assertIn("drift", out)
        self.assertIn("intent.md", out)

    def test_check_detects_stale_manifest(self):
        # A structural manifest edit after install must be flagged stale.
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        gy = t / "glados.yaml"
        gy.write_text(read(gy).replace("disabled-workflows: []",
                                       "disabled-workflows: [brunch]"),
                      encoding="utf-8", newline="\n")
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1)
        self.assertIn("stale compile", out)


class TestManifestHash(unittest.TestCase):
    """The manifest hash covers the structural keys only (F1). Lane-2 keys are
    read live at run time, so editing one must never make `check` fail; a
    structural edit must; comments and whitespace change nothing."""

    def _installed(self):
        t = make_target()
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        return t

    def _edit(self, t, old, new):
        gy = t / "glados.yaml"
        text = read(gy)
        self.assertIn(old, text, "doctoring failed")
        gy.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

    def test_lane2_edits_keep_check_passing(self):
        t = self._installed()
        edits = [
            # declare a sink and bind it
            ("merge-authority: human",
             "sinks:\n  slack:\n    channel: \"#reviews\"\n"
             "    team-visible: true\nmerge-authority: human"),
            ("  escalation:  [issue]", "  escalation:  [issue, slack]"),
            # change a channel binding
            ("  bug:         [issue]", "  bug:         [issue, issue-comment]"),
            # change params
            ("    max-cycles: 5", "    max-cycles: 4"),
            # change a decision class (stricter than the preset: no confession)
            ("  new-dependency: agent", "  new-dependency: escalate"),
            # change branching
            ("  default-target: main", "  default-target: develop"),
        ]
        for old, new in edits:
            with self.subTest(edit=new.strip()[:40]):
                self._edit(t, old, new)
                rc, out = run_cli("check", "--target", t, "--source", REPO)
                self.assertEqual(rc, 0, f"lane-2 edit failed check:\n{out}")
                self.assertNotIn("stale compile", out)
        # the vendored report now predates the edits — doctor says so, as
        # information, and never as staleness
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("manifest hash: current", out)
        self.assertIn("the assembly report predates later glados.yaml edits",
                      out)
        self.assertIn("nothing is stale", out)
        # a re-install refreshes it
        self.assertEqual(install("direct", t)[0], 0)
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertIn("assembly report: current", out)

    def test_structural_edits_make_check_stale(self):
        edits = [
            ("disabled-workflows: []", "disabled-workflows: [brunch]"),
            ("default-modules: [standards-gate]", "default-modules: []"),
            ("phase: evolving", "phase: nascent"),
            ("sda: false", "sda: true"),
            ("  brunch:         [mr-review-panel]",
             "  brunch:         [mr-review-panel, standards-gate]"),
        ]
        for old, new in edits:
            with self.subTest(edit=new):
                t = self._installed()
                self._edit(t, old, new)
                rc, out = run_cli("check", "--target", t, "--source", REPO)
                self.assertEqual(rc, 1, f"structural edit passed check:\n{out}")
                self.assertIn("stale compile", out)
                rc, out = run_cli("doctor", "--target", t, "--source", REPO)
                self.assertIn("STALE", out)

    def test_comments_and_whitespace_change_nothing(self):
        t = self._installed()
        before = read(t / ".glados" / "manifest-hash").strip()
        gy = t / "glados.yaml"
        text = read(gy)
        text = ("# a new leading comment\n\n" + text.replace(
            "disabled-workflows: []", "disabled-workflows:   []   # aligned")
            + "\n\n# trailing comment\n")
        gy.write_text(text, encoding="utf-8", newline="\n")
        self.assertEqual(glados.manifest_hash_of(gy), before)
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)

    def test_hash_is_the_structural_projection(self):
        raw = glados.load_manifest(EXAMPLE)
        self.assertEqual(
            sorted(glados.structural_projection(raw)),
            sorted(k for k in glados.STRUCTURAL_KEYS if k in raw),
            "the projection holds exactly the structural keys the manifest "
            "sets")
        base = glados.structural_hash(raw)
        lane2 = dict(raw, channels={"progress": ["ledger"]},
                     params={}, platform="github", sinks={"x": None})
        self.assertEqual(glados.structural_hash(lane2), base,
                         "lane-2 keys must not move the hash")
        self.assertNotEqual(
            glados.structural_hash(dict(raw, phase="production")), base)
        # key order is irrelevant: the projection is canonicalised
        self.assertEqual(
            glados.structural_hash(dict(reversed(list(raw.items())))), base)
        # the compiled header carries the same hash
        t = self._installed()
        core = read(t / "product-knowledge" / "glados" / "intent.md")
        self.assertIn(f"manifest-sha256: {glados.manifest_hash_of(EXAMPLE)}",
                      core)

    def test_absent_and_null_structural_keys_hash_differently(self):
        # An absent key takes the phase preset's value; an explicit null
        # overrides it (`default-modules:` = no modules). The compiled cores
        # differ, so the hash must too, or check reports drift instead of a
        # stale compile and doctor calls the hash current.
        raw = glados.load_manifest(EXAMPLE)
        absent = {k: v for k, v in raw.items() if k != "default-modules"}
        null = dict(absent, **{"default-modules": None})
        self.assertNotEqual(glados.structural_hash(absent),
                            glados.structural_hash(null))
        line = "default-modules: [standards-gate]\n"
        self.assertIn(line, read(EXAMPLE))
        t = make_target(read(EXAMPLE).replace(line, ""))
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        write(t / "glados.yaml",
              read(EXAMPLE).replace(line, "default-modules:\n"))
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("stale compile", out)
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertIn("manifest hash: STALE", out)
        self.assertNotIn("nothing is stale", out)

    def test_doctor_checks_before_saying_nothing_is_stale(self):
        # The report also differs when GLaDOS itself changed (here: a newer
        # VERSION). The manifest hash is still current, but every compiled
        # file drifts, so doctor must not call the difference informational.
        t = self._installed()
        src = make_doctored_source()
        script = src / "bin" / "glados.py"
        old = f'VERSION = "{glados.VERSION}"'
        text = read(script)
        self.assertIn(old, text)
        script.write_text(text.replace(old, 'VERSION = "99.0.0"', 1),
                          encoding="utf-8", newline="\n")

        def run(*args):
            proc = subprocess.run(
                [sys.executable, str(script), *args, "--target", str(t),
                 "--source", str(src)], capture_output=True, text=True)
            return proc.returncode, proc.stdout + proc.stderr

        rc, out = run("doctor")
        self.assertEqual(rc, 0, out)
        self.assertIn("manifest hash: current", out)
        self.assertNotIn("nothing is stale", out)
        self.assertIn("installed file(s) drift", out)
        self.assertIn("this install was built by GLaDOS "
                      f"{glados.VERSION} and this is GLaDOS 99.0.0",
                      " ".join(out.split()))
        rc, out = run("check")
        self.assertEqual(rc, 1, out)
        self.assertIn("drift in installed file", out)

    def test_an_install_from_another_version_is_named_as_such(self):
        """2.5 changed what the manifest hash covers, so a 2.5 check of an
        untouched 2.4 install mismatches. Blaming "a structural key changed"
        sent people hunting for an edit nobody made: the install was built
        by another version, and check and doctor say so."""
        t = self._installed()
        vendored = t / ".glados" / "glados.py"
        old = f'VERSION = "{glados.VERSION}"'
        text = read(vendored)
        self.assertIn(old, text)
        vendored.write_text(text.replace(old, 'VERSION = "2.4.0"', 1),
                            encoding="utf-8", newline="\n")
        write(t / ".glados" / "manifest-hash", "0" * 64 + "\n")
        report = t / ".glados" / "assembly-report.md"
        write(report, read(report) + "\nrendered by an older GLaDOS\n")
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        flat = " ".join(out.split())
        self.assertIn(f"stale compile: this install was built by GLaDOS 2.4.0 "
                      f"and this is GLaDOS {glados.VERSION} — re-run install "
                      f"with {glados.VERSION} to upgrade it", flat)
        self.assertNotIn("a structural glados.yaml key", flat)
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        flat = " ".join(out.split())
        self.assertIn("manifest hash: STALE — this install was built by "
                      "GLaDOS 2.4.0", flat)
        self.assertIn("assembly report: this install was built by GLaDOS "
                      "2.4.0", flat)
        self.assertNotIn("a structural key changed", flat)
        self.assertNotIn("including a structural one", flat)

    def test_check_still_requires_the_assembly_report(self):
        t = self._installed()
        (t / ".glados" / "assembly-report.md").unlink()
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("missing installed file: .glados/assembly-report.md", out)

    def test_parse_error_fails_clearly(self):
        t = self._installed()
        write(t / "glados.yaml", "phase: evolving\nbranching:\n\tfeature: x\n")
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("glados.yaml:3", out)
        self.assertNotIn("Traceback", out)


class TestVendor(unittest.TestCase):

    def test_vendor_byte_match(self):
        """Self-vendored copies byte-match their sources."""
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        self.assertEqual((t / ".glados" / "glados.py").read_bytes(),
                         GLADOS_PY.read_bytes(), "vendored glados.py must byte-match")
        self.assertEqual((t / ".glados" / "presets.yaml").read_bytes(),
                         (REPO / "src" / "kernel" / "presets" / "phases.yaml").read_bytes(),
                         "vendored presets.yaml must byte-match")
        # manifest-hash file matches the recomputed hash
        vend = read(t / ".glados" / "manifest-hash").strip()
        self.assertEqual(vend, glados.manifest_hash_of(t / "glados.yaml"))
        # the FULL src/ tree is vendored byte-identically (the CI backstop
        # recomputes the compile from it), plus the manifest example
        src_files = sorted(p for p in (REPO / "src").rglob("*") if p.is_file())
        self.assertGreater(len(src_files), 0)
        for s in src_files:
            v = t / ".glados" / "src" / s.relative_to(REPO / "src")
            self.assertTrue(v.exists(), f"missing vendored source {v}")
            self.assertEqual(v.read_bytes(), s.read_bytes(),
                             f"vendored {v.name} must byte-match")
        self.assertEqual((t / ".glados" / "glados.yaml.example").read_bytes(),
                         EXAMPLE.read_bytes())

    def test_vendored_checker_self_contained(self):
        """`python .glados/glados.py check --target .` works with NO --source:
        the vendored src/ tree makes the CI backstop self-contained, and a
        clean install passes it in enforcing mode."""
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        proc = subprocess.run(
            [sys.executable, str(t / ".glados" / "glados.py"),
             "check", "--target", str(t)],
            capture_output=True, text=True)
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, out)
        self.assertIn("glados check: OK", out)

    def test_vendored_checker_ignores_target_src_layout(self):
        """A target repo with its own top-level src/ (a src-layout project)
        must not shadow the vendored .glados/src/. _resolve_source keys on the
        src/kernel/ shape, so the vendored checker still resolves .glados/ with
        NO --source and passes in enforcing mode. Regression for #14, where the
        app's src/ won and check --report-only went silently green."""
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        # Plant an unrelated application source tree at the repo root.
        write(t / "src" / "app" / "main.py", "print('hello')\n")
        proc = subprocess.run(
            [sys.executable, str(t / ".glados" / "glados.py"),
             "check", "--target", str(t)],
            capture_output=True, text=True)
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, out)
        self.assertIn("glados check: OK", out)
        self.assertNotIn("cannot resolve the GLaDOS source tree", out)
        # report-only must genuinely check (and pass), not go green while
        # never resolving its own sources.
        proc = subprocess.run(
            [sys.executable, str(t / ".glados" / "glados.py"),
             "check", "--target", str(t), "--report-only"],
            capture_output=True, text=True)
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, out)
        self.assertNotIn("cannot resolve the GLaDOS source tree", out)

    def test_vendored_tree_stale_files_cleaned(self):
        """A leftover file in a vendored .glados/ subtree (e.g. a renamed
        source after an upgrade) is cleaned on reinstall — it would otherwise
        skew the self-contained checker's recompute forever."""
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        stale_src = t / ".glados" / "src" / "vocabulary" / "old-fragment.md"
        write(stale_src, "renamed away two versions ago\n")
        stale_persona = t / ".glados" / "personas" / "retired.md"
        write(stale_persona, "retired persona\n")
        run_marker = t / ".glados" / "runs" / "2026-07-03-run.md"
        write(run_marker, "# run record — user history, never touched\n")
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertFalse(stale_src.exists(), "stale vendored source lingers")
        self.assertFalse(stale_persona.exists(), "stale persona lingers")
        self.assertTrue(run_marker.exists(), ".glados/runs/ must never be touched")
        # antigravity's glados-* name scoping applies to .agents/workflows
        # only, never to the vendored subtrees
        t2 = make_target()
        self.assertEqual(install("antigravity", t2)[0], 0)
        stale2 = t2 / ".glados" / "src" / "vocabulary" / "old-fragment.md"
        write(stale2, "stale\n")
        self.assertEqual(install("antigravity", t2)[0], 0)
        self.assertFalse(stale2.exists(),
                         "antigravity must clean vendored subtrees too")

    def test_ci_templates_vendored_and_sourceless(self):
        """Both CI templates are vendored to .glados/ci/, run the vendored
        checker without --source, and carry the separate non-blocking
        verify-ledger step; the install prints the enable stanza."""
        for name in ("glados-check.gitlab-ci.yml",
                     "glados-check.github-actions.yml"):
            tmpl = read(REPO / "ci" / name)
            self.assertIn("python .glados/glados.py check --target . "
                          "--report-only", tmpl, name)
            self.assertNotIn("--source .", tmpl,
                             f"{name} must not need a source checkout")
            self.assertIn("verify-ledger --target . --report-only", tmpl, name)
        gitlab = read(REPO / "ci" / "glados-check.gitlab-ci.yml")
        self.assertIn("allow_failure: true", gitlab,
                      "verify-ledger job must be non-blocking")
        github = read(REPO / "ci" / "glados-check.github-actions.yml")
        self.assertIn("continue-on-error: true", github,
                      "verify-ledger step must be non-blocking")
        t = make_target()
        rc, out = install("claude", t)
        self.assertEqual(rc, 0, out)
        for name in ("glados-check.gitlab-ci.yml",
                     "glados-check.github-actions.yml"):
            self.assertEqual((t / ".glados" / "ci" / name).read_bytes(),
                             (REPO / "ci" / name).read_bytes(),
                             f"vendored {name} must byte-match")
        # example manifest says platform: gitlab -> the GitLab stanza prints
        self.assertIn(".glados/ci/glados-check.gitlab-ci.yml", out)
        self.assertIn("include:", out)

    def test_agy_hooks_single_source(self):
        """hooks/agy-hooks.json is the one source of the agy hooks block: it
        stays dumps(indent=2)-normalized, the README fenced block matches it,
        the antigravity install emits it verbatim, and it is vendored."""
        record_path = REPO / "hooks" / "agy-hooks.json"
        record = record_path.read_text(encoding="utf-8")
        data = json.loads(record)
        self.assertEqual(
            record, json.dumps(data, indent=2) + "\n",
            "hooks/agy-hooks.json must stay json.dumps(..., indent=2)-"
            "normalized — _emit_agy_hooks re-emits it through json.dumps")
        readme = (REPO / "hooks" / "README.md").read_text(encoding="utf-8")
        blocks = [b for b in re.findall(r"```json\n(.*?)```", readme, re.S)
                  if "glados-run-record-guard" in b]
        self.assertEqual(len(blocks), 1,
                         "hooks/README.md must show exactly one agy block")
        self.assertEqual(json.loads(blocks[0]), data,
                         "hooks/README.md fenced agy block drifted from "
                         "hooks/agy-hooks.json — update the README from the "
                         "file of record")
        t = make_target()
        rc, out = install("antigravity", t)
        self.assertEqual(rc, 0, out)
        self.assertEqual(read(t / ".agents" / "hooks.json"), record,
                         "emitted .agents/hooks.json must match the record")
        self.assertEqual(
            (t / ".glados" / "hooks" / "agy-hooks.json").read_bytes(),
            record_path.read_bytes(), "agy-hooks.json must be vendored")

    def test_personas_vendored(self):
        """Every install mode vendors the full src/personas/ library into
        <target>/.glados/personas/, byte-identical — panels resolve library
        personas from there (project product-knowledge/personas/ wins)."""
        src_personas = sorted((REPO / "src" / "personas").glob("*.md"))
        self.assertGreater(len(src_personas), 0, "library personas missing")
        for mode in ("claude", "claude-plugin", "direct", "gemini",
                     "antigravity", "aistudio", "pi"):
            with self.subTest(mode=mode):
                t = make_plugin_target() if mode == "claude-plugin" else make_target()
                rc, out = install(mode, t)
                self.assertEqual(rc, 0, out)
                vendored = sorted((t / ".glados" / "personas").glob("*.md"))
                self.assertEqual([p.name for p in vendored],
                                 [p.name for p in src_personas],
                                 f"{mode}: vendored persona set differs")
                for s, v in zip(src_personas, vendored):
                    self.assertEqual(v.read_bytes(), s.read_bytes(),
                                     f"{mode}: {v.name} not byte-identical")


class TestCleanup(unittest.TestCase):

    def test_cleanup_directory_scoped(self):
        # Install claude over the legacy tree; assert directory-scoped cleanup.
        t = tmpdir("glados-legacy-")
        shutil.copytree(LEGACY, t, dirs_exist_ok=True)
        rc, out = install("claude", t)
        self.assertEqual(rc, 0, out)

        owned = t / ".claude" / "commands" / "glados"
        parent = t / ".claude" / "commands"

        # v1 leftovers INSIDE owned dirs are cleaned
        self.assertFalse((owned / "plan_feature.md").exists(),
                         "underscore v1 file inside owned dir should be removed")
        self.assertFalse((owned / "old-removed-workflow.md").exists(),
                         "stale core inside owned dir should be removed")
        # top-level un-namespaced v1 file matching a core name is migrated away
        self.assertFalse((parent / "plan-feature.md").exists(),
                         "top-level v1 command should be migrated away")

        # files OUTSIDE glados-owned dirs are untouched
        self.assertTrue((parent / "my-user-command.md").exists(),
                        "user command must survive")
        self.assertTrue((t / "README.md").exists(), "repo README must survive")
        self.assertTrue((t / ".gemini" / "skills" / "glados" / "SKILL.md").exists(),
                        "v1 gemini layout outside owned dirs must survive")

        # the real cores + alias shims landed
        self.assertTrue((owned / "plan-feature.md").exists())
        self.assertTrue((owned / "fix-bug.md").exists())
        self.assertTrue((owned / "mission.md").exists(), "alias shim expected")

    def test_v1_legacy_cleanup_gemini(self):
        # The gemini install removes the fully v1-owned .gemini/skills/glados/
        # tree; a claude install (above) leaves it alone.
        t = tmpdir("glados-v1-gem-")
        shutil.copytree(LEGACY, t, dirs_exist_ok=True)
        rc, out = install("gemini", t)
        self.assertEqual(rc, 0, out)
        self.assertFalse((t / ".gemini" / "skills" / "glados").exists(),
                         "v1 gemini tree must be removed by the gemini install")
        self.assertTrue(
            (t / ".gemini" / "commands" / "glados" / "intent.toml").exists())
        self.assertIn(".gemini/skills/glados", out.replace("\\", "/"),
                      "removed v1 files must be reported")

    def test_v1_legacy_cleanup_direct(self):
        # The direct install removes ONLY known-v1-named files from the shared
        # product-knowledge/{workflows,modules}/ dirs — never user files.
        t = tmpdir("glados-v1-dir-")
        shutil.copytree(LEGACY, t, dirs_exist_ok=True)
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        pk = t / "product-knowledge"
        self.assertFalse((pk / "workflows" / "plan_feature.md").exists(),
                         "known v1 name (underscore variant) must be removed")
        self.assertFalse((pk / "modules").exists(),
                         "emptied v1 modules dir must be removed")
        self.assertTrue((pk / "workflows" / "my-notes.md").exists(),
                        "unmatched user file must survive")
        self.assertTrue((pk / "workflows").is_dir(),
                        "dir with surviving user files must not be removed")
        # non-direct modes leave the shared dirs alone
        t2 = tmpdir("glados-v1-cla-")
        shutil.copytree(LEGACY, t2, dirs_exist_ok=True)
        rc, out = install("claude", t2)
        self.assertEqual(rc, 0, out)
        self.assertTrue((t2 / "product-knowledge" / "workflows" /
                         "plan_feature.md").exists(),
                        "claude install must not touch product-knowledge/workflows")


class TestDisabledWorkflows(unittest.TestCase):

    MINIMAL = ("glados: 2\nplatform: gitlab\nphase: {phase}\n"
               "branching:\n  feature: \"feat/<slug>\"\n"
               "  default-target: main\n")

    def test_sunset_preset_disables_build_feature(self):
        t = make_target(self.MINIMAL.format(phase="sunset"))
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        for core in ("build-feature", "run-pipeline"):
            self.assertFalse(
                (t / "product-knowledge" / "glados" / f"{core}.md").exists(),
                f"sunset must not install {core}")
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("| disabled-workflows | [build-feature, run-pipeline] | "
                      "(phase:sunset) |", report, report)

    def test_explicit_empty_list_overrides_preset(self):
        t = make_target(self.MINIMAL.format(phase="sunset")
                        + "disabled-workflows: []\n")
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertTrue(
            (t / "product-knowledge" / "glados" / "build-feature.md").exists(),
            "explicit [] must re-enable what the preset disabled")
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("| disabled-workflows | [] | (explicit) |", report)

    def test_disabled_target_alias_shim_says_disabled(self):
        text = read(EXAMPLE).replace("disabled-workflows: []",
                                     "disabled-workflows: [fix-bug]")
        t = make_target(text)
        rc, out = install("claude", t)
        self.assertEqual(rc, 0, out)
        owned = t / ".claude" / "commands" / "glados"
        self.assertFalse((owned / "fix-bug.md").exists())
        shim = read(owned / "plan-fix.md")
        self.assertIn("disabled", shim)
        self.assertNotIn("Run `/glados:fix-bug`", shim,
                         "a disabled target must not be invoked")
        # direct mode's disabled shim says so too
        t2 = make_target(text)
        rc, out = install("direct", t2)
        self.assertEqual(rc, 0, out)
        self.assertIn("disabled",
                      read(t2 / "product-knowledge" / "glados" / "plan-fix.md"))
        # plugin mode: disabled alias stub says disabled AND keeps the
        # generated-stub marker so pruning can still identify it
        t3 = make_plugin_target()
        write(t3 / "glados.yaml.example", text)
        rc, out = install("claude-plugin", t3)
        self.assertEqual(rc, 0, out)
        stub = read(t3 / "skills" / "plan-fix" / "SKILL.md")
        self.assertIn("disabled", stub)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/compiled/claude-plugin/", stub)


class TestAliasShims(unittest.TestCase):

    def test_direct_and_aistudio_alias_shims(self):
        # direct: file-pointer bodies, never slash-command syntax
        t = make_target()
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        shim = read(t / "product-knowledge" / "glados" / "plan-fix.md")
        self.assertIn("product-knowledge/glados/fix-bug.md", shim)
        self.assertNotIn("/glados:", shim,
                         "direct mode has no slash-command syntax")
        self.assertTrue((t / "product-knowledge" / "glados" / "mission.md")
                        .exists(), "every alias gets a shim")
        # aistudio: pointer stubs beside the bundles
        t2 = make_target()
        rc, out = install("aistudio", t2)
        self.assertEqual(rc, 0, out)
        bundles = t2 / "glados" / "adapters" / "aistudio" / "bundles"
        self.assertIn("bundles/fix-bug-advisory.aistudio.md",
                      read(bundles / "plan-fix.aistudio.md"))
        self.assertIn("bundles/intent.aistudio.md",
                      read(bundles / "mission.aistudio.md"))
        self.assertIn("no AI Studio bundle",
                      read(bundles / "autonomous-loop.aistudio.md"))
        # alias stubs are pointers, not bundles: they stay out of MANIFEST.md
        manifest = read(bundles.parent / "MANIFEST.md")
        self.assertNotIn("mission", manifest)


class TestParamsResolution(unittest.TestCase):

    def test_baseline_evaluator_bound_resolves(self):
        # A minimal manifest with no params: block still resolves both loop
        # bounds (and the roster) from the baseline preset.
        manifest = ("glados: 2\nplatform: gitlab\nphase: evolving\n"
                    "branching:\n  feature: \"feat/<slug>\"\n"
                    "  default-target: main\n")
        t = make_target(manifest)
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("| params.evaluator.max-cycles | 3 | (baseline) |", report)
        self.assertIn("| params.review-panel.personas | [] | (baseline) |", report)

    def test_dangling_params_literal_fails(self):
        # A compiled `params.<ns>.<key>` literal with no resolved value is an
        # unbounded loop / missing roster — the install must refuse it.
        src = make_doctored_source()
        core = src / "src" / "workflows" / "intent.md"
        core.write_text(read(core) + "\nBound: `params.bogus.max-cycles`.\n",
                        encoding="utf-8", newline="\n")
        rc, out = install("direct", make_target(), source=src)
        self.assertEqual(rc, 1, out)
        self.assertIn("params.bogus.max-cycles", out)
        self.assertIn("intent", out)
        self.assertNotIn("Traceback", out)

    # -- loop bounds are whole numbers (B1) ----------------------------------

    MINIMAL = ("glados: 2\nplatform: gitlab\nphase: evolving\n"
               "branching:\n  feature: \"feat/<slug>\"\n"
               "  default-target: main\n")

    def _type_errors(self, manifest):
        """The type-check errors ``manifest`` fails with, in-process."""
        try:
            glados._prepare_compilation(glados.Source(REPO),
                                        make_target(manifest), "claude")
        except glados.CheckFailed as exc:
            return exc.errors
        return []

    def test_every_loop_bound_is_a_whole_number_of_one_or_more(self):
        """Every `params.<ns>.<key>` a compiled workflow relies on, the
        persona roster aside, bounds a loop, so it must be a whole number of
        1 or more. Text, true (an int to Python), a list and a number below
        1 used to resolve and install, leaving the loop no count it could
        stop at."""
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        bounds = set()
        for core in (t / "product-knowledge" / "glados").glob("*.md"):
            bounds |= set(glados.PARAMS_LITERAL_RE.findall(read(core)))
        bounds.discard("params.review-panel.personas")
        self.assertIn("params.pipeline.max-cycles", bounds)
        self.assertEqual(len(bounds), 4, bounds)
        bad = (('"8"', "got the text '8'"), ("lots", "got the text 'lots'"),
               ("true", "got true"), ("[8]", "got [8]"), ("0", "got 0"),
               ("-2", "got -2"))
        for lit in sorted(bounds):
            _, ns, key = lit.split(".")
            for value, shown in bad:
                with self.subTest(bound=lit, value=value):
                    errors = self._type_errors(
                        self.MINIMAL + f"params:\n  {ns}:\n    {key}: {value}\n")
                    hit = [e for e in errors if e.startswith(lit + ":")]
                    self.assertTrue(hit, errors)
                    self.assertIn("must be a whole number of 1 or more", hit[0])
                    self.assertIn(shown, hit[0])
                    self.assertIn("(value from explicit)", hit[0])
            with self.subTest(bound=lit, value="1"):
                self.assertEqual(self._type_errors(
                    self.MINIMAL + f"params:\n  {ns}:\n    {key}: 1\n"), [])

    def test_a_preset_bound_and_a_bound_out_of_shape_fail_too(self):
        """A bound the manifest inherits is checked like one it sets, and
        validate (which run-pipeline runs before its first step) names it.
        A namespace written as a number was dropped without a word, leaving
        the baseline's bound in force."""
        src = make_doctored_source()
        presets = src / "src" / "kernel" / "presets" / "phases.yaml"
        text = read(presets)
        self.assertIn("      max-cycles: 8\n", text)
        presets.write_text(text.replace("      max-cycles: 8\n",
                                        "      max-cycles: \"8\"\n"),
                           encoding="utf-8", newline="\n")
        rc, out = install("direct", make_target(), source=src)
        self.assertEqual(rc, 1, out)
        self.assertIn("params.pipeline.max-cycles: must be a whole number of "
                      "1 or more", out)
        self.assertIn("(value from baseline)", out)
        self.assertNotIn("Traceback", out)
        for params, needle in (
                ("  pipeline:\n    max-cycles: true\n",
                 "params.pipeline.max-cycles: must be a whole number"),
                ("  pipeline: 5\n", "params.pipeline: must be a mapping")):
            with self.subTest(params=params):
                t = make_target(self.MINIMAL + "params:\n" + params)
                rc, out = run_cli("validate", "--target", t, "--source", REPO)
                self.assertEqual(rc, 1, out)
                self.assertIn("glados validate: FAIL", out)
                self.assertIn(needle, out)
                self.assertNotIn("Traceback", out)

    def test_a_quoted_key_is_the_key_it_quotes(self):
        """`"max-cycles": true` is max-cycles: true in YAML, and to the agent
        that reads glados.yaml at run time. The parser kept the quotes on
        the key, so the bound checks never saw it (the assembly report even
        listed it beside the baseline's bound), and a decision right
        written `"schema-migration": agent` skipped the relaxation check."""
        quoted = ('params:\n  pipeline:\n    "max-cycles": true\n'
                  "  review-panel:\n    'max-cycles': lots\n")
        self.assertEqual(glados.parse_yaml(quoted, "t"), {"params": {
            "pipeline": {"max-cycles": True},
            "review-panel": {"max-cycles": "lots"}}})
        errors = self._type_errors(self.MINIMAL + quoted)
        for lit, shown in (("params.pipeline.max-cycles", "got true"),
                           ("params.review-panel.max-cycles",
                            "got the text 'lots'")):
            hit = [e for e in errors if e.startswith(lit + ":")]
            self.assertTrue(hit, errors)
            self.assertIn(shown, hit[0])
        # one key, however it is spelt
        with self.assertRaises(glados.YamlError) as ctx:
            glados.parse_yaml('pipeline:\n  max-cycles: 3\n'
                              '  "max-cycles": 9\n', "t")
        self.assertIn("duplicate key 'max-cycles'", str(ctx.exception))
        # a decision right is as lax quoted as plain
        production = self.MINIMAL.replace("phase: evolving",
                                          "phase: production")
        plain = self._type_errors(
            production + "decisions:\n  schema-migration: agent\n")
        self.assertTrue([e for e in plain if "laxer" in e], plain)
        self.assertEqual(self._type_errors(
            production + 'decisions:\n  "schema-migration": agent\n'), plain)
        # a `- "key": value` item is a mapping, as `- key: value` is
        self.assertEqual(
            glados.parse_yaml('items:\n  - "name": a\n    \'kind\': gate\n',
                              "t"),
            {"items": [{"name": "a", "kind": "gate"}]})
        # and the refusal says how to write a bound
        hit = self._type_errors(
            self.MINIMAL + "params:\n  pipeline:\n    max-cycles: 3.0\n")
        self.assertTrue(hit)
        self.assertIn("write a plain integer such as 3, with no quotes or "
                      "decimal point", hit[0])

    def test_every_spelling_yaml_reads_as_the_bound_is_checked_or_refused(self):
        """Quoting was one spelling of a key. The parser kept the rest of
        YAML's key syntax as text: an escape it did not know (`\\x2D`,
        `\\u002D`, `\\U0000002D`), an anchor (`&a`), a tag (`!!str`, on the
        key or on `params:` above it), a merge key (`<<:`). A YAML reader,
        the agent included, reads each of these as
        params.pipeline.max-cycles: true, but every command that reads
        the manifest saw a key nothing reads, warned, and passed with
        the inherited 8. Each is now read as YAML reads it, so the bound
        check names it, or refused with the line it is on."""
        bs = "\\"
        head = "glados: 2\nplatform: github\nphase: evolving\n"
        pipe = head + "params:\n  pipeline:\n"
        bound = ("params.pipeline.max-cycles: must be a whole number of 1 or "
                 "more")
        cases = {
            # read as YAML reads it, so the bound check sees max-cycles
            "x escape": (pipe + f'    "max{bs}x2Dcycles": true\n', bound),
            "u escape": (pipe + f'    "max{bs}u002Dcycles": true\n', bound),
            "U escape": (pipe + f'    "max{bs}U0000002Dcycles": true\n',
                         bound),
            # syntax the subset does not read: refused, naming the line
            "anchor": (pipe + "    &a max-cycles: true\n",
                       "glados.yaml:6: '&a max-cycles' starts with '&'"),
            "tag": (pipe + "    !!str max-cycles: true\n",
                    "glados.yaml:6: '!!str max-cycles' starts with '!'"),
            "tag above": (head + "!!str params:\n  pipeline:\n"
                          "    max-cycles: true\n",
                          "glados.yaml:4: '!!str params' starts with '!'"),
            "merge key": (pipe + "    <<:\n      max-cycles: true\n",
                          "glados.yaml:6: '<<' is a YAML merge key"),
        }
        installed = make_target(head)
        rc, out = install("claude", installed)
        self.assertEqual(rc, 0, out)
        for name, (manifest, needle) in cases.items():
            t = make_target(manifest)
            write(installed / "glados.yaml", manifest)
            for args in (("validate", "--target", t),
                         ("effective-config", "--target", t),
                         ("install", "--mode", "claude", "--target", t),
                         ("check", "--target", installed)):
                with self.subTest(case=name, command=args[0]):
                    rc, out = run_cli(*args, "--source", REPO)
                    self.assertEqual(rc, 1, out)
                    self.assertIn(needle, out)
                    self.assertNotIn("Traceback", out)
                    self.assertNotIn("passes every check", out)

    def test_a_preset_table_out_of_shape_is_named_not_a_traceback(self):
        """A preset layer that is not a mapping, or whose params, channels
        or decisions are not, crashed resolution with an AttributeError or
        TypeError traceback instead of a sentence naming the table."""
        src = make_doctored_source()
        presets = src / "src" / "kernel" / "presets" / "phases.yaml"
        original = read(presets)

        def block(name):
            return re.search(rf"^{name}:\n(?:(?:[ #].*)?\n)*", original,
                             re.M).group(0)

        baseline = block("baseline")
        params_at = baseline.index("  params:\n")
        for label, edited, needle in (
                ("baseline", original.replace(baseline, "baseline: 5\n\n"),
                 "phases.yaml: 'baseline:' must be a mapping"),
                ("phase", original.replace(block("evolving"),
                                           "evolving: 5\n\n"),
                 "phases.yaml: 'evolving:' must be a mapping"),
                ("params", original.replace(
                    baseline, baseline[:params_at] + "  params: 5\n\n"),
                 "phases.yaml (baseline): params: must be a mapping"),
                ("decisions", original.replace(
                    block("evolving"), "evolving:\n  decisions: [agent]\n\n"),
                 "phases.yaml (phase:evolving): decisions: must be a "
                 "mapping")):
            with self.subTest(layer=label):
                self.assertNotEqual(edited, original)
                write(presets, edited)
                rc, out = install("direct", make_target(self.MINIMAL),
                                  source=src)
                self.assertEqual(rc, 1, out)
                self.assertIn(needle, out)
                self.assertNotIn("Traceback", out)

    def test_a_number_too_long_to_read_is_a_named_error(self):
        """Python refuses to read an integer of more than 4300 digits, and
        the ValueError escaped as a traceback from every command: install,
        validate, `check --report-only` (which never fails) and doctor
        (which never fails either)."""
        t = make_target(self.MINIMAL)
        self.assertEqual(install("direct", t)[0], 0)
        write(t / "glados.yaml", self.MINIMAL
              + "params:\n  pipeline:\n    max-cycles: " + "9" * 5000 + "\n")
        limited = getattr(sys, "get_int_max_str_digits", lambda: 0)()
        for args, code in ((("validate",), 1), (("install", "--mode",
                                                 "direct"), 1),
                           (("check", "--report-only"), 0), (("doctor",), 0)):
            with self.subTest(command=args[0]):
                rc, out = run_cli(*args, "--target", t, "--source", REPO)
                self.assertNotIn("Traceback", out)
                if args[0] in ("check", "doctor") or limited:
                    self.assertEqual(rc, code, out)
                if limited:
                    self.assertIn("glados.yaml:9: the number", out)

    def test_a_params_key_nothing_reads_is_named(self):
        """`max_cycles: 1`, or a `run-pipeline:` namespace, installed
        without a word while the inherited bound stayed in force, so a
        team's intended tightening did nothing. It warns (and fails
        nothing), naming the keys that are read."""
        t = make_target(self.MINIMAL + "params:\n  pipeline:\n"
                        "    max_cycles: 1\n  run-pipeline:\n"
                        "    max-cycles: 1\n  review-panel:\n"
                        "    max-cycles: 2\n")
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        for path in ("pipeline.max_cycles", "run-pipeline.max-cycles"):
            needle = f"glados.yaml: params.{path} is read by nothing"
            self.assertEqual(out.count(needle), 1, out)
            self.assertIn("pipeline.max-cycles", out.split(needle)[1])
        self.assertNotIn("params.review-panel.max-cycles is read by", out)
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("params.pipeline.max_cycles is read by nothing", out)

    def test_doctor_names_the_check_that_failed(self):
        """doctor printed only "install checks failed:", the first line of
        the error, so a bound that is not a whole number went unnamed."""
        t = make_target(self.MINIMAL)
        self.assertEqual(install("direct", t)[0], 0)
        write(t / "glados.yaml",
              self.MINIMAL + "params:\n  pipeline:\n    max-cycles: lots\n")
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("could not render a fresh copy to compare "
                      "(params.pipeline.max-cycles: must be a whole number",
                      out)

    def test_a_bound_that_is_no_whole_number_stops_the_loop_at_run_time(self):
        """Bounds are lane-2 values the agent reads live from glados.yaml,
        so one edited after install (no reinstall; CI's check is
        report-only) reaches the loop past every install-time check, and
        only run-pipeline runs validate. Every workflow that bounds a loop
        says what a value that is not a whole number of 1 or more is: no
        bound, so the loop does not start and the run escalates naming the
        key. run-pipeline's no-Python checklist checks its own bound."""
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        rule = ("A bound must resolve to a whole number of 1 or more. "
                "Anything else (missing, text, `true` or `false`, a list, 0 "
                "or less) is no bound: do not start the loop; emit an "
                "`escalation` naming the key and its value, and end the run.")
        bounded = set()
        for core in (t / "product-knowledge" / "glados").glob("*.md"):
            text = " ".join(read(core).split())
            if any(lit.endswith(".max-cycles")
                   for lit in glados.PARAMS_LITERAL_RE.findall(text)):
                bounded.add(core.stem)
                with self.subTest(core=core.stem):
                    self.assertIn(rule, text)
        self.assertTrue({"review-mr", "address-review", "build-feature",
                         "verify-feature", "fix-bug", "run-pipeline"}
                        <= bounded, bounded)
        text = " ".join(read(t / "product-knowledge" / "glados" /
                             "run-pipeline.md").split())
        self.assertIn("7. each pipeline's description is 250 characters or "
                      "fewer; 8. `params.pipeline.max-cycles`, and every "
                      "other `max-cycles` under `params:`, resolves "
                      "(`glados.yaml` over the preset table) to a whole "
                      "number of 1 or more: not text, `true` or `false`, a "
                      "list, or 0 or less.", text)


class TestVerifyLedger(unittest.TestCase):

    def test_verify_ledger_reports(self):
        # Init a git repo with an agent-authored branch and no run records.
        t = tmpdir("glados-ledger-")
        shutil.copyfile(EXAMPLE, t / "glados.yaml")

        def git(*a):
            subprocess.run(["git", "-C", str(t), *a], capture_output=True, text=True)

        git("init", "-q")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        git("checkout", "-q", "-b", "main")
        (t / "a.txt").write_text("x", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "feat: initial")
        git("checkout", "-q", "-b", "feat/thing")
        (t / "b.txt").write_text("y", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "feat: work without a run record")
        rc, out = run_cli("verify-ledger", "--target", t)
        self.assertEqual(rc, 0)
        self.assertIn("run-record commits", out)


class TestYamlParserAttacks(unittest.TestCase):
    """Malformed-manifest attacks: each must die with a line-numbered
    YamlError, never a silent misparse or a raw traceback."""

    def test_yaml_tab_indent_fatal(self):
        # A tab-indented sub-map silently re-parents keys if tolerated.
        t = make_target("glados: 2\nplatform: gitlab\nphase: evolving\n"
                        "branching:\n\tfeature: x\n\tdefault-target: main\n")
        rc, out = install("direct", t)
        self.assertEqual(rc, 1, "tab indentation must be fatal:\n" + out)
        self.assertIn("glados.yaml:5", out)
        self.assertIn("tab", out.lower())
        self.assertNotIn("Traceback", out)

    def test_yaml_flow_map_fatal(self):
        t = make_target("glados: 2\nplatform: gitlab\nphase: evolving\n"
                        "branching: {feature: x, default-target: main}\n")
        rc, out = install("direct", t)
        self.assertEqual(rc, 1, "flow map must be fatal:\n" + out)
        self.assertIn("glados.yaml:4", out)
        self.assertIn("flow mapping", out)
        self.assertNotIn("Traceback", out)

    def test_yaml_duplicate_key_fatal(self):
        t = make_target("glados: 2\nplatform: gitlab\nphase: evolving\n"
                        "phase: nascent\nbranching:\n  default-target: main\n")
        rc, out = install("direct", t)
        self.assertEqual(rc, 1, "duplicate key must be fatal:\n" + out)
        self.assertIn("glados.yaml:4", out)
        self.assertIn("duplicate key 'phase'", out)
        self.assertNotIn("Traceback", out)

    def test_yaml_quoted_comma_flow_list(self):
        parsed = glados.parse_yaml(
            'personas: ["security, compliance", architect]\n', "t")
        self.assertEqual(parsed["personas"], ["security, compliance", "architect"])

    def test_manifest_bom_tolerated(self):
        # PowerShell 5.1 writes a BOM even for `-Encoding utf8`.
        t = tmpdir()
        (t / "glados.yaml").write_bytes(
            b"\xef\xbb\xbf" + EXAMPLE.read_bytes())
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, "BOM manifest must install:\n" + out)
        # and the vendored hash agrees with a re-check (no false stale)
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)

    def test_manifest_utf16_fatal_names_fix(self):
        t = tmpdir()
        text = read(EXAMPLE)
        (t / "glados.yaml").write_bytes(text.encode("utf-16"))
        rc, out = install("direct", t)
        self.assertEqual(rc, 1)
        self.assertIn("glados.yaml", out)
        self.assertIn("UTF-8", out)
        self.assertNotIn("Traceback", out)

    # -- the subset reads what YAML reads, or refuses -----------------------

    def _refused(self, text, line, needle=""):
        with self.assertRaises(glados.YamlError) as ctx:
            glados.parse_yaml(text, "t")
        self.assertIn(f"t:{line}:", str(ctx.exception))
        self.assertIn(needle, str(ctx.exception))

    def test_escapes_read_as_yaml_reads_them(self):
        """A double-quoted scalar takes YAML's escapes, all of them, and no
        others. The parser decoded five and kept the backslash on the rest,
        so `"max\\x2Dcycles"` was a key nothing checks while YAML reads it
        as max-cycles."""
        bs = "\\"
        table = {
            "x2D": "-", "u002D": "-", "U0000002D": "-", "u00e9": "\u00e9",
            "U0001F600": "\U0001F600", "0": "\x00", "a": "\x07", "b": "\x08",
            "t": "\t", "\t": "\t", "n": "\n", "v": "\x0b", "f": "\x0c",
            "r": "\r", "e": "\x1b", " ": " ", '"': '"', "/": "/", bs: bs,
            "N": "\x85", "_": "\xa0", "L": "\u2028", "P": "\u2029",
        }
        for esc, char in table.items():
            with self.subTest(escape=esc):
                self.assertEqual(
                    glados.parse_yaml(f'k: "a{bs}{esc}b"\n', "t"),
                    {"k": f"a{char}b"})
                if unicodedata.category(char) in ("Cc", "Cf"):
                    # a key that differs from a visible one by a character
                    # that does not show is refused (below)
                    self._refused(f'"a{bs}{esc}b": 1\n', 1, "does not show")
                    continue
                self.assertEqual(
                    glados.parse_yaml(f'"a{bs}{esc}b": 1\n', "t"),
                    {f"a{char}b": 1})
                self.assertEqual(
                    glados.parse_yaml(f'k: ["a{bs}{esc}b"]\n', "t"),
                    {"k": [f"a{char}b"]})
        for esc, needle in (("q", f"'{bs}q' is not a YAML escape"),
                            ("x4", "needs 2 hex digits"),
                            ("xZZ", "needs 2 hex digits"),
                            ("u12", "needs 4 hex digits"),
                            ("uD800", "is not a character"),
                            ("U00110000", "is not a character")):
            with self.subTest(escape=esc):
                self._refused(f'k: "a{bs}{esc}"\n', 1, needle)
                self._refused(f'x: 1\n"a{bs}{esc}": 1\n', 2, needle)
                self._refused(f'x: 1\nk: [b, "a{bs}{esc}"]\n', 2, needle)
        self._refused(f'k: "a{bs}"\n', 1, "unterminated")

    def test_yaml_syntax_the_subset_does_not_read_is_refused(self):
        """Anchors, aliases, tags, merge keys, explicit keys and YAML's
        reserved indicators were kept as text, so the parser read another
        key or value than any YAML reader does: `&a max-cycles: true` was
        a key nothing checks. Each is refused, naming the line, wherever it
        stands: a key, a value, a list item, a flow-list item."""
        for key in ("&a k", "*a", "!!str k", "!k", "? k", "?k", "|k", ">k",
                    "%k", "@k", "`k", "[k]", "{k", ",k", ":k"):
            with self.subTest(key=key):
                self._refused(f"m:\n  {key}: 1\n", 2,
                              f"'{key}' starts with '{key[0]}'")
                self._refused(f"l:\n  - {key}: 1\n", 2)
        self._refused("l:\n  - - k: 1\n", 2, "'- k' starts with '-'")
        for key in ("<<", '"<<"'):
            self._refused(f"m:\n  {key}:\n    max-cycles: true\n", 2,
                          "'<<' is a YAML merge key")
        for value in ("&a 1", "*a", "!!int 3", "!x v", "%v", "@v", "`v`",
                      "- v", "? v", "?v", ":v", ",v", "]", "}"):
            with self.subTest(value=value):
                self._refused(f"m:\n  k: {value}\n", 2,
                              f"'{value}' starts with '{value[0]}'")
                self._refused(f"l:\n  - z\n  - {value}\n", 3)
                self._refused(f"x: 1\nl: [a, {value}]\n", 2)
        for text, line, needle in (
                ("k: |2\n   x\n", 1, "block scalar"),
                ("k: >-1\n x\n", 1, "block scalar"),
                ("k: |x\n", 1, "block scalar"),
                ('k: "a" b\n', 1, "after the closing quote"),
                ("k: 'a'b'\n", 1, "after the closing quote"),
                ('"k" x: 1\n', 1, "after the closing quote"),
                ('k: "abc\n', 1, "unterminated"),
                ("k: 'abc\n", 1, "unterminated"),
                ("m:\n  k:v\n", 2, "expected 'key: value', got 'k:v'"),
                ("k: a: b\n", 1, "': '"),
                ("k: a:\n", 1, "': '"),
                ("k: 010\n", 1, "leading zero"),
                ("k: -08\n", 1, "leading zero"),
                ("k: [a: b]\n", 1, "': '"),
                ("k: [?x]\n", 1, "'?'"),
                ("k: [a?b]\n", 1, "'?'"),
                ("k: [a, , b]\n", 1, "empty item"),
                ("k: [a, b] c\n", 1, "after ']'"),
                ('k: ["a" x, b]\n', 1, "after the closing quote"),
                ("k: [a, {b: c}]\n", 1, "nested flow"),
                ("k: [a, b\n", 1, "unterminated inline list"),
                ("k: [a, b # c]\n", 1, "unterminated inline list"),
                ("x: 1\n<<: *a\n", 2, "merge key"),
                ("k: <<\n", 1, "merge key"),
                ("k: [a, <<]\n", 1, "merge key"),
                ("k: =\n", 1, "value key"),
                # a key YAML reads as null, a bool, a number or a date: two
                # keys here were one to YAML (null and ~, 1 and 01)
                ("m:\n  null: a\n  ~: b\n", 2, "the key 'null' is a null"),
                ("m:\n  1: a\n", 2, "the key '1' is"),
                ("m:\n  yes: a\n", 2, "the key 'yes' is"),
                ("m:\n  1.5: a\n", 2, "the key '1.5' is"),
                ("m:\n  2026-10-22: a\n", 2, "the key '2026-10-22' is"),
                # a tab outside quotes, which YAML readers do not agree on
                ("k: a\tb\n", 1, "tab outside quotes"),
                ("k\t: v\n", 1, "tab outside quotes"),
                ("k: v\t# c\n", 1, "tab outside quotes"),
                ("k: [a,\tb]\n", 1, "tab outside quotes"),
                ('k: "v"\t# c\n', 1, "after the closing quote"),
                ("k: v\n\t\n", 2, "tab character on a blank line"),
                # characters YAML refuses, or reads as a line break in 1.1
                ("k: a\x00b\n", 1, "U+0000"),
                ("k: a\x85b\n", 1, "U+0085"),
                ("k: a\u2028b\n", 1, "U+2028"),
                # a key another key in disguise: YAML reads a different key,
                # the agent looking at the text sees the visible one
                ('m:\n  "schema-migration\\0": agent\n', 2, "U+0000"),
                ("m:\n  max-cycles\u200b: 3\n", 2, "U+200B"),
                ('m:\n  "max-cycles\\u200B": 3\n', 2, "U+200B"),
                # lines the parser used to drop: YAML refuses the document
                ("  a: 1\nb: 2\n", 2, "does not continue the document"),
                ("- a\nb: 2\n", 2, "does not continue the document")):
            with self.subTest(text=text):
                self._refused(text, line, needle)
        # a quoted key is text to YAML, whatever it spells
        self.assertEqual(glados.parse_yaml('"1": a\n"null": b\n', "t"),
                         {"1": "a", "null": "b"})

    def test_the_subset_reads_yaml_as_yaml_does(self):
        """What the parser accepts, it reads as YAML does: a quote only
        opens a quoted scalar at the start of one (an apostrophe in a plain
        value no longer swallows the comment after it), an escaped quote
        does not close one, and a key ends at the first ': '."""
        bs = "\\"
        for text, expected in (
                (f'k: "a{bs}" # b" # c\n', {"k": 'a" # b'}),
                ("k: don't # c\n", {"k": "don't"}),
                ("k: it's 'quoted' # c\n", {"k": "it's 'quoted'"}),
                ("k: a:b\n", {"k": "a:b"}),
                ("a:b: c\n", {"a:b": "c"}),
                ("k: http://x/#f\n", {"k": "http://x/#f"}),
                ("k: [a, b,]\n", {"k": ["a", "b"]}),
                ("k: [a:b, http://x]\n", {"k": ["a:b", "http://x"]}),
                ("k: [\"a\" , 'b'] # c\n", {"k": ["a", "b"]}),
                ("k: []  # none\n", {"k": []}),
                ("k: -3\n", {"k": -3}),
                ("k: 0\n", {"k": 0}),
                ("k: -x\n", {"k": "-x"}),
                # digits of another script are text to YAML, not a number
                ("k: \u0663\n", {"k": "\u0663"}),
                ("'it''s': x\n", {"it's": "x"}),
                ('"k" : 1  # c\n', {"k": 1}),
                ("k:  # c\n  m: 1\n", {"k": {"m": 1}}),
                ("l:\n  - |\n    one\n    two\n  - x\n",
                 {"l": ["one\ntwo", "x"]}),
                ("l:\n  - >-\n    one\n    two\n", {"l": ["one two"]}),
                ("l:\n  - # c\n    k: 1\n", {"l": [{"k": 1}]})):
            with self.subTest(text=text):
                self.assertEqual(glados.parse_yaml(text, "t"), expected)

    def test_what_the_subset_reads_a_yaml_reader_reads_too(self):
        """The property behind the cases above, checked against a YAML
        reader when one is installed (PyYAML; the suite needs none): what
        the parser accepts, YAML reads the same way. It may refuse more
        than YAML does, never read differently. The corpus crosses keys
        and values in every position, and adds every YAML file and
        frontmatter block the toolchain reads."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML is not installed")
        bs = "\\"
        keys = ["k", "max-cycles", '"k"', "'k'", f'"m{bs}x41x"',
                f'"{bs}u006b"', f'"k{bs}"', "&a k", "!!str k", "*a", "? k",
                "?k", "<<", '"<<"', "a:b", '"a: b"', "'it''s'", "-k", "[k]",
                "{k}", "|k", ">k", "%k", "@k", "`k", ",k", ":k", "k #c",
                '"k" x', "a b", "a'b", 'a"b', "- k", "k\t", "null", "~",
                "1", "07", "yes", "1.5", '"1"', "=", "k\x85"]
        values = [
            "v", "3", "-3", "0", "010", "08", "true", "false", "null", "~",
            "", '"v"', "'v'", f'"a{bs}" # b"', "don't # c", "a 'b' # c",
            "&a v", "*a", "!!int 3", "!x v", "|", "|-", ">", ">-", "|2",
            ">+", "|+", "[a, b]", "[a, b,]", "[]", "[ ]", "[&a x]", "[*a]",
            "[?x]", "[a?b]", "[a: b]", "[a:b]", "[a:]", '["a" , b]',
            "[a, , b]", "[,]", "[a, b] c", "[a, [b]]", "[a, b # c]",
            "[a b, 'c''d']", "a: b", "a:b", "a:", "http://x#f", "v # c",
            "v#c", '"v" w', '"abc', "'abc", "- x", "-", "? x", "?x", ":x",
            "%x", "@x", "`x", "]", "}", ",x", "{a: b}", "{}", f'"{bs}q"',
            f'"{bs}x4"', f'"{bs}uD800"', f'"{bs}U00110000"',
            f'"{bs}e{bs}N{bs}_{bs}L{bs}P{bs}/{bs} {bs}0{bs}a{bs}b{bs}v{bs}f"',
            f'"{bs}x41{bs}u00e9{bs}U0001F600{bs}t{bs}\t{bs}{bs}{bs}"x"',
            "'a''b'", "a #", "#c", "-x", "a\tb", '"a" # c', "'a' #c",
            "'a'#c", '"a"#c', "a\t# c", "''", '""', "a ' b", 'a " b',
            "\u0663", "-\u0663", "<<", "=", "[<<]", "k\x85",
        ]
        templates = ["{k}: {v}\n", "m:\n  {k}: {v}\n  z: 1\n",
                     "l:\n  - {k}: {v}\n    z: 1\n",
                     "{k}: {v}\n  one\n  two\nz: 1\n"]
        item_templates = ["l:\n  - {v}\n  - z\n", "l:\n- {v}\n",
                          "l:\n  - {v}\n    one\n  - z\n"]
        corpus = [t.format(k=k, v=v) for t in templates
                  for k in keys for v in values]
        corpus += [t.format(v=v) for t in item_templates for v in values]
        corpus += [read(p) for p in (
            EXAMPLE, REPO / "src" / "kernel" / "presets" / "phases.yaml",
            REPO / "src" / "kernel" / "state-registry.yaml",
            REPO / "src" / "kernel" / "aliases.yaml")]
        for md in sorted((REPO / "src").rglob("*.md")):
            lines = read(md).split("\n")
            if lines[0].strip() == "---" and "---" in lines[1:]:
                corpus.append("\n".join(lines[1:lines.index("---", 1)]))

        def norm(node):
            if isinstance(node, dict):
                return {k: norm(v) for k, v in node.items()}
            if isinstance(node, list):
                return [norm(v) for v in node]
            # the subset drops a block scalar's final newline by design
            return node.rstrip("\n") if isinstance(node, str) else node

        accepted, wrong = 0, []
        for text in corpus:
            try:
                mine = glados.parse_yaml(text, "t")
            except glados.YamlError:
                continue
            accepted += 1
            try:
                theirs = yaml.safe_load(text)
            except Exception as exc:  # PyYAML raises ValueError for some
                # ill-formed escapes, not only YAMLError
                wrong.append(f"{text!r}: read {mine!r}, YAML refuses it "
                             f"({str(exc).splitlines()[0]})")
                continue
            if norm(mine) != norm({} if theirs is None else theirs):
                wrong.append(f"{text!r}: read {mine!r}, YAML reads "
                             f"{theirs!r}")
        self.assertGreater(accepted, 500)
        if wrong:
            self.fail(f"{len(wrong)} of {accepted} accepted documents "
                      f"misread:\n" + "\n".join(wrong[:40]))


class TestYamlListOfMaps(unittest.TestCase):
    """`- key: value` opens a mapping item, as in standard YAML (F6a). It
    used to parse as the string 'key: value', silently."""

    def parse(self, text):
        return glados.parse_yaml(text, "t")

    def test_single_key_item(self):
        self.assertEqual(self.parse("items:\n  - name: a\n  - name: b\n"),
                         {"items": [{"name": "a"}, {"name": "b"}]})

    def test_multi_key_item(self):
        parsed = self.parse("items:\n  - name: a\n    kind: gate  # note\n"
                            "    count: 3\n  - name: b\n")
        self.assertEqual(parsed["items"],
                         [{"name": "a", "kind": "gate", "count": 3},
                          {"name": "b"}])

    def test_nested_blocks_under_an_item_key(self):
        parsed = self.parse(
            "- id: shape\n"
            "  audits:\n"
            "    - plan\n"
            "    - spec\n"
            "  options:\n"
            "    review: in-context\n"
            "    nested:\n"
            "      - deep: 1\n"
            "        deeper: [x, y]\n"
            "  note: |\n"
            "    line one\n"
            "    line two\n"
            "- id: open-mr\n")
        self.assertEqual(parsed, [
            {"id": "shape", "audits": ["plan", "spec"],
             "options": {"review": "in-context",
                         "nested": [{"deep": 1, "deeper": ["x", "y"]}]},
             "note": "line one\nline two"},
            {"id": "open-mr"},
        ])

    def test_quoted_and_colon_strings_unchanged(self):
        parsed = self.parse('items:\n  - "a: b"\n  - \'c: d\'\n'
                            "  - http://host/x\n  - plain\n  - [p, q]\n")
        self.assertEqual(parsed["items"],
                         ["a: b", "c: d", "http://host/x", "plain", ["p", "q"]])

    def test_bare_dash_map_still_works(self):
        parsed = self.parse("items:\n  -\n    name: a\n    kind: gate\n"
                            "  - name: b\n")
        self.assertEqual(parsed["items"],
                         [{"name": "a", "kind": "gate"}, {"name": "b"}])

    def test_misaligned_item_key_is_an_error(self):
        with self.assertRaises(glados.YamlError) as ctx:
            self.parse("items:\n  - name: a\n     kind: gate\n")
        self.assertIn("t:3", str(ctx.exception))
        with self.assertRaises(glados.YamlError) as ctx:
            self.parse("- name: a\n  name: b\n")
        self.assertIn("duplicate key 'name'", str(ctx.exception))

    def test_shipped_yaml_parses_the_same_shape(self):
        # Every shipped YAML file still parses, and nothing in them was a
        # `- key: value` string the new rule would turn into a map.
        def no_maps_in_lists(node):
            if isinstance(node, dict):
                return all(no_maps_in_lists(v) for v in node.values())
            if isinstance(node, list):
                return all(not isinstance(v, dict) and no_maps_in_lists(v)
                           for v in node)
            return True
        for path in (EXAMPLE, REPO / "src" / "kernel" / "presets" / "phases.yaml",
                     REPO / "src" / "kernel" / "state-registry.yaml",
                     REPO / "src" / "kernel" / "aliases.yaml"):
            with self.subTest(path=path.name):
                self.assertTrue(no_maps_in_lists(
                    glados.parse_yaml(read(path), path.name)))


class TestManifestTokenAttacks(unittest.TestCase):
    """Typo'd manifest tokens must fail the install, not silently drop
    modules/workflows/sinks — the v1 flagship bug class."""

    def test_unknown_module_in_manifest_fails(self):
        # a) per-workflow list on a core with NO requires (nothing else catches it)
        text = read(EXAMPLE).replace(
            "workflows:\n", "workflows:\n  intent:         [standards-gatee]\n")
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "module typo must fail:\n" + out)
        self.assertIn("standards-gatee", out)
        self.assertIn("intent", out)
        # b) default-modules typo drops the module from EVERY workflow
        text = read(EXAMPLE).replace("default-modules: [standards-gate]",
                                     "default-modules: [standard-gate]")
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "default-modules typo must fail:\n" + out)
        self.assertIn("standard-gate", out)
        # c) unknown workflow name in workflows:
        text = read(EXAMPLE).replace(
            "workflows:\n", "workflows:\n  reviw-mr:       [mr-review-panel]\n")
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "workflow-name typo must fail:\n" + out)
        self.assertIn("reviw-mr", out)
        # d) unknown workflow in disabled-workflows leaves it enabled
        text = read(EXAMPLE).replace("disabled-workflows: []",
                                     "disabled-workflows: [run-epicc]")
        self.assertIn("run-epicc", text, "example must carry the key to edit")
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "disabled-workflows typo must fail:\n" + out)
        self.assertIn("run-epicc", out)

    def test_unknown_channel_type_or_sink_fails(self):
        # a) typo'd outcome type key
        text = read(EXAMPLE).replace("  observation: [ledger]",
                                     "  observaton: [ledger]")
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "channels outcome-type typo must fail:\n" + out)
        self.assertIn("observaton", out)
        # b) typo'd sink on a ledger-ok type (previously invisible)
        text = read(EXAMPLE).replace("  progress:    [ledger]",
                                     "  progress:    [legder]")
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "channels sink typo must fail:\n" + out)
        self.assertIn("legder", out)

    def test_declared_custom_sink_passes(self):
        # A team-declared sink that states its visibility, bound alongside a
        # built-in, installs cleanly.
        text = read(EXAMPLE).replace(
            "  verdict:     [mr-comment]", "  verdict:     [mr-comment, slack]")
        text += ('\nsinks:\n  slack:\n    team-visible: true\n'
                 '    channel: "#code-reviews"\n    format: terse\n')
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 0, "declared custom sink must install:\n" + out)

    def test_declared_sink_without_team_visible_fails(self):
        # The dangerous direction: a declared sink that says nothing about
        # visibility used to satisfy the team-visibility invariant by default,
        # so an outcome no human sees passed the check meant to prevent it.
        text = read(EXAMPLE).replace(
            "  verdict:     [mr-comment]", "  verdict:     [mr-comment, slack]")
        text += '\nsinks:\n  slack:\n    channel: "#code-reviews"\n'
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "sink without team-visible must fail:\n" + out)
        self.assertIn("slack", out)
        self.assertIn("team-visible", out)

    def test_undeclared_sink_in_channels_fails(self):
        # Binding a sink that is neither built-in nor declared is a typo/hole.
        text = read(EXAMPLE).replace(
            "  verdict:     [mr-comment]", "  verdict:     [mr-comment, slack]")
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "undeclared sink must fail:\n" + out)
        self.assertIn("slack", out)
        self.assertIn("not declared", out)

    def test_custom_team_visible_sink_satisfies_visibility(self):
        # A sink that declares itself team-visible alone satisfies a
        # non-ledger-ok outcome's visibility requirement.
        text = read(EXAMPLE).replace(
            "  verdict:     [mr-comment]", "  verdict:     [slack]")
        text += ('\nsinks:\n  slack:\n    team-visible: true\n'
                 '    channel: "#code-reviews"\n')
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 0, "team-visible custom sink must satisfy:\n" + out)

    def test_unstated_visibility_never_satisfies_visibility(self):
        # And the same binding with the key omitted must not slip through on a
        # default — it fails, and it fails naming the visibility hole, not just
        # the missing key.
        text = read(EXAMPLE).replace(
            "  verdict:     [mr-comment]", "  verdict:     [slack]")
        text += '\nsinks:\n  slack:\n    channel: "#code-reviews"\n'
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "unstated visibility must not satisfy:\n" + out)
        self.assertIn("team-visible", out)
        self.assertIn("no team-visible sink", out)

    def test_record_only_sink_alone_fails_visibility(self):
        # team-visible: false opts a sink out; alone on verdict it must fail the
        # same team-visibility check the built-in ledger fails.
        text = read(EXAMPLE).replace(
            "  verdict:     [mr-comment]", "  verdict:     [audit-log]")
        text += '\nsinks:\n  audit-log:\n    team-visible: false\n'
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "record-only sink alone must fail:\n" + out)
        self.assertIn("team-visible", out)

    def test_malformed_sink_body_fails_cleanly(self):
        # A scalar where a sink config belongs must be a clean install error,
        # never a stack trace from the visibility helpers.
        text = read(EXAMPLE).replace(
            "  verdict:     [mr-comment]", "  verdict:     [mr-comment, slack]")
        text += '\nsinks:\n  slack: "#code-reviews"\n'
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "malformed sink body must fail:\n" + out)
        self.assertIn("slack", out)
        self.assertNotIn("Traceback", out)

    # `- name: value` is a mapping item in YAML. In a list that holds names it
    # must be a named error, never an unhashable-dict traceback (and never a
    # hard exit from `check --report-only`).
    MAPPING_ITEM_EDITS = [
        ("disabled-workflows: []", "disabled-workflows:\n  - brunch: x",
         "disabled-workflows: item 1 is a mapping ('brunch: x')"),
        ("default-modules: [standards-gate]",
         "default-modules:\n  - standards-gate: x",
         "default-modules: item 1 is a mapping ('standards-gate: x')"),
        ("  brunch:         [mr-review-panel]",
         "  brunch:\n    - mr-review-panel: x",
         "workflows.brunch: item 1 is a mapping ('mr-review-panel: x')"),
        ("  bug:         [issue]", "  bug:\n    - issue: x",
         "channels.bug: item 1 is a mapping ('issue: x')"),
        ("relaxation-acknowledged: [delete-code]",
         "relaxation-acknowledged:\n  - delete-code: yes",
         "relaxation-acknowledged: item 1 is a mapping ('delete-code: yes')"),
    ]

    def test_mapping_item_in_a_name_list_is_a_named_error(self):
        for old, new, msg in self.MAPPING_ITEM_EDITS:
            with self.subTest(key=msg.split(":")[0]):
                text = read(EXAMPLE)
                self.assertIn(old, text, "doctoring failed")
                rc, out = install("direct",
                                  make_target(text.replace(old, new, 1)))
                self.assertEqual(rc, 1, out)
                self.assertIn(msg, out)
                self.assertIn("'- name: value' is a mapping in YAML", out)
                self.assertNotIn("Traceback", out)

    def test_mapping_item_never_crashes_check_or_doctor(self):
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        original = read(t / "glados.yaml")
        for old, new, msg in self.MAPPING_ITEM_EDITS:
            with self.subTest(key=msg.split(":")[0]):
                write(t / "glados.yaml", original.replace(old, new, 1))
                rc, out = run_cli("check", "--target", t, "--source", REPO,
                                  "--report-only")
                self.assertEqual(rc, 0, "--report-only must not hard-exit:\n"
                                 + out)
                self.assertIn(msg, out)
                self.assertNotIn("Traceback", out)
                rc, out = run_cli("check", "--target", t, "--source", REPO)
                self.assertEqual(rc, 1, out)
                self.assertNotIn("Traceback", out)
                rc, out = run_cli("doctor", "--target", t, "--source", REPO)
                self.assertEqual(rc, 0, "doctor must never fail:\n" + out)
                self.assertNotIn("Traceback", out)

    def test_wrong_shapes_are_named_errors(self):
        # a list where a mapping belongs, and a scalar where a list belongs
        workflows = ("workflows:\n"
                     "  review-mr:      [mr-review-panel]\n"
                     "  verify-feature: [evaluator-spawn]\n"
                     "  fix-bug:        [evaluator-spawn, standards-gate]\n"
                     "  run-epic:       [mr-review-panel, standards-gate]\n"
                     "  brunch:         [mr-review-panel]\n")
        listed = ("workflows:\n"
                  "  - review-mr: [mr-review-panel]\n"
                  "  - brunch: [mr-review-panel]\n")
        cases = [
            (workflows, listed, "'workflows:' must be a mapping"),
            ("disabled-workflows: []", "disabled-workflows: true",
             "disabled-workflows: must be a list of workflow names"),
            ("params:\n", "params: 3\nunused:\n",
             "'params:' must be a mapping"),
        ]
        for old, new, msg in cases:
            with self.subTest(msg=msg):
                text = read(EXAMPLE)
                self.assertIn(old, text, "doctoring failed")
                rc, out = install("direct",
                                  make_target(text.replace(old, new, 1)))
                self.assertEqual(rc, 1, out)
                self.assertIn(msg, out)
                self.assertNotIn("Traceback", out)

    def test_alias_shadowing_core_fails(self):
        src = make_doctored_source()
        aliases = src / "src" / "kernel" / "aliases.yaml"
        aliases.write_text(read(aliases) + "  intent: run-epic\n",
                           encoding="utf-8", newline="\n")
        t = make_target()
        rc, out = install("claude", t, source=src)
        self.assertEqual(rc, 1, "core-shadowing alias must fail:\n" + out)
        self.assertIn("shadows", out)
        self.assertIn("intent", out)


class TestManifestKeysAndDecisions(unittest.TestCase):
    """Unknown top-level keys warn without failing (F6b); a decision value
    outside the four classes is fatal and names the leaf (F6c)."""

    def test_unknown_top_level_key_warns_but_installs(self):
        text = read(EXAMPLE) + "\nchanels:\n  bug: [issue]\n"
        t = make_target(text)
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, "an unknown key must not fail install:\n" + out)
        self.assertIn("unknown top-level key 'chanels'", out)
        self.assertIn("known keys:", out)
        self.assertIn("channels", out.split("unknown top-level key 'chanels'")[1])
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, "an unknown key must not fail check:\n" + out)
        self.assertEqual(out.count("unknown top-level key 'chanels'"), 1, out)
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("manifest keys: unknown top-level key(s) chanels", out)

    def test_unknown_key_is_reported_when_the_install_fails(self):
        # The misspelt key is the cause of the failure: 'sinsk:' leaves the
        # slack sink undeclared. The warning must not vanish with the run.
        bad = (read(EXAMPLE).replace("  escalation:  [issue]",
                                     "  escalation:  [issue, slack]")
               + "\nsinsk:\n  slack:\n    team-visible: true\n")
        rc, out = install("direct", make_target(bad))
        self.assertEqual(rc, 1, out)
        self.assertIn("unknown top-level key 'sinsk'", out)
        self.assertIn("sink 'slack' is not declared", out)
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        write(t / "glados.yaml", bad)
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("unknown top-level key 'sinsk'", out)
        self.assertIn("sink 'slack' is not declared", out)

    def test_known_keys_cover_the_example_and_stay_quiet(self):
        raw = glados.load_manifest(EXAMPLE)
        self.assertEqual(glados.unknown_manifest_keys(raw), [])
        for key in ("pipelines", "steps", "canon", "lifecycle", "concurrency",
                    "phase-declared"):
            self.assertIn(key, glados.KNOWN_MANIFEST_KEYS)
        t = make_target()
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("unknown top-level key", out)
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertIn("manifest keys: all known", out)

    def test_a_decision_right_in_any_key_spelling_meets_the_floor(self):
        """In production, `"schema\\x2Dmigration": agent` and
        `&d schema-migration: agent` are schema-migration: agent to a YAML
        reader, but the parser kept them as other leaves, so the relaxation
        check never fired and validate passed with no warning at all."""
        bs = "\\"
        head = "glados: 2\nplatform: github\nphase: production\ndecisions:\n"

        def validate(body):
            rc, out = run_cli("validate", "--target",
                              make_target(head + body), "--source", REPO)
            self.assertNotIn("Traceback", out)
            return rc, out

        laxer = ("decision 'schema-migration: agent' is laxer than phase "
                 "'production'")
        for body in ("  schema-migration: agent\n",
                     f'  "schema{bs}x2Dmigration": agent\n',
                     f'  "schema{bs}u002Dmigration": agent\n'):
            with self.subTest(body=body):
                rc, out = validate(body)
                self.assertEqual(rc, 1, out)
                self.assertIn(laxer, out)
        for body, needle in (
                ("  &d schema-migration: agent\n",
                 "glados.yaml:5: '&d schema-migration' starts with '&'"),
                ("  schema-migration: !!str agent\n",
                 "glados.yaml:5: '!!str agent' starts with '!'"),
                ("  schema-migration: *d\n",
                 "glados.yaml:5: '*d' starts with '*'")):
            with self.subTest(body=body):
                rc, out = validate(body)
                self.assertEqual(rc, 1, out)
                self.assertIn(needle, out)

    def test_bad_decision_value_is_fatal_and_names_the_leaf(self):
        text = read(EXAMPLE).replace("  new-dependency: agent",
                                     "  new-dependency: agnet")
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, "a misspelt decision class must fail:\n" + out)
        self.assertIn("decisions.new-dependency: 'agnet' is not a decision class",
                      out)
        self.assertIn("agent | record | escalate | forbidden", out)
        self.assertNotIn("Traceback", out)

    def test_decision_leaf_names_stay_open(self):
        text = read(EXAMPLE).replace("  new-dependency: agent",
                                     "  new-dependency: agent\n"
                                     "  vendor-swap: escalate")
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 0, "a project-named decision leaf must install:\n"
                         + out)

    def test_non_mapping_decisions_fails_cleanly(self):
        text = read(EXAMPLE).replace(
            "decisions:\n  schema-migration: record\n",
            "decisions:\n  - schema-migration\n  - delete-code\n"
            "unused:\n  schema-migration: record\n")
        rc, out = install("direct", make_target(text))
        self.assertEqual(rc, 1, out)
        self.assertIn("'decisions:' must be a mapping", out)
        self.assertNotIn("Traceback", out)


class TestRootCauseSynthesis(unittest.TestCase):

    def test_synthesis_step_compiled_into_review_mr(self):
        # The postamble is mandatory and unconditional: it must land in the
        # compiled review-mr text, with both checks and the panel's root-cause
        # field, on a stock manifest.
        t = make_target(read(EXAMPLE))
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        core = read(t / "product-knowledge" / "glados" / "review-mr.md")
        self.assertIn("Root-cause synthesis (mandatory)", core)
        self.assertIn("Did the change attack the underlying cause?", core)
        self.assertIn("Does the finding set converge on one cause?", core)
        self.assertIn("root-cause", core)

    def test_synthesis_runs_before_the_decide_step(self):
        # Ordering is the whole point: synthesize, then decide. A compile that
        # puts the decision first has lost the postamble.
        t = make_target(read(EXAMPLE))
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        core = read(t / "product-knowledge" / "glados" / "review-mr.md")
        self.assertLess(core.index("Root-cause synthesis (mandatory)"),
                        core.index("### 8. Decide"))

    def test_address_review_consumes_the_synthesis(self):
        # The synthesis must not land inert: the fix half is told to treat a
        # consolidated cluster as one design change.
        t = make_target(read(EXAMPLE))
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        core = read(t / "product-knowledge" / "glados" / "address-review.md")
        self.assertIn("root-cause synthesis", core)

    def test_the_pre_existing_rule_reaches_every_core_that_seats_a_panel(self):
        """The scope rule is worthless in a core that does not carry it.

        What it fixes is fifteen advisories about untouched code burying the
        three findings the author can act on. Whether the pooling actually
        FIRES is a property of a review, not of a compile, and only a real
        review over a touched file with known pre-existing breaches can show
        it. What a compile can prove is the half that silently rots: that
        every core seating a panel carries the rule, and that no core tells a
        reviewer to do the opposite.
        """
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        glados_dir = t / "product-knowledge" / "glados"
        seats_a_panel = [
            p for p in glados_dir.glob("*.md")
            if "adversarial MR review panel" in read(p)
        ]
        self.assertGreater(len(seats_a_panel), 0, "no core seats a panel")
        for core in seats_a_panel:
            body = " ".join(read(core).split())
            self.assertIn(
                "A finding is about code the change introduced", body,
                f"{core.name} seats a panel without the scope rule")
            self.assertIn(
                "worth **one line** pointing at", body,
                f"{core.name}: no pooling instruction")
            self.assertIn(
                "a breach the change makes worse", body,
                f"{core.name}: the scope rule without its exception is a rule "
                "that hides a real finding")

    def test_no_core_asks_for_a_finding_per_pre_existing_breach(self):
        """The rule and its opposite must not both be in the compiled text.

        Two instructions in conflict resolve unpredictably, which is why an
        advisory CAP was declined in favour of shortening at the tally. The
        same hazard applies to the rule itself: every mention of a finding
        per instance must be the prohibition, never a request.
        """
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        phrase = "one finding per instance"
        for core in (t / "product-knowledge" / "glados").glob("*.md"):
            flat = " ".join(read(core).split())
            mentions = flat.count(phrase)
            prohibited = flat.count("never " + phrase)
            self.assertEqual(
                mentions, prohibited,
                f"{core.name} mentions '{phrase}' {mentions} time(s) but "
                f"prohibits it {prohibited} — an instruction to list them "
                "one by one is the failure the rule exists to stop")

    def test_the_reader_rule_states_the_fact_not_the_remedy(self):
        """A review can say nothing reads a field. It cannot say nothing should.

        The rule exists because carrying a dropped value costs a field, a
        shape, a caller and a test, and the cheap answer is usually that
        nobody wanted it. But a reader someone is about to write is invisible
        to a review, so the rule is stated as the fact and never as a demand —
        without that clause it becomes an instruction to delete work whose
        reader is one ticket away.
        """
        body = " ".join(read(REPO / "src" / "vocabulary" / "verdicts.md").split())
        self.assertIn("name the line that reads, calls or handles it", body)
        self.assertIn("It cannot establish that nothing *should*", body)
        self.assertIn("stated as the fact and never as a demand", body)

    def test_the_claim_survives_without_its_evidence(self):
        """Folding proof is only safe if the ask is never folded with it.

        "Never drop a finding" and "fits on one screen" pull against each
        other, and the way that fight resolves in practice is a comment
        nobody finishes — which drops every finding at once. Splitting claim
        from evidence dissolves it, but only while the claim stands alone:
        a fold that swallows the ask hides the one thing the author owes.
        """
        body = " ".join(read(REPO / "src" / "vocabulary" / "verdicts.md").split())
        self.assertIn("A finding is a claim and its evidence", body)
        self.assertIn("Only the claim is owed *on the first screen*", body)
        self.assertIn(
            "a reader who expands nothing still learns every blocking thing",
            body,
        )
        # The rule must not read as licence to say less.
        self.assertIn("may never drop a finding", body)

    def test_every_panel_core_carries_the_claim_evidence_split(self):
        """A rendering rule kept in one project's config fixes one project.

        The split has to reach every compiled core that publishes a verdict,
        or each project rediscovers the novel-length comment on its own.
        """
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        glados_dir = t / "product-knowledge" / "glados"
        seats_a_panel = [
            p for p in glados_dir.glob("*.md")
            if "adversarial MR review panel" in read(p)
        ]
        self.assertGreater(len(seats_a_panel), 0, "no core seats a panel")
        for core in seats_a_panel:
            body = " ".join(read(core).split())
            self.assertIn(
                "A finding is a claim and its evidence",
                body,
                f"{core.name} publishes verdicts without the claim/evidence split",
            )

    def test_the_brief_asks_for_jobs_and_a_comparison(self):
        """A green rollup is a claim about the jobs it chose to count.

        A job marked to allow failure reports nothing upward, so it is where
        a defect goes to be invisible — and the ones teams mark that way are
        the slow gates that catch what the fast ones miss. Asking for the job
        list is half of it; the other half is that a red job proves nothing
        on its own, because plenty are red everywhere. Only the comparison
        against another merge request separates the change's fault from the
        repository's, so the rule is worthless if the brief asks for the
        first and not the second.
        """
        body = " ".join(read(REPO / "src" / "workflows" / "review-mr.md").split())
        self.assertIn("Read the pipeline's JOBS, not its status", body)
        self.assertIn("allow failure is not counted", body)
        self.assertIn("run the same job's status on another open merge request", body)
        # The comparison has to name BOTH outcomes, or it reads as "red is
        # always yours" and puts the repository's breakage on this author.
        self.assertIn("Red there too", body)
        self.assertIn("green there and red here is this change's", body.lower())

    def test_the_dedup_rule_names_the_pairs_and_keeps_every_finding(self):
        """Shortening by repetition, not by omission.

        The claim/evidence split moves proof out of the way and leaves the
        surface free to say the same point twice, which is where the length
        actually came from: a summary bullet and the finding's opening
        sentence are one fact told twice. Naming the pairs is what makes the
        rule usable — "do not repeat yourself" is advice nobody can act
        on while reading their own draft.

        The second assertion is the guard: a rule about saying less is one
        word away from a rule about telling the author less, and this one has
        to end with the count, not with a finding.
        """
        body = " ".join(read(REPO / "src" / "vocabulary" / "verdicts.md").split())
        self.assertIn("Say each thing once", body)
        # The pairs, named. Without them this is a platitude.
        self.assertIn("summary bullet and the finding's opening sentence", body)
        self.assertIn("ONLY place those asks are written", body)
        # And it may never become a reason to publish less than was found.
        self.assertIn("cutting it removes no finding", body)

    def test_an_advisory_has_to_name_a_consequence_without_becoming_a_gag(self):
        """The tiers rank findings; nothing ranked whether one was worth writing.

        So `advisory` filled with items whose only effect was that the code
        would read differently, and the list they were buried in is what
        teaches an author to skim. Tightening what QUALIFIES as a finding is
        legitimate where capping the list was not: a preference is not a
        finding being dropped, it never was one.

        Which is exactly why the escapes are asserted too. A rule that lets a
        reviewer decide something has no consequence is one rationalisation
        away from silence, so the uncertain case must stay, and naming and
        boundary findings must not read as exempted.
        """
        body = " ".join(read(REPO / "src" / "vocabulary" / "verdicts.md").split())
        self.assertIn("earns its line by naming a consequence", body)
        # The three, named. A test the reviewer applies from memory is no test.
        self.assertIn("behaviour", body)
        self.assertIn("whether a defect would be caught", body)
        self.assertIn("what someone has to work with when it fails", body)
        # The escapes, both of them.
        self.assertIn("Where you cannot tell whether a consequence exists, it stays", body)
        self.assertIn("does not exempt naming, interfaces or structure", body)
        self.assertIn("never which category the finding falls into", body)
        # And the pricing half, which is what keeps a one-clause ask from
        # buying a restructure.
        self.assertIn("price what you ask for", body)
        self.assertIn("say that instead of implying it is cheap", body)

    def test_the_consequence_test_reaches_the_panelists_themselves(self):
        """A rule only the tally reads arrives after the list is already written.

        The cost of a preference is paid when a lens writes it down and the
        author reads past it, so the standing orders have to carry it too.
        """
        body = " ".join(read(REPO / "src" / "modules" / "mr-review-panel.md").split())
        self.assertIn("name what acting on it would change", body)
        self.assertIn("it is a preference, not a finding", body)
        self.assertIn("say you have not looked rather than implying it is cheap", body)

    def test_a_fragment_is_inlined_once_per_document(self):
        """A core IS a panelist's whole brief, so a second copy is dead weight.

        The shared vocabulary reaches review-mr by two routes — the workflow
        includes it for the tally and the panel module includes it for the
        panelists — and nothing deduplicated them, so it landed twice. That
        was tolerable while the fragment was short and stopped being so when
        it grew: the compiled core went from 513 lines to 886, roughly 200 of
        which were the same page twice, in the one document whose reader is
        most expensive to lose.

        Asserted per core rather than in aggregate, and paired with the
        must-still-appear check, because a deduplicator that drops the last
        copy as well is the failure this would otherwise hide.
        """
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        glados_dir = t / "product-knowledge" / "glados"
        marker = "There is exactly one severity scale and one verdict vocabulary"

        seats_a_panel = [
            p for p in glados_dir.glob("*.md")
            if "adversarial MR review panel" in read(p)
        ]
        self.assertGreater(len(seats_a_panel), 0, "no core seats a panel")

        for core in glados_dir.glob("*.md"):
            body = read(core)
            self.assertLessEqual(
                body.count(marker), 1,
                f"{core.name} inlines the verdict vocabulary "
                f"{body.count(marker)} times")

        for core in seats_a_panel:
            self.assertIn(
                marker, read(core),
                f"{core.name} seats a panel with no severity scale at all")

    def _compiled_direct(self):
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        return t / "product-knowledge" / "glados"

    def test_a_suppressed_fragment_leaves_a_pointer_naming_it(self):
        """A de-duplicated include must leave its lead-in a referent.

        2.3.1 replaced the second copy of a fragment with nothing. The text
        around an include was written to introduce it, so the evaluator brief
        in verify-feature went on telling its reader to copy "the rules below,
        verbatim" over a blank line and the next heading, and a colon
        introducing the retry bound introduced nothing. `glados check` could
        not see it: it recompiles with the same compiler. Asserted on the
        core where it actually broke.
        """
        core = read(self._compiled_direct() / "verify-feature.md")
        for heading in ("Verdicts and finding severities", "Loop bounds"):
            self.assertIn(
                f"*(See **{heading}**, earlier in this document.)*", core,
                f"verify-feature suppressed {heading!r} without a pointer")

    def test_no_lead_in_points_at_an_include_by_position(self):
        """A fragment may be inlined here or earlier; only its NAME is stable.

        Whether an include's own copy survives depends on what else the
        document includes, which the author of a module cannot know. A
        lead-in that says "below" is right in one core and false in the
        next. Scanning the three lines above every include keeps the one
        pattern that broke from being written again.
        """
        positional = ("below", "beneath", "following")
        offenders = []
        for path in sorted((REPO / "src").rglob("*.md")):
            lines = read(path).splitlines()
            for n, line in enumerate(lines):
                if "glados:include" not in line:
                    continue
                for back in lines[max(0, n - 3):n]:
                    if any(w in back.lower() for w in positional):
                        offenders.append(f"{path.relative_to(REPO)}:{n + 1}: {back.strip()}")
        self.assertEqual(offenders, [], "lead-ins that point by position:\n" + "\n".join(offenders))

    def test_every_verdict_producing_core_carries_the_default_shape(self):
        """A repo with no sink config still gets a shape, and it is this one.

        The comment shape lived only in one project's `glados.yaml`, so every
        repository without one composed its review comments from nothing but
        "interpret the sink's keys sensibly". Every core that composes a
        verdict — through a panel or an evaluator — now carries it.
        Identified from the provenance header, not a hand-kept list, so a new
        verdict-producing core is covered without editing this test.
        """
        glados_dir = self._compiled_direct()
        producers = []
        for core in sorted(glados_dir.glob("*.md")):
            body = read(core)
            header = next((l for l in body.splitlines() if "modules-inlined:" in l), "")
            if "mr-review-panel" in header or "evaluator-spawn" in header:
                producers.append(core.name)
                self.assertIn("## Publishing a verdict", body,
                              f"{core.name} composes a verdict with no default shape")
        self.assertGreater(len(producers), 0, "no core composes a verdict")

    def test_the_default_shape_governs_wording_and_never_classifies(self):
        """The render step may not decide what is a finding.

        Twice in one merge request a sink rule classified an item out of
        findinghood and then told the renderer to say nothing about it; each
        time the same file said, a screen later, that no rule there may omit a
        finding. The two cannot both hold. Truth is settled upstream, where
        the reasoning can be recorded, so the shape says so and carries none
        of the phrasings that did the classifying.
        """
        body = " ".join(read(REPO / "src" / "vocabulary" / "comment-shape.md").split())
        self.assertIn("Everything here governs wording and order, never content", body)
        for phrase in ("is not a finding", "does not go on the comment",
                       "say nothing about", "one line or nothing",
                       "preference rather than a finding"):
            self.assertNotIn(phrase, body, f"the shape classifies: {phrase!r}")

    def test_the_default_shape_renders_any_number_of_blocking_findings(self):
        """A cap, "the only place asks are written" and "never fold an ask"
        had no legal rendering together past four unconsolidated blockers.
        Every blocking finding gets its line; length is a cue to consolidate.
        """
        body = " ".join(read(REPO / "src" / "vocabulary" / "comment-shape.md").split())
        self.assertIn("Every blocking finding gets its line", body)
        self.assertIn("never a reason to leave one out", body)
        for cap in ("at most four", "four bullets", "at most 4"):
            self.assertNotIn(cap, body)

    def test_the_default_shape_names_the_vocabulary_instead_of_restating_it(self):
        """A second copy agrees with the first only until one of them changes.

        A project's sink is read live and survives an upgrade that rewrites
        the vendored vocabulary, so a rule restated there goes on stating the
        superseded version. The shape points at *Verdicts and finding
        severities* for the two rules it depends on and repeats neither.
        """
        shape = " ".join(read(REPO / "src" / "vocabulary" / "comment-shape.md").split())
        verdicts = " ".join(read(REPO / "src" / "vocabulary" / "verdicts.md").split())
        self.assertIn("*Verdicts and finding severities* asks that each thing be said once", shape)
        for sentence in ("A finding states a problem; a reader turns it into work",
                         "The claim/evidence split makes a review shorter"):
            self.assertIn(sentence, verdicts, "premise: the rule lives in the vocabulary")
            self.assertNotIn(sentence, shape, "the shape restates the vocabulary")

    def test_a_fold_is_cheap_not_free(self):
        """The team reads reviews through `glab`, which renders the tags.

        A budget that calls folded evidence free is false in the renderer the
        comments are actually read in; there the proof is last, not hidden.
        """
        body = " ".join(read(REPO / "src" / "vocabulary" / "comment-shape.md").split())
        self.assertIn("A fold is cheap, not free", body)
        self.assertIn("render the tags literally", body)

    def test_the_evaluator_brief_carries_the_declared_deferral_rule(self):
        """On the evaluator path the sink was the rule's only home.

        verify-feature and fix-bug reach a verdict through evaluator-spawn,
        whose brief carries the vocabulary but not the root-cause synthesis.
        Moving the deferral rule out of the render sink would have left that
        path without it, so it moves into the brief instead — upstream of
        the verdict, where classifying is allowed.
        """
        body = " ".join(read(REPO / "src" / "modules" / "evaluator-spawn.md").split())
        self.assertIn("What is deliberately out of scope", body)
        self.assertIn("each labelled with who deferred it", body)
        self.assertIn("A deferral excuses an absence", body)
        self.assertNotIn("a decision already made", body)

    def test_synthesis_introduces_no_new_verdict_vocabulary(self):
        # One severity scale, one verdict vocabulary - the synthesis reuses
        # them rather than inventing a third tier or a fourth verdict word.
        body = read(REPO / "src" / "vocabulary" / "root-cause.md")
        for invented in ("CONVERGED", "ROOT_CAUSE", "SYMPTOM", "structural`"):
            self.assertNotIn(invented, body)
        self.assertIn("`blocking`", body)
        self.assertIn("`advisory`", body)


class TestReviewInputs(unittest.TestCase):
    """What a fresh reviewer is told to treat as settled.

    A fresh agent is independent of the author's context, but the author
    writes its brief, and core text told it to settle what the author wrote:
    the MR description's scope, a contract file copied from the author's own
    spec, a criterion that named the author's mechanism. A project pipeline
    cannot reach that text, so each rule is pinned into the compiled cores it
    governs: review-mr, verify-feature, run-pipeline and implement-feature
    (and plan-feature, which writes the criteria). Asserted with whitespace
    flattened, so a re-wrap of the source does not break a test.
    """

    FRAGMENT = (
        "## What a fresh reviewer is given",
        "So a brief carries inputs, never the author's conclusions about them",
        "A brief carries what the workflow that writes it lists for it and "
        "nothing else",
        "no verdict, approval or gate result from an earlier pass",
        "no disposition the author gave a finding",
        "no instruction about what is or is not a defect",
        "A finding still open from an earlier pass may be named, as open",
        "The author is whoever wrote the change, agent or person",
        "is labelled as the author's, and is under review like the code",
        "A person's words, meaning anyone's but the author's",
        "are quoted verbatim with where they were said (a file path or an MR "
        "note) and labelled as theirs, untagged.",
        # words bind as firmly as they were said: one commitment tag per
        # clause, read from its own words, so a hedge never softens a whole
        # quote and a firm clause in an answer keeps its force (v3.1)
        "**A person set only what their quoted words name, as firmly as "
        "they said it.** Each clause takes the tag its words give until the "
        "person corrects it:",
        "*Directive* (\"must\", \"need\", \"never\", \"always\", or a "
        "plain statement of what is wanted) binds.",
        # a hedged want is a Preference, never a Hunch: code cannot test a
        # want (v3.1)
        "*Preference* (\"should\", \"I'd like\", \"prefer\", or a hedged "
        "want: \"I think we need\") sets a default that evidence may "
        "override.",
        # a Hunch is a belief the code can test, and stands until it is
        # contradicted (v3.1); an unhedged claim is one too, so a ticket's
        # statement of what the code does gets tested rather than obeyed,
        # and a problem the ticket or brief states still asks for its own
        # absence (v3.2); a reviewer's stated problem does not, or every
        # advisory a person wrote as a problem would bind (fix round 1)
        "*Hunch* (\"I think\", \"maybe\", \"probably\", \"I wonder\", "
        "or an unhedged claim, such as a stated problem) is a belief about "
        "what is true (a cause, what code does), which the artifact tests "
        "against the code, reporting what it finds; it stands unless "
        "contradicted. A ticket's or brief's stated problem also asks for "
        "its absence, as a Directive.",
        # a go-ahead approves only what was shown; an answer binds the
        # outcome its reading describes, never the option's wording, and
        # only named evidence the person never saw reopens it (v3, v3.1)
        # an option's words are its writer's, so choosing one is Assent
        # even when they read as an order (v3.2)
        "*Assent* (\"seems fine\", \"yes\", \"go with that\", choosing a "
        "question's reading, however worded) approves only the direction of "
        "what they were shown, which stays its writer's: a chosen reading's outcome, not "
        "its mechanism, scope words or phrasing. Material evidence they "
        "were not shown reopens it as a question naming that evidence.",
        # evidence against words is stated in one form, from outside the
        # change, never blocking, and has a channel where the workflow takes
        # no questions (v3.1)
        "**Challenge in the open.** Where evidence outside the change "
        "suggests a person's words miss what they want, the artifact says "
        "\"your words say X (tag); the code shows Y; I propose Z\", naming "
        "where.",
        "Against a Directive, which stands until they answer, or where it is "
        "material, that is a question for them; otherwise the work follows "
        "Z.",
        "Neither raising a challenge nor following one past a Preference or "
        "Hunch blocks: where the workflow takes no questions, a challenge is "
        "an advisory written as one.",
        # a change that does not do what the words say, or departs under a
        # softened tag, is not a challenge (v3.1)
        "Any other departure from a person's words, under too soft a tag "
        "included, breaks a criterion the work received.",
        "A scope statement excuses an absence, never a presence",
        # an author's deferral never excuses an outcome a person set, and
        # only words that name it let it go (v3)
        "means the reviewer does not report that thing as missing, except a "
        "criterion the work received: only a person's quoted words naming it "
        "and letting it go waive one, never a go-ahead on an artifact that "
        "lists it unmet.",
        "No scope statement, the author's or a person's, makes what the "
        "change does add correct: what it adds is reviewed on its merits",
        "Deferring a unit's consumer does not excuse the unit: that nothing "
        "calls it is still a finding",
    )

    VERDICTS = (
        "breaks an acceptance criterion the work received (one the ticket "
        "or someone other than the author set; the author's own are design "
        "under review)",
        "Pre-existing means already on the target branch",
        "Commits this branch already carries (an earlier revision, an "
        "earlier run's work) are part of the change and are not precedent. "
        "This settles what counts as pre-existing, not what a delta pass "
        "re-reads",
        "**For every type, field, parameter, public method or function, and "
        "exception type a change adds, name the line that reads, calls or "
        "handles it.**",
        "A reader acts on the value in production code: it branches on it, "
        "computes with it, or passes it out of the change to a receiver "
        "that acts on it",
        "A test, a copy into another field, a check of the value against "
        "itself or its twin, and a serializer whose output no receiver acts "
        "on are not readers",
        "a check that only rejects the value reads it only when some "
        "production code can produce the value it rejects",
        "A unit is public when code outside its own module can reach it",
        "For a public method or function the change adds, or keeps while "
        "removing its last production caller, name its production caller; "
        "for one the project publishes as its API, name that export instead",
        "For an exception type the change adds, name the handler that "
        "decides what happens next and what it decides for this failure; "
        "the framework's default is not a handler",
        # the reader rule still states a fact, and still advises
        "stated as the fact and never as a demand",
        "It is `advisory` unless the unread or uncalled thing also breaks "
        "something",
    )

    DECISION_RIGHTS = (
        "Judge a decision against the target branch. A table, migration, "
        "interface or format this branch adds is one decision, made once "
        "under its class; reworking it before it reaches the target is part "
        "of that decision, not a further schema migration or API break. That "
        "holds unless the project deploys or publishes from a branch other "
        "than the target",
    )

    FOUR = ("review-mr", "verify-feature", "run-pipeline", "implement-feature")

    @classmethod
    def setUpClass(cls):
        t = make_target(read(EXAMPLE))
        rc, out = install("direct", t)
        assert rc == 0, out
        cls.dir = t / "product-knowledge" / "glados"

    def core(self, name):
        return " ".join(read(self.dir / f"{name}.md").split())

    def assertAllIn(self, rules, core):
        text = self.core(core)
        for rule in rules:
            self.assertIn(rule, text, f"{core} lacks: {rule!r}")

    def inlining(self, module):
        """Every compiled core whose provenance header inlines `module`."""
        names = set()
        for path in self.dir.glob("*.md"):
            header = next((l for l in read(path).splitlines()
                           if "modules-inlined:" in l), "")
            if module in header:
                names.add(path.stem)
        return names

    def test_the_fragment_reaches_every_fresh_reviewer_once(self):
        """One rule, three include sites, one copy per document.

        The panel, the evaluator and the fresh-agent design review each brief
        a reviewer, and each must carry the fragment. Identified from the
        provenance header too, so a new core that seats a panel or an
        evaluator is covered without editing this test.
        """
        reviewers = ({"review-mr", "verify-feature", "run-pipeline"}
                     | self.inlining("mr-review-panel")
                     | self.inlining("evaluator-spawn"))
        for name in sorted(reviewers):
            with self.subTest(core=name):
                self.assertAllIn(self.FRAGMENT, name)
                text = self.core(name)
                self.assertEqual(
                    text.count("excuses an absence, never a presence"), 1,
                    f"{name} states the scope rule more than once")

    def test_the_fragment_adds_no_tier_and_no_verdict_word(self):
        # the tags and the challenge live in their own fragment since v3.2,
        # so address-review can carry them without the brief rules
        body = (read(REPO / "src" / "vocabulary" / "review-inputs.md")
                + read(REPO / "src" / "vocabulary" / "person-words.md"))
        for word in ("`blocking`", "`advisory`", "APPROVE", "REQUEST_CHANGES",
                     "ESCALATE", "PASS", "FAIL"):
            self.assertNotIn(word, body)

    def test_no_reviewer_is_told_author_scope_is_settled(self):
        """The phrase that disarmed every reviewer is gone from all three."""
        for name in ("review-mr", "verify-feature", "run-pipeline"):
            with self.subTest(core=name):
                text = self.core(name)
                self.assertNotIn("a decision already made", text)
                self.assertNotIn("work the author declared is a decision", text)
                self.assertNotIn("a contract file, if one exists, takes "
                                 "precedence", text)

    def test_the_vocabulary_changes_reach_all_four_cores(self):
        for name in self.FOUR:
            with self.subTest(core=name):
                self.assertAllIn(self.VERDICTS, name)
                self.assertNotIn("breaks an acceptance criterion, opens",
                                 self.core(name))

    def test_decision_rights_are_judged_against_the_target_branch(self):
        """Every core gets the preamble, so every core gets the sentence."""
        cores = [p.stem for p in sorted(self.dir.glob("*.md"))
                 if p.stem in glados.CORES]
        self.assertTrue(set(self.FOUR) <= set(cores))
        for name in cores:
            with self.subTest(core=name):
                self.assertAllIn(self.DECISION_RIGHTS, name)

    def test_only_a_received_criterion_blocks_the_evaluator(self):
        """An author's criterion is design under review, in the verdict too.

        verdicts makes only a criterion the work received blocking, so the
        evaluator's PASS cannot need every criterion: a plain design that
        drops a mechanism the author's own criterion named would otherwise
        FAIL, and map to REQUEST_CHANGES, whatever tier the vocabulary gives.
        """
        cores = self.inlining("evaluator-spawn")
        self.assertIn("verify-feature", cores)
        for name in sorted(cores):
            with self.subTest(core=name):
                self.assertAllIn((
                    "PASS — every criterion the work received passed and no "
                    "blocking issue found.",
                    "A failed criterion the brief labels as the author's is "
                    "not one the work received: it is an issue at the tier "
                    "its consequence earns, and where the criterion itself "
                    "is unnecessary, say so",
                    "Acceptance criteria (criterion | source | PASS/FAIL | "
                    "evidence)",
                ), name)
                self.assertNotIn("PASS — every criterion passed",
                                 self.core(name))

    def test_the_panel_reads_scope_as_an_absence(self):
        self.assertAllIn((
            # the panel's brief list is the one list of what the panel is
            # given; review-mr gathers from it rather than keeping a second
            # list that drifted from it (v3.2)
            "the spec and the merge-request description (without its step "
            "table or the findings it lists), labelled as the author's;",
            "Gather what *Assemble the brief* lists, and the personas active "
            "for this feature",
            "the rules in *Verdicts and finding severities* and *What a fresh "
            "reviewer is given*, copied verbatim",
            "3. Read the merge-request description before you raise "
            "anything, as the brief carries it: without its step table or "
            "the findings it lists",
            "tells you what the change leaves out. Do not report that back "
            "as a gap",
            "It never makes what the change puts in correct, whoever asked "
            "for it: that is reviewed on its merits",
            "5. For every type, field, parameter, public method and "
            "exception type this change adds, or leaves without a production "
            "caller, find its reader, production caller or handler",
            "what it declares left out is a deferral",
            "**Which acceptance criteria the work received does the diff "
            "meet?**",
            "**What is in the diff that no criterion the work received asked "
            "for?**",
        ), "review-mr")
        self.assertNotIn("the severity scale, verdict words, and composition "
                         "rules above", self.core("review-mr"))

    def test_a_replan_rebriefs_the_whole_change(self):
        """A delta pass over a re-planned change never judges the new plan."""
        self.assertAllIn((
            "**Cycle 2 and after brief the delta**",
            "**Unless the work was re-planned.** When a plan, shape or spec "
            "record differs between `review.reviewed-head` and this head, "
            "this cycle briefs the whole change against the target branch, "
            "as cycle 1 does, with the open findings still named",
            "**For a delta pass, check first that the reviewed head is still "
            "an ancestor of this one.**",
        ), "review-mr")
        text = self.core("review-mr")
        self.assertLess(text.index("**Cycle 2 and after brief the delta**"),
                        text.index("**Unless the work was re-planned.**"))
        self.assertLess(text.index("**Unless the work was re-planned.**"),
                        text.index("**For a delta pass, check first"))

    def test_the_evaluator_brief_labels_its_inputs(self):
        self.assertAllIn((
            "| What was agreed | The acceptance criteria, each with its "
            "source: the ticket, a person's words quoted (an answer to a "
            "question, with the reading it chose, among them), or the "
            "author's plan, shape or spec, labelled as the author's, each "
            "assumption they label included",
            "A contract file takes precedence over the plan and spec only for "
            "what a person's words name; a criterion the author derived is "
            "the author's, under review like the code",
            "or against the branch's merge-base with the target branch when "
            "that commit is not on the target",
            "declares deferred, each labelled with who deferred it: the "
            "author, or a person quoted. A deferral excuses an absence, as "
            "*What a fresh reviewer is given* sets out",
            "| Vocabulary | The rules in *Verdicts and finding severities* and "
            "*What a fresh reviewer is given*, copied verbatim |",
            "acceptance criteria in their own words, each with its source",
        ), "verify-feature")
        self.assertNotIn("wrote or approved", self.core("verify-feature"))

    def test_the_design_review_brief_labels_its_deferrals(self):
        self.assertAllIn((
            "| What is deliberately out of scope | Anything the plan, the "
            "spec or an earlier step deferred, each labelled with who "
            "deferred it",
            "| Vocabulary | The rules in *Verdicts and finding severities*, "
            "*What a fresh reviewer is given* and *Questions for a person*, "
            "copied verbatim |",
            "the base commit (`work.base-sha`, or the branch's merge-base "
            "with the target branch when that commit is not on the target)",
        ), "run-pipeline")

    def test_the_shape_is_laid_down_and_then_checked(self):
        """shape.md promised implement-feature lays the shape down first.

        The promise was only in the shape step; implement-feature and
        verify-feature never mentioned a shape. Now the implementer lays it
        down and states departures, and the evaluator lists every public unit
        the diff adds or drops against it. Stating a departure declares it;
        it never excuses a unit the diff adds.
        """
        self.assertAllIn((
            "When the caller passes a shape with the spec, take it too. Its "
            "units are the first task of the breakdown: lay their signatures "
            "down before any body",
            "Any public unit the diff adds that the shape does not list, or a "
            "shape unit the diff drops, is a departure",
            "the test result, and each departure from the shape with its "
            "reason",
        ), "implement-feature")
        self.assertAllIn((
            "the shape's path when the run has one",
            "| Shape | Only when the run has a shape: its path, and each "
            "departure from it that implement-feature's `progress` outcome "
            "states, labelled as the author's",
            "6. If the brief names a shape, list every public unit the diff "
            "adds that the shape does not list, and every shape unit the diff "
            "drops. One the brief does not list as a stated departure is an "
            "issue. A stated departure is not undeclared drift, but a unit it "
            "adds is still reviewed on its merits, and its stated reason is "
            "the author's",
            "Shape when the brief names one (unit | added/dropped | stated "
            "departure or not)",
        ), "verify-feature")
        self.assertNotIn("Each is an issue unless the brief lists it as a "
                         "stated departure", self.core("verify-feature"))
        self.assertAllIn((
            "When implement-feature or verify-feature runs after a shape, "
            "pass it the shape with the spec",
            "| Readers | For every new field, parameter, public method or "
            "function, and exception type, the unit that reads, calls or "
            "handles it, as *Verdicts and finding severities* defines them. |",
            "| Precedent | The unit on the target branch each new one "
            "follows. |",
        ), "run-pipeline")

    def test_each_requirement_names_its_source(self):
        """The label does the work; a mechanism criterion is not moved.

        A criterion the author invented is an assumption, and verdicts makes
        only a received criterion blocking, so labelling is enough. Moving a
        criterion that names a code construct to Approach is left to a
        project plan step.
        """
        self.assertAllIn((
            "Label each requirement with its source: the ticket, a person's "
            "words (quoted, with where they were said), or \"assumption\" for "
            "one you invented rather than received, so spec-feature can "
            "confirm or kill it",
        ), "plan-feature")
        text = self.core("plan-feature")
        self.assertNotIn("names a code construct", text)
        self.assertNotIn("Requirements you invented rather than received are "
                         "assumptions", text)


class TestDesignLoop(unittest.TestCase):
    """How run-pipeline's revise loop ends: questions and stalls park.

    Two trial runs of a plain-first pipeline spent hours in design: the
    fresh-agent gate caught real defects, but every cycle counted against the
    bound, progress included, and a finding that turned on what a person
    meant could only block, use up a cycle and end the run. A project cannot
    change how run-pipeline counts, closes or parks, so each rule is pinned
    into compiled run-pipeline. Asserted with whitespace flattened, so a
    re-wrap of the source does not break a test.
    """

    QUESTIONS = (
        "## Questions for a person",
        "No code or file settles what a person meant.",
        # a choice no one's words reach becomes a question by its class
        "Whoever finds an artifact resting on words whose readings differ "
        "materially, or on an `escalate` choice no one's words reach, "
        "raises a question: the author, a reviewer or a gate's audit.",
        # material means the readings differ in whether a named outcome is
        # met, judged in the people's own words at their fullest reading,
        # so a rival meaning of an outcome's words is judged from the
        # widest and an author's restatement never narrows it; what a
        # person's words gave up is not counted; and a finder unsure
        # whether readings differ asks rather than assumes (v3.2)
        "**Materially**: the readings differ in whether an outcome the "
        "ticket's or a person's own words name is met, or one needs a "
        "choice `decisions:` classes `escalate`; when unsure, they do. Each "
        "outcome counts as fully as any reading reads it, less what a "
        "person's words let go.",
        # narrow variants that meet the same outcomes do not park: they
        # take the project's own precedent before the plainest, and a test
        # pins the assumption; a stored record is one, its class in
        # `decisions:` deciding whether it is asked (v3, v3.1). The list is
        # of differences, not categories exempt whatever they leave unmet
        # (v3.2)
        "Readings that meet the same outcomes (differing in a unit, a "
        "stored record, a failure path) are not: the artifact takes the one "
        "the project's standards or nearest in-tree precedent follows, else "
        "the plainest, labelled as an assumption for a test to pin.",
        "**Form**: numbered, under *Questions for a person* in its finder's "
        "file",
        # a tested Hunch and a reopened Assent carry their evidence where
        # the person reads the words (v3.2)
        "the words it turns on, quoted with where said and their tag (a "
        "Hunch with what the code showed, a reopened Assent with what its "
        "giver was not shown), or the `escalate` class it needs",
        "the readings, plainest first, each an outcome the person might "
        "want, never a mechanism",
        # a question is never a way around a finding
        "**A question never replaces a finding** and fails nothing",
        "What code, files, a standard, a stated outcome or the blocking "
        "definition settles is a finding at its tier, even where a person's "
        "words are silent",
        "A question goes beside it only if the answer changes its fix",
        "Any other doubt is an advisory written as a question",
        # nor is an assumption a way around a question: the artifact that
        # assumes has the blocking finding, whoever raises the question
        "raises a question: the author, a reviewer or a gate's audit. An "
        "artifact that assumes an answer instead has a blocking finding.",
    )

    PARK = (
        "**Questions.** The run records each question for a person, a "
        "nested plan's open ones included, and how it went:",
        # routed from the readings as their finder wrote them
        "the question and its readings stay their finder's",
        # decision rights decide what is never asked
        "A reading that needs a choice classed `forbidden` is refused as "
        "*Decision rights* sets out, never asked.",
        # only `escalate` makes a choice material (questions.md), so an
        # `agent` or `record` choice by itself asks nothing
        "or one needs a choice `decisions:` classes `escalate`",
        # a body may defer its questions to a later step, which parks even
        # when it asks nothing, and never past code or the MR
        "**A one-way door parks the step** once its check is done (with no "
        "check, once its artifact is written), or at the end or skip of a "
        "later step its body names, none up to it producing `change` or "
        "`mr`: one park for all of them, as at a `human` checkpoint, the "
        "questions standing where the approval would",
        "Any other pipeline claims no branch until it parks and cuts one.",
        "At a bound, the run stops instead, its escalation carrying the "
        "questions too",
        "**Answers.** Record each verbatim, with who gave it and where, "
        "noting when that is not the person whose words the question turns "
        "on; the question and its readings stay their finder's",
        # an answer costs a revise cycle (Bound's definition counts it),
        # wherever it reaches: an overturned two-way door from an earlier
        # step is revised in each artifact built on it (v3.1)
        "The author then revises for the answers, in each artifact they "
        "reach, and any finding still open (**Bound**)",
        "A step after open-mr parks for no question: its questions go on "
        "the MR with its `verdict`",
        # a question park resumes inside the step, on an answer
        "continues after the checkpoint, or inside the step for answers, "
        "once a maintainer, or a CODEOWNER of `glados.yaml` or "
        "`product-knowledge/steps/`, has approved or answered on the park's "
        "escalation",
        "quote the approval or answers in the new record",
        "With no approval or answer yet, say so in the record",
        "check the approval or answer as **Resume** in step 4 sets out",
    )

    BOUND = (
        "**Bound.** A revise cycle is one revision of a step's artifact, "
        "whatever it answers (open blocking findings, a person's answers, a "
        "refusal), and the check after it",
        "one row per check (a review, a gate's audit, or an ask at a "
        "`human` checkpoint)",
        "`check | file | given | closed | raised | questions | stalled`",
        # no check overwrites another, so the table can be checked
        "`check` is the row's number n. Each check's files carry it, so none "
        "overwrites another; a gate's audit done here is "
        "`<record>.<id>.audit-<n>.md`. `file` links them, or quotes the "
        "answer to an ask",
        "A finding is named by its check and number (`2.1`)",
        "`given`: what earlier rows left open. `closed`: those its file "
        "reports closed or not a defect, naming whose call it was; a check "
        "done here reports as step 5 of the reviewer's prompt sets out",
        # recurrence is the same consequence elsewhere, and doubt parks
        "`raised`: its new blocking findings, each `new`, or `recurs <n>` "
        "when its file shows earlier finding n's defect (the same "
        "consequence) at another path, input or place, a re-open included, "
        "saying why; when unsure, `recurs`.",
        "`questions`: those it asked (**Questions**)",
        "`stalled`: `yes` when it raises a `recurs`, or ends a revise cycle "
        "given findings that closes none of them; `—` for a check after no "
        "revision; else `no`",
        # a stall parks at once, with the decision framed for the person
        # and the research an informed answer needs, named field by field
        # since a stall turns on findings, not words (v3.1)
        "A stalled check parks the step at once, naming the open findings, "
        "their kind and how the author would remove it, for the person to "
        "approve that, rule a finding not a defect, waive findings by name, "
        "or stop, with a scenario, each option's cost and risk, and the "
        "author's recommendation, confidence and evidence.",
        "At the bound, mark the row `failed`.",
        "On hitting a bound: stop, emit an `escalation` outcome carrying the "
        "open findings and the cycle history, and end the run.",
        # a refusal is a finding the ask raises: it costs a revise cycle
        "A refusal, with the person's reasons, is a blocking finding the ask "
        "raises: revise the artifact as `required` does, whatever the "
        "modifier, and ask again within the step's bounds",
        # a park never resets the count
        "copies the parked run's step and cycle tables instead",
        # loop-bounds names the runaway guard; its re-open stop stands for
        # every other loop and names run-pipeline's park as the exception,
        # so the compiled document holds no two contrary rules
        "| revise cycles per pipeline step (run-pipeline) | "
        "`params.pipeline.max-cycles` |",
        "that is a stalemate regardless of the counter: stop and emit an "
        "`escalation` immediately rather than spending remaining cycles on "
        "it, except in run-pipeline's revise loop, which parks for a person "
        "(its **Bound**).",
    )

    REVIEW = (
        "| Findings still open | Those the cycle table leaves open, by "
        "number, copied verbatim from where they were raised |",
        # the reviewer knows what the work received, not only the author's
        # restatement of it (v3); an answer the author gave a two-way door
        # is the author's, not a criterion the work received (v3.1)
        "| What was asked | The ticket, each instruction a person gave this "
        "run, and each question a person answered, with its readings and "
        "answer, copied verbatim with where said: the criteria the work "
        "received |",
        "| Vocabulary | The rules in *Verdicts and finding severities*, *What "
        "a fresh reviewer is given* and *Questions for a person*, copied "
        "verbatim |",
        "exactly two files beside the run record, numbered n by the check "
        "(**Bound** in step 4): `<record>.<id>.review-brief-<n>.md` (input) "
        "and `<record>.<id>.review-<n>.md` (output). Nothing else is shared.",
        # closure is per kind, and a wrong finding can be retired
        "5. Report each finding the brief names as open: closed, only when "
        "nothing else in the artifact has the same defect (no other path, "
        "input or place of its kind); not closed, and where it still holds; "
        "or not a defect, and why. One not closed is still blocking.",
        "6. List every other issue",
        # the reviewer checks what the author filed and how it routed it,
        # and looks for words used untagged or departed from silently (v3.1)
        "7. Check each assumption, tag, challenge and question (its form "
        "and door) the artifact states, and any person's words it rests on "
        "untagged or departs from unstated; raise questions for a person, as "
        "the vocabulary in the brief sets out.",
        "Open findings (number | status | where or why)",
        "Issues (numbered; location, severity, what would fix it), Questions "
        "for a person, Canon conflicts",
        "PASS: no blocking issue. FAIL: list the blocking issues, open "
        "findings not closed included.",
        "The result feeds the step's cycle table (**Bound**) and, for a "
        "gate, its pass or fail.",
    )

    @classmethod
    def setUpClass(cls):
        t = make_target(read(EXAMPLE))
        rc, out = install("direct", t)
        assert rc == 0, out
        cls.target = t
        cls.dir = t / "product-knowledge" / "glados"
        cls.text = " ".join(read(cls.dir / "run-pipeline.md").split())

    def assertAllIn(self, rules, text):
        for rule in rules:
            self.assertIn(rule, text, f"run-pipeline lacks: {rule!r}")

    def test_a_question_is_defined_once_and_reaches_the_reviewer(self):
        self.assertAllIn(self.QUESTIONS, self.text)
        self.assertEqual(self.text.count("## Questions for a person"), 1,
                         "one fragment, one copy per document")
        # the brief copies it by name, beside the rules it already copies
        self.assertAllIn(self.REVIEW[2:3], self.text)

    def test_a_question_adds_no_tier_no_verdict_and_no_status(self):
        body = read(REPO / "src" / "vocabulary" / "questions.md")
        for word in ("`blocking`", "`advisory`", "APPROVE", "REQUEST_CHANGES",
                     "ESCALATE", "PASS", "FAIL"):
            self.assertNotIn(word, body)
        self.assertIn("`pending | done | skipped | waived | parked | "
                      "failed`", self.text, "no new step status")

    def test_a_one_way_door_parks_and_is_routed_from_its_readings(self):
        self.assertAllIn(self.PARK, self.text)
        # no going on under an unasked assumption to the MR: a question that
        # does not park is answered and put to the person (v3.1, two-way door)
        self.assertNotIn("the author goes on with the plainest reading",
                         self.text)
        self.assertNotIn("every question for a person the run went on "
                         "without", self.text)
        # a choice any class covers no longer parks: only `escalate` does
        self.assertNotIn("needs a choice a class under `decisions:` covers",
                         self.text)
        self.assertNotIn("The park is not a revise cycle", self.text)
        # the rule sits with the park rules it builds on
        self.assertLess(self.text.index("- **Resume.**"),
                        self.text.index("- **Questions.**"))
        self.assertLess(self.text.index("- **Questions.**"),
                        self.text.index("- **Selection re-check.**"))

    def test_the_bound_counts_all_cycles_and_stalled_ones(self):
        self.assertAllIn(self.BOUND, self.text)
        self.assertNotIn("Count each step's revise cycles in the record and "
                         "check `params.pipeline.max-cycles` before starting "
                         "another", self.text)
        self.assertNotIn("Cycles count against the step's bound", self.text)
        self.assertNotIn("max-total-cycles", self.text)
        # one file per check: the old shared names are gone
        self.assertNotIn("<record>.<id>.review.md", self.text)
        self.assertNotIn("<record>.<id>.review-brief.md", self.text)

    def test_the_design_review_reports_closure_and_questions(self):
        self.assertAllIn(self.REVIEW, self.text)
        self.assertNotIn("PASS: no blocking issue found. FAIL", self.text)
        self.assertNotIn("as the vocabulary in the brief sets out, not an "
                         "issue", self.text)

    def test_parked_tickets_wait_for_an_approval_or_an_answer(self):
        text = " ".join(read(self.dir / "run-epic.md").split())
        self.assertIn("A ticket whose run parks, at a checkpoint or on a "
                      "question, waits for its approval or answer", text)
        self.assertIn("check each parked ticket once for its approval or "
                      "answer", text)

    def test_the_runaway_guard_resolves_and_no_stall_count_is_tuned(self):
        """`params.pipeline.max-cycles` is compiled into run-pipeline, so it
        must resolve with no params: block, in every phase, from the
        baseline (a dangling literal fails the install). A stall has no
        number: the first stalled check parks, so no stalled-cycle bound is
        set or compiled anywhere."""
        report = read(self.target / ".glados" / "assembly-report.md")
        self.assertIn("| params.pipeline.max-cycles | 8 | (baseline) |",
                      report)
        self.assertNotIn("max-stalled-cycles", report)
        source = glados.Source(REPO)
        for phase in glados.PHASES:
            with self.subTest(phase=phase):
                raw = {"glados": 2, "platform": "gitlab", "phase": phase}
                r = glados.resolve_manifest(raw, source.presets, "glados.yaml")
                pipeline = r.values["params"]["pipeline"]
                self.assertEqual(pipeline["max-cycles"], 8)
                self.assertNotIn("max-stalled-cycles", pipeline)
        for path in sorted(self.dir.glob("*.md")):
            with self.subTest(core=path.stem):
                self.assertNotIn("max-stalled-cycles", read(path))
        # a project that set max-cycles keeps its meaning: all cycles
        raw = {"glados": 2, "platform": "gitlab", "phase": "evolving",
               "params": {"pipeline": {"max-cycles": 2}}}
        r = glados.resolve_manifest(raw, source.presets, "glados.yaml")
        self.assertEqual(r.values["params"]["pipeline"]["max-cycles"], 2)
        self.assertEqual(r.provenance["params.pipeline.max-cycles"],
                         "explicit")

    def test_the_other_loops_keep_their_counting(self):
        """Only run-pipeline's revise loop changed: the MR review loop, the
        evaluator and the standards gate keep their bounds, and the cycle
        table stays in the one core that keeps it."""
        for name in ("review-mr", "verify-feature", "address-review"):
            with self.subTest(core=name):
                text = " ".join(read(self.dir / f"{name}.md").split())
                for row in (
                    "| review-mr ⇄ address-review cycles per MR round | "
                    "`params.review-panel.max-cycles` |",
                    "| evaluator verify/fix cycles per feature | "
                    "`params.evaluator.max-cycles` |",
                    "| standards-gate re-runs per gated artifact | "
                    "`params.standards-gate.max-cycles` |",
                ):
                    self.assertIn(row, text)
                self.assertNotIn("`check | file | given | closed", text)
                self.assertNotIn("`stalled`: `yes`", text)


class TestHealthierRun(unittest.TestCase):
    """The v3 rules from the first plain-first trial runs (docs/proposals/
    v3.md): an outcome a person set cannot be deferred by the author, an
    answer binds the outcome it chose and is traced to code and a test, a
    repeated advisory goes to the person, a fix covers its kind, one full
    suite per fix loop, and a record that is an index. Each rule is pinned
    into the compiled cores it governs, with whitespace flattened so a
    re-wrap of the source does not break a test.
    """

    @classmethod
    def setUpClass(cls):
        t = make_target(read(EXAMPLE))
        rc, out = install("direct", t)
        assert rc == 0, out
        cls.dir = t / "product-knowledge" / "glados"

    def core(self, name):
        return " ".join(read(self.dir / f"{name}.md").split())

    def assertAllIn(self, rules, name):
        text = self.core(name)
        for rule in rules:
            self.assertIn(rule, text, f"{name} lacks: {rule!r}")

    def test_an_author_cannot_defer_a_received_criterion(self):
        """The ticket's outcome stays owed until a person waives it, at every
        fresh reviewer (the rule is in the fragment TestReviewInputs pins
        into each); the panel's scope order points at it by name, and each
        brief's out-of-scope row raises one, not only what breaks."""
        self.assertAllIn((
            "Do not report that back as a gap, except where *What a fresh "
            "reviewer is given* says to",), "review-mr")
        self.assertNotIn("Do not report that back as a gap: it costs",
                         self.core("review-mr"))
        for name in ("run-pipeline", "verify-feature"):
            with self.subTest(core=name):
                self.assertAllIn((
                    "Raise one where living with it breaks something, an "
                    "unmet criterion the work received included, and say "
                    "what breaks",), name)
                self.assertNotIn("Raise one only where living with it",
                                 self.core(name))

    def test_every_fresh_reviewer_is_given_what_was_asked(self):
        """A gate briefed only with the author's restated outcomes checks the
        author's words; the ticket and the person's words reach the design
        reviewer and the panel too, the author's spec labelled as such."""
        self.assertAllIn((
            "| What was asked | The ticket, each instruction a person gave "
            "this run, and each question a person answered, with its "
            "readings and answer, copied verbatim with where said: the "
            "criteria the work received |",), "run-pipeline")
        # the panel gets the answers a person gave, as the design reviewer
        # does, so it never blocks on a choice a person already made (C7,
        # v3.2), and each instruction or answer people gave on the MR: an
        # overturn posted there is an answer (fix round 1)
        self.assertAllIn((
            "the ticket or a person's brief, each question a person answered "
            "in the run that opened the MR, with its readings and answer, and "
            "each instruction or answer people gave on the MR, quoted with "
            "where said;",
        ), "review-mr")
        self.assertNotIn("the changed-file list, the spec or ticket",
                         self.core("review-mr"))

    def test_words_bind_as_firmly_as_they_were_said(self):
        """Hedged words set a default evidence can revise; firm ones bind;
        an answer binds its reading's outcome, never the option's wording.
        v3.1's commitment tags absorb v3's wording rather than sit beside
        it: pinned into every reviewer by TestReviewInputs.FRAGMENT; here,
        that each core says it once and that the old readings are gone."""
        for name in ("run-pipeline", "verify-feature", "review-mr"):
            with self.subTest(core=name):
                text = self.core(name)
                self.assertEqual(text.count("as firmly as they said it"), 1)
                self.assertNotIn("Words bind as firmly as they were said",
                                 text)
                self.assertNotIn("Evidence against a default", text)
                self.assertNotIn("and the proposal stays the author's", text)
                self.assertNotIn("and its wording stays its writer's", text)

    def test_an_answer_and_an_assumption_are_traced_to_code_and_test(self):
        """An answer is a criterion the work received, and an assumption the
        author labelled instead of asking is the author's: the evaluator
        checks both, and an untested one is a test gap at the tier its
        source earns."""
        self.assertAllIn((
            "a person's words quoted (an answer to a question, with the "
            "reading it chose, among them)",
            "or the author's plan, shape or spec, labelled as the author's, "
            "each assumption they label included",
            "5. Mark each acceptance criterion PASS or FAIL, with the "
            "evidence you observed: the code that meets it and the test "
            "that pins it. One a test can pin that no test pins is an issue: "
            "blocking for a criterion the work received, advisory for the "
            "author's.",
        ), "verify-feature")
        # the answers reach the nested verify-feature that writes the brief
        self.assertAllIn((
            # a nested stage tags people's words as the design review it
            # faces checks them (v3.1)
            "Pass the artifacts that meet their needs, by path from the step "
            "table, and the run's answers and the tags of *What a fresh "
            "reviewer is given* as caller context.",
        ), "run-pipeline")

    def test_a_repeated_declined_advisory_goes_to_the_person(self):
        """Recorded where a reader of the index finds it, asked once
        whatever the materiality rule says, and parking only where its
        door is one-way."""
        self.assertAllIn((
            "**A declined advisory** (a fresh agent's, left undone when its "
            "row ends) is noted in that row by file and number.",
            "Once two fresh reviewers or evaluators in this run have raised "
            "it (the same defect at the same unit), it is a question for the "
            "person, asked once whatever *Materially* says: whether they "
            "want it, readings \"wanted\" and \"not wanted\", the two "
            "findings quoted as its words and recommendation, beside the "
            "author's reasons for declining.",
            # the author who declined it twice does not write the case it
            # is asked on, and its door routes it like any question: the two
            # findings are its recommendation, so *Doors* makes that its
            # default unless a person's words take another reading, rather
            # than keeping the state two independent checks found wanting
            # (FID-9, v3.2); a second default rule here would override a
            # person's answer (fix round 1)
            "beside the author's reasons for declining. It is never made "
            "blocking.",
        ), "run-pipeline")
        text = self.core("run-pipeline")
        self.assertNotIn("the work unchanged until they answer", text)
        self.assertNotIn("Its default is the findings' recommendation", text)
        self.assertNotIn("**An advisory two fresh agents", text)
        # it sits with the question routes, after the two it builds on
        self.assertLess(text.index("**A one-way door parks the step**"),
                        text.index("**A two-way door parks nothing.**"))
        self.assertLess(text.index("**A two-way door parks nothing.**"),
                        text.index("**A declined advisory**"))

    def test_a_fix_covers_its_kind_in_code(self):
        """Every place the change has the defect, not a sweep of code that
        predates it, and a place left alone names the input that shows it."""
        self.assertAllIn((
            "A finding the caller passes to fix (a gate's or an evaluator's) "
            "is a task covering its kind: list in the checklist every place "
            "where the change has the same defect (each other path, input or "
            "place of its kind; a breach that predates the change is not "
            "one), then fix each or name, per place, the input that shows it "
            "does not hold there. Fixing only the place it names leaves it "
            "open.",
        ), "implement-feature")

    def test_one_full_suite_per_fix_loop(self):
        self.assertAllIn((
            "run the tests of every area the diff touches and the project's "
            "unit suite — not just the tests written above",
            "The full suite runs once per fix loop, in verify-feature's "
            "evaluator.",
        ), "implement-feature")
        self.assertNotIn("run the full test suite — not just the tests",
                         self.core("implement-feature"))
        # the one full run is checked against CI, not the author's list
        self.assertAllIn((
            "| How to verify | The full test suite and lint commands, as CI "
            "runs them, and the path of the CI configuration;",
            "3. Run every test and lint command in the brief. A test job in "
            "the CI configuration it names that the brief leaves out is an "
            "issue.",
        ), "verify-feature")
        # committing code needs the full suite, and the evaluator's run of
        # it on the same diff counts, so a fix loop pays for it once
        for name in ("run-pipeline", "build-feature", "fix-bug"):
            with self.subTest(core=name):
                self.assertAllIn((
                    "Run the project's full test suite before committing "
                    "code, and its exact CI checks locally before pushing "
                    "it; a fresh evaluator's run of them on the same diff "
                    "counts.",), name)

    def test_the_record_is_an_index_and_commits_go_by_row(self):
        """A reader reads the head and its rows, not the whole record; a
        revision's dispositions stay out of the artifact the next reviewer
        reads; a row's process files go to the ledger in one save when it
        ends or parks, never onto the branch, which a run with no branch of
        its own does not claim until it parks (v3.2)."""
        self.assertAllIn((
            "**The record is an index**: under its header, `## Now` (the "
            "step in progress, what it waits on, the next action), kept "
            "current; a reader reads it and the rows its step needs.",
            "Findings stay in their check's files, and how the revision "
            "before check n answered them in `<record>.<id>.revision-<n>.md`, "
            "which no brief names.",
            "**Commits.** When a row ends or parks, its process files "
            "(artifact, briefs, check results, record) go to the ledger in "
            "one save (*Before ending this run*, step 4).",
            "Any other pipeline claims no branch until it parks and cuts one.",
            # the mandatory epilogue's save, compiled into the same core,
            # is the one that row saves point at
            "**Save the record to the ledger.**",
        ), "run-pipeline")
        text = self.core("run-pipeline")
        self.assertNotIn("PASS with advisory issues records them in the "
                         "step's row", text)
        self.assertNotIn("none is committed alone", text)
        self.assertNotIn("claims no branch, and commits nothing", text)
        self.assertNotIn("go in one commit when the row ends or parks", text)

    def test_each_rule_is_said_once_in_run_pipeline(self):
        """Text the v3 rules made redundant is gone, so run-pipeline did not
        grow: each of these is stated by the section the remaining pointer
        names."""
        text = self.core("run-pipeline")
        # a nested escalation ends the run: said under the modifiers only
        self.assertEqual(text.count("ends in `escalation`"), 1)
        self.assertIn("A nested workflow that ends in `escalation`, and the "
                      "standards gate stopping at its bound", text)
        # pending MR items: the epilogue lists whose; open-mr points at it
        self.assertIn("post every item waiting for it, as *No MR yet is not "
                      "a failed delivery*", text)
        self.assertNotIn("the `## Pending MR delivery` items of this run's "
                         "record", text)
        # self-review defers to After the MR opens instead of restating it
        self.assertIn("Its verdict follows **After the MR opens** in "
                      "run-pipeline's step 4, whatever the step's modifier",
                      text)
        self.assertNotIn("queue fixes so review line references stay stable",
                         text)
        # a design review's result is no verdict before the MR, and a step
        # after the MR posts one: said once, by run-pipeline's step 4
        self.assertNotIn("It never becomes a `verdict` outcome", text)
        # the work left for a human: one rule, under Branch, which step 5
        # points at; the record it names is on the ledger, saved by the
        # epilogue before any outcome is published, so no second push
        # (v3.2)
        self.assertEqual(text.count("leaves its work there for a human"), 1)
        self.assertNotIn("once the epilogue has committed the record", text)
        self.assertIn("When no MR was opened, the artifacts in the record are "
                      "the deliverable (**Branch** in step 4).", text)
        # a re-open: Loop bounds names run-pipeline's park as its exception,
        # so Bound does not restate the stop it overrides
        self.assertNotIn("not the stop *Loop bounds* sets for a re-open",
                         text)
        # the gate's bound stop is Loop bounds' own, not restated
        self.assertNotIn("do not re-run again", text)
        # the bypass is documented in the pipelines guide, not run-time text
        self.assertNotIn("Known gap", text)
        self.assertIn("**Known gap.** Anyone can still run build-feature "
                      "directly", " ".join(read(
                          REPO / "docs" / "guides" / "pipelines.md").split()))

    def test_a_retired_stall_count_is_reported_not_silently_kept(self):
        """A manifest that still tunes the v2 stall count resolves, but
        install and validate warn that nothing reads it, and the assembly
        report marks it retired instead of listing it as a live setting."""
        raw = {"glados": 2, "platform": "gitlab", "phase": "evolving",
               "params": {"pipeline": {"max-cycles": 5,
                                       "max-stalled-cycles": 2}}}
        warnings = glados.manifest_warnings(raw, "glados.yaml")
        self.assertIn("glados.yaml: params.pipeline.max-stalled-cycles is "
                      "retired in 2.5 (v3): the first stalled check parks "
                      "the step for a person, so no stall count is read; "
                      "remove it", warnings)
        self.assertEqual(glados.manifest_warnings(
            {"glados": 2, "params": {"pipeline": {"max-cycles": 5}}},
            "glados.yaml"), [])
        manifest = read(EXAMPLE).replace(
            "\nparams:\n", "\nparams:\n  pipeline:\n    "
            "max-stalled-cycles: 2\n", 1)
        self.assertIn("max-stalled-cycles: 2", manifest)
        t = make_target(manifest)
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertIn("params.pipeline.max-stalled-cycles is retired", out)
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("| params.pipeline.max-stalled-cycles | 2 | (explicit; "
                      "retired, read by nothing) |", report)


class TestInformedInput(unittest.TestCase):
    """The v3.1 rules (docs/proposals/v3.md, *v3.1*): people's words carry
    a commitment tag, evidence against them is stated as a challenge, a
    question reaches a person only with the research behind it, and only a
    one-way door parks the run. A project cannot change what a fresh
    reviewer is told about people's words, what a question must carry or
    when run-pipeline parks, so each rule is pinned into the compiled cores
    it governs, with whitespace flattened so a re-wrap of the source does
    not break a test.
    """

    TAGS = ("*Directive* (", "*Preference* (", "*Hunch* (", "*Assent* (")

    @classmethod
    def setUpClass(cls):
        t = make_target(read(EXAMPLE))
        rc, out = install("direct", t)
        assert rc == 0, out
        cls.dir = t / "product-knowledge" / "glados"

    def core(self, name):
        return " ".join(read(self.dir / f"{name}.md").split())

    def assertAllIn(self, rules, name):
        text = self.core(name)
        for rule in rules:
            self.assertIn(rule, text, f"{name} lacks: {rule!r}")

    def reviewers(self):
        names = {"review-mr", "verify-feature", "run-pipeline"}
        for path in self.dir.glob("*.md"):
            header = next((l for l in read(path).splitlines()
                           if "modules-inlined:" in l), "")
            if "mr-review-panel" in header or "evaluator-spawn" in header:
                names.add(path.stem)
        return sorted(names)

    def test_each_clause_carries_one_of_four_tags_defined_once(self):
        """V31-1: every fresh reviewer gets the four tags, each defined once,
        in order from firmest to the assent that binds only what was shown.
        A tag is read from each clause's own words, so a hedge in front of
        a want leaves a Preference and a firm clause inside an answer keeps
        its force; the brief quotes the words untagged, so a reviewer is
        never handed the author's reading of them."""
        for name in self.reviewers():
            with self.subTest(core=name):
                text = self.core(name)
                at = [text.index(tag) for tag in self.TAGS]
                self.assertEqual(at, sorted(at))
                for tag in self.TAGS:
                    self.assertEqual(text.count(tag), 1, tag)
                self.assertIn("Each clause takes the tag its words give "
                              "until the person corrects it:", text)
                self.assertIn("or a hedged want: \"I think we need\")", text)
                self.assertIn("is a belief about what is true (a cause, "
                              "what code does)", text)
                self.assertIn("and labelled as theirs, untagged.", text)
                # no rule lets a hedge anywhere soften the whole quote
                self.assertNotIn("the softer where they mix", text)

    def test_evidence_against_words_is_a_challenge_never_a_block(self):
        """V31-2: one form, said once, from evidence outside the change; a
        Directive's challenge is a question and the Directive stands
        meanwhile; a softer tag's is the work's decision unless it is
        material; raising one never blocks. A change that does not do what
        the words say is not a challenge, nor is a departure under a tag
        softer than the words: both break a criterion the work received."""
        for name in self.reviewers():
            with self.subTest(core=name):
                text = self.core(name)
                self.assertEqual(text.count(
                    "\"your words say X (tag); the code shows Y; I propose "
                    "Z\""), 1)
                self.assertIn("Where evidence outside the change suggests a "
                              "person's words miss what they want", text)
                self.assertIn("Against a Directive, which stands until they "
                              "answer, or where it is material, that is a "
                              "question for them; otherwise the work follows "
                              "Z.", text)
                self.assertIn("Any other departure from a person's words, "
                              "under too soft a tag included, breaks a "
                              "criterion the work received.", text)
                self.assertNotIn("Where code or evidence points away", text)
        # the design reviewer checks what the artifact filed and how it
        # routed each question, and looks for words it used untagged or left
        # without saying so (v3.1)
        self.assertAllIn((
            "7. Check each assumption, tag, challenge and question (its form "
            "and door) the artifact states, and any person's words it rests "
            "on untagged or departs from unstated;",), "run-pipeline")
        # every challenge the work followed is pooled with the run's other
        # decisions, so the person whose words were overridden can see it
        self.assertAllIn(("every two-way door the author answered "
                          "(**Questions**), every challenge the work "
                          "followed and,",), "run-pipeline")

    def test_a_question_carries_what_an_informed_answer_needs(self):
        """V31-3: no question reaches a person without the decision, a
        scenario, each reading's consequences, its door and what makes it
        one-way, a recommendation with its confidence, evidence a reader can
        open and what favours it over the other readings, and what silence
        means; a part that says nothing about this question is missing. A
        stall's park names the parts that fit a choice among findings."""
        # v3.2, from a worked demonstration on two real questions: the
        # parts a person answers from come first and the words for checking
        # last; the scenario is traced once, through today's code, and each
        # reading says what users would see in it, so the two no longer
        # repeat each other; reversibility is back; and the no-answer line,
        # which the door already settles, gives way to what would change
        # the recommendation
        self.assertAllIn((
            "**Form**: numbered, under *Questions for a person* in its "
            "finder's file, complete and specific to it before a person sees "
            "it, in this order: the decision, in one line; a concrete "
            "scenario through today's code; the readings, plainest first, "
            "each an outcome the person might want, never a mechanism, with "
            "what users would see in that scenario, its cost, risk and "
            "reversibility; the finder's recommendation, with its "
            "confidence, evidence (a file and line, test, data or quote), "
            "what favours it over each other reading and what fact would "
            "change it; the door and its default, naming what makes it "
            "one-way; and the "
            "words it turns on, quoted with where said and their tag (a "
            "Hunch with what the code showed, a reopened Assent with what "
            "its giver was not shown), or the `escalate` class it needs.",
        ), "run-pipeline")
        text = self.core("run-pipeline")
        self.assertNotIn("and what happens if no one answers", text)
        self.assertNotIn("a concrete scenario, today and under each reading",
                         text)
        self.assertNotIn("in its finder's file: the question;", text)
        self.assertNotIn("never a mechanism; and what each changes", text)
        self.assertNotIn("in the form *Questions for a person* sets out",
                         text)

    def test_only_a_one_way_door_parks(self):
        """V31-4: a door is judged from the readings by one list, so a
        reviewer can check the routing. The project's `decisions:` classes
        decide schema, API and data choices, as every phase preset sets
        them; core adds only an outcome a person names left unmet or
        changed where users see it. A one-way door parks with the informed
        question; a two-way door is answered on its finder's recommendation,
        except that a person's Directive or chosen reading stands, and is
        pooled with the run's other decisions and put to the person without
        waiting, standing if no one answers."""
        # v3.2: three blind classifiers applying v3.1's test found every
        # material question one-way (a reading that changes an outcome
        # nearly always leaves it unmet somewhere), could not say from
        # whose reading "unmet" was judged, fired on an outcome unmet under
        # every reading, and left "users" undefined. The door is now judged
        # from the one reading that would stand, the default: a person's
        # words take it where they do, else the finder's recommendation.
        # Only a person answers a question whose default gives up an
        # outcome another reading meets, needs an `escalate` choice, or
        # does not exist because people's words take two readings.
        self.assertAllIn((
            "**Doors**: a question's default is the reading a person's "
            "Directive or chosen reading takes, else its finder's "
            "recommendation. Only a person answers a one-way door: one with "
            "no default (people's words take two readings), or whose default "
            "needs an `escalate` choice or leaves unmet an outcome another "
            "reading meets; when unsure, one-way. Others are two-way doors.",
            "**A two-way door parks nothing.** The author answers it by its "
            "default (*Doors*). The question joins the next park, else the "
            "MR, for the person to confirm or overturn; unanswered, the "
            "answer stands.",
            "emit one pooled `decision` outcome: every `record` checkpoint, "
            "every two-way door the author answered (**Questions**), every "
            "challenge the work followed and, when "
            "`decisions.pipeline-discretion` is `record`, every "
            "discretionary act.",
        ), "run-pipeline")
        text = self.core("run-pipeline")
        self.assertNotIn("**Every other question parks the step**", text)
        self.assertEqual(text.count("**Doors**"), 1)
        # one test, not a list and a gloss that disagree; no fixed list of
        # mechanisms that would override a phase's `agent` or `record`; and
        # no undefined "users" deciding the route, nor an outcome unmet
        # under every reading (v3.2)
        for gone in ("a stored schema or format", "a public API, data no "
                     "change could take back", "no user to tell",
                     "a named outcome users see", "differ in what users see",
                     "leaves such an outcome unmet",
                     "the author answering one assumes its answer"):
            self.assertNotIn(gone, text)
        # the route sits with the other question routes in step 4
        self.assertLess(text.index("- **Questions.**"),
                        text.index("**A two-way door parks nothing.**"))
        self.assertLess(text.index("**A two-way door parks nothing.**"),
                        text.index("- **Selection re-check.**"))
        # Doors builds on the outcomes materiality names
        self.assertLess(text.index("**Materially**"),
                        text.index("**Doors**"))


class TestPeopleOnTheMR(unittest.TestCase):
    """The v3.2 rules (docs/proposals/v3.md, *v3.2*): a person's review on
    the merge request is an input to the review loop. In the third trial
    run the panel approved, a human reviewer then posted two gaps and seven
    advisories, and the run said "No document of this run routes a
    person's MR note": nothing read it. On the attempt before, every gate
    approved and the human found four blocking issues. GLaDOS posts under
    a person's account, so what it posts is marked and anything unmarked
    is a person's. Pinned into the compiled cores that read and answer MR
    notes, with whitespace flattened.
    """

    @classmethod
    def setUpClass(cls):
        t = make_target(read(EXAMPLE))
        rc, out = install("direct", t)
        assert rc == 0, out
        cls.dir = t / "product-knowledge" / "glados"

    def core(self, name):
        return " ".join(read(self.dir / f"{name}.md").split())

    def assertAllIn(self, rules, name):
        text = self.core(name)
        for rule in rules:
            self.assertIn(rule, text, f"{name} lacks: {rule!r}")

    NOTES = (
        "## People on the merge request",
        # the account a note came from proves nothing: GLaDOS posts under a
        # person's, so the marker, at the start of the first line (a quote
        # of a GLaDOS note is still a person's), tells them apart; a role on
        # the project makes the words a person's, so a bot, a system note
        # or a passer-by on a public repository sets no criterion, and the
        # change's own author is under review, never a person giving it
        # criteria (fix round 1). Where the agents commit, push and post
        # under the owner's account, the MR and commits carry the owner's
        # name, so who wrote a change a run made is said outright: the owner
        # reviewing the agents' change is the case this rule exists for
        # (final round)
        "A note or reply on the merge request whose first line does not "
        "start with `(GLaDOS <workflow>)` is a person's when someone with a "
        "role on the project wrote it, whichever account posted it, unless "
        "they wrote the change. GLaDOS wrote a change its runs made, "
        "whatever name it carries. A system note or a bot's is no one's, "
        "and anyone else's is evidence.",
        # GitHub keeps a person's words in three lists, and the usual read
        # of the first misses inline review comments (fix round 1)
        "**Read each**, of every kind the platform (`platform:`) keeps: on "
        "GitHub, comments, reviews with their state, and inline review "
        "comments are three lists.",
        # an overturn or an instruction posted on the MR is what the work
        # received (L10); a tier the person gives stands, so "nothing
        # blocks" blocks nothing and a stated problem binds only as firmly
        # as they said it (fix round 1)
        "An instruction or answer in one is a criterion the work received, "
        "and each point a finding labelled as theirs, at the tier they give "
        "it whatever the scale says; with none given, a Directive or chosen "
        "reading the change does not meet is `blocking`, and any other "
        "point takes the scale's tier.",
        # no silent decline, and a panel cannot approve past a person
        "**Theirs to close.** A point is open until the change meets it or "
        "the author answers it on the MR in the *Challenge in the open* "
        "form, the only way the author declines or departs from one.",
        "Against a `blocking` point that answer is a question for that "
        "person: it closes only when the change meets it or they withdraw "
        "or waive it in their own words, never by approval, refutation or "
        "the author's reasons.",
        # a confirmation asked of someone else is theirs to give, not the
        # author's to answer (fix round 1)
        "One asking anyone but the author (a confirmation, a reopened "
        "answer) closes only when they answer.",
    )

    def test_the_loop_reads_and_answers_people_on_the_mr(self):
        for name in ("review-mr", "address-review"):
            with self.subTest(core=name):
                self.assertAllIn(self.NOTES, name)
                text = self.core(name)
                self.assertEqual(
                    text.count("## People on the merge request"), 1)
                # read at their tags: the tags travel with the rule
                self.assertEqual(text.count("*Directive* ("), 1)
                self.assertEqual(text.count("**Challenge in the open.**"), 1)

    def test_review_mr_carries_people_into_its_pass_and_decision(self):
        self.assertAllIn((
            # a review usually lands after the loop has used its cycles, so
            # a person's new point starts a new round (fix round 1); the
            # round restarts the bound only, and the cycle number runs on so
            # the open findings stay named (fix round 2)
            # the guard run quotes what it hands over, so the pass after
            # the fix does not start a second round for the same note
            # (final round)
            "A person's point no run of this workflow has quoted starts a "
            "new round of cycles: the record notes the cycle it follows. "
            "`review.cycle` is not reset, so open findings stay named.",
            # a point on an unchanged head is not ignored: it goes to the fix
            # half, whatever the last pass decided; a note with no point
            # (an approval, "LGTM") sends nothing (fix round 1)
            "there is nothing new to review: this run produces a `progress` "
            "outcome saying so and stops, handing any such point, quoted "
            "with its id, to address-review, whatever that pass decided "
            "(*People on the merge request*).",
            # read by id, not by time, and again before deciding: the trial's
            # human review landed while the pass ran (fix round 1)
            "Every pass quotes, with its id, each person's note no earlier "
            "pass quoted, listing them again before it decides, and names "
            "each person's point still open, which closes only as *People "
            "on the merge request* sets out.",
            # a one-way door posted after the MR opened waits for a person
            "a one-way question among them stays open, keeping the MR from "
            "review-clean, until a person answers it on the MR.",
            # the decision names everything step 4 says keeps the MR from
            # review-clean, so step 8 read alone cannot call it clean while
            # a one-way question waits on a person (final round)
            "the MR is review-clean, unless a one-way question step 4 "
            "carries is still open, which leaves it waiting on that person; "
            "the loop ends, once address-review has answered any person's "
            "point still open.",
            # the Goal points at the two places that end the loop instead of
            # restating an older, shorter condition (final round)
            "A dirty pass hands off to the address-review workflow, forming "
            "the loop review-mr ⇄ address-review; step 8 and "
            "address-review's handoff say when it ends.",
            # whether the loop runs again is said once, in address-review's
            # handoff: a fix pass that committed nothing ends it
            "never as its members; its handoff starts the next cycle.",
        ), "review-mr")
        self.assertNotIn("then re-enter this workflow for the next cycle",
                         self.core("review-mr"))
        self.assertNotIn("`review.cycle` to 0", self.core("review-mr"))
        for gone in ("A clean pass ends the loop",
                     "runs until every panelist approves",
                     "A person's point no pass has quoted"):
            self.assertNotIn(gone, self.core("review-mr"))

    def test_address_review_takes_people_points_as_its_work(self):
        self.assertAllIn((
            "Read every person's point open on the MR too. If neither demands "
            "changes or an answer, there is nothing to address",
            # answering without a commit leaves nothing to re-review
            "The loop continues until the MR is review-clean or the bound "
            "escalates; a pass that committed nothing ends it.",
            # a round is review-mr's to start; the bound check says where it
            # finds one (final round)
            "Check the cycle bound for the round review-mr's record notes, "
            "then run the review-mr workflow against the new HEAD.",
            # a human review has no synthesis, and that case stays stated
            "**When `review.verdicts` carries no synthesis** (an older "
            "record, a review a human wrote by hand)",
        ), "address-review")
        text = self.core("address-review")
        self.assertNotIn("If no verdict demands changes, there is nothing "
                         "to address", text)

    def test_everything_glados_posts_is_marked(self):
        """The reader rule is only as good as the writer rule: every core
        can post on an MR, mid-run too (address-review's replies), so the
        epilogue marks it, whatever a sink's config says, at the start, where
        a quote of it cannot pass for it."""
        for path in sorted(self.dir.glob("*.md")):
            if path.stem not in glados.CORES:
                continue
            with self.subTest(core=path.stem):
                text = self.core(path.stem)
                self.assertIn(
                    "Everything a run posts on a merge request, in any step, "
                    "starts with `(GLaDOS <workflow>)`, whatever a sink's "
                    "config says.", text)
                # the verdict comment's "lead with the verdict, no preamble"
                # makes room for the marker (final round)
                if "## Publishing a verdict" in text:
                    self.assertIn("Lead with the verdict, after `(GLaDOS "
                                  "<workflow>)`. No preamble", text)

    def test_commit_messages_meet_the_projects_checks_when_made(self):
        """The third trial run's messages broke the project's 80-column
        rule, enforced by a commit-msg hook its clones never installed, so
        CI went red after the push, when fixing a message costs a rewrite.
        Fresh clones are how agents usually run, and a clone carries no
        hooks."""
        for name in ("run-pipeline", "build-feature", "fix-bug",
                     "address-review"):
            with self.subTest(core=name):
                self.assertAllIn((
                    "a fresh evaluator's run of them on the same diff counts. "
                    "Install any commit-msg hook the project declares before "
                    "the first commit.",), name)


class TestSinkConfig(unittest.TestCase):
    """Sink bodies are freeform config the agent interprets, but a key that
    cannot possibly do anything must fail the install instead of resolving to
    a silent no-op, and a multi-line body must not tear apart the assembly
    report's table."""

    MULTILINE = (
        "sinks:\n"
        "  mr-comment:\n"
        "    grouping: aggregate\n"
        "    voice: |\n"
        "      Lead with the verdict.\n"
        "      One finding per paragraph | even with a pipe in it.\n"
        "\n"
        "      No praise, no emoji headers.\n"
    )

    def _manifest(self, extra=""):
        return read(EXAMPLE) + "\n" + extra

    def test_team_visible_rejected_on_builtin(self):
        # BUILTIN_SINKS fixes a built-in's visibility and _sink_is_team_visible
        # never reads the body for one, so accepting the key would install
        # clean and change nothing.
        t = make_target(self._manifest(
            "sinks:\n  mr-comment:\n    team-visible: false\n"))
        rc, out = install("direct", t)
        self.assertEqual(rc, 1, out)
        self.assertIn("mr-comment", out)
        self.assertIn("built-in", out)

    def test_team_visible_honored_on_a_declared_sink(self):
        # The same key on a sink the project owns is real config, not a no-op:
        # reject the built-in case without over-rejecting this one.
        t = make_target(self._manifest(
            "sinks:\n  audit-log:\n    team-visible: false\n"))
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("audit-log", report)
        self.assertIn("no (record-only)", report)

    def test_multiline_body_keeps_the_report_table_intact(self):
        t = make_target(self._manifest(self.MULTILINE))
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        report = read(t / ".glados" / "assembly-report.md")
        section = self._sinks_section(report)
        header = next(i for i, l in enumerate(section)
                      if l.startswith("| Sink |"))
        # The section's own prose must state the rule the epilogue implements,
        # in full: this sentence spans several string literals and a partial
        # edit leaves a grammatical-looking half-sentence behind.
        intro = " ".join(l for l in section[:header] if l.strip())
        self.assertIn("a bound sink that fails to receive its outcome escalates",
                      intro)
        self.assertNotIn("reaches no team-visible sink", intro)
        rows = [l for l in section[header:] if l.strip()]
        # A raw newline in a cell ends the ROW: the body's remaining lines
        # would land here as non-table text.
        for line in rows:
            self.assertTrue(line.startswith("|"),
                            f"torn table — stray line in the Sinks table: {line!r}")
        mr = [l for l in rows if l.startswith("| mr-comment ")]
        self.assertEqual(len(mr), 1, rows)
        self.assertIn("lines)", mr[0], "multi-line body must be summarized")
        self.assertNotIn("No praise", mr[0], "body must not be inlined")

    def test_compiled_core_escalates_on_a_failed_sink(self):
        # The compiled core is the artifact the agent actually reads; a bound
        # sink that fails must escalate, never downgrade to a warning because
        # some other sink got a copy.
        t = make_target()
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        core = read(t / "product-knowledge" / "glados" / "review-mr.md")
        self.assertIn("emit an `escalation`", core)
        self.assertNotIn("as a warning and continue", core)

    @staticmethod
    def _sinks_section(report: str) -> list:
        lines = report.splitlines()
        start = lines.index("## Sinks")
        out = []
        for line in lines[start + 1:]:
            if line.startswith("## "):
                break
            out.append(line)
        return out


class TestInstallVisibility(unittest.TestCase):
    """A checker that cannot see the thing it checks must say so, and a
    vendored tree must be able to re-install itself."""

    def test_check_fails_when_no_install_is_detectable(self):
        # Every install mode lands in a directory a project may gitignore, so
        # on a fresh CI clone "no install detected" is the shape of a repo
        # whose compiled artifacts never travel. Returning 0 there turns the
        # whole job into a pass that read nothing.
        t = make_target()
        rc, out = run_cli("check", "--target", t, "--source", REPO,
                          "--report-only")
        self.assertEqual(rc, 1, "report-only must still fail:\n" + out)
        self.assertIn("no GLaDOS install detected", out)
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, "enforcing mode must fail too:\n" + out)

    def test_check_passes_once_an_install_is_present(self):
        # The control: the same target, after an install, checks clean. The
        # failure above must come from invisibility, not from the manifest.
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        rc, out = run_cli("check", "--target", t, "--source", REPO,
                          "--report-only")
        self.assertEqual(rc, 0, out)

    def test_vendored_tree_can_reinstall_itself_with_sda(self):
        # `check` was self-contained but `install` was not: an sda: true repo
        # died with "pass --source <a full glados checkout>", so the one
        # command a consumer needs to pick up a re-vendor could not be run
        # from the repo it was vendored into.
        manifest = read(EXAMPLE).replace("sda: false", "sda: true")
        self.assertIn("sda: true", manifest)
        t = make_target(manifest)
        self.assertEqual(install("direct", t)[0], 0)
        vendored = t / ".glados" / "glados.py"
        self.assertTrue(vendored.is_file())
        proc = subprocess.run(
            [sys.executable, str(vendored), "install", "--mode", "direct",
             "--target", str(t)],
            capture_output=True, text=True)
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0,
                         "vendored install must need no --source:\n" + out)
        self.assertTrue((t / ".glados" / "docs" / "standards").is_dir(),
                        "the sda docs install reads must be vendored")


class TestDeliveryAndPanelContract(unittest.TestCase):
    """Contracts that only exist as compiled text. Assert on what the agent
    receives, not on the source file."""

    def _core(self, name):
        t = make_target(read(EXAMPLE))
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        return read(t / "product-knowledge" / "glados" / f"{name}.md")

    def test_escalation_about_delivery_has_a_floor(self):
        core = self._core("review-mr")
        self.assertIn("never itself escalated", core)
        self.assertIn("One escalation per run", core)

    def test_grouping_values_are_all_defined(self):
        # The manifest may set any of these; the epilogue defined only one,
        # so composing `aggregate` + `summary: false` literally yielded
        # "post nothing".
        core = self._core("review-mr")
        for value in ("`aggregate`", "`per-persona`", "`per-finding`"):
            self.assertIn(value, core)
        self.assertIn("always produces at least one comment", core)

    def test_address_review_gets_the_root_cause_vocabulary(self):
        # It uses "symptom patch" and cluster/member as terms of art; the
        # definitions have to travel with it.
        core = self._core("address-review")
        self.assertIn("symptom patch", core)
        self.assertIn("Does the finding set converge on one cause?", core)

    def test_address_review_states_the_no_synthesis_case(self):
        # Requiring a consolidated list with no clause for its absence is a
        # guess waiting to happen — older records and human reviews have no
        # synthesis at all.
        core = self._core("address-review")
        self.assertIn("no synthesis", core)

    def test_blocking_findings_are_refuted_before_the_tally(self):
        core = self._core("review-mr")
        self.assertIn("Refute before believing", core)
        self.assertIn("one fresh agent per blocking finding", core)
        for outcome in ("confirmed", "refuted", "unconfirmed"):
            self.assertIn(outcome, core)
        self.assertIn("never lowered by this step", core)

    def test_refutation_is_invoked_before_the_decision(self):
        # The module defining the stage is not enough: the compiler appends
        # module text after the numbered steps, so an agent reading the
        # workflow in order decides before it ever reaches the definition.
        # The CORE has to call it, in a step that precedes the decision.
        core = self._core("review-mr")
        call = core.index("Refute every `blocking` finding before counting it")
        self.assertLess(call, core.index("### 8. Decide"))
        self.assertLess(call, core.index("Refute before believing"),
                        "the call site must precede the definition")


class TestKernelRunRules(unittest.TestCase):
    """Run-lifecycle rules that exist only as compiled text: the nested-run
    marker stack (F2), pending MR delivery (F3), preset defaults (F4), the
    plugin path mapping (F4/F5), the standards-gate bound (F6d) and the
    evaluator's persona slot (F6e). Asserted on compiled output, with
    whitespace flattened so a re-wrap of the source does not break a test."""

    @classmethod
    def setUpClass(cls):
        cls.direct = make_target(read(EXAMPLE))
        rc, out = install("direct", cls.direct)
        assert rc == 0, out
        cls.plugin = make_plugin_target()
        rc, out = install("claude-plugin", cls.plugin)
        assert rc == 0, out

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    def _cores(self):
        cores = sorted((self.direct / "product-knowledge" / "glados").glob("*.md"))
        cores = [c for c in cores if c.stem in glados.CORES]
        self.assertEqual(len(cores), len(glados.CORES))
        return cores

    def _core(self, name):
        return self.flat(read(
            self.direct / "product-knowledge" / "glados" / f"{name}.md"))

    def test_aistudio_contract_matches_the_paste_kit(self):
        """The bundle's runtime contract said glados.yaml's values were
        inlined at compile time, while the paste kit's README says the live
        keys are not baked in and must be pasted. Both now say paste it,
        with the preset table the defaults come from."""
        t = make_target(read(EXAMPLE))
        rc, out = install("aistudio", t)
        self.assertEqual(rc, 0, out)
        kit = t / "glados" / "adapters" / "aistudio"
        bundle = self.flat(read(kit / "bundles" / "review-mr.aistudio.md"))
        self.assertNotIn("inlined at compile time", bundle)
        self.assertIn("You cannot read `glados.yaml` here. Only its "
                      "optimize-for sentence was compiled in", bundle)
        self.assertIn("ask for it rather than guess", bundle)
        self.assertIn("`.glados/presets.yaml`: ask for that file too", bundle)
        readme = self.flat(read(kit / "README.md"))
        self.assertIn("together with `.glados/presets.yaml`", readme)
        self.assertIn("the current `glados.yaml` and `.glados/presets.yaml`",
                      readme)

    def test_review_mr_takes_over_findings_posted_after_the_mr(self):
        """A pipeline step after open-mr posts its verdict and hands its
        blocking findings to review-mr; cycle 1 carries them, and one still
        open reaches address-review like a synthesis finding."""
        text = self._core("review-mr")
        self.assertIn("**Findings handed over with the MR.**", text)
        self.assertIn("cycle 1 carries them in the brief, each named and open "
                      "until this pass refutes or closes it", text)
        self.assertIn("joins the consolidated list in step 7 at its severity, "
                      "as a synthesis finding does", text)

    def test_every_core_pushes_and_pops_the_marker_stack(self):
        for core in self._cores():
            with self.subTest(core=core.stem):
                text = self.flat(read(core))
                self.assertIn("`.glados/runs/stack` lists every run in flight, "
                              "one filename per line, outermost first, and its "
                              "last line always equals `current`", text)
                # nesting is decided by who started the run, never by
                # whether a leftover record looks unfinished
                self.assertIn("**Nested run.** This run is nested only when a "
                              "workflow you are running in this session "
                              "started it as one of its own steps", text)
                self.assertIn("under `## Nested runs`", text)
                self.assertIn("**Fresh run.**", text)
                self.assertIn("Any other `current` or `stack` is stale, "
                              "whatever its record says", text)
                self.assertIn("note the stale filename(s) in this record",
                              text)
                self.assertIn("A run that resumes earlier work (run-epic "
                              "picking up its ticket table) is fresh too", text)
                self.assertNotIn("its epilogue has not finalized it", text)
                self.assertIn("pop this run off the marker stack: remove this "
                              "run's line from `.glados/runs/stack`; if lines "
                              "remain, write the last remaining line into "
                              "`.glados/runs/current`", text)
                self.assertIn("otherwise delete both `current` and `stack`", text)
                self.assertNotIn("unconditionally", text.split(
                    "## Before ending this run")[1])

    def test_nested_runs_work_under_the_outer_claim_and_row(self):
        text = self._core("plan-feature")
        self.assertIn("A nested run (step 1) adds no claim of its own", text)
        self.assertIn("works under that claim, which the outermost run clears",
                      text)
        self.assertIn("a run that is not nested (preamble step 1) appends the "
                      "single work-unit row for the whole unit of work", text)
        self.assertIn("A nested run does neither", text)
        self.assertIn("a nested plan's row would mark the whole feature done "
                      "early", text)

    def test_run_epic_tickets_are_their_own_unit_of_work(self):
        text = self._core("build-feature")
        self.assertIn("a ticket's build inside run-epic is a unit of work of "
                      "its own (its own branch and MR), so it records and "
                      "clears its own claim", text)
        self.assertIn("it appends the ticket's row and clears the ticket's "
                      "claim; the runs nested inside it do neither", text)

    def test_pending_mr_delivery_is_not_an_escalation(self):
        text = self._core("verify-feature")
        self.assertIn("**No MR yet is not a failed delivery.**", text)
        self.assertIn("record it in the run record under `## Pending MR "
                      "delivery`. This does not escalate.", text)
        self.assertIn("posts every pending MR item from its own record, from "
                      "the records of the runs nested inside it, and from a "
                      "parked run it resumed", text)
        self.assertIn('"no MR for this work; mr-comment delivery not applicable"',
                      text)
        # a parked unit of work has not ended: its items wait for the resume
        self.assertIn("A run that ends with its unit still waiting on a "
                      "person (step 3) has not ended it: its items stay "
                      "pending for the run that resumes the work and opens "
                      "the MR", text)
        # the existing guarantees survive
        self.assertIn("a verdict that never reached the MR leaves the change "
                      "looking unreviewed", text)
        self.assertIn("One escalation per run", text)
        self.assertIn("Once the MR exists, a post that fails is a failed "
                      "delivery", text)

    def test_pending_mr_items_post_before_review_and_get_committed(self):
        text = self._core("build-feature")
        self.assertIn("as soon as the MR is open, before handing the MR to "
                      "review (build-feature right after it opens the MR in "
                      "its step 5, before its self-review", text)
        # the end case is about the item's own work, not the whole unit
        self.assertIn("no MR exists for the work an item is about (run-epic's "
                      "backlog selection, a standalone plan)", text)
        self.assertIn("even if nested runs opened MRs for their own work", text)
        self.assertIn("Save again for any record update made in this step, "
                      "before step 6", text)
        self.assertNotIn("one more `chore(glados): record <workflow> run` "
                         "commit", text)
        self.assertNotIn("Commit these record updates like any other", text)

    def test_absent_keys_default_from_the_preset_table(self):
        for core in self._cores():
            with self.subTest(core=core.stem):
                text = self.flat(read(core))
                self.assertIn("## Reading glados.yaml", text)
                self.assertIn("take its default from the preset table, "
                              "`.glados/presets.yaml`", text)
                self.assertIn("the table's `baseline`, then the preset named "
                              "by the manifest's `phase:`, then the keys the "
                              "manifest sets explicitly", text)
                self.assertNotIn("**Plugin paths.**", text,
                                 "the plugin mapping is plugin-only")

    def test_plugin_maps_presets_and_personas_to_its_own_copies(self):
        guard = glados.PLUGIN_BOOTSTRAP_GUARD
        flat_guard = self.flat(guard)
        self.assertIn("when `.glados/presets.yaml` is missing, the preset "
                      "table is `src/kernel/presets/phases.yaml` there",
                      flat_guard)
        self.assertIn("when `.glados/personas/` is missing, the library "
                      "personas are `src/personas/` there", flat_guard)
        self.assertIn("two levels above this file", flat_guard)
        # the mapping names exactly two read-only files; run state is never
        # looked for in the plugin
        self.assertIn("Run records and the `.glados/runs/` markers always "
                      "live in this repo: create them here", flat_guard)
        self.assertNotIn("When a file the text names under `.glados/` is "
                         "missing", flat_guard)
        for core in sorted((self.plugin / "compiled" / "claude-plugin").glob("*.md")):
            with self.subTest(core=core.stem):
                text = read(core)
                self.assertTrue(text.startswith(guard), core.name)
                self.assertIn("## Reading glados.yaml", text)
        # the mapped files really are where the guard says, relative to the
        # plugin root (the repo root holds compiled/claude-plugin/)
        self.assertTrue((REPO / "src" / "kernel" / "presets" / "phases.yaml").is_file())
        self.assertTrue(any((REPO / "src" / "personas").glob("*.md")))

    def test_standards_gate_reruns_are_bounded(self):
        source = glados.Source(REPO)
        self.assertEqual(
            source.presets["baseline"]["params"]["standards-gate"]["max-cycles"], 3)
        self.assertIn("escalation", source.modules["standards-gate"]["emits"])
        text = self._core("implement-feature")
        # the bound's stop is Loop bounds' own rule, said once there
        self.assertIn("Each re-run of the gate on a corrected artifact is one "
                      "gate cycle, bounded by "
                      "`params.standards-gate.max-cycles` as *Loop bounds* "
                      "sets out", text)
        self.assertIn("On hitting a bound: stop, emit an `escalation` outcome "
                      "carrying the open findings and the cycle history, and "
                      "end the run", text)
        self.assertIn("A run enclosing this one (preamble step 1) stops too, "
                      "rather than advancing on an artifact the gate did not "
                      "pass", text)
        self.assertIn("| standards-gate re-runs per gated artifact | "
                      "`params.standards-gate.max-cycles` |", text)
        self.assertIn("## Loop bounds", text)
        # where another module already inlined Loop bounds, the gate's copy is
        # a pointer and the bound row is still in the document
        fix = self._core("fix-bug")
        self.assertIn("`params.standards-gate.max-cycles`", fix)
        self.assertEqual(fix.count("## Loop bounds"), 1, "one copy per document")

    def test_evaluator_brief_has_a_persona_slot(self):
        text = self._core("verify-feature")
        self.assertIn("| Personas to consult |", text)
        self.assertIn("`run.active-personas` (recorded by plan-feature); when "
                      "that key is absent, the default roster in "
                      "`params.review-panel.personas`", text)
        self.assertIn("`product-knowledge/personas/`, then the library personas "
                      "in `.glados/personas/`", text)
        self.assertIn("critique the change from that persona's mandate", text)


class TestPipelines(unittest.TestCase):
    """Project workflows (Part P): `steps:` + `pipelines:` in glados.yaml,
    run by the run-pipeline core. The rule set (V1-V10, W1-W2) is asserted
    in-process through check_pipelines; install, check, validate, doctor and
    the per-pipeline shims through the real CLI."""

    MINIMAL = ("glados: 2\nplatform: gitlab\nphase: {phase}\n"
               "branching:\n  feature: \"feat/<slug>\"\n"
               "  default-target: main\n")

    STEPS = (
        "steps:\n"
        "  architecture-review:\n"
        "    description: Audit structure against our layering rules\n"
        "    kind: gate\n"
        "    stage: speccing\n"
        "    audits: [shape, target-structure, spec-feature]\n"
        "  target-structure:\n"
        "    description: Describe the structure the refactor ends in\n"
        "    kind: produce\n"
        "    produces: spec\n"
        "    stage: speccing\n")

    PIPELINES = (
        "pipelines:\n"
        "  backend-feature:\n"
        "    description: A change to an endpoint or a schema\n"
        "    when: The change adds or alters an endpoint or a schema.\n"
        "    sequence:\n"
        "      - plan-feature\n"
        "      - shape\n"
        "      - architecture-review\n"
        "      - spec-feature\n"
        "      - implement-feature\n"
        "      - verify-feature\n"
        "      - open-mr\n"
        "      - self-review\n"
        "    step-options:\n"
        "      architecture-review:\n"
        "        review: fresh-agent\n"
        "  refactor:\n"
        "    description: Behavior-preserving restructuring\n"
        "    when: The goal is structural and no behavior may change.\n"
        "    sequence: [target-structure, architecture-review, "
        "implement-feature, verify-feature, open-mr]\n")

    BUILD_FEATURE_SHA = ("9785018be6559a32f6880ded7252240c6c7a177f0fa7b052"
                         "b7bc82bf053afcc9")
    FIX_BUG_SHA = ("669ebcf2caa27b0a2b99198f741ed9e2d9dd7722a13424b90f787ef"
                   "7996bc953")

    @classmethod
    def setUpClass(cls):
        cls.source = glados.Source(REPO)

    # -- helpers -------------------------------------------------------------

    def check(self, extra, phase="evolving", target=None):
        """check_pipelines over MINIMAL + ``extra``, in-process."""
        text = self.MINIMAL.format(phase=phase) + extra
        raw = glados.parse_yaml(text, "glados.yaml")
        r = glados.resolve_manifest(raw, self.source.presets, "glados.yaml")
        enabled = [c for c in glados.CORES
                   if c not in set(r.values.get("disabled-workflows") or [])]
        return glados.check_pipelines(self.source, r, enabled, target)

    def assertError(self, pc, *needles):
        joined = "\n".join(pc.errors)
        for needle in needles:
            self.assertIn(needle, joined, f"missing {needle!r} in:\n{joined}")

    def pipeline(self, sequence, options="", name="p"):
        return (f"pipelines:\n  {name}:\n    description: d\n    when: w\n"
                f"    sequence: [{', '.join(sequence)}]\n" + options)

    def project(self, extra=None, phase="evolving", bodies=None):
        """A target with MINIMAL + steps + pipelines and a body per step."""
        extra = self.STEPS + self.PIPELINES if extra is None else extra
        t = make_target(self.MINIMAL.format(phase=phase) + extra)
        for sid in (["architecture-review", "target-structure"]
                    if bodies is None else bodies):
            write(t / "product-knowledge" / "steps" / f"{sid}.md",
                  f"## What to check\n- {sid}\n")
        return t

    # -- the declarations that ship ------------------------------------------

    def test_valid_declarations_pass_and_rows_get_defaults(self):
        pc = self.check(self.STEPS + self.PIPELINES)
        self.assertEqual(pc.errors, [])
        self.assertEqual(pc.warnings, [])
        rows = {r["id"]: r for r in pc.pipelines["backend-feature"]["rows"]}
        self.assertEqual(rows["shape"]["review"], "in-context")
        self.assertEqual(rows["plan-feature"]["review"], "none")
        self.assertEqual(rows["architecture-review"]["review"], "fresh-agent")
        self.assertEqual(rows["architecture-review"]["modifier"], "required")
        self.assertEqual(rows["architecture-review"]["checkpoint"], "none")
        # V4: a gate audits the LATEST earlier step its audits: names
        self.assertEqual(rows["architecture-review"]["audits"], "shape")
        refactor = {r["id"]: r for r in pc.pipelines["refactor"]["rows"]}
        self.assertEqual(refactor["architecture-review"]["audits"],
                         "target-structure")
        # a produces: spec step satisfies implement-feature (no V3 error)
        self.assertEqual(refactor["target-structure"]["produces"], "spec")

    def test_example_blocks_validate(self):
        """The commented steps:/pipelines: blocks in glados.yaml.example,
        uncommented, are a valid declaration (and stay commented: presets
        cannot set what the example does not declare live)."""
        lines = read(EXAMPLE).splitlines()
        start = lines.index("# steps:")
        block = []
        for line in lines[start:]:
            if not line.startswith("#"):
                break
            block.append(line[2:] if line.startswith("# ") else line[1:])
        self.assertIn("pipelines:", block)
        raw = glados.load_manifest(EXAMPLE)
        self.assertNotIn("pipelines", raw)
        self.assertNotIn("steps", raw)
        self.assertIn("# pipeline-discretion:", read(EXAMPLE))
        pc = self.check("\n".join(block) + "\n")
        self.assertEqual(pc.errors, [])
        t = self.project("\n".join(block) + "\n",
                         bodies=["architecture-review"])
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("glados validate: OK", out)

    def test_guide_examples_validate(self):
        """The four example pipelines in docs/guides/pipelines.md are valid
        as written, and every YAML block in the guide parses."""
        guide = read(REPO / "docs" / "guides" / "pipelines.md")
        blocks = re.findall(r"```yaml\n(.*?)```", guide, re.S)
        self.assertGreater(len(blocks), 2)
        for block in blocks:
            glados.parse_yaml(block, "pipelines.md")
        # the first two snippets, copied together, are a first valid try
        self.assertIn("steps:", blocks[0])
        self.assertIn("pipelines:", blocks[1])
        first = blocks[0] + blocks[1]
        ids = list(glados.parse_yaml(first, "pipelines.md")["steps"])
        t = self.project(first, bodies=ids)
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("1 pipeline(s), 1 project step(s), 0 warning(s)", out)
        full = next(b for b in blocks
                    if "pipelines:" in b and "steps:" in b and "rfc:" in b)
        ids = list(glados.parse_yaml(full, "pipelines.md")["steps"])
        t = self.project(full, bodies=ids)
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("4 pipeline(s), 6 project step(s), 0 warning(s)", out)

    # -- V1-V10 --------------------------------------------------------------

    def test_v1_names_are_kebab_case_and_unique(self):
        self.assertError(self.check(
            "steps:\n  Bad_Id:\n    description: d\n    kind: produce\n"
            "    stage: planning\n"), "'Bad_Id' is not kebab-case")
        cases = [("review-mr", "is a GLaDOS workflow"),
                 ("mission", "is a v1 alias"),
                 ("shape", "is a built-in step"),
                 ("init", "is the Claude Code plugin's init skill"),
                 ("run-pipeline", "is the workflow that runs pipelines")]
        for name, why in cases:
            with self.subTest(name=name):
                pc = self.check(self.pipeline(["plan-feature"], name=name))
                self.assertError(pc, f"pipelines.{name}: '{name}' {why}")
        pc = self.check(
            "steps:\n  twin:\n    description: d\n    kind: produce\n"
            "    stage: planning\n" + self.pipeline(["twin"], name="twin"))
        self.assertError(pc, "share one namespace")

    def test_vocabulary_constants_agree(self):
        """The built-in contracts use only the closed artifact kinds, and
        V1 refuses every reserved name with the reason the table gives."""
        kinds = set(glados.ARTIFACT_KINDS)
        for sid, b in glados.BUILTIN_STEPS.items():
            with self.subTest(step=sid):
                self.assertLessEqual(set(b["needs"]), kinds)
                if b["produces"] is not None:
                    self.assertIn(b["produces"], kinds)
        self.assertLessEqual(set(glados.STEP_PRODUCES), kinds)
        for name, why in glados.RESERVED_STEP_NAMES.items():
            with self.subTest(name=name):
                pc = self.check(self.pipeline(["plan-feature"], name=name))
                self.assertError(pc, f"pipelines.{name}: '{name}' is {why}")

    def test_v1_collision_fails_the_install(self):
        t = make_target(read(EXAMPLE) + "\n" + self.pipeline(
            ["plan-feature"], name="fix-bug"))
        rc, out = install("claude", t)
        self.assertEqual(rc, 1, out)
        self.assertIn("pipelines.fix-bug: 'fix-bug' is a GLaDOS workflow", out)
        self.assertNotIn("Traceback", out)
        self.assertFalse((t / ".claude").exists(), "nothing may be emitted")

    def test_v2_sequences(self):
        self.assertError(self.check(
            "pipelines:\n  p:\n    description: d\n    when: w\n"
            "    sequence: []\n"), "pipelines.p.sequence: required and not empty")
        self.assertError(self.check(self.pipeline(["plan-feture"])),
                         "'plan-feture' is neither a built-in step")
        self.assertError(self.check(self.pipeline(
            ["plan-feature", "plan-feature"])), "'plan-feature' appears twice")
        self.assertError(self.check(
            "pipelines:\n  p:\n    description: d\n    when: w\n"
            "    sequence: plan-feature\n"),
            "pipelines.p.sequence: must be a list of step ids")
        self.assertError(self.check(
            "pipelines:\n  p:\n    description: d\n    when: w\n"
            "    sequence:\n      - plan-feature: x\n"),
            "item 1 is a mapping ('plan-feature: x')")
        # a typo'd id does not cascade into "nothing produces a spec"
        pc = self.check(self.pipeline(["spec-featur", "implement-feature"]))
        self.assertNotIn("needs a spec", "\n".join(pc.errors))

    def test_v3_needs_come_from_an_earlier_step(self):
        self.assertError(self.check(self.pipeline(
            ["implement-feature", "open-mr"])),
            "'implement-feature' needs a spec, but no step before it in the "
            "sequence produces one")
        self.assertError(self.check(self.pipeline(
            ["plan-feature", "self-review"])), "'self-review' needs an MR")
        optional_spec = ("    step-options:\n      spec-feature:\n"
                         "        modifier: optional\n        when: w\n")
        seq = ["plan-feature", "spec-feature", "implement-feature"]
        self.assertError(self.check(self.pipeline(seq, optional_spec)),
                         "'implement-feature' needs a spec, but its only "
                         "earlier producer 'spec-feature' is optional")
        # an advisory step always runs, so the same holds for it
        advisory = optional_spec + ("      implement-feature:\n"
                                    "        modifier: advisory\n")
        self.assertError(self.check(self.pipeline(seq, advisory)),
                         "its only earlier producer 'spec-feature' is optional")
        # an optional consumer of an optional producer is fine
        both = optional_spec + ("      implement-feature:\n"
                                "        modifier: optional\n        when: w\n")
        self.assertEqual(self.check(self.pipeline(seq, both)).errors, [])

    def test_v4_a_gate_audits_an_earlier_step(self):
        pc = self.check(self.STEPS + self.pipeline(
            ["architecture-review", "plan-feature", "shape"]))
        self.assertError(pc, "gate 'architecture-review' audits [shape, "
                             "target-structure, spec-feature], but none of "
                             "them runs before it")
        opt = ("    step-options:\n      shape:\n        modifier: optional\n"
               "        when: w\n")
        pc = self.check(self.STEPS + self.pipeline(
            ["plan-feature", "shape", "architecture-review"], opt))
        self.assertError(pc, "can audit only optional steps before it")
        self.assertError(self.check(
            "steps:\n  g:\n    description: d\n    kind: gate\n"
            "    stage: speccing\n" + self.pipeline(["g"])),
            "steps.g.audits: a gate must name the steps it may audit")

    def test_prose_keys_of_the_wrong_type_are_named(self):
        """`when: true` or `description: 5` was reported as missing
        ("required"), which sent the user looking for a key they wrote."""
        pc = self.check(
            "steps:\n  s:\n    description: [a, b]\n    kind: produce\n"
            "    stage: planning\n"
            "pipelines:\n  a:\n    description: 5\n    when: true\n"
            "    sequence: [s]\n    step-options:\n      s:\n"
            "        modifier: optional\n        when: false\n")
        self.assertError(
            pc,
            "steps.s.description: must be one line of prose — got [a, b], "
            "which YAML reads as a list; quote it if you meant text",
            "pipelines.a.description: must be one line of prose — got 5",
            "pipelines.a.when: must be one line of prose — got true, which "
            "YAML reads as a number or a boolean",
            "pipelines.a.step-options.s.when: must be one line of prose — got "
            "false")
        joined = "\n".join(pc.errors)
        self.assertNotIn("description: required", joined)
        self.assertNotIn("when: required", joined)
        # absent is still "required"
        self.assertError(self.check(
            "pipelines:\n  a:\n    sequence: [plan-feature]\n"),
            "pipelines.a.description: required", "pipelines.a.when: required")

    def test_v5_closed_keys_and_values(self):
        cases = [
            ("steps:\n  s:\n    description: d\n    kidn: produce\n"
             "    stage: planning\n", ["steps.s.kidn: unknown key",
                                      "steps.s.kind: required"]),
            ("steps:\n  s:\n    kind: produce\n    stage: later\n",
             ["steps.s.description: required", "'later' is not a stage"]),
            ("steps:\n  s:\n    description: d\n    kind: gate\n"
             "    stage: speccing\n    audits: [shape]\n    produces: spec\n",
             ["only a produce step declares what it produces"]),
            ("steps:\n  s:\n    description: d\n    kind: produce\n"
             "    stage: speccing\n    audits: [shape]\n",
             ["only a gate audits"]),
            ("steps:\n  s:\n    description: d\n    kind: produce\n"
             "    stage: speccing\n    produces: mr\n",
             ["'mr' is not an artifact a step can declare"]),
            (self.pipeline(["plan-feature"]).replace("    when: w\n",
                                                     "    whne: w\n"),
             ["pipelines.p.whne: unknown key", "pipelines.p.when: required"]),
            (self.pipeline(["plan-feature"], "    step-options:\n"
                           "      plan-feature:\n        modifer: optional\n"),
             ["step-options.plan-feature.modifer: unknown key"]),
            (self.pipeline(["plan-feature"], "    step-options:\n"
                           "      shape:\n        review: none\n"),
             ["'shape' is not in this pipeline's sequence"]),
            (self.pipeline(["plan-feature"], "    step-options:\n"
                           "      plan-feature:\n        when: w\n"),
             ["only an optional step takes when:"]),
            (self.pipeline(["plan-feature"], "    step-options:\n"
                           "      plan-feature:\n        modifier: optional\n"),
             ["modifier: optional needs a when:"]),
            (self.pipeline(["plan-feature"], "    step-options:\n"
                           "      plan-feature:\n        modifier: maybe\n"
                           "        checkpoint: always\n"),
             ["modifier: 'maybe'", "checkpoint: 'always'"]),
            (self.pipeline(["plan-feature"], "    step-options:\n"
                           "      plan-feature:\n        review: bogus\n"),
             ["step-options.plan-feature.review: 'bogus' — one of none | "
              "in-context | fresh-agent"]),
        ]
        for extra, needles in cases:
            with self.subTest(needles=needles[0]):
                self.assertError(self.check(extra), *needles)

    def test_v6_review_only_where_the_step_takes_it(self):
        self.assertError(self.check(self.pipeline(
            ["plan-feature", "spec-feature", "implement-feature"],
            "    step-options:\n      implement-feature:\n"
            "        review: none\n")),
            "implement-feature takes no review: setting")
        mr = ["plan-feature", "spec-feature", "implement-feature", "open-mr",
              "self-review"]
        for sid in ("open-mr", "self-review"):
            with self.subTest(step=sid):
                self.assertError(self.check(self.pipeline(
                    mr, f"    step-options:\n      {sid}:\n"
                        f"        review: in-context\n")),
                    f"{sid} takes no review: setting")
        self.assertError(self.check(self.pipeline(
            ["plan-feature", "spec-feature"],
            "    step-options:\n      spec-feature:\n"
            "        review: in-context\n")),
            "spec-feature takes only none | fresh-agent")
        self.assertEqual(self.check(self.pipeline(
            ["plan-feature", "spec-feature"],
            "    step-options:\n      spec-feature:\n"
            "        review: fresh-agent\n      plan-feature:\n"
            "        review: in-context\n")).errors, [])

    def test_v7_step_bodies_exist_without_frontmatter(self):
        t = tmpdir("glados-steps-")
        extra = self.STEPS + self.PIPELINES
        # no target: no body check
        self.assertEqual(self.check(extra).errors, [])
        self.assertError(self.check(extra, target=t),
                         "steps.architecture-review: no body at "
                         "product-knowledge/steps/architecture-review.md")
        write(t / "product-knowledge" / "steps" / "architecture-review.md",
              "---\nkind: gate\n---\n\n## What to check\n")
        write(t / "product-knowledge" / "steps" / "target-structure.md",
              "## What to produce\n")
        pc = self.check(extra, target=t)
        self.assertError(pc, "architecture-review.md starts with YAML "
                             "frontmatter")
        self.assertNotIn("target-structure", "\n".join(pc.errors))
        # a case mismatch fails on every platform, not only on Linux CI
        c = tmpdir("glados-steps-case-")
        write(c / "product-knowledge" / "steps" / "Architecture-Review.md",
              "## What to check\n")
        write(c / "product-knowledge" / "steps" / "target-structure.md",
              "## What to produce\n")
        self.assertError(self.check(extra, target=c),
                         "steps.architecture-review: the body is "
                         "product-knowledge/steps/Architecture-Review.md, but "
                         "the step needs product-knowledge/steps/"
                         "architecture-review.md")
        # install checks bodies too (with the target), and names the file
        p = self.project(bodies=["target-structure"])
        rc, out = install("direct", p)
        self.assertEqual(rc, 1, out)
        self.assertIn("no body at product-knowledge/steps/"
                      "architecture-review.md", out)

    def test_v8_nested_workflows_must_be_enabled(self):
        pc = self.check("disabled-workflows: [spec-feature]\n"
                        + self.pipeline(["plan-feature", "spec-feature"]))
        self.assertError(pc, "'spec-feature' is a workflow disabled-workflows "
                             "turns off")
        pc = self.check(self.pipeline(["plan-feature"]), phase="sunset")
        self.assertEqual(pc.errors, [])
        self.assertTrue(any("run-pipeline is disabled" in w
                            for w in pc.warnings), pc.warnings)

    def test_v9_pipeline_discretion_is_a_decision_class(self):
        source = self.source
        self.assertEqual(
            source.presets["baseline"]["decisions"]["pipeline-discretion"],
            "record")
        self.assertEqual(
            source.presets["baseline"]["params"]["pipeline"]["max-cycles"], 8)
        for phase, want in (("nascent", "agent"), ("evolving", "agent"),
                            ("production", "record"), ("sunset", "record")):
            self.assertEqual(
                source.presets[phase]["decisions"]["pipeline-discretion"],
                want, phase)
        t = make_target(self.MINIMAL.format(phase="production")
                        + "decisions:\n  pipeline-discretion: sometimes\n")
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("decisions.pipeline-discretion: 'sometimes' is not a "
                      "decision class", out)
        # laxer than the phase needs a confession, like any decision
        t = make_target(self.MINIMAL.format(phase="production")
                        + "decisions:\n  pipeline-discretion: agent\n")
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("relaxation-acknowledged", out)

    def test_v10_description_fits_250_characters(self):
        long = "x" * 251
        pc = self.check(self.pipeline(["plan-feature"]).replace(
            "description: d", f"description: {long}"))
        self.assertError(pc, "251 characters — keep it to 250 or fewer")
        ok = self.check(self.pipeline(["plan-feature"]).replace(
            "description: d", "description: " + "x" * 250))
        self.assertEqual(ok.errors, [])

    def test_warnings_w1_w2(self):
        pc = self.check(
            "steps:\n  spare:\n    description: d\n    kind: produce\n"
            "    stage: planning\n"
            + self.pipeline(["plan-feature", "spec-feature",
                             "implement-feature", "open-mr"], name="quick"))
        self.assertEqual(pc.errors, [])
        self.assertIn("pipelines.quick: opens an MR with no verification "
                      "step; the MR description will say so", pc.warnings)
        self.assertIn("steps.spare: declared but no pipeline uses it — add "
                      "it to a sequence or remove it", pc.warnings)
        # validate prints them and still passes; install prints them too
        t = self.project(
            "steps:\n  spare:\n    description: d\n    kind: produce\n"
            "    stage: planning\n"
            + self.pipeline(["plan-feature", "spec-feature",
                             "implement-feature", "open-mr"], name="quick"),
            bodies=[])
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("glados: warning: pipelines.quick: opens an MR", out)
        self.assertIn("2 warning(s)", out)
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertIn("glados: warning: steps.spare: declared", out)
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("- pipelines.quick: opens an MR with no verification "
                      "step", report)

    def test_warnings_survive_a_failed_install(self):
        # an unused step is often the other half of a misspelt sequence id
        extra = ("steps:\n  arch-review:\n    description: d\n"
                 "    kind: produce\n    stage: planning\n"
                 + self.pipeline(["arch-reveiw"]))
        rc, out = install("direct", self.project(extra, bodies=[]))
        self.assertEqual(rc, 1, out)
        self.assertIn("'arch-reveiw' is neither a built-in step", out)
        self.assertIn("glados: warning: steps.arch-review: declared but no "
                      "pipeline uses it", out)

    def test_malformed_blocks_never_crash(self):
        bad = [
            "pipelines:\n  - backend-feature\n",
            "steps: scalar\n",
            "steps:\n  s: scalar\n",
            self.pipeline(["plan-feature"], "    step-options:\n"
                          "      - plan-feature\n"),
            self.pipeline(["plan-feature"], "    step-options:\n"
                          "      plan-feature: scalar\n"),
            "pipelines:\n  p:\n    description: [a, b]\n    when: 3\n"
            "    sequence: [1, 2]\n",
        ]
        for extra in bad:
            with self.subTest(extra=extra[:40]):
                pc = self.check(extra)
                self.assertTrue(pc.errors, extra)
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        write(t / "glados.yaml", read(EXAMPLE) + "\n" + bad[0])
        rc, out = run_cli("check", "--target", t, "--source", REPO,
                          "--report-only")
        self.assertEqual(rc, 0, out)
        self.assertIn("pipelines: must be a mapping", out)
        self.assertNotIn("Traceback", out)
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Traceback", out)

    # -- presets, phases, hash ------------------------------------------------

    def test_preset_setting_pipelines_rejected(self):
        for key in ("pipelines", "steps"):
            with self.subTest(key=key):
                src = make_doctored_source()
                presets = src / "src" / "kernel" / "presets" / "phases.yaml"
                text = read(presets).replace(
                    "nascent:\n", f"nascent:\n  {key}:\n    x:\n"
                                  f"      description: d\n", 1)
                presets.write_text(text, encoding="utf-8", newline="\n")
                rc, out = install("direct", make_target(), source=src)
                self.assertEqual(rc, 1, out)
                self.assertIn(f"preset 'nascent' sets '{key}'", out)
                self.assertIn("the team's own declaration, not a phase "
                              "default", out)
                self.assertNotIn("Traceback", out)

    def test_sunset_disables_run_pipeline(self):
        t = self.project(phase="sunset")
        rc, out = install("claude", t)
        self.assertEqual(rc, 0, out)
        owned = t / ".claude" / "commands" / "glados"
        self.assertFalse((owned / "run-pipeline.md").exists())
        shim = read(owned / "backend-feature.md")
        self.assertIn("run-pipeline, the workflow that runs it, is disabled",
                      shim)
        self.assertNotIn("read and follow", shim)
        self.assertIn("run-pipeline is disabled", out)
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("**run-pipeline is disabled**", report)
        # sunset disabled it, not a disabled-workflows: line the manifest
        # does not have: shim, warning and report name the preset
        flat = " ".join(shim.split())
        self.assertIn("is disabled by the sunset phase preset (glados.yaml "
                      "sets no `disabled-workflows:`", flat)
        self.assertNotIn("in this project's glados.yaml", flat)
        self.assertIn("disabled by the sunset phase preset", " ".join(out.split()))
        self.assertIn("disabled** by the sunset phase preset", report)
        # an explicit list is named as such
        t2 = self.project(self.STEPS + self.PIPELINES
                          + "disabled-workflows: [run-pipeline]\n")
        rc, out = install("claude", t2)
        self.assertEqual(rc, 0, out)
        shim = " ".join(read(t2 / ".claude" / "commands" / "glados" /
                             "backend-feature.md").split())
        self.assertIn("is disabled in this project's glados.yaml "
                      "(`disabled-workflows:`)", shim)

    def test_hash_moves_on_names_and_descriptions_only(self):
        raw = glados.parse_yaml(self.MINIMAL.format(phase="evolving")
                                + self.STEPS + self.PIPELINES, "glados.yaml")
        base = glados.structural_hash(raw)
        self.assertEqual(
            glados.structural_projection(raw)["pipelines"],
            {"backend-feature": "A change to an endpoint or a schema",
             "refactor": "Behavior-preserving restructuring"})

        def edited(fn):
            copy = json.loads(json.dumps(raw))
            fn(copy)
            return glados.structural_hash(copy)

        self.assertEqual(base, edited(
            lambda m: m["pipelines"]["refactor"]["sequence"].pop()))
        self.assertEqual(base, edited(
            lambda m: m["pipelines"]["refactor"].update(when="other")))
        self.assertEqual(base, edited(lambda m: m.pop("steps")))
        self.assertNotEqual(base, edited(
            lambda m: m["pipelines"]["refactor"].update(description="new")))
        self.assertNotEqual(base, edited(
            lambda m: m["pipelines"].update(extra={"description": "d"})))
        # the same through check: a sequence edit keeps it passing, a
        # description edit makes the compile stale
        t = self.project()
        self.assertEqual(install("direct", t)[0], 0)
        gy = t / "glados.yaml"
        write(gy, read(gy).replace("      - self-review\n", ""))
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        write(gy, read(gy).replace("Behavior-preserving restructuring",
                                   "Restructuring that keeps behavior"))
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("stale compile", out)

    # -- shims -----------------------------------------------------------------

    def test_shims_per_script_mode_and_cleanup(self):
        modes = {
            "claude": (".claude/commands/glados/backend-feature.md",
                       ".claude/commands/glados/run-pipeline.md",
                       "/glados:run-pipeline backend-feature <brief>"),
            "direct": ("product-knowledge/glados/backend-feature.md",
                       "product-knowledge/glados/run-pipeline.md", None),
            "gemini": (".gemini/commands/glados/backend-feature.toml",
                       ".gemini/commands/glados/run-pipeline.toml",
                       "/glados:run-pipeline backend-feature <brief>"),
            "antigravity": (".agents/workflows/glados-backend-feature.md",
                            ".agents/workflows/glados-run-pipeline.md",
                            "/glados-run-pipeline backend-feature <brief>"),
            "pi": (".pi/prompts/glados-backend-feature.md",
                   ".pi/prompts/glados-run-pipeline.md",
                   "/glados-run-pipeline backend-feature <brief>"),
        }
        for mode, (shim, runner, invoke) in modes.items():
            with self.subTest(mode=mode):
                t = self.project()
                rc, out = install(mode, t)
                self.assertEqual(rc, 0, out)
                self.assertTrue((t / runner).is_file(), runner)
                text = read(t / shim)
                if mode == "gemini":
                    data = tomllib.loads(text)
                    self.assertEqual(data["description"],
                                     "A change to an endpoint or a schema")
                    text = data["prompt"]
                elif mode != "direct":
                    fm, _ = glados.split_frontmatter(text, shim)
                    self.assertEqual(fm["description"],
                                     "A change to an endpoint or a schema")
                self.assertIn(f"read and follow `{runner}`", text)
                self.assertIn("with `backend-feature` as the first word of "
                              "its arguments", text)
                if invoke:
                    self.assertIn(invoke, text)
                if mode == "pi":
                    self.assertEqual(text.count("${ARGUMENTS"), 1)
                    self.assertIn(
                        "ignore its closing `## Invocation arguments` "
                        "section, which is an unexpanded placeholder when "
                        "the file is read", " ".join(text.split()))
                self.assertTrue((t / shim.replace("backend-feature",
                                                  "refactor")).is_file())
                rc, out = run_cli("check", "--target", t, "--source", REPO)
                self.assertEqual(rc, 0, out)
                # removing a pipeline removes its shim at the next install
                gy = t / "glados.yaml"
                text = read(gy)
                write(gy, text[:text.index("  refactor:\n")])
                self.assertEqual(install(mode, t)[0], 0)
                self.assertFalse((t / shim.replace("backend-feature",
                                                   "refactor")).exists(),
                                 f"{mode}: removed pipeline's shim lingers")
                self.assertTrue((t / shim).is_file())

    def test_no_shims_in_plugin_or_aistudio(self):
        t = self.project()
        rc, out = install("aistudio", t)
        self.assertEqual(rc, 0, out)
        names = [p.name for p in all_files(t / "glados")]
        self.assertFalse(any("backend-feature" in n for n in names), names)
        p = make_plugin_target()
        write(p / "glados.yaml.example",
              read(EXAMPLE) + "\n" + self.STEPS + self.PIPELINES)
        rc, out = install("claude-plugin", p)
        self.assertEqual(rc, 0, out)
        self.assertFalse((p / "skills" / "backend-feature").exists())
        self.assertFalse(
            (p / "compiled" / "claude-plugin" / "backend-feature.md").exists())
        self.assertTrue(
            (p / "compiled" / "claude-plugin" / "run-pipeline.md").is_file())

    # -- validate --------------------------------------------------------------

    def test_validate_lists_errors_and_writes_nothing(self):
        t = self.project(self.pipeline(["implement-feature"], name="Bad")
                         + "steps:\n  s:\n    kind: nope\n", bodies=[])
        before = {f.relative_to(t).as_posix() for f in all_files(t)}
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("glados validate: FAIL", out)
        self.assertIn("  - pipelines.Bad: 'Bad' is not kebab-case", out)
        self.assertIn("  - steps.s.kind: 'nope' is not a step kind", out)
        self.assertNotIn("Traceback", out)
        after = {f.relative_to(t).as_posix() for f in all_files(t)}
        self.assertEqual(before, after, "validate must write nothing")
        # no manifest at all: a clean failure, not a traceback
        rc, out = run_cli("validate", "--target", tmpdir(), "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("no manifest", out)
        self.assertNotIn("Traceback", out)

    def test_validate_runs_from_a_plugin_layout_with_no_install(self):
        """A plugin-only repo has no .glados/: validate runs from the
        plugin's own bin/glados.py, which finds src/ beside bin/."""
        plugin = tmpdir("glados-plugin-root-")
        shutil.copytree(REPO / "bin", plugin / "bin",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO / "src", plugin / "src")
        shutil.copyfile(EXAMPLE, plugin / "glados.yaml.example")
        t = self.project()
        self.assertFalse((t / ".glados").exists())
        proc = subprocess.run(
            [sys.executable, str(plugin / "bin" / "glados.py"), "validate",
             "--target", str(t)], capture_output=True, text=True)
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, out)
        self.assertIn("2 pipeline(s), 2 project step(s)", out)
        self.assertFalse((t / ".glados").exists(), "validate wrote files")
        # and a vendored .glados/glados.py validates without --source
        self.assertEqual(install("direct", t)[0], 0)
        proc = subprocess.run(
            [sys.executable, str(t / ".glados" / "glados.py"), "validate",
             "--target", str(t)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_vendored_toolchain_ignores_a_project_src_kernel(self):
        """A project with its own src/kernel/ (an OS kernel's sources) made
        the vendored .glados/glados.py resolve the project root as the
        GLaDOS source, so validate failed, and run-pipeline runs validate
        before its first step."""
        t = self.project()
        self.assertEqual(install("direct", t)[0], 0)
        write(t / "src" / "kernel" / "sched.c", "int main(void) { return 0; }\n")
        for cmd in ("validate", "check"):
            with self.subTest(cmd=cmd):
                proc = subprocess.run(
                    [sys.executable, str(t / ".glados" / "glados.py"), cmd,
                     "--target", str(t)], capture_output=True, text=True)
                out = proc.stdout + proc.stderr
                self.assertEqual(proc.returncode, 0, out)
                self.assertNotIn("missing kernel source", out)

    # -- report, scaffold, doctor, guard ---------------------------------------

    def test_assembly_report_lists_pipelines(self):
        t = self.project()
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("## Pipelines", report)
        self.assertIn("### `backend-feature`", report)
        self.assertIn("| 3 | architecture-review | project gate | required | "
                      "fresh-agent | none | `shape` |", report)
        self.assertIn("| 2 | shape | library step | required | in-context | "
                      "none |  |", report)
        self.assertIn("### Project steps", report)
        self.assertIn("| target-structure | produce | speccing | spec |  | "
                      "`product-knowledge/steps/target-structure.md` |", report)
        self.assertIn("| params.pipeline.max-cycles | 8 | (baseline) |", report)
        # no declarations, no section
        t2 = make_target()
        self.assertEqual(install("direct", t2)[0], 0)
        self.assertNotIn("## Pipelines",
                         read(t2 / ".glados" / "assembly-report.md"))

    def test_scaffold_and_doctor_cover_the_steps_dir(self):
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        self.assertTrue(
            (t / "product-knowledge" / "steps" / ".gitkeep").exists())
        write(t / "CODEOWNERS", "/glados.yaml @maintainers\n")
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("product-knowledge/steps/", out,
                         "no steps in use: nothing to report")
        p = self.project()
        # no CODEOWNERS at all: the none-found line names the steps dir too
        rc, out = run_cli("doctor", "--target", p, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("CODEOWNERS: none found — consider one covering "
                      "glados.yaml and product-knowledge/steps/", out)
        write(p / "CODEOWNERS", "/glados.yaml @maintainers\n")
        rc, out = run_cli("doctor", "--target", p, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("has no pattern found covering product-knowledge/steps/",
                      out)
        write(p / "CODEOWNERS",
              "/glados.yaml @maintainers\n/product-knowledge/ @maintainers\n")
        rc, out = run_cli("doctor", "--target", p, "--source", REPO)
        self.assertIn("covers product-knowledge/steps/", out)
        # patterns that name the directory's files, or float to any depth
        cover = glados._codeowners_cover
        gdir = "product-knowledge/steps/"
        for pattern in ("/product-knowledge/steps/*.md", "**/steps/",
                        "steps/", "product-knowledge/**"):
            with self.subTest(pattern=pattern):
                self.assertTrue(cover(f"{pattern} @a\n", gdir))
        for pattern in ("*", "/steps/", "docs/steps/", "/glados.yaml",
                        "/product-knowledge/stepsx/"):
            with self.subTest(pattern=pattern):
                self.assertFalse(cover(f"{pattern} @a\n", gdir))

    def test_plugin_guard_names_pipelines_and_the_toolchain(self):
        flat = " ".join(glados.PLUGIN_BOOTSTRAP_GUARD.split())
        self.assertIn("any project workflows and steps (`pipelines:`, "
                      "`steps:`) and any canon (`canon:`) govern this run",
                      flat)
        self.assertIn("when `.glados/glados.py` is missing, the toolchain is "
                      "`bin/glados.py` there", flat)
        self.assertTrue((REPO / "bin" / "glados.py").is_file())

    # -- compiled text ---------------------------------------------------------

    def test_run_pipeline_compiled_rules(self):
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        text = " ".join(read(t / "product-knowledge" / "glados" /
                             "run-pipeline.md").split())
        for rule in (
            # selection
            "Record `pipeline: <name> (selected by: <rule>)`",
            "never a silent fallback",
            "A defect report goes to fix-bug",
            # validate first, from the GLaDOS that compiled this document
            "Run `glados.py validate --target .` from the GLaDOS that "
            "compiled this document",
            "never improvise around it",
            # the step table, written before anything runs
            "`# | step | kind | modifier | review | checkpoint | status | "
            "artifact | result | note`",
            "Before any step runs, write the step table into the run record",
            "no markdown checkboxes",
            # pinned inputs
            "`git hash-object`", "gating inputs changed mid-run",
            # modifiers and the bound
            "| `required` | always |", "| `optional` | when the agent judges",
            "| `advisory` | always |", "`waived` by a named person",
            "`params.pipeline.max-cycles`",
            # checkpoint: save the process files, commit the code and push
            # before waiting, park when unattended, and the park keeps MR
            # items pending
            "`human`: save first (**Commits**), commit any working diff a "
            "step left uncommitted, and push the branch",
            "A refusal, with the person's reasons, is a blocking finding",
            "mark the row `parked`",
            # a park has not finished its unit: the epilogue's rule, cited
            "and end the run, which has not finished its unit of work "
            "(*Before ending this run*, steps 3 and 5)",
            # resume: the parked pipeline, its table, and its pins
            "(selected by: resume)",
            "compares its fresh pins with the parked run's",
            # a code-changing pipeline is on its branch before its first step
            "When the caller already put this run on a working branch "
            "(run-epic does), stay on it",
            # a modifier never softens a stop
            "It never softens a stop",
            # no verdict before an MR exists; after it, findings go to one
            "Gates and reviews that run before open-mr publish no `verdict` "
            "outcome",
            "its blocking findings start no revise loop",
            "This holds on every way the run ends",
            # the no-Python checklist names the closed key sets
            "a step takes only `description`, `kind` and `stage` (all "
            "required)",
            # the library steps
            "Never write stub files to the branch",
            "No verification step ran in this pipeline.",
            "as *No MR yet is not a failed delivery* (step 5 of *Before "
            "ending this run*) sets out",
            "## Persona pass", "## Fresh-agent design review",
        ):
            self.assertIn(rule, text)
        self.assertIn("A run that ends with its unit of work still waiting "
                      "on a person has not finished it: run-pipeline "
                      "parking a step or resuming a park that has no "
                      "approval or answer yet, and run-epic stopping with "
                      "only parked tickets left", text,
                      "the epilogue owns the parked rule")
        # said once: run-pipeline no longer restates the claim, row and
        # pending-item consequences of a park
        self.assertNotIn("the parked-run rule in step 3", text)
        self.assertNotIn("the claim stays, no work-unit row is appended",
                         text)
        self.assertEqual(text.count("## Verdicts and finding severities"), 1)
        for rule in (
            # rule 1 is a person's choice only: run-epic hands over its row
            "| 1 | A person invoked this run, and the first word of their "
            "arguments names a pipeline",
            # a park is resumed from its own branch, pinned against the target
            "fetch that branch and check it out first, whatever branch this "
            "run started on",
            "check the approval or answer as **Resume** in step 4 sets "
            "out before step 2",
            "emit one `escalation` naming the branch, this run's record, the "
            "artifact paths and the approval needed",
            "`git rev-parse <target>:<path>` after a fetch",
            "With no approval or answer yet, say so in the record and end "
            "the run there, running no step and copying no table",
            # an in-session wait is resumable too
            "If a person invoked the run, mark the row `parked` in that "
            "save",
            # post-MR findings: posted at once, then handed to review-mr
            "delivered to its bound sinks when the step ends, not at the end "
            "of the run",
            # a one-way question a post-MR step posts has a reader, so the
            # MR cannot go review-clean with the door unanswered (fix round 1)
            "handing it the blocking findings and one-way questions of every "
            "verdict a step after open-mr posted, each named, as still open",
            # the hand-off keys on an MR having been opened, not on the
            # sequence listing open-mr (an optional open-mr can be skipped)
            "When this run, or the parked run it resumed, opened an MR",
            "When no MR was opened, the artifacts in the record are the "
            "deliverable",
            # one rule for every end with no MR: the work stays on the
            # branch; the record and artifacts its escalation names are on
            # the ledger, saved before any outcome is published (v3.2)
            "A run on its own branch that ends with no MR, a park included, "
            "leaves its work there for a human: it commits any working diff, "
            "pushes, and says so in the record.",
            # a gate with no persona seated is still audited
            "With no persona seated, this agent does the audit itself "
            "against the body",
        ):
            self.assertIn(rule, text)
        # one hand-off rule, stated once (step 5), not in each fragment
        self.assertNotIn("### Hand off", text)
        self.assertNotIn("for review-mr and address-review to settle", text)

    # -- the configuration a run obeys is pinned (B2) ------------------------

    def effective(self, t, *extra, source=REPO):
        """The digest `effective-config` prints for target ``t``."""
        rc, out = run_cli("effective-config", "--target", t, "--source",
                          source, *extra)
        self.assertEqual(rc, 0, out)
        found = re.search(r"glados effective-config: ([0-9a-f]{64})", out)
        self.assertTrue(found, out)
        return found.group(1)

    @staticmethod
    def blob(t, rel):
        return subprocess.run(["git", "hash-object", str(t / rel)],
                              capture_output=True, text=True).stdout.strip()

    def test_a_run_pins_the_configuration_in_effect(self):
        """glados.yaml's blob is not the configuration a run obeys: a bound
        or a decision class it leaves out comes from the preset table, so
        the run pins the digest of the layered result too, in one rule."""
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        text = " ".join(read(t / "product-knowledge" / "glados" /
                             "run-pipeline.md").split())
        self.assertIn("record the git blob SHA (`git hash-object`) of "
                      "`glados.yaml` and of each step body used, and the "
                      "digest of the configuration in effect that "
                      "`glados.py effective-config --target .` prints", text)
        self.assertIn("(without Python, the preset table's blob SHA)", text)
        self.assertIn("(`git rev-parse <target>:<path>` after a fetch, and "
                      "`effective-config --ref <target>`)", text)
        self.assertEqual(text.count("Pin the gating inputs"), 1)
        self.assertEqual(text.count("effective-config"), 3)
        # a configuration the command refuses is no pin to run under
        self.assertIn("Re-check them, in the working tree, before each step "
                      "and before finishing. A change means an `escalation` "
                      "(\"gating inputs changed mid-run\") and a stop; so does "
                      "an `effective-config` that fails or prints no digest, "
                      "naming what it printed.", text)

    def test_an_inherited_bound_or_decision_right_moves_the_pin(self):
        """A preset change that alters a run's bounds or decision rights
        leaves glados.yaml's blob as it was and moves the digest, from the
        vendored table or, with no .glados/ (the plugin), the toolchain's
        own. A change that alters nothing (a comment) leaves it alone."""
        t = self.project()
        self.assertEqual(install("direct", t)[0], 0)
        table = t / ".glados" / "presets.yaml"
        original = read(table)
        manifest_blob = self.blob(t, "glados.yaml")
        pinned = self.effective(t)
        evolving = original.index("\nevolving:")
        for label, edited in (
                ("baseline bound", original.replace(
                    "      max-cycles: 8\n", "      max-cycles: 20\n")),
                ("phase decision class", original[:evolving]
                 + original[evolving:].replace(
                     "    pipeline-discretion: agent\n",
                     "    pipeline-discretion: escalate\n", 1))):
            with self.subTest(change=label):
                self.assertNotEqual(edited, original)
                write(table, edited)
                self.assertEqual(self.blob(t, "glados.yaml"), manifest_blob)
                self.assertNotEqual(self.effective(t), pinned)
        write(table, "# a comment changes nothing a run obeys\n" + original)
        self.assertEqual(self.effective(t), pinned)
        # a bound the table makes unenforceable is refused, not pinned
        write(table, original.replace("      max-cycles: 8\n",
                                      "      max-cycles: \"8\"\n"))
        rc, out = run_cli("effective-config", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("params.pipeline.max-cycles: must be a whole number", out)
        self.assertNotIn("Traceback", out)
        # no .glados/: the plugin's own table, which an update can change
        plugin_side = self.project()
        src = make_doctored_source()
        before = self.effective(plugin_side, source=src)
        presets = src / "src" / "kernel" / "presets" / "phases.yaml"
        write(presets, read(presets).replace("      max-cycles: 8\n",
                                             "      max-cycles: 20\n"))
        self.assertNotEqual(self.effective(plugin_side, source=src), before)

    def test_the_run_table_must_bound_every_loop_it_runs(self):
        """validate resolves against the toolchain's table, but a run reads
        .glados/presets.yaml, and effective-config, the gate run-pipeline
        runs on that table, skipped an absent or null bound: a table with
        no params.pipeline.max-cycles (or a null review-panel bound) printed
        a digest to pin. Every bound a compiled workflow references must
        resolve there, and a table out of shape is named, not a traceback."""
        t = self.project()
        self.assertEqual(install("direct", t)[0], 0)
        table = t / ".glados" / "presets.yaml"
        original = read(table)
        bound = "      max-cycles: 8\n"
        self.assertEqual(original.count(bound), 1)
        evolving = original.index("\nevolving:")
        pipeline_ns = re.search(r"^    pipeline:\n(?:(?:      .*| *#.*)?\n)*",
                                original, re.M).group(0)
        baseline = re.search(r"^baseline:\n(?:(?:[ #].*)?\n)*", original,
                             re.M).group(0)
        for label, edited, needle in (
                ("null", original.replace(bound, "      max-cycles:\n"),
                 "`params.pipeline.max-cycles` but the resolved manifest has "
                 "no value"),
                ("line deleted", original.replace(bound, ""),
                 "`params.pipeline.max-cycles` but the resolved manifest has "
                 "no value"),
                ("namespace removed", original.replace(pipeline_ns, ""),
                 "`params.pipeline.max-cycles` but the resolved manifest has "
                 "no value"),
                ("phase bound null", original[:evolving]
                 + original[evolving:].replace("      max-cycles: 5\n",
                                               "      max-cycles:\n", 1),
                 "`params.review-panel.max-cycles` but the resolved manifest "
                 "has no value"),
                ("baseline not a mapping", original.replace(
                    baseline, "baseline: 5\n\n"),
                 "presets.yaml: 'baseline:' must be a mapping"),
                ("phase not a mapping", original[:evolving] + "\nevolving: 5\n"
                 + original[original.index("\nproduction:"):],
                 "presets.yaml: 'evolving:' must be a mapping"),
                ("params not a mapping", original[:evolving]
                 + "\nevolving:\n  params: 5\n"
                 + original[original.index("\nproduction:"):],
                 "presets.yaml (phase:evolving): params: must be a mapping")):
            with self.subTest(table=label):
                self.assertNotEqual(edited, original)
                write(table, edited)
                rc, out = run_cli("effective-config", "--target", t,
                                  "--source", REPO)
                self.assertEqual(rc, 1, out)
                self.assertIn(needle, out)
                self.assertNotRegex(out, r"[0-9a-f]{64}")
                self.assertNotIn("Traceback", out)
        write(table, original)
        self.effective(t)

    def test_a_resumed_run_takes_the_targets_configuration(self):
        """--ref reads glados.yaml and the preset table as the branch the
        work targets has them, so a bound the target changed while the work
        was parked is a changed pin, though the parked checkout still has
        the old table."""
        t = self.project()
        self.assertEqual(install("direct", t)[0], 0)

        def git(*a):
            p = subprocess.run(["git", "-C", str(t), *a],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)

        git("init", "-q")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        git("checkout", "-q", "-b", "main")
        git("add", "-A")
        git("commit", "-q", "-m", "chore: install glados")
        git("branch", "feat/parked")
        parked = self.effective(t)
        self.assertEqual(self.effective(t, "--ref", "main"), parked)
        table = t / ".glados" / "presets.yaml"
        write(table, read(table).replace("      max-cycles: 8\n",
                                         "      max-cycles: 20\n"))
        git("commit", "-q", "-am", "chore: raise the pipeline bound")
        on_main = self.effective(t)
        git("checkout", "-q", "feat/parked")
        self.assertEqual(self.effective(t), parked)
        self.assertEqual(self.effective(t, "--ref", "main"), on_main)
        self.assertNotEqual(on_main, parked)
        for ref, needle in (("no-such-branch", "not a commit"),
                            ("main~1^{tree}", "not a commit")):
            with self.subTest(ref=ref):
                rc, out = run_cli("effective-config", "--target", t,
                                  "--source", REPO, "--ref", ref)
                self.assertEqual(rc, 1, out)
                self.assertIn(needle, out)
                self.assertNotIn("Traceback", out)
        # the target's manifest is read even where the checkout has none
        git("rm", "-q", "glados.yaml")
        git("commit", "-q", "-m", "chore: drop the manifest")
        self.assertEqual(self.effective(t, "--ref", "main"), on_main)
        rc, out = run_cli("effective-config", "--target", t, "--source",
                          REPO, "--ref", "HEAD")
        self.assertEqual(rc, 1, out)
        self.assertIn("no glados.yaml", out)
        self.assertNotIn("Traceback", out)

    def test_run_epic_assigns_pipelines(self):
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        text = " ".join(read(t / "product-knowledge" / "glados" /
                             "run-epic.md").split())
        self.assertIn("`id | depends-on | pipeline | holder | status`", text)
        self.assertIn("run the run-pipeline workflow for the ticket, handing "
                      "it the ticket's row (its pipeline included) as caller "
                      "context, never the pipeline name as an argument; a "
                      "`build-feature` row runs the build-feature workflow "
                      "instead", text)
        self.assertIn("only a pipeline whose sequence contains `open-mr`, "
                      "and not as `optional`, qualifies", text)
        # a disabled run-pipeline (preset or explicit) means build-feature
        self.assertIn("(only when `glados.yaml` declares `pipelines:` and "
                      "run-pipeline is enabled)", text)
        self.assertIn("With run-pipeline in the effective `disabled-workflows` "
                      "(the phase preset's list included), every ticket gets "
                      "`build-feature`", text)
        # a parked ticket resumes on its own branch, and the run that
        # stops on parked tickets keeps the epic's claim
        self.assertIn("a parked ticket resumes on the branch its row notes",
                      text)
        self.assertIn("note the parked branch and record the park's "
                      "escalation names", text)
        self.assertIn("it keeps its claim and appends no work-unit row", text)
        self.assertIn("is never overwritten", text)
        self.assertIn("`awaiting-approval:<step>`", text)
        self.assertIn("no row may still be `awaiting-approval`", text)
        # agent choices are marked, so a re-check may switch only those
        self.assertIn("Write a pipeline you chose as `<name> (agent)`", text)
        # only parked tickets left: end the run, never loop
        self.assertIn("end this run with a `progress` outcome listing each "
                      "parked row and the approval or answer it waits for",
                      text)
        self.assertIn("Never loop over the queue again within one run", text)

    def test_build_feature_and_fix_bug_sources_unchanged(self):
        """Maintainer decision: customization adds pipelines and steps; the
        two fixed workflows stay byte-for-byte as they were (LF-normalized
        sha256 of their source on main before this release)."""
        import hashlib
        for name, want in (("build-feature", self.BUILD_FEATURE_SHA),
                           ("fix-bug", self.FIX_BUG_SHA)):
            data = (REPO / "src" / "workflows" / f"{name}.md").read_bytes()
            got = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
            self.assertEqual(got, want, f"src/workflows/{name}.md changed")


class TestCanon(unittest.TestCase):
    """Canon (Part C): `canon:` in glados.yaml, checked by check_canon
    (in-process) and by install, check, validate and doctor (the real CLI).
    The consult instruction lives in vocabulary/canon.md, included only by
    the cores that consult canon; digests are project files the compiler
    never copies."""

    MINIMAL = TestPipelines.MINIMAL

    CANON = (
        "canon:\n"
        "  clean-architecture:\n"
        "    source: \"Robert C. Martin, Clean Architecture (2017)\"\n"
        "    url: https://example.com/clean-architecture\n"
        "    digest: product-knowledge/canon/clean-architecture.md\n"
        "    applies-to: [plan-feature, spec-feature, review-mr]\n"
        "    seats: [philosophy, architect]\n"
        "  domain-driven-design:\n"
        "    source: \"Eric Evans, Domain-Driven Design (2003)\"\n"
        "    digest: product-knowledge/canon/domain-driven-design.md\n")

    # A string that exists only inside a digest, so finding it anywhere the
    # compiler wrote means digest content leaked into an installed file.
    MARKER = "zebra-digest-marker-7731"

    CONSULT_CORES = ["plan-feature", "spec-feature", "verify-feature",
                     "review-mr", "review-codebase", "brunch", "run-pipeline"]

    @classmethod
    def setUpClass(cls):
        cls.source = glados.Source(REPO)

    # -- helpers -------------------------------------------------------------

    def check(self, extra, target=None, phase="evolving"):
        """check_canon over MINIMAL + ``extra``, in-process."""
        raw = glados.parse_yaml(self.MINIMAL.format(phase=phase) + extra,
                                "glados.yaml")
        r = glados.resolve_manifest(raw, self.source.presets, "glados.yaml")
        return glados.check_canon(self.source, r, target)

    def assertError(self, cc, *needles):
        joined = "\n".join(cc.errors)
        for needle in needles:
            self.assertIn(needle, joined, f"missing {needle!r} in:\n{joined}")

    def entry(self, body, name="work"):
        return (f"canon:\n  {name}:\n    source: \"A Work\"\n"
                f"    digest: product-knowledge/canon/{name}.md\n" + body)

    def digest(self, name, retrieved=None, drafted="source", words=40):
        retrieved = retrieved or datetime.date.today().isoformat()
        body = " ".join(["word"] * words)
        return (f"---\ncanon: {name}\nversion: \"1\"\n"
                f"retrieved: {retrieved}\ndrafted-from: {drafted}\n---\n\n"
                f"# Work\n\n<!-- guidance that doctor does not count -->\n\n"
                f"## dependency-rule\n\n{self.MARKER} {body}\n\n"
                f"**Ask:** q?\n\n**Here, specifically:** here.\n")

    def project(self, manifest=None, digests=("clean-architecture",
                                              "domain-driven-design")):
        t = make_target(manifest if manifest is not None
                        else read(EXAMPLE) + "\n" + self.CANON)
        for name in digests:
            write(t / "product-knowledge" / "canon" / f"{name}.md",
                  self.digest(name))
        return t

    # -- the declaration ---------------------------------------------------------

    def test_valid_block_passes_with_defaults_applied(self):
        cc = self.check(self.CANON)
        self.assertEqual(cc.errors, [])
        ca = cc.entries["clean-architecture"]
        self.assertEqual(ca["applies-to"],
                         ["plan-feature", "spec-feature", "review-mr"])
        self.assertEqual(ca["seats"], ["philosophy", "architect"])
        self.assertFalse(ca["default-applies-to"])
        ddd = cc.entries["domain-driven-design"]
        self.assertEqual(ddd["applies-to"], glados.CANON_DEFAULT_APPLIES_TO)
        self.assertEqual(ddd["seats"], ["philosophy"])
        self.assertTrue(ddd["default-seats"])
        self.assertEqual(glados.CANON_DEFAULT_APPLIES_TO,
                         ["plan-feature", "shape", "spec-feature",
                          "verify-feature", "review-mr"])
        self.assertEqual(glados.CANON_CONSULT_POINTS,
                         glados.CANON_DEFAULT_APPLIES_TO
                         + ["review-codebase", "brunch"])
        # no block, no findings
        self.assertEqual(self.check("").errors, [])
        self.assertEqual(self.check("canon:\n").errors, [])

    def test_shape_errors_are_named(self):
        cases = [
            (self.entry("    seat: [architect]\n"),
             "canon.work.seat: unknown key"),
            ("canon:\n  work:\n    digest: product-knowledge/canon/w.md\n",
             "canon.work.source: required"),
            ("canon:\n  work:\n    source: \"W\"\n",
             "canon.work.digest: required"),
            ("canon:\n  Clean_Arch:\n    source: \"W\"\n"
             "    digest: product-knowledge/canon/w.md\n",
             "'Clean_Arch' is not kebab-case"),
            ("canon:\n  work: scalar\n",
             "canon.work: must be a mapping with source and digest"),
            ("canon: [a, b]\n", "not a list"),
            ("canon: text\n", "canon: must be a mapping of name -> entry"),
            (self.entry("    url: [a]\n"), "canon.work.url: must be"),
        ]
        for extra, needle in cases:
            with self.subTest(needle=needle):
                self.assertError(self.check(extra), needle)

    def test_a_list_shaped_block_is_rejected(self):
        """`- name: ...` items parse as a list of mappings (F6a), the
        commonest wrong shape for a block keyed by name."""
        cc = self.check("canon:\n  - clean-architecture:\n"
                        "      source: \"W\"\n"
                        "      digest: product-knowledge/canon/w.md\n")
        self.assertError(cc, "canon: must be a mapping keyed by each work's "
                             "name, not a list")

    def test_digest_path_must_stay_in_the_repo(self):
        for path in ("/etc/passwd", "C:/canon/w.md", "C:\\\\canon\\\\w.md",
                     "~/canon/w.md", "../outside.md",
                     "product-knowledge/../../outside.md",
                     "https://example.com/w.md", "file:///etc/passwd"):
            with self.subTest(path=path):
                cc = self.check("canon:\n  work:\n    source: \"W\"\n"
                                f"    digest: \"{path}\"\n")
                self.assertTrue(any("canon.work.digest:" in e
                                    for e in cc.errors), cc.errors)
        # a URL is named as one, and a drive letter keeps its own message
        for url in ("https://example.com/w.md", "file:///etc/passwd"):
            self.assertIn("is a URL", glados.canon_digest_problem(url))
            self.assertIn("put the address under url:",
                          glados.canon_digest_problem(url))
        self.assertIn("is an absolute path",
                      glados.canon_digest_problem("C:/canon/w.md"))
        self.assertEqual(glados.canon_digest_problem(
            "product-knowledge/canon/../canon/w.md"), None)
        self.assertIn("names the repo root",
                      glados.canon_digest_problem("product-knowledge/.."))
        # a directory is an error once the project is known
        t = make_target(self.MINIMAL.format(phase="evolving"))
        (t / "product-knowledge" / "canon" / "w.md").mkdir(parents=True)
        cc = self.check(self.entry("").replace("work.md", "w.md"), target=t)
        self.assertError(cc, "is a directory")

    def dir_link(self, link, to):
        """A directory symlink, or on Windows without the privilege a
        junction, which needs none; skips when neither can be made."""
        try:
            os.symlink(to, link, target_is_directory=True)
            return
        except (OSError, NotImplementedError):
            pass
        if os.name == "nt":
            proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link),
                                   str(to)], capture_output=True)
            if proc.returncode == 0:
                return
        self.skipTest("this platform makes neither symlinks nor junctions")

    def test_digest_symlink_out_of_the_repo_is_rejected(self):
        t = make_target(self.MINIMAL.format(phase="evolving"))
        outside = tmpdir()
        write(outside / "work.md", "secret\n")
        link = t / "product-knowledge" / "canon" / "work.md"
        link.parent.mkdir(parents=True)
        try:
            os.symlink(outside / "work.md", link)
        except (OSError, NotImplementedError):
            # no file symlinks here: link the canon directory itself
            link.parent.rmdir()
            self.dir_link(link.parent, outside)
        self.assertTrue(link.is_file())
        self.assertError(self.check(self.entry(""), target=t),
                         "resolves outside the repo")
        lines = glados._canon_doctor_lines(
            t, {"canon": {"work": {"digest":
                                   "product-knowledge/canon/work.md"}}})
        self.assertIn("resolves outside the repo", lines[1])

    def test_a_digest_symlink_loop_is_reported_never_raised(self):
        """Python 3.10 to 3.12 raise RuntimeError resolving a loop; check
        and doctor report it by name and keep going."""
        t = make_target(self.MINIMAL.format(phase="evolving"))
        canon = t / "product-knowledge" / "canon"
        canon.mkdir(parents=True)
        self.dir_link(canon / "loop", canon / "x")
        self.dir_link(canon / "x", canon / "loop")
        write(canon / "good.md", self.digest("good"))
        self.assertEqual(install("direct", t)[0], 0)
        manifest = ("canon:\n"
                    "  loop:\n    source: \"L\"\n"
                    "    digest: product-knowledge/canon/loop\n"
                    "  good:\n    source: \"G\"\n"
                    "    digest: product-knowledge/canon/good.md\n")
        cc = self.check(manifest, target=t)
        self.assertEqual(len(cc.errors), 1, cc.errors)
        self.assertTrue(cc.errors[0].startswith(
            "canon.loop.digest: product-knowledge/canon/loop"), cc.errors)
        # 3.10-3.12 name the loop; 3.13 resolves no further, and the
        # is-a-file check names it instead
        self.assertTrue("symlink loop" in cc.errors[0], cc.errors)
        lines = glados._canon_doctor_lines(
            t, glados.parse_yaml(manifest, "glados.yaml"))
        self.assertEqual(len(lines), 3, lines)
        self.assertIn("- loop: product-knowledge/canon/loop", lines[1])
        self.assertIn("(run check for details)", lines[1])
        self.assertIn("- good: product-knowledge/canon/good.md ok", lines[2])
        write(t / "glados.yaml", read(EXAMPLE) + "\n" + manifest)
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("symlink loop", out)
        self.assertNotIn("Traceback", out)
        rc, out = run_cli("check", "--target", t, "--source", REPO,
                          "--report-only")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Traceback", out)

    def test_a_digest_path_that_matches_only_by_case_is_a_warning(self):
        """At any depth: a case-insensitive checkout opens it silently, and
        Linux CI would report it missing."""
        t = make_target(self.MINIMAL.format(phase="evolving"))
        write(t / "product-knowledge" / "canon" / "w.md", self.digest("w"))
        for declared in ("product-knowledge/canon/W.md",
                         "Product-Knowledge/Canon/w.md"):
            with self.subTest(declared=declared):
                cc = self.check("canon:\n  w:\n    source: \"W\"\n"
                                f"    digest: {declared}\n", target=t)
                self.assertEqual(cc.errors, [])
                self.assertEqual(cc.warnings, [
                    f"canon.w.digest: the path on disk is "
                    f"product-knowledge/canon/w.md, but the entry names "
                    f"{declared} — match the case (a case-sensitive "
                    f"checkout, such as Linux CI, will not find it)"])
        cc = self.check("canon:\n  w:\n    source: \"W\"\n"
                        "    digest: product-knowledge/canon/w.md\n",
                        target=t)
        self.assertEqual((cc.errors, cc.warnings), ([], []))

    def test_applies_to_names_consult_points_or_declared_steps(self):
        for point in glados.CANON_CONSULT_POINTS:
            with self.subTest(point=point):
                self.assertEqual(self.check(self.entry(
                    f"    applies-to: [{point}]\n")).errors, [])
        cc = self.check(self.entry("    applies-to: [implement-feature]\n"))
        self.assertError(cc, "'implement-feature' is not a consult point")
        self.assertError(self.check(self.entry("    applies-to: []\n")),
                         "canon.work.applies-to: empty")
        self.assertError(self.check(self.entry(
            "    applies-to:\n      - plan-feature: x\n")),
            "item 1 is a mapping")
        # a declared project step is a consult point; a pipeline is not
        steps = TestPipelines.STEPS + TestPipelines.PIPELINES
        self.assertEqual(self.check(steps + self.entry(
            "    applies-to: [architecture-review, shape]\n")).errors, [])
        cc = self.check(steps + self.entry(
            "    applies-to: [backend-feature]\n"))
        self.assertError(cc, "'backend-feature' is a pipeline, not a "
                             "consult point")
        # with no steps: declared, a step id is just unknown
        self.assertError(self.check(self.entry(
            "    applies-to: [architecture-review]\n")),
            "'architecture-review' is not a consult point")

    def test_seats_name_lenses_or_personas(self):
        for seat in glados.STANDING_LENSES + ["architect", "data-modeler"]:
            with self.subTest(seat=seat):
                self.assertEqual(self.check(self.entry(
                    f"    seats: [{seat}]\n")).errors, [])
        self.assertError(self.check(self.entry("    seats: []\n")),
                         "canon.work.seats: empty")
        # with no project in view an unknown name may be a project persona
        self.assertEqual(self.check(self.entry(
            "    seats: [domain-expert]\n")).errors, [])
        t = make_target(self.MINIMAL.format(phase="evolving"))
        cc = self.check(self.entry("    seats: [domain-expert]\n"), target=t)
        self.assertError(cc, "'domain-expert' is neither a standing lens")
        write(t / "product-knowledge" / "personas" / "domain-expert.md",
              "---\ntype: review\n---\n# Domain expert\n")
        cc = self.check(self.entry("    seats: [domain-expert]\n"), target=t)
        self.assertNotIn("domain-expert", "\n".join(cc.errors))
        write(t / "product-knowledge" / "personas" / "Ops-Lead.md", "x\n")
        cc = self.check(self.entry("    seats: [ops-lead]\n"), target=t)
        self.assertError(cc, "match the file's case")

    def test_a_missing_digest_is_a_warning_not_an_error(self):
        t = self.project(digests=("clean-architecture",))
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertIn("glados: warning: canon.domain-driven-design.digest: "
                      "product-knowledge/canon/domain-driven-design.md does "
                      "not exist yet", out)
        self.assertNotIn("canon.clean-architecture.digest", out)
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("does not exist yet", out)
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        # in-process: no target, no filesystem check
        self.assertEqual(self.check(self.CANON).warnings, [])

    def test_install_check_and_validate_reject_a_bad_block(self):
        bad = self.CANON.replace("seats: [philosophy, architect]",
                                 "seats: [philosophy, architekt]")
        t = self.project(read(EXAMPLE) + "\n" + bad)
        rc, out = install("direct", t)
        self.assertEqual(rc, 1, out)
        self.assertIn("canon.clean-architecture.seats: 'architekt' is "
                      "neither a standing lens", out)
        self.assertNotIn("Traceback", out)
        self.assertFalse((t / ".glados").exists(), "nothing may be emitted")
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1, out)
        self.assertIn("  - canon.clean-architecture.seats:", out)
        # check --report-only and doctor never crash on any malformed shape
        good = self.project()
        self.assertEqual(install("direct", good)[0], 0)
        for broken in ("canon: [a]\n", "canon:\n  w: 3\n",
                       "canon:\n  - w:\n      digest: /x\n"):
            with self.subTest(broken=broken):
                write(good / "glados.yaml", read(EXAMPLE) + "\n" + broken)
                rc, out = run_cli("check", "--target", good, "--source",
                                  REPO, "--report-only")
                self.assertEqual(rc, 0, out)
                self.assertIn("canon", out)
                self.assertNotIn("Traceback", out)
                rc, out = run_cli("doctor", "--target", good, "--source",
                                  REPO)
                self.assertEqual(rc, 0, out)
                self.assertNotIn("Traceback", out)

    def test_preset_setting_canon_rejected(self):
        src = make_doctored_source()
        presets = src / "src" / "kernel" / "presets" / "phases.yaml"
        text = read(presets).replace(
            "nascent:\n", "nascent:\n  canon:\n    x:\n      source: s\n", 1)
        presets.write_text(text, encoding="utf-8", newline="\n")
        rc, out = install("direct", make_target(), source=src)
        self.assertEqual(rc, 1, out)
        self.assertIn("preset 'nascent' sets 'canon'", out)
        self.assertIn("not a phase default", out)
        self.assertNotIn("Traceback", out)
        self.assertIn("canon", glados.EXPLICIT_ONLY_KEYS)
        self.assertIn("canon", glados.KNOWN_MANIFEST_KEYS)
        # the example keeps its block commented, so presets cannot set it
        self.assertNotIn("canon", glados.load_manifest(EXAMPLE))

    def test_example_block_validates(self):
        """The commented canon: block in glados.yaml.example, uncommented,
        is a valid declaration."""
        lines = read(EXAMPLE).splitlines()
        start = lines.index("# canon:")
        block = []
        for line in lines[start:]:
            if not line.startswith("#"):
                break
            block.append(line[2:] if line.startswith("# ") else line[1:])
        text = "\n".join(block) + "\n"
        self.assertEqual(self.check(text).errors, [])
        t = self.project(read(EXAMPLE) + "\n" + text,
                         digests=("clean-architecture",))
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("0 warning(s)", out)

    def test_guide_examples_parse_and_validate(self):
        guide = read(REPO / "docs" / "guides" / "canon.md")
        blocks = re.findall(r"```yaml\n(.*?)```", guide, re.S)
        self.assertGreaterEqual(len(blocks), 2)
        for block in blocks:
            glados.parse_yaml(block, "canon.md")
        self.assertIn("canon:", blocks[0])
        self.assertEqual(self.check(blocks[0]).errors, [])
        t = self.project(read(EXAMPLE) + "\n" + blocks[0])
        rc, out = run_cli("validate", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("0 warning(s)", out)

    def test_registry_and_scaffold(self):
        keys = self.source.registry["keys"]
        self.assertEqual(keys["manifest.canon"]["home"], "manifest")
        self.assertEqual(keys["canon.digests"]["home"],
                         "repo:product-knowledge/canon/")
        self.assertEqual(keys["canon.digests"]["writer"], "human")
        self.assertIn("canon.digests", self.source.human_written_keys())
        # people write the digests, so disabling steward (the one workflow
        # that also writes them) never leaves their readers without a
        # writer (the install still fails, on steward's other keys)
        t = make_target(read(EXAMPLE).replace(
            "disabled-workflows: []", "disabled-workflows: [steward]"))
        rc, out = install("direct", t)
        self.assertIn("no enabled writer", out)
        self.assertNotIn("canon.digests", out)
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        self.assertTrue(
            (t / "product-knowledge" / "canon" / ".gitkeep").exists())
        # the template ships, with the frontmatter doctor and steward read
        tmpl = read(REPO / "src" / "templates" / "CANON.md")
        fm, body = glados.split_frontmatter(tmpl, "CANON.md")
        self.assertEqual(set(fm), {"canon", "version", "retrieved",
                                   "source-sha256", "drafted-from"})
        # fails safe: a copy nobody edits never passes for a sourced digest
        self.assertEqual(fm["drafted-from"], "recall")
        self.assertIn("response body, byte for byte as", body)
        self.assertIn("## <principle-id>", body)
        self.assertIn("**Ask:**", body)
        self.assertIn("**Here, specifically:**", body)
        self.assertIn("Quote at most one sentence", body)
        self.assertTrue(
            (t / ".glados" / "src" / "templates" / "CANON.md").is_file())

    # -- lane 2: never compiled, never hashed ------------------------------------

    def test_canon_stays_out_of_the_hash_and_check_stays_current(self):
        base = glados.parse_yaml(read(EXAMPLE), "glados.yaml")
        with_canon = glados.parse_yaml(read(EXAMPLE) + "\n" + self.CANON,
                                       "glados.yaml")
        self.assertNotIn("canon", glados.structural_projection(with_canon))
        self.assertEqual(glados.structural_hash(base),
                         glados.structural_hash(with_canon))
        t = self.project()
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        gy = t / "glados.yaml"
        for edit in (
            lambda s: s.replace("applies-to: [plan-feature, spec-feature, "
                                "review-mr]", "applies-to: [brunch]"),
            lambda s: s + ("  refactoring:\n    source: \"Martin Fowler, "
                           "Refactoring\"\n    digest: "
                           "product-knowledge/canon/refactoring.md\n"),
            lambda s: s[:s.index("\ncanon:\n") + 1],
        ):
            write(gy, edit(read(gy)))
            rc, out = run_cli("check", "--target", t, "--source", REPO)
            self.assertEqual(rc, 0, out)
            self.assertNotIn("stale", out)
        # a digest edit changes nothing the compiler wrote, either
        write(t / "glados.yaml", read(EXAMPLE) + "\n" + self.CANON)
        write(t / "product-knowledge" / "canon" / "clean-architecture.md",
              self.digest("clean-architecture", words=900))
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)

    def test_no_canon_content_in_compiled_output(self):
        """Neither a digest's text nor the block's own values are compiled:
        the cores carry only how to consult canon. The report lists the
        declarations and never a digest's content."""
        for mode in ("direct", "claude", "pi"):
            with self.subTest(mode=mode):
                t = self.project()
                rc, out = install(mode, t)
                self.assertEqual(rc, 0, out)
                for f in all_files(t):
                    rel = f.relative_to(t).as_posix()
                    if rel.startswith("product-knowledge/canon/") or \
                            rel == "glados.yaml" or rel.startswith(".glados/src"):
                        continue
                    if f.suffix not in (".md", ".toml", ".json", ".yaml"):
                        continue
                    text = read(f)
                    self.assertNotIn(self.MARKER, text, rel)
                    if rel != ".glados/assembly-report.md":
                        self.assertNotIn("Eric Evans", text, rel)
                        self.assertNotIn("domain-driven-design", text, rel)

    # -- where the fragment compiles ---------------------------------------------

    def _assert_consult_cores_only(self, glados_dir):
        for core in glados.CORES:
            path = glados_dir / f"{core}.md"
            if not path.exists():
                continue
            text = read(path)
            with self.subTest(core=core):
                full = text.count("## Consulting canon")
                pointer = text.count("*(See **Consulting canon**")
                if core in self.CONSULT_CORES:
                    self.assertEqual(full, 1, f"{core}: one full copy")
                    self.assertEqual(pointer, 0, f"{core}: no second route")
                else:
                    self.assertEqual(full + pointer, 0,
                                     f"{core} is not a consult point")

    def test_fragment_compiles_into_the_consult_points_only(self):
        """Included in the bodies of the cores that consult canon, never
        through a module: default-modules appends standards-gate and the
        review panel to every core, so a module route would carry the
        fragment into documents that never consult canon."""
        self.assertEqual(sorted(self.CONSULT_CORES), sorted(
            c for c in glados.CORES
            if "vocabulary/canon.md" in self.source.cores[c]["body"]))
        for m in glados.MODULES:
            self.assertNotIn("vocabulary/canon.md",
                             self.source.modules[m]["body"], m)
        for phase in ("nascent", "production"):
            with self.subTest(phase=phase):
                t = make_target(self.MINIMAL.format(phase=phase))
                rc, out = install("direct", t)
                self.assertEqual(rc, 0, out)
                self._assert_consult_cores_only(
                    t / "product-knowledge" / "glados")
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        self._assert_consult_cores_only(t / "product-knowledge" / "glados")
        p = make_plugin_target()
        self.assertEqual(install("claude-plugin", p)[0], 0)
        self._assert_consult_cores_only(p / "compiled" / "claude-plugin")

    def test_consult_points_declare_their_reads_and_observations(self):
        """A core that consults canon reads manifest.canon, and one that
        files canon conflicts emits `observation` (and writes the pending
        observations unless it never commits to the branch it reviews, as
        review-mr does)."""
        for core in self.CONSULT_CORES + ["steward"]:
            unit = self.source.cores[core]
            with self.subTest(core=core):
                self.assertIn("manifest.canon", unit["reads"])
                self.assertIn("canon.digests", unit["reads"])
                if core != "steward":
                    self.assertIn("observation", unit["emits"])
                if core not in ("review-mr", "steward"):
                    self.assertIn("observations.pending", unit["writes"])
        self.assertNotIn("observations.pending",
                         self.source.cores["review-mr"]["writes"])
        self.assertIn("canon.digests", self.source.cores["steward"]["writes"])

    def test_fragment_stays_lean_and_states_the_rules(self):
        frag = read(REPO / "src" / "vocabulary" / "canon.md")
        self.assertLessEqual(len(frag.split()), 460,
                             "keep the consult instruction lean; "
                             "explanation belongs in docs/guides/canon.md")
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        flat = " ".join(read(t / "product-knowledge" / "glados" /
                             "plan-feature.md").split())
        for rule in (
            "If it has no `canon:` block, skip this section",
            "Never fetch its `url` during a run",
            "Never fill a principle in from memory",
            "With no `applies-to`, it applies at `plan-feature`, `shape`, "
            "`spec-feature`, `verify-feature` and `review-mr`",
            "gets the digest paths for its seats, never a summary, and the "
            "Weight, Recall drafts, Cite and Conflicts rules here, copied "
            "verbatim",
            "a decision the project recorded, its standards, its "
            "philosophies, canon",
            "is an `advisory` finding unless a `must` standard or a `core` "
            "philosophy adopts the principle",
            "the finding names its consequence",
            "`drafted-from: recall`",
            "`canon:<name>#<principle-id>`",
            "the disagreement is an observation, not a finding",
            "carries it in the outcome only",
            "A fresh agent lists each conflict under **Canon conflicts** in "
            "its output instead, and the workflow that spawned it files it",
        ):
            self.assertIn(rule, flat)

    def test_consult_sites_and_routing_text(self):
        t = make_target(read(EXAMPLE))
        self.assertEqual(install("direct", t)[0], 0)
        d = t / "product-knowledge" / "glados"

        def core(name):
            return " ".join(read(d / f"{name}.md").split())

        self.assertIn("Check the approach against the canon that applies at "
                      "`plan-feature`", core("plan-feature"))
        self.assertIn("The pass also presses each principle of the canon "
                      "that applies at `spec-feature`", core("spec-feature"))
        self.assertIn("standards documents and canon digests (paths, not "
                      "summaries", core("verify-feature"))
        self.assertIn("| Canon digests | Only when this document has a "
                      "*Consulting canon* section", core("verify-feature"))
        self.assertIn("against each canon digest it lists",
                      core("verify-feature"))
        self.assertIn("Give each panelist the digest paths of the canon that "
                      "applies at `review-mr`", core("review-mr"))
        self.assertIn("**Canon**: set the architecture and conventions "
                      "beside the canon", core("review-codebase"))
        self.assertIn("routed to its seat", core("brunch"))
        self.assertIn("brunch seats no standing lens, so an entry seated on a "
                      "lens goes to every reviewer", core("brunch"))
        self.assertIn("File each canon conflict a reviewer lists",
                      core("brunch"))
        rm = core("review-mr")
        self.assertIn("and the rules *Consulting canon* gives a fresh agent, "
                      "copied verbatim", rm)
        self.assertIn("**File the canon conflicts.** Each `canon-conflicts` "
                      "entry a panelist returns is an `observation` outcome",
                      rm)
        self.assertIn("When the brief lists canon digests, add "
                      "`canon-conflicts`", rm)
        self.assertIn("for a canon principle the canon rules it carries", rm)
        vf = core("verify-feature")
        self.assertIn("and the rules that section gives a fresh agent, copied "
                      "verbatim", vf)
        self.assertIn("Canon conflicts when the brief lists canon digests "
                      "(canon id | what overrides it)", vf)
        self.assertIn("File each canon conflict the evaluation lists", vf)
        rp = core("run-pipeline")
        self.assertIn("**Check the shape against canon.** The consult point "
                      "is `shape`", rp)
        self.assertIn("inside run-pipeline, the current step (`shape`, or a "
                      "project step's id); a step's review and standards gate "
                      "belong to that step", rp)
        # said once: run-pipeline's project-step bullet no longer repeats it
        self.assertNotIn("the consult point for *Consulting canon* is the "
                         "step's id", rp)
        self.assertIn("principle of the canon that applies at this step", rp)
        self.assertIn("the digest of each entry that applies at the reviewed "
                      "step, as *Consulting canon* sets out", rp)
        self.assertIn("and the rules that section gives a fresh agent", rp)
        self.assertIn("Canon conflicts when the brief lists canon digests", rp)
        self.assertIn("File each canon conflict the review lists", rp)
        # module wording rides everywhere, conditioned on the section
        self.assertIn("| canon, not adopted | `advisory` |",
                      core("implement-feature"))
        self.assertIn("when the workflow consults canon, against the canon "
                      "digests seated on this lens", core("run-epic"))
        # steward refreshes; it is the one workflow that fetches
        sw = core("steward")
        self.assertIn("### 4. Refresh canon digests", sw)
        self.assertIn("This is the one workflow that fetches a canon source",
                      sw)
        self.assertIn("Never make that change yourself", sw)
        self.assertIn("### 8. Open the cleanup MR", sw)
        self.assertIn("the suite result from step 6", sw)

    # -- report, doctor, guard ---------------------------------------------------

    def test_assembly_report_lists_declarations_only(self):
        t = self.project()
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("## Canon", report)
        self.assertLess(report.index("## Sinks"), report.index("## Canon"))
        self.assertLess(report.index("## Canon"),
                        report.index("## RELAXED(phase)"))
        self.assertIn("| clean-architecture | Robert C. Martin, Clean "
                      "Architecture (2017) | "
                      "`product-knowledge/canon/clean-architecture.md` | "
                      "plan-feature, spec-feature, review-mr | "
                      "philosophy, architect |", report)
        self.assertIn("| domain-driven-design | Eric Evans, Domain-Driven "
                      "Design (2003) | "
                      "`product-knowledge/canon/domain-driven-design.md` | "
                      "plan-feature, shape, spec-feature, verify-feature, "
                      "review-mr (default) | philosophy (default) |", report)
        self.assertNotIn(self.MARKER, report)
        self.assertNotIn("example.com", report, "the URL is not reported")
        # no block, no section, and a clean check
        t2 = make_target()
        self.assertEqual(install("direct", t2)[0], 0)
        self.assertNotIn("## Canon", read(t2 / ".glados" / "assembly-report.md"))
        rc, out = run_cli("check", "--target", t2, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("canon", out)

    def test_doctor_reports_each_digest(self):
        manifest = read(EXAMPLE) + "\n" + self.CANON + (
            "  stale-book:\n    source: \"S\"\n"
            "    digest: product-knowledge/canon/stale-book.md\n"
            "  long-post:\n    source: \"L\"\n"
            "    digest: product-knowledge/canon/long-post.md\n"
            "  remembered:\n    source: \"R\"\n"
            "    digest: product-knowledge/canon/remembered.md\n")
        t = self.project(manifest, digests=("clean-architecture",))
        old = (datetime.date.today() - datetime.timedelta(days=400)).isoformat()
        canon = t / "product-knowledge" / "canon"
        write(canon / "stale-book.md", self.digest("stale-book", retrieved=old))
        write(canon / "long-post.md", self.digest("long-post", words=1200))
        write(canon / "remembered.md",
              self.digest("remembered", drafted="recall"))
        self.assertEqual(install("direct", t)[0], 0)
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, out)
        self.assertIn("canon: 5 entries declared", out)
        self.assertIn("- clean-architecture: product-knowledge/canon/"
                      "clean-architecture.md ok (retrieved", out)
        self.assertIn("- domain-driven-design: product-knowledge/canon/"
                      "domain-driven-design.md missing", out)
        self.assertIn(f"retrieved {old}, 400 days ago (over 180)", out)
        self.assertIn("words (keep a digest under about 1,000", out)
        self.assertIn("- remembered: product-knowledge/canon/remembered.md — "
                      "drafted from recall", out)
        self.assertNotIn(self.MARKER, out)
        self.assertNotIn("Traceback", out)
        # the guidance comment does not count toward the length: the
        # fixture's body is 50 words, 58 with its comment
        today = datetime.date.today().isoformat()
        self.assertIn("- clean-architecture: product-knowledge/canon/"
                      f"clean-architecture.md ok (retrieved {today}, 50 "
                      "words)", out)
        rc, out = run_cli("doctor", "--target", make_target(), "--source",
                          REPO)
        self.assertIn("canon: none declared", out)

    def test_doctor_thresholds_and_odd_digests(self):
        """In-process, on a fixed date: each limit at its boundary, and each
        way a digest can be wrong reported on its own line."""
        today = datetime.date(2026, 10, 17)
        t = make_target(self.MINIMAL.format(phase="evolving"))
        canon = t / "product-knowledge" / "canon"
        # 200 words of guidance comment: counted, it would push w1000 over
        comment = "<!-- " + " ".join(["guidance"] * 200) + " -->"

        def body(words):
            return "\n".join([comment, " ".join(["word"] * words), ""])

        def fm(retrieved):
            return (f"---\ncanon: x\nretrieved: {retrieved}\n"
                    f"drafted-from: source\n---\n")

        def days_ago(n):
            return (today - datetime.timedelta(days=n)).isoformat()

        write(canon / "d180.md", fm(days_ago(180)) + body(10))
        write(canon / "d181.md", fm(days_ago(181)) + body(10))
        write(canon / "w1000.md", fm(days_ago(1)) + body(1000))
        write(canon / "w1001.md", fm(days_ago(1)) + body(1001))
        write(canon / "future.md", fm("2027-12-01") + body(10))
        write(canon / "not-a-date.md", fm("YYYY-MM-DD") + body(10))
        write(canon / "no-date.md", "---\ncanon: x\n---\n" + body(10))
        write(canon / "unterminated.md", "---\ncanon: x\n" + body(10))
        (canon / "utf16.md").write_text(fm(days_ago(1)) + body(10),
                                        encoding="utf-16")
        (canon / "a-dir").mkdir()
        names = ["d180", "d181", "w1000", "w1001", "future", "not-a-date",
                 "no-date", "unterminated", "utf16", "a-dir"]
        raw = {"canon": {n: {"source": "S", "digest":
                             f"product-knowledge/canon/{n}"
                             + ("" if n == "a-dir" else ".md")}
                         for n in names}}
        lines = glados._canon_doctor_lines(t, raw, today=today)
        got = {l.split(":", 1)[0].strip(" -"): l for l in lines[1:]}
        self.assertEqual(sorted(got), sorted(names), lines)
        self.assertIn(f"d180.md ok (retrieved {days_ago(180)}, 10 words)",
                      got["d180"])
        self.assertIn("181 days ago (over 180)", got["d181"])
        self.assertIn(f"w1000.md ok (retrieved {days_ago(1)}, 1000 words)",
                      got["w1000"])
        self.assertIn("1001 words (keep a digest under about 1,000",
                      got["w1001"])
        self.assertIn("`retrieved: 2027-12-01` is in the future",
                      got["future"])
        self.assertIn("`retrieved: YYYY-MM-DD` is not a date (YYYY-MM-DD)",
                      got["not-a-date"])
        self.assertIn("no `retrieved:` date (YYYY-MM-DD)", got["no-date"])
        self.assertIn("unterminated.md has unreadable frontmatter — ",
                      got["unterminated"])
        self.assertIn("unterminated frontmatter", got["unterminated"])
        self.assertIn("utf16.md cannot be read — ", got["utf16"])
        self.assertIn("not valid UTF-8", got["utf16"])
        self.assertIn("product-knowledge/canon/a-dir is a directory (run "
                      "check for details)", got["a-dir"])
        self.assertNotIn("missing", got["a-dir"])
        # the template, copied unedited, reports its placeholder date and
        # its safe default, recall
        write(canon / "copied.md",
              read(REPO / "src" / "templates" / "CANON.md"))
        lines = glados._canon_doctor_lines(t, {"canon": {"copied": {
            "digest": "product-knowledge/canon/copied.md"}}}, today=today)
        self.assertIn("`retrieved: YYYY-MM-DD` is not a date", lines[1])
        self.assertIn("drafted from recall", lines[1])
        # a block that is not a mapping
        self.assertEqual(glados._canon_doctor_lines(t, {"canon": ["a"]}),
                         ["  canon: INVALID — the block must be a mapping "
                          "keyed by name (run check for details)"])

    def test_doctor_codeowners_covers_the_canon_dir(self):
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        write(t / "CODEOWNERS", "/glados.yaml @maintainers\n")
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertNotIn("product-knowledge/canon/", out,
                         "no canon in use: nothing to report")
        p = self.project()
        rc, out = run_cli("doctor", "--target", p, "--source", REPO)
        self.assertIn("CODEOWNERS: none found — consider one covering "
                      "glados.yaml and product-knowledge/canon/", out)
        self.assertIn("the canon digests weigh in reviews", out)
        write(p / "CODEOWNERS", "/glados.yaml @maintainers\n")
        rc, out = run_cli("doctor", "--target", p, "--source", REPO)
        self.assertIn("has no pattern found covering product-knowledge/canon/ "
                      "— the canon digests weigh in reviews", out)
        write(p / "CODEOWNERS",
              "/glados.yaml @maintainers\n/product-knowledge/canon/ @m\n")
        rc, out = run_cli("doctor", "--target", p, "--source", REPO)
        self.assertIn("covers product-knowledge/canon/", out)

    def test_plugin_guard_names_canon(self):
        flat = " ".join(glados.PLUGIN_BOOTSTRAP_GUARD.split())
        self.assertIn("any canon (`canon:`) govern this run", flat)


class TestReleaseHygiene(unittest.TestCase):
    """The version lives in three files and the release checks guard the
    paths that change behaviour (F6f-h)."""

    def test_versions_agree(self):
        plugin = json.loads(read(REPO / ".claude-plugin" / "plugin.json"))
        package = json.loads(read(REPO / "package.json"))
        self.assertEqual(glados.VERSION, plugin["version"],
                         "bin/glados.py VERSION != .claude-plugin/plugin.json")
        self.assertEqual(glados.VERSION, package["version"],
                         "bin/glados.py VERSION != package.json")

    def test_version_check_covers_functional_paths(self):
        wf = read(REPO / ".github" / "workflows" / "version-check.yml")
        block = wf.split("FUNCTIONAL_PATHS=(")[1].split(")")[0]
        for path in ("src/", "skills/", "bin/", "hooks/", "ci/", "compiled/",
                     "glados.yaml.example", "package.json",
                     ".claude-plugin/plugin.json"):
            self.assertIn(f"'{path}'", block, f"{path} not a functional path")

    def test_gitlab_verify_ledger_job_has_git(self):
        ci = read(REPO / "ci" / "glados-check.gitlab-ci.yml")
        job = ci.split("glados-verify-ledger:")[1]
        self.assertIn("python:3.12-slim", job)
        self.assertIn("apt-get install -y --no-install-recommends git", job)
        self.assertIn("safe.directory", job)
        self.assertLess(job.index("before_script:"), job.index("  script:\n"),
                        "git must be installed before verify-ledger runs")


class TestSourceTreeAttacks(unittest.TestCase):

    def test_include_cycle_fatal_names_cycle(self):
        src = make_doctored_source()
        vocab = src / "src" / "vocabulary"
        write(vocab / "cycle-a.md", "<!-- glados:include vocabulary/cycle-b.md -->\n")
        write(vocab / "cycle-b.md", "<!-- glados:include vocabulary/cycle-a.md -->\n")
        core = src / "src" / "workflows" / "intent.md"
        core.write_text(
            read(core) + "\n<!-- glados:include vocabulary/cycle-a.md -->\n",
            encoding="utf-8", newline="\n")
        rc, out = install("direct", make_target(), source=src)
        self.assertEqual(rc, 1)
        self.assertIn("cycle", out)
        self.assertIn("cycle-a.md", out)
        self.assertNotIn("Traceback", out)

    def test_missing_kernel_file_fatal(self):
        src = make_doctored_source()
        (src / "src" / "kernel" / "aliases.yaml").unlink()
        rc, out = install("direct", make_target(), source=src)
        self.assertEqual(rc, 1)
        self.assertIn("aliases.yaml", out)
        self.assertNotIn("Traceback", out)

    def test_include_escape_fatal(self):
        # A ../ include resolving OUTSIDE src/ must die naming the directive,
        # even though the escaped-to file exists.
        src = make_doctored_source()
        core = src / "src" / "workflows" / "intent.md"
        core.write_text(
            read(core) + "\n<!-- glados:include ../glados.yaml.example -->\n",
            encoding="utf-8", newline="\n")
        rc, out = install("direct", make_target(), source=src)
        self.assertEqual(rc, 1, out)
        self.assertIn("escapes the source tree", out)
        self.assertIn("../glados.yaml.example", out)
        self.assertNotIn("Traceback", out)

    def test_frontmatter_type_validation(self):
        # a) non-string description must fail with the file + field named,
        # not crash an adapter with a raw AttributeError.
        src = make_doctored_source()
        core = src / "src" / "workflows" / "intent.md"
        core.write_text(
            read(core).replace(
                "description: Establish or refresh the product mission and roadmap",
                "description: [not, a, string]"),
            encoding="utf-8", newline="\n")
        rc, out = install("gemini", make_target(), source=src)
        self.assertEqual(rc, 1, out)
        self.assertIn("description", out)
        self.assertIn("intent.md", out)
        self.assertNotIn("Traceback", out)
        # b) a bare-string list field must fail (list() on a str would
        # silently produce a per-character list)
        src2 = make_doctored_source()
        core2 = src2 / "src" / "workflows" / "fix-bug.md"
        core2.write_text(
            read(core2).replace("reads: [manifest.branching, manifest.platform]",
                                "reads: manifest.branching"),
            encoding="utf-8", newline="\n")
        rc, out = install("direct", make_target(), source=src2)
        self.assertEqual(rc, 1, out)
        self.assertIn("reads", out)
        self.assertIn("fix-bug.md", out)
        self.assertNotIn("Traceback", out)


class TestDoctor(unittest.TestCase):

    def test_doctor_never_fails(self):
        # doctor's contract is 'never fails': a malformed manifest and an
        # unreadable CI file become report lines, not exits.
        t = make_target("glados: 2\nplatform: gitlab\nphase: evolving\n"
                        "branching:\n\tfeature: x\n")  # tab -> YamlError
        (t / ".gitlab-ci.yml").write_bytes("glados\n".encode("utf-16"))
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, "doctor must never fail:\n" + out)
        self.assertIn("phase: UNREADABLE", out)
        self.assertIn("CI check wired: UNREADABLE", out)
        self.assertIn("never fails", out)
        self.assertNotIn("Traceback", out)

    def test_doctor_survives_a_manifest_that_cannot_compile(self):
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        write(t / "glados.yaml", read(EXAMPLE).replace(
            "disabled-workflows: []", "disabled-workflows:\n  - brunch: x"))
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, "doctor must never fail:\n" + out)
        self.assertIn("assembly report: could not render a fresh copy", out)
        self.assertIn("never fails", out)
        self.assertNotIn("Traceback", out)

    def test_assembly_report_line_survives_any_error(self):
        # Not only a Fatal: any error while rendering becomes a report line.
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        original = glados._prepare_compilation

        def boom(*_a, **_k):
            raise RuntimeError("boom")

        glados._prepare_compilation = boom
        try:
            line = glados._assembly_report_doctor_line(
                glados.Source(REPO), t, ["direct"])
        finally:
            glados._prepare_compilation = original
        self.assertIn("could not render a fresh copy to compare", line)
        self.assertIn("RuntimeError: boom", line)

    def test_doctor_reports_codeowners(self):
        t = make_target()
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0)
        self.assertIn("CODEOWNERS: none found", out)
        write(t / "CODEOWNERS", "/glados.yaml @maintainers\n")
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0)
        self.assertIn("covers glados.yaml", out)
        write(t / "CODEOWNERS", "* @maintainers\n")
        rc, out = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0)
        self.assertIn("does not mention glados.yaml", out)


class TestSda(unittest.TestCase):
    """The explicit-only `sda:` manifest key — install-time scaffolding,
    the assembly-report row, doctor status, and the two guardrails (presets
    may never set it; non-bool values die naming the key)."""

    def _sda_manifest(self) -> str:
        text = read(EXAMPLE)
        self.assertIn("sda: false", text,
                      "glados.yaml.example must document sda: false")
        return text.replace("sda: false", "sda: true")

    def test_sda_true_install_scaffolds_all(self):
        t = make_target(self._sda_manifest())
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        # claims.md at the repo root, from the template, dated today
        claims = read(t / "claims.md")
        self.assertIn("# Claims", claims)
        self.assertIn("SDA: v1.0", claims)
        self.assertNotIn("YYYY-MM-DD", claims, "template date must be filled")
        self.assertIn(datetime.date.today().isoformat(), claims)
        # SPEC_LOG.md carries the work-unit-log table header whose columns
        # match the epilogue's row fields (date, workflow, scope, outcome,
        # links), dated today
        spec = read(t / "product-knowledge" / "SPEC_LOG.md")
        self.assertIn("| Date | Workflow | Scope | Outcome | Links |", spec)
        self.assertNotIn("YYYY-MM-DD", spec, "template date must be filled")
        self.assertIn(datetime.date.today().isoformat(), spec)
        # the freshly scaffolded PROJECT_STATUS.md gets the version header
        status = read(t / "product-knowledge" / "PROJECT_STATUS.md")
        self.assertTrue(status.startswith("<!-- SDA: v1.0 -->"), status[:80])
        # ROADMAP.md is NOT created — headers only stamp existing files
        self.assertFalse((t / "product-knowledge" / "ROADMAP.md").exists(),
                         "sda scaffolding must not invent a roadmap")
        # every shipped standards doc is copied byte-identically
        docs = sorted((REPO / "docs" / "standards").glob("sda-*.md"))
        self.assertGreater(len(docs), 0, "repo must ship sda standards docs")
        for d in docs:
            dest = t / "product-knowledge" / "standards" / d.name
            self.assertTrue(dest.exists(), f"missing scaffolded {d.name}")
            self.assertEqual(dest.read_bytes(), d.read_bytes(),
                             f"{d.name} must be copied byte-identically")
        # assembly report: the sda row plus the artifact listing
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("| sda | true | (explicit) |", report)
        self.assertIn("## SDA conformance", report)
        self.assertIn("claims.md", report)
        self.assertIn("SPEC_LOG.md", report)
        # the install output says what this run scaffolded
        self.assertIn("sda: true", out)
        self.assertIn("claims.md", out)
        # doctor reports status + artifact presence, informationally
        rc, dout = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, dout)
        self.assertIn("sda: true", dout)
        self.assertIn("claims.md: present", dout)
        self.assertIn("SPEC_LOG.md: present", dout)

    def test_sda_false_install_unchanged(self):
        t = make_target()   # the example manifest carries sda: false
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertFalse((t / "claims.md").exists(),
                         "sda: false must scaffold no claims.md")
        self.assertFalse((t / "product-knowledge" / "SPEC_LOG.md").exists())
        std = t / "product-knowledge" / "standards"
        self.assertEqual(list(std.glob("sda-*.md")), [],
                         "sda: false must copy no standards docs")
        status = read(t / "product-knowledge" / "PROJECT_STATUS.md")
        self.assertNotIn("SDA: v1.0", status, "no header without sda: true")
        report = read(t / ".glados" / "assembly-report.md")
        self.assertIn("| sda | false | (explicit) |", report)
        self.assertNotIn("## SDA conformance", report)
        rc, dout = run_cli("doctor", "--target", t, "--source", REPO)
        self.assertEqual(rc, 0, dout)
        self.assertIn("sda: false", dout)

    def test_sda_reinstall_idempotent(self):
        t = make_target(self._sda_manifest())
        self.assertEqual(install("direct", t)[0], 0)
        snap1 = {f.relative_to(t).as_posix(): f.read_bytes() for f in all_files(t)}
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertIn("already present", out,
                      "re-install must report the artifacts as present")
        snap2 = {f.relative_to(t).as_posix(): f.read_bytes() for f in all_files(t)}
        self.assertEqual(snap1, snap2,
                         "sda re-install must be a byte-wise no-op")

    def test_sda_header_prepend_idempotent(self):
        # A pre-existing ROADMAP.md gets exactly one header, its content
        # survives byte-for-byte, and a re-install never stacks a second.
        t = make_target(self._sda_manifest())
        roadmap = t / "product-knowledge" / "ROADMAP.md"
        original = "# Roadmap\n\n## Phase 1: Foundation\n\n**Goal**: Ship.\n"
        write(roadmap, original)
        self.assertEqual(install("direct", t)[0], 0)
        text = read(roadmap)
        self.assertTrue(text.startswith("<!-- SDA: v1.0 -->"), text[:80])
        self.assertIn(original, text, "existing roadmap content must survive")
        self.assertEqual(text.count("SDA: v1.0"), 1)
        self.assertEqual(install("direct", t)[0], 0)
        self.assertEqual(read(roadmap), text,
                         "re-install must not stack a second header")
        # a doc already carrying the (multi-line) header form is left alone
        t2 = make_target(self._sda_manifest())
        headered = ("<!--\nSDA: v1.0\nLast Updated: 2026-01-01\n-->\n\n"
                    "# Roadmap\n")
        write(t2 / "product-knowledge" / "ROADMAP.md", headered)
        self.assertEqual(install("direct", t2)[0], 0)
        self.assertEqual(read(t2 / "product-knowledge" / "ROADMAP.md"),
                         headered, "an existing header must be respected")

    def test_preset_setting_sda_rejected(self):
        # sda is in the manifest schema, so the anti-inflation cap alone would
        # admit it — the explicit-only rule must reject a preset naming it.
        src = make_doctored_source()
        presets = src / "src" / "kernel" / "presets" / "phases.yaml"
        text = read(presets).replace("nascent:\n", "nascent:\n  sda: true\n")
        self.assertIn("nascent:\n  sda: true", text, "doctoring failed")
        presets.write_text(text, encoding="utf-8", newline="\n")
        rc, out = install("direct", make_target(), source=src)
        self.assertEqual(rc, 1, "a preset must never set sda:\n" + out)
        self.assertIn("sda", out)
        self.assertIn("nascent", out)
        self.assertIn("team declaration", out)
        self.assertNotIn("Traceback", out)

    def test_sda_non_bool_fatal(self):
        text = read(EXAMPLE).replace("sda: false", 'sda: "yes"')
        t = make_target(text)
        rc, out = install("direct", t)
        self.assertEqual(rc, 1, "non-bool sda must be fatal:\n" + out)
        self.assertIn("'sda'", out)
        self.assertIn("bool", out)
        self.assertIn("yes", out)
        self.assertNotIn("Traceback", out)


class TestInstallUx(unittest.TestCase):

    MINIMAL = ("glados: 2\nplatform: gitlab\nphase: evolving\n"
               "branching:\n  feature: \"feat/<slug>\"\n"
               "  default-target: main\n")

    def test_phase_transition_advisory_printed(self):
        t = make_target(self.MINIMAL)
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("phase transition", out)
        write(t / "glados.yaml",
              self.MINIMAL.replace("phase: evolving", "phase: production"))
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertIn("phase transition evolving -> production", out)
        self.assertIn("smoke suite", out)
        self.assertIn("advisory", out)
        # a repeat install in the same phase prints no checklist
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("phase transition", out)
        # a backward move adds the confession line
        write(t / "glados.yaml", self.MINIMAL)
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        self.assertIn("phase transition production -> evolving", out)
        self.assertIn("backward move", out)

    def test_v1_leftovers_hint_before_missing_manifest_fatal(self):
        t = tmpdir("glados-v1-hint-")
        shutil.copytree(LEGACY, t, dirs_exist_ok=True)
        (t / "glados.yaml").unlink()
        rc, out = install("claude", t)
        self.assertEqual(rc, 1)
        self.assertIn("v1 -> v2 migration", out)   # the prefilled hint
        self.assertIn("MIGRATION.md", out)
        self.assertIn("no manifest", out)          # the Fatal still fires

    def test_scaffold_includes_personas(self):
        t = make_target()
        rc, out = install("direct", t)
        self.assertEqual(rc, 0, out)
        for sub in ("observations", "standards", "philosophies", "personas"):
            self.assertTrue(
                (t / "product-knowledge" / sub / ".gitkeep").exists(),
                f"product-knowledge/{sub}/ must be scaffolded")


class TestCheckResilience(unittest.TestCase):

    def test_check_report_only_survives_unresolvable_source(self):
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        empty = tmpdir("glados-empty-src-")
        rc, out = run_cli("check", "--target", t, "--source", empty,
                          "--report-only")
        self.assertEqual(rc, 0, "--report-only must not hard-exit:\n" + out)
        self.assertIn("report-only", out)
        self.assertIn("cannot resolve the GLaDOS source tree", out)
        self.assertNotIn("Traceback", out)
        # enforcing mode still fails, cleanly
        rc, out = run_cli("check", "--target", t, "--source", empty)
        self.assertEqual(rc, 1)
        self.assertIn("cannot resolve the GLaDOS source tree", out)
        self.assertNotIn("Traceback", out)


class TestPluginSkills(unittest.TestCase):

    def test_plugin_skills_pruned_by_marker_only(self):
        t = make_plugin_target()
        write(t / "skills" / "my-custom" / "SKILL.md",
              "---\ndescription: mine\n---\n\nA user skill, no marker.\n")
        write(t / "skills" / "stale-stub" / "SKILL.md",
              "---\ndescription: stale\n---\n\nRead "
              "`${CLAUDE_PLUGIN_ROOT}/compiled/claude-plugin/stale-stub.md`.\n")
        write(t / "skills" / "no-skill-md" / "notes.txt", "keep me\n")
        rc, out = install("claude-plugin", t)
        self.assertEqual(rc, 0, out)
        self.assertTrue((t / "skills" / "my-custom" / "SKILL.md").exists(),
                        "user skill without the marker must survive")
        self.assertTrue((t / "skills" / "no-skill-md" / "notes.txt").exists(),
                        "dir without a SKILL.md must survive")
        self.assertFalse((t / "skills" / "stale-stub").exists(),
                         "stale generated stub must be pruned by its marker")
        # every generated stub carries the marker, so a retired core/alias
        # can be identified structurally on the next install
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/compiled/claude-plugin/",
                      read(t / "skills" / "intent" / "SKILL.md"))
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/compiled/claude-plugin/",
                      read(t / "skills" / "mission" / "SKILL.md"))


class TestHookGuards(unittest.TestCase):
    """The run-record guard scripts, driven as real subprocesses through their
    three states: no marker / marker + unsaved record / record saved to the
    glados/ledger branch (v3.2: records never go on a work branch)."""

    def _repo(self):
        t = tmpdir("glados-hooks-")

        def git(*a):
            subprocess.run(["git", "-C", str(t), *a],
                           capture_output=True, text=True)

        git("init", "-q")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        git("checkout", "-q", "-b", "main")
        (t / "a.txt").write_text("x", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "feat: initial")
        return t, git

    def _run_claude(self, repo):
        # claude-stop-hook takes the repo root from the event's "cwd" field
        return subprocess.run(
            [sys.executable, str(REPO / "hooks" / "claude-stop-hook.py")],
            input=json.dumps({"cwd": str(repo)}),
            capture_output=True, text=True)

    def _run_gemini(self, repo):
        # gemini-afteragent-guard uses the process cwd
        return subprocess.run(
            [sys.executable, str(REPO / "hooks" / "gemini-afteragent-guard.py")],
            input="{}", capture_output=True, text=True, cwd=str(repo))

    def test_no_marker_allows(self):
        repo, _ = self._repo()
        p = self._run_claude(repo)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "", "must emit nothing (allow)")
        p = self._run_gemini(repo)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr.strip(), "", "must stay silent (allow)")

    def test_marker_with_uncommitted_record_blocks(self):
        repo, _ = self._repo()
        write(repo / ".glados" / "runs" / "current", "run-1.md\n")
        write(repo / ".glados" / "runs" / "run-1.md", "# run record\n")
        p = self._run_claude(repo)
        self.assertEqual(p.returncode, 0, p.stderr)
        payload = json.loads(p.stdout)
        self.assertEqual(payload["decision"], "block")
        self.assertIn("run-1.md", payload["reason"])
        p = self._run_gemini(repo)
        self.assertEqual(p.returncode, 2, "exit 2 retries the gemini turn")
        self.assertIn("run-1.md", p.stderr)

    def test_marker_with_saved_record_allows(self):
        repo, git = self._repo()
        write(repo / ".glados" / "runs" / "run-1.md", "# run record\n")
        self._ledger_save(repo)
        write(repo / ".glados" / "runs" / "current", "run-1.md\n")
        p = self._run_claude(repo)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "",
                         "saved record must not block")
        p = self._run_gemini(repo)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr.strip(), "",
                         "saved record must not retry the turn")

    def test_record_on_the_work_branch_is_not_saved(self):
        """Committing the record to the branch, as before v3.2, is not the
        save: the guard wants it on the ledger, and names the command."""
        repo, git = self._repo()
        write(repo / ".glados" / "runs" / "run-1.md", "# run record\n")
        git("add", "-f", ".glados/runs/run-1.md")
        git("commit", "-q", "-m", "chore(glados): record test run")
        write(repo / ".glados" / "runs" / "current", "run-1.md\n")
        self._assert_blocks(repo, "run-1.md")
        self.assertIn("ledger save", json.loads(
            self._run_claude(repo).stdout)["reason"])
        rc, out = run_cli("ledger", "save", "--target", repo, "--no-push",
                          ".glados/runs/run-1.md")
        self.assertEqual(rc, 0, out)
        self._assert_allows(repo)

    def test_a_change_after_the_save_and_an_unsaved_artifact_block(self):
        repo, _ = self._repo()
        runs = repo / ".glados" / "runs"
        write(runs / "run-1.md", "# run record\n")
        self._ledger_save(repo)
        write(runs / "stack", "run-1.md\n")
        write(runs / "current", "run-1.md\n")
        self._assert_allows(repo)
        write(runs / "run-1.md", "# run record\n\n## Now\nstep 2\n")
        self._assert_blocks(repo, "run-1.md")
        self._ledger_save(repo)
        self._assert_allows(repo)
        # a step artifact is the run's too
        write(runs / "run-1.shape.md", "# shape\n")
        self._assert_blocks(repo, "run-1.shape.md")
        self._ledger_save(repo)
        self._assert_allows(repo)
        # another run's file is not this run's to save, while the stack
        # lists the runs in flight
        write(runs / "other-run.md", "# another session's record\n")
        self._assert_allows(repo)

    def test_a_fetched_remote_ledger_counts(self):
        """A record saved and pushed from another clone, then restored here,
        is saved: the guard reads the remote-tracking copy too, and restore
        neither creates nor moves this clone's own ledger branch."""
        remote = tmpdir("glados-hooks-remote-")
        subprocess.run(["git", "init", "-q", "--bare", str(remote)],
                       capture_output=True)
        repo, git = self._repo()
        git("remote", "add", "origin", str(remote))
        write(repo / ".glados" / "runs" / "run-1.md", "# run record\n")
        self._ledger_save(repo, push=True)
        other, ogit = self._repo()
        ogit("remote", "add", "origin", str(remote))
        rc, out = run_cli("ledger", "restore", "--target", other)
        self.assertEqual(rc, 0, out)
        local = subprocess.run(
            ["git", "-C", str(other), "rev-parse", "--verify", "--quiet",
             "refs/heads/glados/ledger"], capture_output=True, text=True)
        self.assertNotEqual(local.returncode, 0,
                            "restore never creates the local ledger branch")
        write(other / ".glados" / "runs" / "current", "run-1.md\n")
        self._assert_allows(other)

    # -- nested runs: .glados/runs/stack (F2) ---------------------------------

    def _ledger_save(self, repo, push=False):
        rc, out = run_cli("ledger", "save", "--target", repo,
                          *(() if push else ("--no-push",)))
        self.assertEqual(rc, 0, out)

    def _commit_records(self, repo, git, *names):
        """Save each record to the ledger (the name is from when records
        were committed to the branch)."""
        for name in names:
            write(repo / ".glados" / "runs" / name, f"# {name}\n")
        self._ledger_save(repo)

    def _assert_blocks(self, repo, name):
        p = self._run_claude(repo)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.strip(), "claude hook must block")
        payload = json.loads(p.stdout)
        self.assertEqual(payload["decision"], "block")
        self.assertIn(name, payload["reason"])
        p = self._run_gemini(repo)
        self.assertEqual(p.returncode, 2, "exit 2 retries the gemini turn")
        self.assertIn(name, p.stderr)

    def _assert_allows(self, repo):
        p = self._run_claude(repo)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "", "claude hook must allow")
        p = self._run_gemini(repo)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr.strip(), "", "gemini guard must allow")

    def test_stack_with_uncommitted_outer_record_blocks(self):
        # build-feature (outer) runs plan-feature (inner): the inner record is
        # committed, the outer one is not — the session must not end.
        repo, git = self._repo()
        self._commit_records(repo, git, "inner.md")
        write(repo / ".glados" / "runs" / "outer.md", "# outer\n")
        write(repo / ".glados" / "runs" / "stack", "outer.md\ninner.md\n")
        write(repo / ".glados" / "runs" / "current", "inner.md\n")
        self._assert_blocks(repo, "outer.md")

    def test_stack_outer_record_never_tracked_blocks(self):
        # The outer record is not on disk at all, so the dirty-tree check sees
        # nothing; only reading the stack finds it. `current` alone (the
        # pre-stack behaviour) names a committed record and would allow.
        repo, git = self._repo()
        self._commit_records(repo, git, "inner.md")
        write(repo / ".glados" / "runs" / "stack", "outer.md\ninner.md\n")
        write(repo / ".glados" / "runs" / "current", "inner.md\n")
        self._assert_blocks(repo, "outer.md")

    def test_stack_all_committed_allows(self):
        repo, git = self._repo()
        self._commit_records(repo, git, "outer.md", "inner.md")
        write(repo / ".glados" / "runs" / "stack", "outer.md\ninner.md\n")
        write(repo / ".glados" / "runs" / "current", "inner.md\n")
        self._assert_allows(repo)

    def test_legacy_current_without_stack_still_guards(self):
        # An install compiled before the stack existed writes only `current`.
        repo, git = self._repo()
        write(repo / ".glados" / "runs" / "current", "missing.md\n")
        self._assert_blocks(repo, "missing.md")
        self._commit_records(repo, git, "missing.md")
        self._assert_allows(repo)

    def test_stack_without_current_still_guards(self):
        repo, git = self._repo()
        write(repo / ".glados" / "runs" / "stack", "outer.md\n")
        self._assert_blocks(repo, "outer.md")
        # an empty leftover stack with no current means nothing is in flight
        write(repo / ".glados" / "runs" / "stack", "")
        self._assert_allows(repo)

    def test_markers_in_any_shell_encoding(self):
        repo, git = self._repo()
        runs = repo / ".glados" / "runs"
        self._commit_records(repo, git, "run-1.md")
        # a UTF-8 BOM must not make a committed record look untracked
        (runs / "stack").write_bytes(b"\xef\xbb\xbfrun-1.md\n")
        (runs / "current").write_bytes("run-1.md\n".encode("utf-8-sig"))
        self._assert_allows(repo)
        # UTF-16 (Windows PowerShell 5.1 redirection) naming an uncommitted
        # record: decoded, and it blocks
        (runs / "stack").unlink()
        (runs / "current").write_bytes("run-2.md\r\n".encode("utf-16"))
        write(runs / "run-2.md", "# run 2\n")
        self._assert_blocks(repo, "run-2.md")
        # an undecodable marker blocks, naming itself and every unsaved file
        # under .glados/runs/, and the guard never crashes open
        (runs / "current").write_bytes(b"\x80\x81run-2.md\n")
        self._assert_blocks(repo, "run-2.md")
        self._assert_blocks(repo, ".glados/runs/current cannot be read")
        (runs / "current").unlink()
        (runs / "stack").write_bytes(b"\x80\x81run-2.md\n")
        self._assert_blocks(repo, "run-2.md")
        self._assert_blocks(repo, ".glados/runs/stack cannot be read")

    def test_an_unreadable_marker_blocks_though_every_file_is_saved(self):
        """A marker that exists but cannot be read or decoded hides which
        runs are in flight, so none of them can be shown saved. It used to
        read as no record at all: with every file on disk saved, the
        session ended though the run it named might have no record yet."""
        repo, git = self._repo()
        runs = repo / ".glados" / "runs"
        self._commit_records(repo, git, "outer.md", "inner.md")
        way_out = "delete both .glados/runs/current and .glados/runs/stack"
        undecodable = b"\x80\x81outer.md\ninner.md\n"
        for state in ("stack undecodable", "current undecodable",
                      "stack unreadable, current readable"):
            with self.subTest(state=state):
                for name in ("stack", "current"):
                    path = runs / name
                    if path.is_dir():
                        path.rmdir()
                    elif path.exists():
                        path.unlink()
                if state == "stack undecodable":
                    (runs / "stack").write_bytes(undecodable)
                    bad = ".glados/runs/stack"
                elif state == "current undecodable":
                    (runs / "current").write_bytes(undecodable)
                    bad = ".glados/runs/current"
                else:
                    (runs / "stack").mkdir()  # exists; reading it fails
                    write(runs / "current", "inner.md\n")
                    bad = ".glados/runs/stack"
                self._assert_blocks(repo, f"{bad} cannot be read")
                reason = json.loads(self._run_claude(repo).stdout)["reason"]
                self.assertIn(way_out, reason)
                self.assertIn(way_out, self._run_gemini(repo).stderr)
        # rewritten as text, the same saved records let the session end
        (runs / "stack").rmdir()
        write(runs / "stack", "outer.md\ninner.md\n")
        self._assert_allows(repo)

    def test_an_unreadable_stack_still_guards_the_outer_run(self):
        """With current readable, an unreadable stack used to narrow the
        check to current's own record, so an outer run's unsaved record let
        the session end. As before the ledger (918f16a), the guard blocks
        while any run that may be on the stack lacks a saved record, and
        names it."""
        repo, git = self._repo()
        runs = repo / ".glados" / "runs"
        self._commit_records(repo, git, "inner.md")
        write(runs / "outer.md", "# outer\n")
        (runs / "stack").write_bytes("outer.md\ninner.md\n".encode("utf-16")
                                     [:-1])  # a truncated UTF-16 write
        write(runs / "current", "inner.md\n")
        self._assert_blocks(repo, "outer.md")
        self._assert_blocks(repo, ".glados/runs/stack cannot be read")
        # the same outer run on a readable stack is guarded as it always was
        write(runs / "stack", "outer.md\ninner.md\n")
        self._assert_blocks(repo, "outer.md")
        self._ledger_save(repo)
        self._assert_allows(repo)

    def test_a_current_with_no_stack_lines_guards_every_record(self):
        """With `current` set, a stack that is missing, empty or blank names
        no run enclosing it (the preamble writes the stack for every run,
        its last line equal to current), so it cannot clear one. Only
        current's own files were checked, and an outer run's unsaved record
        let the session end; 918f16a's dirty check covered every record."""
        for state in ("missing", "empty", "blank lines"):
            with self.subTest(stack=state):
                repo, git = self._repo()
                runs = repo / ".glados" / "runs"
                self._commit_records(repo, git, "inner.md")
                write(runs / "outer.md", "# outer\n")
                write(runs / "current", "inner.md\n")
                if state == "empty":
                    (runs / "stack").write_bytes(b"")
                elif state == "blank lines":
                    (runs / "stack").write_bytes(b"\n  \r\n\t\n")
                self._assert_blocks(repo, "outer.md")
                self._ledger_save(repo)
                self._assert_allows(repo)
        # a stack that lists the runs in flight is the authority: a file no
        # run on it owns is not this session's to save
        write(runs / "stack", "inner.md\n")
        write(runs / "stale.md", "# a crashed session's record\n")
        self._assert_allows(repo)
        (runs / "stack").unlink()
        self._assert_blocks(repo, "stale.md")

    def test_a_marker_names_a_record_by_its_exact_name(self):
        """On Windows and macOS a name that differs in case (or, on Windows,
        ends in a dot) opens the record, so it did not count as missing,
        but no file matched it exactly, so none was checked and an unsaved
        run let the session end. A marker names a record exactly, or the
        guard blocks and says so."""
        repo, git = self._repo()
        runs = repo / ".glados" / "runs"
        self._commit_records(repo, git, "inner.md")
        write(runs / "outer.md", "# outer\n")
        write(runs / "stack", "Outer.md\ninner.md\n")
        write(runs / "current", "inner.md\n")
        self._assert_blocks(repo, ".glados/runs/Outer.md")
        self._assert_blocks(repo, "no file has exactly the name")
        self._ledger_save(repo)  # saves outer.md, which is not `Outer.md`
        self._assert_blocks(repo, ".glados/runs/Outer.md")
        write(runs / "stack", "outer.md\ninner.md\n")
        self._assert_allows(repo)
        # a trailing dot reaches inner.md on Windows; it names no record
        write(runs / "inner.md", "# inner, changed since the save\n")
        write(runs / "stack", "outer.md\ninner.md.\n")
        write(runs / "current", "inner.md.\n")
        self._assert_blocks(repo, ".glados/runs/inner.md.")

    def _deny(self, path, listing_only=False):
        """Take this user's access to ``path`` (only the right to list it,
        with ``listing_only``) for the rest of the test. Skips where the
        account ignores it (root)."""
        if os.name == "nt":
            user = os.environ.get("USERNAME")
            if not user:
                self.skipTest("no USERNAME to deny access to")
            rights = "(RD)" if listing_only else "(OI)(CI)(F)"
            p = subprocess.run(["icacls", str(path), "/deny",
                                f"{user}:{rights}"],
                               capture_output=True, text=True)
            if p.returncode:
                self.skipTest(f"icacls refused: {p.stdout}{p.stderr}")
            self.addCleanup(subprocess.run, ["icacls", str(path),
                                             "/remove:d", user],
                            capture_output=True)
        else:
            mode = path.stat().st_mode
            os.chmod(path, 0o300 if listing_only else 0)
            self.addCleanup(os.chmod, path, mode)
        try:
            os.listdir(path)
        except PermissionError:
            return
        self.skipTest("this account lists a directory it was denied")

    def test_a_runs_directory_that_cannot_be_read_blocks(self):
        """A permission error on .glados/runs/ or a directory in it hid the
        files there. From Python 3.13, Path.exists() reads it as no marker,
        so no run was in flight; on 3.10, listing the directory raised,
        which both hosts treat as a non-blocking error. Either way the
        session ended with a run's record unsaved. A directory under
        .glados/runs/ that rglob could not read was skipped the same way."""
        for state in ("all access denied", "listing denied"):
            with self.subTest(runs=state):
                repo, git = self._repo()
                runs = repo / ".glados" / "runs"
                self._commit_records(repo, git, "inner.md")
                write(runs / "outer.md", "# outer\n")
                write(runs / "stack", "outer.md\ninner.md\n")
                write(runs / "current", "inner.md\n")
                self._deny(runs, listing_only=state == "listing denied")
                self._assert_blocks(repo, ".glados/runs cannot be listed")
        repo, git = self._repo()
        runs = repo / ".glados" / "runs"
        self._commit_records(repo, git, "outer.md", "inner.md")
        write(runs / "inner.steps" / "design.md", "# not saved\n")
        write(runs / "stack", "outer.md\ninner.md\n")
        write(runs / "current", "inner.md\n")
        self._assert_blocks(repo, "inner.steps/design.md")
        self._deny(runs / "inner.steps", listing_only=True)
        self._assert_blocks(repo, ".glados/runs/inner.steps cannot be listed")

    def test_a_marker_that_is_a_dangling_link_blocks(self):
        """Path.exists() follows a link, so a marker that is a link to
        nothing counted as no marker at all."""
        repo, git = self._repo()
        runs = repo / ".glados" / "runs"
        self._commit_records(repo, git, "run.md")
        try:
            os.symlink(runs / "nowhere", runs / "current")
        except (OSError, NotImplementedError):
            self.skipTest("this account cannot make a symbolic link")
        self._assert_blocks(repo, ".glados/runs/current cannot be read")

    def test_block_message_names_both_markers_and_the_way_out(self):
        repo, _ = self._repo()
        runs = repo / ".glados" / "runs"
        write(runs / "outer.md", "# outer\n")
        write(runs / "inner.md", "# inner\n")
        write(runs / "stack", "outer.md\ninner.md\n")
        write(runs / "current", "inner.md\n")
        way_out = "delete both .glados/runs/current and .glados/runs/stack"
        for state in ("both markers", "stack only"):
            with self.subTest(state=state):
                if state == "stack only":
                    # following half the hint keeps the guard on
                    (runs / "current").unlink()
                self._assert_blocks(repo, "outer.md")
                reason = json.loads(self._run_claude(repo).stdout)["reason"]
                self.assertIn(".glados/runs/stack", reason)
                self.assertIn(way_out, reason)
                self.assertIn(way_out, self._run_gemini(repo).stderr)
        (runs / "stack").unlink()
        self._assert_allows(repo)

    def test_toml_special_chars_roundtrip(self):
        # Backslashes, quotes and a Python triple-quote inside a core body must
        # survive the gemini TOML byte-for-byte under tomllib.
        src = make_doctored_source()
        core = src / "src" / "workflows" / "intent.md"
        doctored = ("\n## Doctored edge cases\n\n"
                    "Windows path: C:\\Users\\test and regex \\d+\\.\\d+\n"
                    "Quotes: \"double\" and 'single' and '''triple''' inline.\n")
        core.write_text(read(core) + doctored, encoding="utf-8", newline="\n")
        t = make_target()
        rc, out = install("gemini", t, source=src)
        self.assertEqual(rc, 0, "special chars must not break gemini:\n" + out)
        data = tomllib.loads(read(t / ".gemini/commands/glados/intent.toml"))
        self.assertIn(doctored, data["prompt"], "content must be byte-preserved")

    def test_emitted_frontmatter_descriptions_safe(self):
        # A block-scalar description with colons/quotes/backslashes must emit
        # valid TOML and valid one-line YAML frontmatter in every adapter.
        src = make_doctored_source()
        core = src / "src" / "workflows" / "intent.md"
        nasty = ('description: |-\n  Establish mission: refresh "roadmap"\n'
                 "  and C:\\paths on line two")
        core.write_text(
            read(core).replace(
                "description: Establish or refresh the product mission and roadmap",
                nasty),
            encoding="utf-8", newline="\n")
        expected = 'Establish mission: refresh "roadmap" and C:\\paths on line two'
        # gemini: description must parse and round-trip
        t = make_target()
        rc, out = install("gemini", t, source=src)
        self.assertEqual(rc, 0, out)
        data = tomllib.loads(read(t / ".gemini/commands/glados/intent.toml"))
        self.assertEqual(data["description"], expected)
        # antigravity: frontmatter must be parseable and single-line
        t = make_target()
        rc, out = install("antigravity", t, source=src)
        self.assertEqual(rc, 0, out)
        fm, _ = glados.split_frontmatter(
            read(t / ".agents/workflows/glados-intent.md"), "glados-intent.md")
        self.assertEqual(fm["description"], expected)
        # claude-plugin: SKILL.md frontmatter must be parseable and single-line
        t = make_plugin_target()
        rc, out = install("claude-plugin", t, source=src)
        self.assertEqual(rc, 0, out)
        fm, _ = glados.split_frontmatter(
            read(t / "skills/intent/SKILL.md"), "SKILL.md")
        self.assertEqual(fm["description"], expected)


class TestRunLedger(unittest.TestCase):
    """v3.2 item 6: run records stay off the work branch.

    The third trial run committed its record and 63 step artifacts to the
    feature branch, so its MR showed 112 changed files, most of them process
    records. Every run's record and step artifacts now live on the
    glados/ledger branch (epilogue step 4, said once), moved there by
    `glados.py ledger save`, which commits without touching the checked-out
    branch, the index or tracked files, merges what another session pushed,
    and pushes. These tests drive the helper against real repositories and
    a bare remote, and pin the compiled rules that point at it."""

    # -- repositories ----------------------------------------------------------

    def _git(self, repo, *a, check=True):
        p = subprocess.run(["git", "-C", str(repo), *a], capture_output=True,
                           text=True)
        if check:
            self.assertEqual(p.returncode, 0, f"git {a}: {p.stderr}")
        return p.stdout.strip()

    def _remote(self):
        remote = tmpdir("glados-ledger-remote-")
        subprocess.run(["git", "init", "-q", "--bare", str(remote)],
                       capture_output=True)
        return remote

    def _clone(self, remote=None, seed=False):
        """A work repository on `main` with one commit, its origin the bare
        ``remote`` when given; ``seed`` pushes main there first."""
        t = tmpdir("glados-ledger-repo-")
        self._git(t, "init", "-q")
        self._git(t, "config", "user.email", "t@example.com")
        self._git(t, "config", "user.name", "t")
        self._git(t, "config", "commit.gpgsign", "false")
        self._git(t, "checkout", "-q", "-b", "main")
        write(t / "app.py", "print('hi')\n")
        self._git(t, "add", "-A")
        self._git(t, "commit", "-q", "-m", "feat: initial")
        if remote is not None:
            self._git(t, "remote", "add", "origin", str(remote))
            if seed:
                self._git(t, "push", "-q", "origin", "main")
        return t

    def _save(self, repo, *extra, ok=True):
        rc, out = run_cli("ledger", "save", "--target", repo, *extra)
        if ok:
            self.assertEqual(rc, 0, out)
        return rc, out

    def _ledger_files(self, repo, ref="glados/ledger"):
        return set(self._git(repo, "ls-tree", "-r", "--name-only", ref)
                   .split())

    def _show(self, repo, ref, path):
        return self._git(repo, "show", f"{ref}:{path}")

    # -- the helper ------------------------------------------------------------

    def test_save_leaves_the_work_branch_alone(self):
        remote = self._remote()
        repo = self._clone(remote, seed=True)
        self._git(repo, "checkout", "-q", "-b", "feat/thing")
        write(repo / "app.py", "print('changed')\n")      # unstaged work
        write(repo / "lib.py", "x = 1\n")
        self._git(repo, "add", "lib.py")                   # staged work
        runs = repo / ".glados" / "runs"
        write(runs / "2026-10-21-run-pipeline-x.md", "# record\n")
        write(runs / "2026-10-21-run-pipeline-x.shape.md", "# shape\n")
        write(runs / "2026-10-21-run-pipeline-x.evidence" / "log.txt", "ok\n")
        write(runs / "current", "2026-10-21-run-pipeline-x.md\n")
        write(runs / "stack", "2026-10-21-run-pipeline-x.md\n")
        head = self._git(repo, "rev-parse", "HEAD")
        status = self._git(repo, "status", "--porcelain")
        rc, out = self._save(repo)
        self.assertIn("pushed glados/ledger to origin", out)
        self.assertEqual(self._git(repo, "rev-parse", "HEAD"), head)
        self.assertEqual(self._git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
                         "feat/thing")
        # the index and the work are as they were, and nothing is new: the
        # records are ignored through the clone's exclude file
        self.assertEqual(self._git(repo, "diff", "--cached", "--name-only"),
                         "lib.py")
        self.assertIn("M app.py", self._git(repo, "status", "--porcelain"))
        self.assertEqual(
            set(self._git(repo, "status", "--porcelain", "-uall")
                .splitlines()) - set(status.splitlines()), set())
        self.assertFalse((runs / ".gitignore").exists())
        # the ledger holds the run's files and nothing else: an orphan branch
        # with no markers and none of the project's files
        expected = {".glados/runs/2026-10-21-run-pipeline-x.md",
                    ".glados/runs/2026-10-21-run-pipeline-x.shape.md",
                    ".glados/runs/2026-10-21-run-pipeline-x.evidence/log.txt"}
        self.assertEqual(self._ledger_files(repo), expected)
        self.assertEqual(self._ledger_files(repo, "origin/glados/ledger"),
                         expected)
        self.assertEqual(
            self._git(repo, "rev-list", "--count", "glados/ledger"), "1")
        # committing everything on the work branch takes no record
        self._git(repo, "add", "-A")
        self._git(repo, "commit", "-q", "-m", "feat: the change")
        changed = self._git(repo, "diff", "--name-only", "main", "HEAD")
        self.assertNotIn("2026-10-21", changed)
        self.assertEqual(set(changed.split()), {"app.py", "lib.py"})
        # the link points at the ledger copy, never the work branch
        self._git(repo, "remote", "set-url", "origin",
                  "git@gitlab.example.com:group/project.git")
        rc, out = run_cli("ledger", "link", "--target", repo,
                          "2026-10-21-run-pipeline-x.md")
        self.assertEqual(rc, 0, out)
        self.assertEqual(out.strip(),
                         "https://gitlab.example.com/group/project/-/blob/"
                         "glados/ledger/.glados/runs/"
                         "2026-10-21-run-pipeline-x.md")

    def test_another_clone_restores_and_both_sides_survive(self):
        """A run resumed on another machine reads the records back; saves
        from two sessions that both moved the ledger keep both: new files
        from each, and both sides' lines of a record they both edited."""
        remote = self._remote()
        a = self._clone(remote, seed=True)
        write(a / ".glados" / "runs" / "r1.md", "# r1\nstep 1\n")
        self._save(a)
        b = self._clone(remote)
        rc, out = run_cli("ledger", "restore", "--target", b)
        self.assertEqual(rc, 0, out)
        self.assertEqual(read(b / ".glados" / "runs" / "r1.md"),
                         "# r1\nstep 1\n")
        self.assertEqual(self._git(b, "status", "--porcelain", "-uall"), "",
                         "restored records are ignored in the new clone")
        # both edit r1 and add a record of their own
        write(a / ".glados" / "runs" / "r1.md", "# r1\nstep 1\nfrom a\n")
        write(a / ".glados" / "runs" / "ra.md", "# ra\n")
        write(b / ".glados" / "runs" / "r1.md", "# r1\nstep 1\nfrom b\n")
        write(b / ".glados" / "runs" / "rb.md", "# rb\n")
        self._save(a)
        rc, out = self._save(b)
        self.assertIn("merged keeping both sides' lines", out)
        files = self._ledger_files(b, "origin/glados/ledger")
        self.assertEqual(files, {".glados/runs/r1.md", ".glados/runs/ra.md",
                                 ".glados/runs/rb.md"})
        merged = self._show(b, "origin/glados/ledger", ".glados/runs/r1.md")
        self.assertIn("from a", merged)
        self.assertIn("from b", merged)
        # the merged copy is written back, so b's copy is the saved one
        self.assertEqual(read(b / ".glados" / "runs" / "r1.md").strip(),
                         merged)
        # a: its own copy of r1 is an earlier version now; restore refreshes
        # it, and a save would not write it back over the ledger's
        rc, out = run_cli("ledger", "restore", "--target", a)
        self.assertEqual(rc, 0, out)
        self.assertIn("from b", read(a / ".glados" / "runs" / "r1.md"))
        self.assertTrue((a / ".glados" / "runs" / "rb.md").is_file())

    def test_a_stale_copy_never_overwrites_the_ledger(self):
        remote = self._remote()
        a = self._clone(remote, seed=True)
        write(a / ".glados" / "runs" / "r1.md", "# r1\nv1\n")
        self._save(a)
        b = self._clone(remote)
        run_cli("ledger", "restore", "--target", b)
        write(a / ".glados" / "runs" / "r1.md", "# r1\nv1\nv2\n")
        self._save(a)
        # b never touched r1; its save must not put v1 back
        write(b / ".glados" / "runs" / "rb.md", "# rb\n")
        rc, out = self._save(b)
        self.assertIn("earlier version", out)
        self.assertEqual(
            self._show(b, "origin/glados/ledger", ".glados/runs/r1.md"),
            "# r1\nv1\nv2")
        self.assertEqual(read(b / ".glados" / "runs" / "r1.md"),
                         "# r1\nv1\nv2\n", "the stale copy is refreshed")

    def test_restore_keeps_unsaved_work_and_named_records(self):
        remote = self._remote()
        a = self._clone(remote, seed=True)
        runs = a / ".glados" / "runs"
        write(runs / "2026-10-20-run-pipeline-p.md", "# parked\n")
        write(runs / "2026-10-20-run-pipeline-p.plan.md", "# plan\n")
        write(runs / "2026-10-19-review-mr-q.md", "# other\n")
        self._save(a)
        b = self._clone(remote)
        write(b / ".glados" / "runs" / "2026-10-20-run-pipeline-p.md",
              "# parked\nunsaved local work\n")
        rc, out = run_cli("ledger", "restore", "--target", b,
                          "2026-10-20-run-pipeline-p.md")
        self.assertEqual(rc, 0, out)
        bruns = b / ".glados" / "runs"
        self.assertEqual(read(bruns / "2026-10-20-run-pipeline-p.md"),
                         "# parked\nunsaved local work\n")
        self.assertIn("kept this copy", out)
        self.assertTrue((bruns / "2026-10-20-run-pipeline-p.plan.md").is_file(),
                        "a named record comes back with its step artifacts")
        self.assertFalse((bruns / "2026-10-19-review-mr-q.md").exists(),
                         "only the named record and its artifacts")

    def test_a_push_rejected_by_a_newer_remote_is_merged_and_retried(self):
        """The remote moved between this save's fetch and its push: the push
        is rejected, the save fetches, merges and pushes again, and neither
        side's commit is lost (nothing is force-pushed)."""
        remote = self._remote()
        a = self._clone(remote, seed=True)
        b = self._clone(remote)
        write(a / ".glados" / "runs" / "ra.md", "# ra\n")
        self._save(a)
        a_tip = self._git(a, "rev-parse", "glados/ledger")
        write(b / ".glados" / "runs" / "rb.md", "# rb\n")
        real_fetch = glados._ledger_fetch
        calls = []

        def stale_first(git, remote_name):
            calls.append(remote_name)
            if len(calls) == 1:
                return None                 # pretend: nothing new out there
            return real_fetch(git, remote_name)

        args = argparse.Namespace(target=str(b), paths=[], remote="origin",
                                  message=None, no_push=False)
        buf = io.StringIO()
        glados._ledger_fetch = stale_first
        try:
            with contextlib.redirect_stdout(buf):
                rc = glados.cmd_ledger_save(args)
        finally:
            glados._ledger_fetch = real_fetch
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertGreaterEqual(len(calls), 2, "the rejection fetched again")
        tip = self._git(b, "rev-parse", "origin/glados/ledger")
        kept = subprocess.run(["git", "-C", str(b), "merge-base",
                               "--is-ancestor", a_tip, tip])
        self.assertEqual(kept.returncode, 0, "the other session's save is "
                                             "an ancestor of the new tip")
        self.assertEqual(self._ledger_files(b, "origin/glados/ledger"),
                         {".glados/runs/ra.md", ".glados/runs/rb.md"})

    def test_a_failed_push_keeps_the_commit_for_the_next_save(self):
        repo = self._clone()
        self._git(repo, "remote", "add", "origin",
                  str(tmpdir("glados-ledger-gone-") / "missing.git"))
        write(repo / ".glados" / "runs" / "r1.md", "# r1\n")
        rc, out = self._save(repo, ok=False)
        self.assertEqual(rc, 1, out)
        self.assertIn("NOT pushed", out)
        self.assertIn("the next `ledger save` pushes it", out)
        self.assertEqual(self._ledger_files(repo), {".glados/runs/r1.md"})
        remote = self._remote()
        self._git(repo, "remote", "set-url", "origin", str(remote))
        rc, out = self._save(repo)
        self.assertIn("pushed glados/ledger to origin", out)
        # it pushed a save from before, so it does not say nothing happened
        self.assertIn("no new or changed file to save", out)
        self.assertNotIn("nothing new", out)
        self.assertEqual(self._ledger_files(repo, "origin/glados/ledger"),
                         {".glados/runs/r1.md"})

    def test_a_save_that_only_merges_does_not_say_nothing_happened(self):
        """A clone whose unpushed saves diverged from the remote's merges
        and pushes them with no file of its own to add. The hand smoke test
        of the final check saw this print "nothing new to save" above
        "pushed" (final round)."""
        remote = self._remote()
        a = self._clone(remote, seed=True)
        write(a / ".glados" / "runs" / "ra.md", "# ra\n")
        self._save(a)
        b = self._clone(remote)
        write(b / ".glados" / "runs" / "rb.md", "# rb\n")
        self._save(b, "--no-push")
        rc, out = self._save(b)
        self.assertIn("no new or changed file to save", out)
        self.assertIn("this clone's earlier saves were merged", out)
        self.assertIn("pushed glados/ledger to origin", out)
        self.assertNotIn("nothing new", out)
        self.assertEqual(self._ledger_files(b, "origin/glados/ledger"),
                         {".glados/runs/ra.md", ".glados/runs/rb.md"})

    def test_a_named_path_that_is_gone_leaves_the_ledger(self):
        """steward's compaction: a deleted record, named, is removed from the
        ledger, and the digest that replaces it is saved with it."""
        repo = self._clone()
        runs = repo / ".glados" / "runs"
        write(runs / "old.md", "# settled\n")
        write(runs / "old.review-1.md", "# review\n")
        self._save(repo, "--no-push")
        (runs / "old.md").unlink()
        (runs / "old.review-1.md").unlink()
        write(runs / "DIGEST.md", "| 2026-10-01 | run-pipeline | done |\n")
        rc, out = self._save(repo, "--no-push", ".glados/runs/old.md",
                             "old.review-1.md", ".glados/runs/DIGEST.md")
        self.assertIn("removed 2", out)
        self.assertEqual(self._ledger_files(repo), {".glados/runs/DIGEST.md"})
        # history keeps what compaction removed
        self.assertIn("# settled", self._show(repo, "glados/ledger~1",
                                              ".glados/runs/old.md"))
        rc, out = run_cli("ledger", "save", "--target", repo, "--no-push",
                          repo / "app.py")
        self.assertEqual(rc, 1)
        self.assertIn("not under .glados/runs/", out)

    def test_records_a_branch_already_carries_are_left_alone(self):
        """Migration: records committed to a branch before v3.2 stay there,
        untouched; a save does not copy them and a restore does not
        overwrite them, and no history is rewritten."""
        repo = self._clone()
        runs = repo / ".glados" / "runs"
        write(runs / "2026-06-01-build-feature-old.md", "# old record\n")
        self._git(repo, "add", "-A")
        self._git(repo, "commit", "-q", "-m", "chore(glados): record run")
        before = self._git(repo, "rev-parse", "HEAD")
        write(runs / "2026-10-21-build-feature-new.md", "# new record\n")
        self._save(repo, "--no-push")
        self.assertEqual(self._ledger_files(repo),
                         {".glados/runs/2026-10-21-build-feature-new.md"})
        self.assertEqual(self._git(repo, "rev-parse", "HEAD"), before)
        self.assertEqual(self._git(repo, "status", "--porcelain",
                                   "--", ".glados/runs/2026-06-01-"
                                   "build-feature-old.md"), "")

    def test_refuses_to_move_a_ledger_checked_out_in_a_worktree(self):
        repo = self._clone()
        write(repo / ".glados" / "runs" / "r1.md", "# r1\n")
        self._save(repo, "--no-push")
        wt = tmpdir("glados-ledger-wt-") / "ledger"
        self._git(repo, "worktree", "add", "-q", str(wt), "glados/ledger")
        write(repo / ".glados" / "runs" / "r2.md", "# r2\n")
        rc, out = self._save(repo, "--no-push", ok=False)
        self.assertEqual(rc, 1)
        self.assertIn("is checked out at", out)
        self.assertEqual(self._ledger_files(repo), {".glados/runs/r1.md"})

    def test_links_by_platform(self):
        base = glados._remote_web_base
        self.assertEqual(base("git@gitlab.com:inc/research.git"),
                         "https://gitlab.com/inc/research")
        self.assertEqual(base("https://user:tok@gitlab.com/inc/research.git"),
                         "https://gitlab.com/inc/research")
        self.assertEqual(base("ssh://git@gitlab.example.com:2222/a/b/c.git"),
                         "https://gitlab.example.com/a/b/c")
        self.assertEqual(base("https://github.com/o/r"), "https://github.com/o/r")
        self.assertIsNone(base("C:/Users/x/remote.git"))
        self.assertIsNone(base("/srv/git/remote.git"))
        self.assertIsNone(base("file:///srv/git/remote.git"))
        repo = self._clone()
        self._git(repo, "remote", "add", "origin",
                  "https://github.com/o/r.git")
        rc, out = run_cli("ledger", "link", "--target", repo, "a b.md")
        self.assertEqual(out.strip(), "https://github.com/o/r/blob/glados/"
                                      "ledger/.glados/runs/a%20b.md")
        # a manifest's platform wins over the host name
        write(repo / "glados.yaml", "platform: gitlab\n")
        rc, out = run_cli("ledger", "link", "--target", repo, "a.md")
        self.assertEqual(out.strip(), "https://github.com/o/r/-/blob/glados/"
                                      "ledger/.glados/runs/a.md")
        # no web address: the git revision that reads it
        self._git(repo, "remote", "set-url", "origin", "/srv/git/r.git")
        rc, out = run_cli("ledger", "link", "--target", repo, "a.md")
        self.assertEqual(out.strip(), "glados/ledger:.glados/runs/a.md")

    # -- install, CI and verify-ledger ----------------------------------------

    def test_records_stay_out_of_every_branch_across_checkouts(self):
        """An ignore file inside `.glados/runs/` is tracked on some branches
        and not others, so a checkout either aborted over an untracked copy
        or deleted it and left every record open to `git add -A`. The
        clone's exclude file holds on every branch and in every worktree,
        and install vendors nothing to commit (fix round 1)."""
        t = make_target()
        self.assertEqual(install("direct", t)[0], 0)
        self.assertFalse((t / ".glados" / "runs" / ".gitignore").exists(),
                         "install vendors no ignore file")
        remote = self._remote()
        repo = self._clone(remote, seed=True)
        self._git(repo, "checkout", "-q", "-b", "feat/old")
        write(repo / "old.py", "x = 0\n")
        self._git(repo, "add", "-A")
        self._git(repo, "commit", "-q", "-m", "feat: old work")
        self._git(repo, "checkout", "-q", "main")
        rc, out = run_cli("ledger", "restore", "--target", repo)
        self.assertEqual(rc, 0, out)
        exclude = Path(self._git(repo, "rev-parse", "--git-path",
                                 "info/exclude"))
        exclude = exclude if exclude.is_absolute() else repo / exclude
        self.assertIn(glados.RUNS_EXCLUDE, read(exclude).splitlines())
        runs = repo / ".glados" / "runs"
        write(runs / "2026-10-21-run-pipeline-x.md", "# record\n")
        write(runs / "2026-10-21-run-pipeline-x.plan.md", "# plan\n")
        self._save(repo)
        for n, branch in enumerate(("feat/old", "main", "feat/old")):
            self._git(repo, "checkout", "-q", branch)
            self._git(repo, "checkout", "-q", "-b", f"feat/new-{n}")
            self._git(repo, "add", "-A")
            self.assertEqual(self._git(repo, "diff", "--cached",
                                       "--name-only"), "",
                             f"git add -A from {branch} stages no record")
        self.assertTrue((runs / "2026-10-21-run-pipeline-x.md").is_file())
        # the line is written once, however often a command runs
        self._save(repo)
        self.assertEqual(read(exclude).splitlines().count(glados.RUNS_EXCLUDE),
                         1)
        # a worktree shares it
        wt = tmpdir("glados-ledger-wt-") / "wt"
        self._git(repo, "worktree", "add", "-q", "-b", "feat/wt", str(wt),
                  "main")
        write(wt / ".glados" / "runs" / "r.md", "# r\n")
        self.assertEqual(self._git(wt, "status", "--porcelain", "-uall"), "")

    def test_install_excludes_records_at_a_repository_top_level(self):
        """Committing `.glados/` follows an install, before any `ledger`
        command, and an upgraded clone may hold records no save has seen:
        install adds the exclude line, but only at a repository's top
        level, the one place it covers, and never for the plugin build,
        whose target is GLaDOS itself (fix round 3)."""
        repo = self._clone()
        shutil.copyfile(EXAMPLE, repo / "glados.yaml")
        write(repo / ".glados" / "runs" / "2026-10-01-fix-bug-x.md", "# r\n")
        exclude = repo / self._git(repo, "rev-parse", "--git-path",
                                   "info/exclude")
        rc, out = install("direct", repo)
        self.assertEqual(rc, 0, out)
        self.assertIn(f"added {glados.RUNS_EXCLUDE}", out)
        self.assertIn(glados.RUNS_EXCLUDE, read(exclude).splitlines())
        self._git(repo, "add", ".glados")
        staged = self._git(repo, "diff", "--cached", "--name-only").split()
        self.assertIn(".glados/glados.py", staged)
        self.assertNotIn(".glados/runs/2026-10-01-fix-bug-x.md", staged)
        rc, out = install("direct", repo)
        self.assertNotIn(f"added {glados.RUNS_EXCLUDE}", out)
        self.assertEqual(read(exclude).splitlines().count(glados.RUNS_EXCLUDE),
                         1)
        for sub, mode in (("sub", "direct"), ("plugin", "claude-plugin")):
            other = self._clone()
            target = other / sub if sub == "sub" else other
            name = "glados.yaml" if mode == "direct" else "glados.yaml.example"
            target.mkdir(exist_ok=True)
            shutil.copyfile(EXAMPLE, target / name)
            rc, out = install(mode, target)
            self.assertEqual(rc, 0, out)
            path = other / self._git(other, "rev-parse", "--git-path",
                                     "info/exclude")
            self.assertNotIn(glados.RUNS_EXCLUDE,
                             read(path) if path.is_file() else "", mode)

    def test_a_reverted_copy_is_an_edit(self):
        """A copy put back to text the ledger held before is an edit once
        this tree has synced the path: saved, never replaced by the version
        it reverted (fix round 1)."""
        remote = self._remote()
        a = self._clone(remote, seed=True)
        f = a / ".glados" / "runs" / "2026-10-22-verify-feature-z.verdict.md"
        for text in ("PASS\n", "FAIL: test gap\n", "PASS\n"):
            write(f, text)
            rc, out = self._save(a)
            self.assertNotIn("earlier version", out)
        self.assertEqual(read(f), "PASS\n")
        self.assertEqual(self._show(a, "origin/glados/ledger",
                                    ".glados/runs/2026-10-22-verify-feature-"
                                    "z.verdict.md"), "PASS")
        # restore keeps a revert not yet saved
        write(f, "FAIL: test gap\n")
        rc, out = run_cli("ledger", "restore", "--target", a)
        self.assertEqual(rc, 0, out)
        self.assertEqual(read(f), "FAIL: test gap\n")
        self.assertIn("kept this copy", out)

    def test_restore_drops_what_the_ledger_compacted(self):
        """steward in one clone compacts a record; another clone that had
        restored it loses its copy at the next restore, so it is neither
        read as a prior record nor compacted twice. A copy edited since is
        kept (fix round 1)."""
        remote = self._remote()
        a = self._clone(remote, seed=True)
        runs = a / ".glados" / "runs"
        write(runs / "old.md", "# settled\n")
        write(runs / "old.review-1.md", "# review\n")
        write(runs / "edited.md", "# settled too\n")
        self._save(a)
        c = self._clone(remote)
        run_cli("ledger", "restore", "--target", c)
        cruns = c / ".glados" / "runs"
        self.assertTrue((cruns / "old.md").is_file())
        write(cruns / "edited.md", "# settled too\nlocal note\n")
        for name in ("old.md", "old.review-1.md", "edited.md"):
            (runs / name).unlink()
        write(runs / "DIGEST.md", "| old | edited |\n")
        self._save(a, "old.md", "old.review-1.md", "edited.md", "DIGEST.md")
        rc, out = run_cli("ledger", "restore", "--target", c)
        self.assertEqual(rc, 0, out)
        self.assertIn("removed 2 the ledger no longer has", out)
        self.assertFalse((cruns / "old.md").exists())
        self.assertFalse((cruns / "old.review-1.md").exists())
        self.assertTrue((cruns / "DIGEST.md").is_file())
        self.assertEqual(read(cruns / "edited.md"),
                         "# settled too\nlocal note\n")

    def test_a_push_that_lost_the_ref_lock_is_retried(self):
        """Another push landed after the remote advertised its refs, so the
        remote could not lock the ledger ref ("[remote rejected] ... failed
        to update ref"): the save fetches, merges and pushes again rather
        than stopping as if a hook had refused it (fix round 1)."""
        remote = self._remote()
        a = self._clone(remote, seed=True)
        write(a / ".glados" / "runs" / "r0.md", "# r0\n")
        self._save(a)
        b = self._clone(remote)
        run_cli("ledger", "restore", "--target", b)
        # a's next save, pushed from b's pre-push hook: after the remote
        # advertised its refs to b, before b's update lands
        write(a / ".glados" / "runs" / "ra.md", "# ra\n")
        self._save(a, "--no-push")
        a_tip = self._git(a, "rev-parse", "glados/ledger")
        hooks = tmpdir("glados-ledger-hooks-")
        flag = hooks / "moved-once"
        hook = hooks / "pre-push"
        self._git(b, "config", "core.hooksPath", hooks.as_posix())
        hook.write_text(
            "#!/bin/sh\n"
            "cat >/dev/null\n"
            f"if [ ! -f '{flag.as_posix()}' ]; then\n"
            f"  touch '{flag.as_posix()}'\n"
            "  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE\n"
            f"  git -C '{a.as_posix()}' push -q origin "
            f"{a_tip}:refs/heads/glados/ledger\n"
            "fi\n"
            "exit 0\n", encoding="utf-8", newline="\n")
        os.chmod(hook, 0o755)
        write(b / ".glados" / "runs" / "rb.md", "# rb\n")
        rc, out = self._save(b)
        self.assertTrue(flag.exists(), "the hook moved the ledger")
        self.assertIn("pushed glados/ledger to origin", out)
        tip = self._git(b, "rev-parse", "origin/glados/ledger")
        kept = subprocess.run(["git", "-C", str(b), "merge-base",
                               "--is-ancestor", a_tip, tip])
        self.assertEqual(kept.returncode, 0)
        self.assertEqual(self._ledger_files(b, "origin/glados/ledger"),
                         {".glados/runs/r0.md", ".glados/runs/ra.md",
                          ".glados/runs/rb.md"})

    def test_ci_fetches_the_ledger_before_scanning(self):
        gitlab = read(REPO / "ci" / "glados-check.gitlab-ci.yml")
        job = gitlab.split("glados-verify-ledger:")[1]
        fetch = job.index("+refs/heads/glados/ledger:refs/remotes/origin/"
                          "glados/ledger")
        self.assertLess(job.index("before_script:"), fetch)
        self.assertLess(fetch, job.index("  script:\n"))
        github = read(REPO / "ci" / "glados-check.github-actions.yml")
        self.assertIn("fetch-depth: 0", github)
        self.assertIn("GITHUB_BASE_REF", github)

    def test_verify_ledger_lists_records_a_branch_commits(self):
        repo = self._clone()
        write(repo / ".glados" / "runs" / "kept.md", "# history\n")
        self._git(repo, "add", "-f", ".glados/runs/kept.md")
        self._git(repo, "commit", "-q", "-m", "chore(glados): record run")
        self._git(repo, "checkout", "-q", "-b", "feat/x")
        write(repo / "lib.py", "x = 1\n")
        write(repo / ".glados" / "runs" / "new.md", "# new\n")
        self._git(repo, "add", "-f", "lib.py", ".glados/runs/new.md")
        self._git(repo, "commit", "-q", "-m", "feat: x")
        rc, out = run_cli("verify-ledger", "--target", repo, "--base", "main")
        self.assertEqual(rc, 0, out)
        self.assertIn("run records this branch commits (since main): 1", out)
        self.assertIn(".glados/runs/new.md", out)
        self.assertNotIn("kept.md", out, "history before the base is left")
        self.assertIn("run records belong on glados/ledger", out)
        self.assertIn("glados/ledger is not in this clone", out)
        write(repo / ".glados" / "runs" / "r.md", "# r\n")
        self._save(repo, "--no-push", ".glados/runs/r.md")
        # With no --base, verify-ledger takes the base from CI's merge or
        # pull request; run outside one, as a developer would, or a pull
        # request's own GITHUB_BASE_REF leaks in as this repo's base.
        env = {k: v for k, v in os.environ.items()
               if k not in ("GITHUB_BASE_REF", "CI_MERGE_REQUEST_DIFF_BASE_SHA")}
        rc, out = run_cli("verify-ledger", "--target", repo, env=env)
        self.assertIn("ledger branch: refs/heads/glados/ledger", out)
        self.assertIn("not checked (no base", out)

    # -- the compiled rules ----------------------------------------------------

    @classmethod
    def setUpClass(cls):
        t = make_target(read(EXAMPLE))
        rc, out = install("direct", t)
        assert rc == 0, out
        cls.dir = t / "product-knowledge" / "glados"

    def core(self, name):
        return " ".join(read(self.dir / f"{name}.md").split())

    def test_every_core_saves_its_record_to_the_ledger(self):
        """Said once, in the epilogue every core carries, with the restore
        that brings records back in the preamble: review-mr's and
        address-review's ledger rule became the general one."""
        for name in glados.CORES:
            with self.subTest(core=name):
                text = self.core(name)
                for rule in (
                        "after `.glados/glados.py ledger restore` copies in "
                        "the ledger's records",
                        "A run without a saved run record and a published "
                        "outcome is an incomplete run",
                        "4. **Save the record to the ledger.** Every run's "
                        "record and step artifacts live on the "
                        "`glados/ledger` branch, never on a work branch: the "
                        "MR carries the change and the comment, and the "
                        "ledger carries the trail.",
                        # a failed push is the helper's to say, when it
                        # happens (fix round 1)
                        "`.glados/glados.py ledger save` commits every new or "
                        "changed file under `.glados/runs/` there and pushes "
                        "it. Link",
                        "Link a record or artifact by its ledger copy (`ledger "
                        "link <path>`), never by a work-branch path.",
                        # the project's own rows ride the work, where SDA
                        # reads them, and land only when the change does,
                        # so the commit is pushed (fix round 1)
                        "Commit and push step 3's row and claim, and any "
                        "pending observations, on the working branch: "
                        "`chore(glados): log <workflow> run`.",
                        # a run on an MR someone else opened works on that
                        # MR's unit: the opener's row is already on the
                        # branch, so a fix pass leaves it only its change
                        # (final round)
                        "clears its entry in `claims.md`; review-mr and "
                        "address-review, on another's MR, do neither.",
                        "The epilogue clears the entry. review-mr and "
                        "address-review claim nothing.",
                        "Save again for any record update made in this step, "
                        "before step 6."):
                    self.assertIn(rule, text)
                for gone in ("**Commit the record**",
                             "commit their record to the `glados/ledger` "
                             "branch instead",
                             "ride the record commit below",
                             "ride the step 4 commit",
                             "if the push fails, say so in the record",
                             "both committed with the work (step 4)",
                             "review-mr, which never commits to the branch "
                             "it reviews, appends none"):
                    self.assertNotIn(gone, text)
                self.assertEqual(text.count("Every run's record and step "
                                            "artifacts live on"), 1)

    def test_the_workflows_that_assumed_a_branch_copy(self):
        rp = self.core("run-pipeline")
        for rule in (
                "A parked run leaves its work on its own branch and its "
                "record on the ledger, which the park's `escalation` and "
                "run-epic's ticket row name.",
                "**Commits.** When a row ends or parks, its process files "
                "(artifact, briefs, check results, record) go to the ledger "
                "in one save",
                "`human`: save first (**Commits**), commit any working diff "
                "a step left uncommitted, and push the branch.",
                # open-mr: the links the description carries resolve on the
                # ledger
                "Commit the work on the branch and push it, and save this "
                "run's record and step artifacts so far to the ledger, so "
                "every link the description carries resolves"):
            self.assertIn(rule, rp)
        for gone in ("A parked run's record is committed on its own branch",
                     "pushes again once the epilogue has committed the record",
                     "together with this run's record and step artifacts"):
            self.assertNotIn(gone, rp)
        self.assertIn("review-mr, which never commits to the branch it "
                      "reviews, carries it in the outcome only", rp)
        steward = self.core("steward")
        self.assertIn("Save the digest and every deleted path to the ledger "
                      "(`.glados/glados.py ledger save <paths>`).", steward)
        self.assertIn("recent records alone, and any this branch tracks.",
                      steward)
        # the clone's exclude file keeps records out; nothing in the tree
        # needs committing (fix round 1)
        self.assertNotIn(".glados/runs/.gitignore",
                         self.core("adopt-codebase"))
        self.assertIn("update the ticket's row in `epic.progress` and save it "
                      "to the ledger before starting the next ticket",
                      self.core("run-epic"))
        self.assertIn("its artifacts live beside this run's record, on the run "
                      "ledger", self.core("spec-feature"))


class TestInstallRobustness(unittest.TestCase):

    def test_readonly_file_in_owned_dir_overwritten(self):
        # A read-only leftover inside a glados-owned dir must be overwritten
        # (the dir is ours), not crash with a PermissionError traceback.
        t = make_target()
        stale = t / ".claude" / "commands" / "glados" / "intent.md"
        write(stale, "old read-only leftover\n")
        os.chmod(stale, 0o444)
        rc, out = install("claude", t)
        self.assertEqual(rc, 0, "read-only leftover must not break install:\n" + out)
        self.assertNotIn("old read-only leftover", read(stale))

    def test_owned_path_conflict_fatal_no_traceback(self):
        # .claude/commands/glados existing as a FILE blocks the owned dir.
        t = make_target()
        write(t / ".claude" / "commands" / "glados", "i am a file\n")
        rc, out = install("claude", t)
        self.assertEqual(rc, 1)
        self.assertIn("glados", out)
        self.assertNotIn("Traceback", out)

    def test_install_survives_legacy_console_encoding(self):
        # cp850 console (legacy Windows) cannot encode the report's em dashes;
        # printing must never crash an install that already wrote files.
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "cp850"
        t = make_target()
        rc, out = install("direct", t, env=env)
        self.assertEqual(rc, 0, "cp850 console must not crash install:\n" + out)
        self.assertNotIn("UnicodeEncodeError", out)

    def test_reinstall_same_target_idempotent(self):
        t = make_target()
        self.assertEqual(install("claude", t)[0], 0)
        snap1 = {f.relative_to(t).as_posix(): f.read_bytes() for f in all_files(t)}
        self.assertEqual(install("claude", t)[0], 0)
        snap2 = {f.relative_to(t).as_posix(): f.read_bytes() for f in all_files(t)}
        self.assertEqual(snap1, snap2, "second install must be a byte-wise no-op")

    def test_planted_files_outside_owned_dirs_survive(self):
        # Files a user plants JUST OUTSIDE owned dirs must survive install +
        # cleanup; glados-prefixed strays INSIDE .agents/workflows are owned.
        t = tmpdir("glados-planted-")
        shutil.copytree(LEGACY, t, dirs_exist_ok=True)
        write(t / ".claude" / "commands" / "glados.md", "user file\n")
        write(t / ".gemini" / "commands" / "glados-mine.toml", "user toml\n")
        write(t / ".agents" / "workflows" / "my-workflow.md", "user workflow\n")
        write(t / ".agents" / "workflows" / "glados-stale-v1.md", "stale v1\n")
        for mode in ("claude", "gemini", "antigravity"):
            rc, out = install(mode, t)
            self.assertEqual(rc, 0, f"{mode}:\n{out}")
        self.assertTrue((t / ".claude" / "commands" / "glados.md").exists())
        self.assertTrue((t / ".gemini" / "commands" / "glados-mine.toml").exists())
        self.assertTrue((t / ".agents" / "workflows" / "my-workflow.md").exists())
        self.assertFalse(
            (t / ".agents" / "workflows" / "glados-stale-v1.md").exists(),
            "glados-prefixed stray inside the owned namespace must be cleaned")


class TestMigrate(unittest.TestCase):
    """The guided v1 -> v2 `migrate` command: detection + suggested mode,
    manifest generation (platform/sda auto-filled, phase left REQUIRED),
    specs/ -> run-record conversion with SPEC_LOG rows, idempotence,
    --dry-run, --clean, and create-only semantics end to end."""

    REC1 = ".glados/runs/2026-05-01-migrated-login-timeout.md"
    REC2 = ".glados/runs/2026-06-10-migrated-reporting.md"

    LOGIN_README = (
        "# Login timeout fix\n\nIntro line.\n\n## Findings\n\n"
        "- finding one\n- finding two\n- finding three\n- finding four\n"
        "- finding five\n- finding six\n\n## Outcome\n\n"
        "Shipped in MR !41.\n")
    REPORTING_README = ("# Reporting spec\n\nSuperseded by workspace "
                        "reports.\nOutcome: merged in MR !77.\n")

    def _v1_repo(self, remote="git@gitlab.com:acme/thing.git", specs=True,
                 sda=True):
        """A rich v1-era repo: git history, a gitlab origin, the v1 claude
        layout (namespaced + un-namespaced + a user file), SDA claims.md,
        and two date-prefixed specs/ dirs."""
        t = tmpdir("glados-migrate-")

        def git(*a):
            subprocess.run(["git", "-C", str(t), *a],
                           capture_output=True, text=True)

        git("init", "-q")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        git("checkout", "-q", "-b", "main")
        if remote:
            git("remote", "add", "origin", remote)
        write(t / "README.md", "# my project\n")
        write(t / ".claude" / "commands" / "plan-feature.md",
              "# Plan Feature\n\nv1 un-namespaced command body.\n")
        write(t / ".claude" / "commands" / "glados" / "plan_feature.md",
              "# Plan Feature\n\nv1 namespaced command body.\n")
        write(t / ".claude" / "commands" / "my-user-command.md",
              "a user command, not glados's\n")
        if sda:
            write(t / "claims.md", "<!-- SDA: v1.0 -->\n\n# Claims\n\n- one\n")
        if specs:
            write(t / "specs" / "2026-05-01_login-timeout" / "README.md",
                  self.LOGIN_README)
            write(t / "specs" / "2026-06-10_reporting" / "README.md",
                  self.REPORTING_README)
        git("add", "-A")
        git("commit", "-q", "-m", "v1 state")
        return t, git

    def _snapshot(self, t):
        return {f.relative_to(t).as_posix(): f.read_bytes()
                for f in all_files(t)
                if ".git" not in f.relative_to(t).parts}

    def _migrate(self, t, *extra):
        return run_cli("migrate", "--target", t, "--source", REPO, *extra)

    @staticmethod
    def _row(date, dirname, rec):
        return f"| {date} | migrate | specs/{dirname} | migrated | {rec} |"

    def test_dry_run_writes_nothing_and_prints_plan(self):
        t, _ = self._v1_repo()
        before = self._snapshot(t)
        rc, out = self._migrate(t, "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self._snapshot(t), before,
                         "--dry-run must write nothing")
        self.assertFalse((t / "glados.yaml").exists())
        self.assertIn("suggested install mode: claude", out)
        self.assertIn("platform: gitlab", out)
        self.assertIn("sda: true", out)
        self.assertIn("2026-05-01-migrated-login-timeout.md", out)
        self.assertIn("2026-06-10-migrated-reporting.md", out)

    def test_generate_convert_fail_fast_then_install(self):
        t, _ = self._v1_repo()
        rc, out = self._migrate(t)
        self.assertEqual(rc, 0, out)
        # generated manifest: platform + sda auto-filled, phase left REQUIRED
        gy = read(t / "glados.yaml")
        self.assertIn("platform: gitlab", gy)
        self.assertIn("sda: true", gy)
        self.assertIn(glados.MIGRATE_PHASE_LINE, gy)
        # the generated text parses in the tool's own YAML subset, phase unset
        raw = glados.load_manifest(t / "glados.yaml")
        self.assertIsNone(raw.get("phase"))
        # fail-fast: install refuses until a human picks a phase
        rc, iout = install("claude", t)
        self.assertEqual(rc, 1, iout)
        self.assertIn("phase", iout)
        self.assertIn("nascent", iout)
        # converted records: title, date, excerpt (heading + tail), git pointer
        rec1 = read(t / self.REC1)
        self.assertIn("# Migrated spec: 2026-05-01_login-timeout", rec1)
        self.assertIn("Date: 2026-05-01 (from the directory name)", rec1)
        self.assertIn("# Login timeout fix", rec1)
        self.assertIn("Shipped in MR !41.", rec1)
        self.assertIn("git log", rec1)
        rec2 = read(t / self.REC2)
        self.assertIn("# Migrated spec: 2026-06-10_reporting", rec2)
        self.assertIn("Date: 2026-06-10", rec2)
        self.assertIn("merged in MR !77", rec2)
        # SPEC_LOG created from the template with one row per dir, newest first
        spec = read(t / "product-knowledge" / "SPEC_LOG.md")
        self.assertIn("| Date | Workflow | Scope | Outcome | Links |", spec)
        row_new = self._row("2026-06-10", "2026-06-10_reporting",
                            ".glados/runs/2026-06-10-migrated-reporting.md")
        row_old = self._row("2026-05-01", "2026-05-01_login-timeout",
                            ".glados/runs/2026-05-01-migrated-login-timeout.md")
        self.assertIn(row_new, spec)
        self.assertIn(row_old, spec)
        self.assertLess(spec.index(row_new), spec.index(row_old),
                        "SPEC_LOG rows must land newest-first")
        # fill phase -> the full install succeeds over the migrated tree
        write(t / "glados.yaml",
              gy.replace(glados.MIGRATE_PHASE_LINE, "phase: evolving"))
        self.assertEqual(
            glados.load_manifest(t / "glados.yaml")["phase"], "evolving")
        rec_bytes = (t / self.REC1).read_bytes()
        claims_bytes = (t / "claims.md").read_bytes()
        rc, iout = install("claude", t)
        self.assertEqual(rc, 0, iout)
        # converted records + carried-over SDA artifacts survive (create-only)
        self.assertEqual((t / self.REC1).read_bytes(), rec_bytes,
                         "run records must survive install untouched")
        self.assertEqual((t / "claims.md").read_bytes(), claims_bytes,
                         "an existing claims.md must never be clobbered")
        self.assertIn(row_old, read(t / "product-knowledge" / "SPEC_LOG.md"))

    def test_rerun_is_byte_wise_noop(self):
        t, _ = self._v1_repo()
        self.assertEqual(self._migrate(t)[0], 0)
        snap1 = self._snapshot(t)
        rc, out = self._migrate(t)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self._snapshot(t), snap1,
                         "re-run must be a byte-wise no-op")
        self.assertIn("never overwritten", out)
        self.assertIn("record exists", out)

    def test_existing_manifest_never_overwritten(self):
        t, _ = self._v1_repo()
        shutil.copyfile(EXAMPLE, t / "glados.yaml")
        before = (t / "glados.yaml").read_bytes()
        rc, out = self._migrate(t)
        self.assertEqual(rc, 0, out)
        self.assertEqual((t / "glados.yaml").read_bytes(), before,
                         "an existing glados.yaml must never be rewritten")
        self.assertIn("never overwritten", out)
        # differences are reported: SDA artifacts exist but sda: false
        self.assertIn("sda: true", out)
        # conversion still runs; SPEC_LOG rows skipped (manifest sda wins)
        self.assertTrue((t / self.REC1).exists())
        self.assertFalse(
            (t / "product-knowledge" / "SPEC_LOG.md").exists(),
            "sda: false in the manifest must skip SPEC_LOG rows")
        self.assertIn("skipped (sda is not true)", out)

    def test_clean_removes_converted_and_v1_only(self):
        t, _ = self._v1_repo()
        rc, out = self._migrate(t, "--clean")
        self.assertEqual(rc, 0, out)
        # converted specs/ dirs are gone, records + everything else stay
        self.assertFalse((t / "specs").exists(),
                         "emptied specs/ tree must be removed")
        self.assertTrue((t / self.REC1).exists())
        self.assertTrue((t / self.REC2).exists())
        self.assertTrue((t / "glados.yaml").exists())
        self.assertTrue((t / "README.md").exists())
        self.assertTrue((t / "claims.md").exists())
        # v1 claude layout removed; the user's own command survives
        self.assertFalse((t / ".claude" / "commands" / "plan-feature.md").exists())
        self.assertFalse((t / ".claude" / "commands" / "glados").exists())
        self.assertTrue(
            (t / ".claude" / "commands" / "my-user-command.md").exists(),
            "--clean must never touch user files")

    def test_clean_never_removes_v2_artifacts(self):
        # After a real install, .claude/commands/glados/plan-feature.md is a
        # v1-KNOWN NAME with v2 content — the content check must protect it.
        t, _ = self._v1_repo()
        self.assertEqual(self._migrate(t)[0], 0)
        write(t / "glados.yaml",
              read(t / "glados.yaml").replace(glados.MIGRATE_PHASE_LINE,
                                              "phase: evolving"))
        self.assertEqual(install("claude", t)[0], 0)
        owned = t / ".claude" / "commands" / "glados"
        v2_files = sorted(p.name for p in owned.glob("*.md"))
        self.assertIn("plan-feature.md", v2_files)
        rc, out = self._migrate(t, "--clean")
        self.assertEqual(rc, 0, out)
        self.assertEqual(sorted(p.name for p in owned.glob("*.md")), v2_files,
                         "migrate --clean must never remove v2 compiled files")
        self.assertFalse((t / "specs").exists())

    def test_spec_dir_without_readme_converts(self):
        t, _ = self._v1_repo(specs=False)
        write(t / "specs" / "2026-04-01_no-readme" / "notes.txt", "notes\n")
        rc, out = self._migrate(t)
        self.assertEqual(rc, 0, out)
        rec = read(t / ".glados" / "runs" / "2026-04-01-migrated-no-readme.md")
        self.assertIn("# Migrated spec: 2026-04-01_no-readme", rec)
        self.assertIn("No README.md", rec)

    def test_generated_manifest_installs_under_every_phase(self):
        # The example's explicit decisions: block is written for its own
        # `phase: evolving` (it confesses exactly delete-code); carried
        # verbatim into a generated manifest it fails production/sunset
        # installs with relaxation errors the team never chose. Migrate must
        # comment those overrides out so the ONE human edit the guide
        # promises — fill phase:, any phase — always yields a green install.
        t, _ = self._v1_repo()
        self.assertEqual(self._migrate(t)[0], 0)
        gy = read(t / "glados.yaml")
        self.assertIn("# decisions:", gy)
        self.assertIn("#   schema-migration: record", gy)
        self.assertIn("# relaxation-acknowledged:", gy)
        self.assertNotIn("\ndecisions:", gy,
                         "the active decisions block must be commented out")
        raw = glados.load_manifest(t / "glados.yaml")
        self.assertNotIn("decisions", raw)
        self.assertNotIn("relaxation-acknowledged", raw)
        for phase in glados.PHASES:
            write(t / "glados.yaml",
                  gy.replace(glados.MIGRATE_PHASE_LINE, f"phase: {phase}"))
            rc, out = install("claude", t)
            self.assertEqual(rc, 0,
                             f"phase '{phase}' must install cleanly over the "
                             f"generated manifest:\n{out}")

    def test_platform_github_and_no_remote_todo(self):
        t, _ = self._v1_repo(remote="git@github.com:acme/thing.git")
        self.assertEqual(self._migrate(t)[0], 0)
        self.assertIn("platform: github", read(t / "glados.yaml"))
        t2, _ = self._v1_repo(remote=None)
        rc, out = self._migrate(t2)
        self.assertEqual(rc, 0, out)
        line = re.search(r"(?m)^platform:.*$", read(t2 / "glados.yaml")).group(0)
        self.assertIn("platform: gitlab", line,
                      "no remote must keep the example default")
        self.assertIn("TODO", line)

    def test_git_date_fallback_and_create_only_records(self):
        # a) no dirname date prefix -> the dir's last commit date is used
        t, git = self._v1_repo(specs=False)
        write(t / "specs" / "no-date-prefix" / "README.md", "# No date\n\nBody.\n")
        git("add", "-A")
        git("commit", "-q", "-m", "add spec")
        proc = subprocess.run(
            ["git", "-C", str(t), "log", "-1", "--format=%cs", "--",
             "specs/no-date-prefix"], capture_output=True, text=True)
        expected = proc.stdout.strip()
        self.assertRegex(expected, r"^\d{4}-\d{2}-\d{2}$")
        rc, out = self._migrate(t)
        self.assertEqual(rc, 0, out)
        rec = t / ".glados" / "runs" / f"{expected}-migrated-no-date-prefix.md"
        self.assertTrue(rec.exists(), out)
        self.assertIn("from git history", read(rec))
        # b) create-only: a pre-existing record wins, but its SPEC_LOG row
        # still lands (the dir counts as converted)
        t2, _ = self._v1_repo()
        write(t2 / self.REC1, "HUMAN OWNED RECORD\n")
        rc, out = self._migrate(t2)
        self.assertEqual(rc, 0, out)
        self.assertEqual(read(t2 / self.REC1), "HUMAN OWNED RECORD\n",
                         "an existing record must win (create-only)")
        self.assertIn("kept", out)
        self.assertIn("2026-05-01-migrated-login-timeout.md",
                      read(t2 / "product-knowledge" / "SPEC_LOG.md"))

    def test_migrated_records_stay_out_of_the_commit_and_reach_the_ledger(self):
        """migrate writes records before any `ledger` command runs, and
        MIGRATION step 3 then commits `.glados/`. migrate adds the clone's
        exclude line first, so that commit takes no record, and the
        `ledger save` after it, which skips files HEAD tracks, finds them
        all (fix round 3)."""
        t, git = self._v1_repo()

        def out(*a):
            return subprocess.run(["git", "-C", str(t), *a],
                                  capture_output=True, text=True).stdout

        exclude = t / out("rev-parse", "--git-path", "info/exclude").strip()
        rc, dry = self._migrate(t, "--dry-run")
        self.assertIn(f"would add {glados.RUNS_EXCLUDE}", dry)
        self.assertNotIn(glados.RUNS_EXCLUDE,
                         read(exclude) if exclude.is_file() else "")
        rc, mout = self._migrate(t)
        self.assertEqual(rc, 0, mout)
        self.assertIn(glados.RUNS_EXCLUDE, read(exclude).splitlines())
        self.assertIn("ledger save --target", mout)
        gy = read(t / "glados.yaml")
        write(t / "glados.yaml",
              gy.replace(glados.MIGRATE_PHASE_LINE, "phase: evolving"))
        self.assertEqual(install("direct", t)[0], 0)
        git("add", "glados.yaml", ".glados", "product-knowledge")
        staged = out("diff", "--cached", "--name-only").split()
        self.assertIn(".glados/glados.py", staged)
        self.assertEqual([p for p in staged if p.startswith(".glados/runs/")],
                         [], "the migration commit takes no record")
        git("commit", "-q", "-m", "chore: migrate to glados v2")
        remote = tmpdir("glados-migrate-remote-")
        subprocess.run(["git", "init", "-q", "--bare", str(remote)],
                       capture_output=True)
        git("remote", "set-url", "origin", str(remote))
        rc, sout = run_cli("ledger", "save", "--target", t)
        self.assertEqual(rc, 0, sout)
        self.assertEqual(
            set(out("ls-tree", "-r", "--name-only", "glados/ledger").split()),
            {self.REC1, self.REC2})



class TestPiAdapter(unittest.TestCase):

    def test_pi_prompt_templates(self):
        """pi mode emits flat .pi/prompts/glados-<core>.md templates with a
        description and an argument trailer, and leaves user prompts alone."""
        t = make_target()
        user_prompt = t / ".pi" / "prompts" / "mine.md"
        user_prompt.parent.mkdir(parents=True)
        user_prompt.write_text("my own template\n", encoding="utf-8")
        rc, out = install("pi", t)
        self.assertEqual(rc, 0, out)
        prompts = t / ".pi" / "prompts"
        fix = prompts / "glados-fix-bug.md"
        self.assertTrue(fix.is_file(), "glados-fix-bug.md missing")
        text = read(fix)
        self.assertTrue(text.startswith("---\ndescription: "), "no frontmatter")
        self.assertIn("${ARGUMENTS:-", text, "argument trailer missing")
        self.assertEqual(text.count("${ARGUMENTS"), 1,
                         "only the trailer may carry a placeholder")
        self.assertFalse(any(p.is_dir() for p in prompts.iterdir()),
                         "pi loads only direct children; no subdirectories")
        # reinstall keeps user files, prunes only glados-* leftovers
        stale = prompts / "glados-retired.md"
        stale.write_text("old\n", encoding="utf-8")
        self.assertEqual(install("pi", t)[0], 0)
        self.assertTrue(user_prompt.is_file(), "user prompt was removed")
        self.assertFalse(stale.exists(), "stale glados-* prompt kept")

if __name__ == "__main__":
    unittest.main(verbosity=2)
