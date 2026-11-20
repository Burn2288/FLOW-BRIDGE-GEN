"""Structural guard regression: no network or private credentials."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('completion_checker', ROOT/'.github/check_completion_register.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class CompletionRegisterTest(unittest.TestCase):
    def setUp(self):
        p = ROOT/'docs/planning'
        self.old = json.loads((p/'historical-tasks-v1.json').read_text(encoding='utf-8'))['tasks']
        self.data = json.loads((p/'completion-level-register.json').read_text(encoding='utf-8'))
        self.task = next(t for t in self.data['tasks'] if t.get('evidence'))

    def reject(self):
        with self.assertRaises((AssertionError, KeyError, TypeError)):
            checker.validate(self.old, self.data)

    def test_valid_registry(self):
        self.assertGreater(checker.validate(self.old, self.data), 0)

    def test_bad_sha(self):
        self.task['evidence'][0]['checkout_sha'] = 'bad'
        self.reject()

    def test_bad_task_id(self):
        self.task['evidence'][0]['task_id'] = 'WRONG-01'
        self.reject()

    def test_missing_candidate_evidence(self):
        self.task['evidence'] = []
        self.reject()

    def test_premature_completion(self):
        self.task['completed_level'] = 'FUNCTIONAL_TEST'
        self.reject()

    def test_synthetic_tree_requires_proof(self):
        self.task['evidence'][0]['tree_relation'] = 'SYNTHETIC_EQUAL_TREE'
        self.task['evidence'][0]['tree_proof_url'] = None
        self.reject()


if __name__ == '__main__':unittest.main()
