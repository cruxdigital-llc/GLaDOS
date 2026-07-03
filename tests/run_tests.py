#!/usr/bin/env python3
"""GLaDOS v2 self-test — stdlib unittest, no third-party deps.

Run from the repo root (or anywhere):  python tests/run_tests.py

Compiles every adapter over the fixtures and exercises the type-checker,
cleanup, determinism, drift detection and the runtime artifacts. A mode that
stops shipping modules — v1's flagship bug — fails this build.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
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
        """All six modes compile with zero unresolved includes/placeholders."""
        forbidden = ["{{", "<!-- glados:include"]
        for mode in ["claude", "direct", "gemini", "antigravity", "aistudio"]:
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

    def test_determinism(self):
        """Two installs of the same mode produce byte-identical trees."""
        for mode in ("claude", "direct", "gemini", "antigravity", "aistudio",
                     "claude-plugin"):
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
        gy.write_text(read(gy) + "\n# structural edit\n",
                      encoding="utf-8", newline="\n")
        rc, out = run_cli("check", "--target", t, "--source", REPO)
        self.assertEqual(rc, 1)
        self.assertIn("stale compile", out)


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

    def test_personas_vendored(self):
        """Every install mode vendors the full src/personas/ library into
        <target>/.glados/personas/, byte-identical — panels resolve library
        personas from there (project product-knowledge/personas/ wins)."""
        src_personas = sorted((REPO / "src" / "personas").glob("*.md"))
        self.assertGreater(len(src_personas), 0, "library personas missing")
        for mode in ("claude", "claude-plugin", "direct", "gemini",
                     "antigravity", "aistudio"):
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
        text = read(EXAMPLE) + "\ndisabled-workflows: [run-epicc]\n"
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
