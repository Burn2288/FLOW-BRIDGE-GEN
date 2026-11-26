import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from jsonschema import ValidationError

from scripts.check_audit_handoff_candidate import validate_candidate


class CandidateGateTests(unittest.TestCase):
    def setUp(self):
        payload = self.enterContext(tempfile.TemporaryDirectory())
        self.payload = Path(payload)
        self.file = self.payload / "results.txt"
        self.file.write_bytes(b"synthetic test result")
        self.digest = hashlib.sha256(self.file.read_bytes()).hexdigest()
        self.source = {
            "repository": "Burn2288/FLOW-BRIDGE-GEN",
            "base_sha": "1" * 40,
            "head_sha": "2" * 40,
            "tree_sha": "3" * 40,
        }
        self.manifest = {
            "schema_version": 1, "task_id": "AU-01", "batch_id": "AUDIT-TEST-01",
            "source": copy.deepcopy(self.source), "developer": "Burn2288",
            "reviewer": None, "acceptance_state": "CANDIDATE_NOT_ACCEPTED",
            "owner_approval": None, "archive_location": None,
            "pr_url": "https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/27",
            "changed_scope": ["synthetic test fixture"],
            "tests": [{
                "workflow_url": "https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/1",
                "checkout_sha": "2" * 40, "checkout_tree": "3" * 40,
                "conclusion": "SUCCESS", "summary": "synthetic",
            }],
            "artifacts": {"results.txt": self.digest},
        }

    def validate(self, **options):
        validate_candidate(self.manifest, self.payload, expected_source=self.source, **options)

    def test_valid_offline_candidate(self):
        self.validate(previous_hashes={"results.txt": self.digest})

    def test_missing_sha(self):
        del self.manifest["source"]["head_sha"]
        with self.assertRaises(ValidationError):
            self.validate()

    def test_mismatched_ci_tree(self):
        self.manifest["tests"][0]["checkout_tree"] = "5" * 40
        with self.assertRaisesRegex(ValueError, "not exact"):
            self.validate()

    def test_substituted_source(self):
        self.manifest["source"]["tree_sha"] = "4" * 40
        self.manifest["tests"][0]["checkout_tree"] = "4" * 40
        with self.assertRaisesRegex(ValueError, "trusted source"):
            self.validate()

    def test_missing_artifact(self):
        self.file.unlink()
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            self.validate()

    def test_unregistered_artifact(self):
        (self.payload / "unexpected.txt").write_bytes(b"unregistered")
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            self.validate()

    def test_invalid_checksum(self):
        self.manifest["artifacts"]["results.txt"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.validate()

    def test_false_ready(self):
        self.manifest["acceptance_state"] = "READY"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_self_pass(self):
        self.manifest["reviewer"] = {
            "identity": "burn2288", "verdict": "PASS",
            "evidence_url": "https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/1#issuecomment-1",
        }
        with self.assertRaisesRegex(ValueError, "self-review"):
            self.validate()

    def test_overwritten_history_with_recomputed_checksum(self):
        self.file.write_bytes(b"rewritten prior result")
        self.manifest["artifacts"]["results.txt"] = hashlib.sha256(self.file.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "historical artifact"):
            self.validate(previous_hashes={"results.txt": self.digest})
