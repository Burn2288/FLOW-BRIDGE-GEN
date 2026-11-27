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
        self.actual_data = json.loads((p/'completion-level-register.json').read_text(encoding='utf-8'))
        self.data = copy.deepcopy(self.actual_data)
        self.data.pop('acceptance_record', None)
        for task in self.data['tasks']:
            task['completed_level'] = None
        self.task = next(t for t in self.data['tasks'] if t.get('evidence'))

    def reject(self):
        with self.assertRaises((AssertionError, KeyError, TypeError)):
            checker.validate(self.old, self.data)

    def test_valid_registry(self):
        self.assertGreater(checker.validate(self.old, self.actual_data), 0)

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

    def accepted_fixture(self):
        self.task['completed_level'] = 'FUNCTIONAL_TEST'
        self.data['acceptance_record'] = {
            'task_ids': [self.task['task_id']],
            'accepted_product_head': '1' * 40,
            'accepted_product_tree': '2' * 40,
            'product_merge_sha': '3' * 40,
            'product_pr_url': 'https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/116',
            'owner_approval_ref': 'TEST FIXTURE ONLY',
            'main_target_ci_url': 'https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/1',
            'independent_audits': [dict(auditor_id=name, independence_confirmed=True,
                verdict='PASS_FUNCTIONAL_TEST', checked_head='1' * 40, checked_tree='2' * 40,
                report_sha256=digest * 64, report_ref='TEST FIXTURE ONLY')
                for name, digest in [('auditor A', 'a'), ('auditor B', 'b')]],
        }
        return self.data['acceptance_record']

    def test_documented_acceptance_is_structurally_valid(self):
        self.accepted_fixture()
        self.assertGreater(checker.validate(self.old, self.data), 0)

    def test_acceptance_cannot_cover_another_task(self):
        self.accepted_fixture()['task_ids'] = ['UNKNOWN-01']
        self.reject()

    def test_acceptance_rejects_same_auditor_twice(self):
        record = self.accepted_fixture()
        record['independent_audits'][1]['auditor_id'] = record['independent_audits'][0]['auditor_id']
        self.reject()

    def test_acceptance_rejects_different_tree(self):
        record = self.accepted_fixture()
        record['independent_audits'][1]['checked_tree'] = '4' * 40
        self.reject()

    def test_acceptance_requires_owner_approval_and_actual_merge(self):
        record = self.accepted_fixture()
        record['owner_approval_ref'] = ''
        self.reject()
        record['owner_approval_ref'] = 'TEST FIXTURE ONLY'
        record['product_merge_sha'] = record['accepted_product_head']
        self.reject()

    def test_implementation_status_is_separate_from_completed_level(self):
        self.task['implementation_status'] = 'AWAITING_GLOBAL_ACCEPTANCE'
        self.task['global_audit_status'] = 'PENDING_GLOBAL_AUDIT'
        self.assertEqual(checker.validate(self.old, self.data), sum(bool(t.get('evidence')) for t in self.data['tasks']))

    def test_unknown_implementation_status_rejected(self):
        self.task['implementation_status'] = 'DONE'
        self.reject()

    def test_current_integration_can_advance_past_historical_evidence(self):
        self.data['observed_refs']['integration_sha'] = 'a889d8306c743c0046b710b950608052eabfdc78'
        self.assertGreater(checker.validate(self.old, self.data), 0)

    def test_synthetic_tree_requires_proof(self):
        self.task['evidence'][0]['tree_relation'] = 'SYNTHETIC_EQUAL_TREE'
        self.task['evidence'][0]['tree_proof_url'] = None
        self.reject()


if __name__ == '__main__':unittest.main()
