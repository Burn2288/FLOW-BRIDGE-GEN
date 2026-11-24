"""Negative and history-preservation checks for the AU-02 synthetic handoff."""

import copy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs/audit/handoffs/AU-02-SYNTHETIC"
SPEC = importlib.util.spec_from_file_location("validate_au02_handoff", ROOT / "scripts/validate_au02_handoff.py")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))

    def copy_package(self, directory: Path):
        (directory / "r1").mkdir()
        (directory / "r2").mkdir()
        for name in ("r1/report.md", "r2/report.md"):
            (directory / name).write_bytes((PACKAGE / name).read_bytes())

    def run_rejecting(self, mutate):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.copy_package(root)
            manifest = copy.deepcopy(self.manifest)
            mutate(manifest, root)
            with self.assertRaises(CHECKER.HandoffError):
                CHECKER.validate(root, manifest)

    def test_synthetic_r1_r2_preserves_negative_verdict(self):
        self.assertEqual(CHECKER.validate(PACKAGE, self.manifest), (2, 2))
        self.assertEqual(self.manifest["revisions"][0]["verdict"]["result"], "REJECTED")
        self.assertEqual(
            self.manifest["revisions"][1]["verdict"]["preserved_prior_verdict"],
            self.manifest["revisions"][0]["verdict"],
        )

    def test_missing_file(self):
        self.run_rejecting(lambda data, _root: data["revisions"][0]["files"].__setitem__(0, {"path": "missing.md", "sha256": "0" * 64}))

    def test_wrong_hash(self):
        self.run_rejecting(lambda data, _root: data["revisions"][0]["files"][0].__setitem__("sha256", "0" * 64))

    def test_bad_schema(self):
        self.run_rejecting(lambda data, _root: data.__setitem__("schema_version", "unknown"))

    def test_missing_pr_reference(self):
        self.run_rejecting(lambda data, _root: data["revisions"][1].__setitem__("pr_url", ""))

    def test_missing_ci_reference(self):
        self.run_rejecting(lambda data, _root: data["revisions"][1].__setitem__("ci_url", None))

    def test_secret_canary(self):
        def mutate(data, root):
            (root / "r1/report.md").write_text("fixture secret: sk-ABCDEFGHIJKLMNOPQRSTUVWX", encoding="utf-8")
            data["revisions"][0]["files"][0]["sha256"] = CHECKER.hashlib.sha256((root / "r1/report.md").read_bytes()).hexdigest()

        self.run_rejecting(mutate)

    def test_r2_cannot_overwrite_or_drop_prior_verdict(self):
        self.run_rejecting(lambda data, _root: data["revisions"][1]["verdict"].__setitem__("preserved_prior_verdict", {"result": "PASS"}))

    def test_application_code_cannot_be_archived(self):
        self.run_rejecting(lambda data, _root: data["revisions"][1]["files"][0].__setitem__("path", "r2/source.py"))

    def test_unlisted_source_in_nested_directory(self):
        def mutate(_data, root):
            (root / "r2/nested").mkdir()
            (root / "r2/nested/source.py").write_text("pass", encoding="utf-8")

        self.run_rejecting(mutate)

    def test_unlisted_markdown(self):
        self.run_rejecting(lambda _data, root: (root / "r1/extra.md").touch())

    def test_same_report_used_for_both_revisions(self):
        self.run_rejecting(
            lambda data, _root: data["revisions"][1]["files"].__setitem__(
                0, copy.deepcopy(data["revisions"][0]["files"][0])
            )
        )

    def test_hard_link_cannot_supply_two_physical_reports(self):
        def mutate(data, root):
            other = root / "r2/report.md"
            other.unlink()
            os.link(root / "r1/report.md", other)
            data["revisions"][1]["files"][0]["sha256"] = data["revisions"][0]["files"][0]["sha256"]

        self.run_rejecting(mutate)

    def test_directory_symlink_rejected(self):
        def mutate(_data, root):
            try:
                (root / "alias").symlink_to(root / "r1", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

        self.run_rejecting(mutate)


if __name__ == "__main__":
    unittest.main()

