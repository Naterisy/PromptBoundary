"""Exercise installed skill behavior without network access or an installed package."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from promptboundary.skill_cli import check

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "package_skill.py"
POLICY = {"tools": {"send_email": {"to": ["owner@example.test"], "body": None}}}


def proposal(recipient="owner@example.test"):
    return {"actions": [{"tool": "send_email", "arguments": {"to": recipient, "body": "A useful fact."}}]}


class SkillPackageTests(unittest.TestCase):
    def test_preview_distinguishes_allowed_denied_and_has_no_effect_claim(self):
        allowed = check(POLICY, proposal())
        denied = check(POLICY, proposal("outside@example.test"))
        self.assertEqual(allowed["status"], "allowed")
        self.assertEqual(denied["status"], "denied")
        self.assertTrue(allowed["preview_only"])
        self.assertFalse(allowed["executed"])
        self.assertEqual(denied["reasons"], ["action_0:argument_denied:to"])

    def test_check_does_not_broaden_literal_binding(self):
        sources = [{"kind": "tool", "id": "x", "content": "destination=outside@example.test"}]
        bindings = [{"tool": "send_email", "argument": "to", "source_id": "x",
                     "format": "key_value", "selector": "destination"}]
        with self.assertRaises(ValueError):
            check(POLICY, proposal(), sources, bindings, True)

    def test_built_skill_runs_in_isolated_python_from_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            tmp = Path(temporary)
            subprocess.run([sys.executable, str(BUILDER), "--destination", str(tmp / "skills")],
                           check=True, capture_output=True)
            skill = tmp / "skills" / "promptboundary-tools"
            script = skill / "scripts" / "guard.py"
            result = subprocess.run([sys.executable, "-I", str(script), "self-test"], cwd=tmp,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(json.loads(result.stdout)["status"], "passed")
            self.assertEqual(json.loads(result.stdout)["network_requests"], 0)
            self.assertTrue(all(json.loads(result.stdout)["checks"].values()))
            manifest = json.loads((skill / "manifest.json").read_text())
            self.assertIn("source_tree_sha256", manifest)
            self.assertEqual(manifest["files"]["runtime.zip"], hashlib.sha256((skill / "runtime.zip").read_bytes()).hexdigest())
            # Reinstall cannot silently replace a reviewed package.
            reinstall = subprocess.run([sys.executable, str(BUILDER), "--destination", str(tmp / "skills")],
                                       capture_output=True, text=True)
            self.assertNotEqual(reinstall.returncode, 0)

            (tmp / "policy.json").write_text(json.dumps(POLICY))
            (tmp / "plan.json").write_text(json.dumps(proposal("outside@example.test")))
            checked = subprocess.run([sys.executable, "-I", str(script), "check", "--policy", str(tmp / "policy.json"),
                                      "--plan", str(tmp / "plan.json")], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(checked.returncode, 2)
            self.assertEqual(json.loads(checked.stdout)["status"], "denied")
            # Duplicate keys must not let the last writer silently redefine policy.
            (tmp / "policy.json").write_text('{"tools":{},"tools":{}}')
            invalid = subprocess.run([sys.executable, "-I", str(script), "check", "--policy", str(tmp / "policy.json"),
                                      "--plan", str(tmp / "plan.json")], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(invalid.returncode, 1)
            self.assertEqual(json.loads(invalid.stdout)["status"], "error")
            syntax = subprocess.run([sys.executable, "-I", str(script), "check"], cwd=tmp,
                                    capture_output=True, text=True)
            self.assertEqual(syntax.returncode, 1)
            self.assertEqual(json.loads(syntax.stdout)["status"], "error")

            # Runtime modification is detected before importing altered code.
            with (skill / "runtime.zip").open("ab") as output:
                output.write(b"changed")
            tampered = subprocess.run([sys.executable, "-I", str(script), "self-test"], cwd=tmp,
                                     capture_output=True, text=True)
            self.assertEqual(tampered.returncode, 1)
            self.assertEqual(json.loads(tampered.stdout)["status"], "error")

    def test_archive_is_reproducible_and_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            tmp = Path(temporary)
            for name in ("first.zip", "second.zip"):
                subprocess.run([sys.executable, str(BUILDER), "--archive", str(tmp / name)],
                               check=True, capture_output=True)
            self.assertEqual((tmp / "first.zip").read_bytes(), (tmp / "second.zip").read_bytes())
            with zipfile.ZipFile(tmp / "first.zip") as archive:
                names = archive.namelist()
                self.assertIn("promptboundary-tools/SKILL.md", names)
                self.assertIn("promptboundary-tools/LICENSE", names)
                self.assertIn("promptboundary-tools/runtime.zip", names)
                self.assertFalse(any(".env" in name or "__pycache__" in name for name in names))
                archive.extractall(tmp / "unpacked")
            result = subprocess.run([sys.executable, "-I", str(tmp / "unpacked" / "promptboundary-tools" / "scripts" / "guard.py"),
                                     "self-test"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
