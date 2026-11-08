"""Tests for bundled tools, not for arbitrary user repositories."""
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module("brainaid_validate_spec", SCRIPTS / "validate_spec.py")
auditor = load_module("brainaid_audit_project", SCRIPTS / "audit_project.py")
lab = load_module("brainaid_fault_lab", SCRIPTS / "fault_lab.py")


class SkillTests(unittest.TestCase):
    def test_skill_metadata_name_and_description(self):
        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\n"))
        header = content.split("---", 2)[1]
        name = re.search(r"^name:\s*(.*)$", header, flags=re.MULTILINE)
        desc = re.search(r"^description:\s*(.*)$", header, flags=re.MULTILINE)
        self.assertIsNotNone(name)
        self.assertIsNotNone(desc)
        self.assertEqual(name.group(1), ROOT.name)
        self.assertLessEqual(len(desc.group(1)), 1024)
        self.assertLessEqual(len(name.group(1)), 64)
        self.assertLess(len(content.splitlines()), 500)

    def test_valid_spec_has_no_errors(self):
        obj = json.loads((ROOT / "examples/content_pipeline.json").read_text(encoding="utf-8"))
        result = validator.validate(obj)
        self.assertFalse([x for x in result if x["severity"] == "ERROR"], result)

    def test_invalid_spec_fails(self):
        obj = json.loads((ROOT / "examples/invalid_graph.json").read_text(encoding="utf-8"))
        codes = {x["code"] for x in validator.validate(obj)}
        self.assertIn("TRAPPED_CYCLE", codes)
        self.assertIn("MISSING_GUARD", codes)
        self.assertIn("NO_EXIT_PATH", codes)

    def test_static_scanner_finds_unsafe_fixture(self):
        result = auditor.audit(ROOT / "fixtures")
        codes = {x["code"] for x in result["findings"]}
        self.assertEqual(result["scanned_files"], 1)
        self.assertTrue({"WHILE_TRUE", "GRAPH_CYCLE", "EXTERNAL_EFFECT"}.issubset(codes), codes)

    def test_fault_lab_all_scenarios(self):
        self.assertEqual(len(lab.SCENARIOS), 12)
        for scenario in lab.SCENARIOS:
            with self.subTest(scenario=scenario):
                outcome = lab.run_scenario(scenario)
                self.assertTrue(outcome["pass"], outcome)
                self.assertEqual(outcome["environment"], "OFFLINE_SIMULATION")

    def test_invalid_untrusted_graph_types_are_reported_not_crashed(self):
        invalid = {
            "nodes": [{"id": "begin", "type": "START"}, {"id": "end", "type": "END"}],
            "start": ["begin"], "end": "end",
            "edges": [{"from": [], "to": "end", "on": "PASS"}],
            "approval": {"required_nodes": None},
            "external_actions": [{"node": "end", "requires_approval": True}],
        }
        codes = {x["code"] for x in validator.validate(invalid)}
        self.assertTrue({"TERMINALS", "BAD_EDGE", "APPROVAL_FORMAT", "APPROVAL_BINDING"}.issubset(codes), codes)

    def test_long_graph_no_recursion_error(self):
        nodes = [{"id": "n0", "type": "START"}] + [
            {"id": f"n{i}", "type": "TOOL_CALL"} for i in range(1, 1300)
        ] + [{"id": "end", "type": "END"}]
        edges = [{"from": f"n{i}", "to": f"n{i+1}", "on": "NEXT"} for i in range(1299)]
        edges.extend([{"from": "n1299", "to": "end", "on": "NEXT"}])
        result = validator.validate({"nodes": nodes, "edges": edges, "start": "n0", "end": "end"})
        self.assertFalse(any(x["severity"] == "ERROR" for x in result), result)

    def test_package_doctor(self):
        proc = subprocess.run([sys.executable, str(SCRIPTS / "doctor.py")], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS skill_frontmatter", proc.stdout)

    def test_installer_force_keeps_backup(self):
        with tempfile.TemporaryDirectory(prefix="brainaid-install-upgrade-") as directory:
            root = Path(directory)
            base = [sys.executable, str(ROOT / "install_skill.py"), "--target", "codex", "--scope", "project", "--project", str(root)]
            first = subprocess.run(base, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            destination = root / ".agents" / "skills" / "brainaid-agent-architect"
            (destination / "local-user-note.txt").write_text("keep me", encoding="utf-8")
            upgrade = subprocess.run(base + ["--force"], capture_output=True, text=True)
            self.assertEqual(upgrade.returncode, 0, upgrade.stderr)
            backup = list(destination.parent.glob("brainaid-agent-architect.backup-*"))
            self.assertEqual(len(backup), 1)
            self.assertTrue((backup[0] / "local-user-note.txt").is_file())
            self.assertFalse((destination / "local-user-note.txt").exists())
            self.assertTrue((destination / "SKILL.md").is_file())

    def test_installer_real_copy_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="brainaid-install-live-") as directory:
            project = Path(directory)
            args = [sys.executable, str(ROOT / "install_skill.py"), "--target", "both", "--scope", "project", "--project", str(project)]
            first = subprocess.run(args, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue((project / ".claude/skills/brainaid-agent-architect/SKILL.md").is_file())
            self.assertTrue((project / ".agents/skills/brainaid-agent-architect/SKILL.md").is_file())
            second = subprocess.run(args, capture_output=True, text=True, check=False)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("already exists", second.stderr)

    def test_installer_dry_run(self):
        with tempfile.TemporaryDirectory(prefix="brainaid-install-test-") as directory:
            destination = Path(directory)
            result = subprocess.run([sys.executable, str(ROOT / "install_skill.py"), "--target", "both", "--scope", "project", "--project", str(destination), "--dry-run"], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("DRY RUN", result.stdout)
            self.assertFalse((destination / ".claude").exists())
            self.assertFalse((destination / ".agents").exists())


if __name__ == "__main__":
    unittest.main()
