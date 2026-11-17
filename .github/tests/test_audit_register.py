import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('audit_register',ROOT/'.github/check_audit_register.py')
checker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
directory=ROOT/'docs/audit/register'


class RegisterChecks(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((directory/'REGISTER.json').read_text(encoding='utf-8'))
        self.review=json.loads((directory/'DEFERRED_REVIEW.json').read_text(encoding='utf-8'))
        self.md=(directory/'DEFERRED_REVIEW.md').read_text(encoding='utf-8')

    def reject(self):
        with self.assertRaises(ValueError):checker.validate(self.data,self.review,self.md)

    def test_current_snapshot(self):
        self.assertEqual(checker.validate(self.data,self.review,self.md),(6,6,7))

    def test_duplicate_task_revision(self):
        self.data['entries'].append(copy.deepcopy(self.data['entries'][0]));self.reject()

    def test_invalid_sha(self):
        self.data['entries'][0]['source_sha']='short';self.reject()

    def test_invalid_url(self):
        self.data['entries'][0]['ci'][0]['url']='https://example.invalid/run';self.reject()

    def test_missing_evidence(self):
        self.data['entries'][0]['evidence_id']='missing';self.reject()

    def test_wrong_audit_pr(self):
        self.data['entries'][0]['private_audit_pr']='https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/11';self.reject()

    def test_bad_evidence_commit(self):
        self.data['evidence_catalog'][0]['audit_sha']='0'*40;self.reject()

    def test_bad_evidence_blob(self):
        self.data['evidence_catalog'][0]['report_git_blob_sha']='wrong';self.reject()

    def test_accepted_without_integration(self):
        self.data['entries'][0]['acceptance_status']='ACCEPTED';self.reject()

    def test_integration_without_commit(self):
        self.data['entries'][0]['integration_status']='INTEGRATED';self.reject()

    def test_peer_review_without_link(self):
        self.data['entries'][0]['peer_review']='PEER_REVIEW_COMPLETE';self.reject()

    def test_evidence_pass_without_success(self):
        self.data['entries'][0]['evidence_status']='TEST_EVIDENCE_PASS'
        self.data['entries'][0]['ci'][0]['status']='FAILURE';self.reject()

    def test_missing_review_link(self):
        self.data['entries'][0]['review_ids'].append('R-MISSING');self.reject()

    def test_missing_markdown_review(self):
        self.md='';self.reject()

    def test_stale_markdown_review(self):
        self.md=self.md.replace(self.review['items'][0]['risk'],'');self.reject()

    def test_wrong_review_pr(self):
        self.review['items'][0]['public_prs']=['https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/1'];self.reject()

    def test_synthetic_tree_proof_required(self):
        self.data['entries'][0]['ci'][0]['tree_proof_url']='';self.reject()

    def test_ci_evidence_bound_to_sha(self):
        self.data['entries'][2]['ci'][0]['tested_sha']='0'*40;self.reject()

    def test_candidate_and_evidence_crosslink(self):
        self.data['entries'][2]['candidate_sha']='0'*40;self.reject()

    def test_unknown_candidate_dependency(self):
        self.data['entries'][-1]['candidate_dependencies'].append('MISSING-TASK');self.reject()

    def test_dependency_cycle(self):
        self.data['entries'][2]['candidate_dependencies']=[self.data['entries'][-1]['task_id']];self.reject()

    def test_contract_not_self_approved(self):
        self.data['contract_status']='APPROVED';self.reject()


if __name__=='__main__':unittest.main()
