"""Offline structure validation; GitHub evidence must be checked separately."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r'[0-9a-f]{40}\Z')
PR = re.compile(r'https://github\.com/Burn2288/FLOW-BRIDGE-GEN/pull/[1-9][0-9]*\Z')
RUN = re.compile(r'https://github\.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/[1-9][0-9]*\Z')


def validate(old, register):
    new = register['tasks']
    assert len(old) == len(new) == 81
    assert len({t['task_id'] for t in new}) == len(new)
    assert [t['task_id'] for t in old] == [t['task_id'] for t in new]
    assert all(a['dependencies'] == b['dependencies'] and a['developer'] == b['owner'] for a, b in zip(old, new))
    assert all(t['list_id'] == t['owner'] for t in new)
    assert all(t['global_list_id'] == 'MASTER' for t in new)
    assert all(set(t['dependencies']) <= {x['task_id'] for x in new} for t in new)
    for owner, count in [('Burn2288', 40), ('vankhu21', 41)]:
        rows = [t for t in new if t['owner'] == owner]
        assert [t['list_position'] for t in rows] == list(range(1, count + 1))
    assert [t['global_list_position'] for t in new] == list(range(1, 82))
    assert all(t['target_level'] == 'FUNCTIONAL_TEST' and t['completed_level'] is None for t in new)
    assert set(register['completion_levels']) == {'FUNCTIONAL_TEST', 'STANDARD', 'HIGH_PRODUCTION'}
    status_values = set(register['implementation_status_values'])
    assert {'NOT_ASSESSED','IN_PROGRESS','CANDIDATE_PREPARED','AWAITING_GLOBAL_ACCEPTANCE','BLOCKED','DEFERRED'} <= status_values
    assert all(t['implementation_status'] in status_values for t in new)
    graph = {t['task_id']: t['dependencies'] for t in new}
    def visit(node, active, done):
        assert node not in active, 'dependency cycle'
        if node in done:return
        active.add(node)
        for dep in graph[node]:visit(dep, active, done)
        active.remove(node);done.add(node)
    done = set()
    for node in graph:visit(node, set(), done)
    observed = register['observed_refs']
    for key in ('main_sha', 'integration_sha', 'candidate_sha'):
        assert SHA.fullmatch(observed[key])
    assert SHA.fullmatch(register['main_sha']) and SHA.fullmatch(register['source_registry_sha'])
    for task in new:
        evidence = task.get('evidence', [])
        assert isinstance(evidence, list)
        assert task['implementation_status'] in status_values
        assert task['global_audit_status'] in ('NOT_ASSESSED','PENDING_GLOBAL_AUDIT')
        if task['implementation_status'] == 'CANDIDATE_PREPARED':
            assert evidence, 'prepared candidate requires physical evidence'
        if task['implementation_status'] == 'AWAITING_GLOBAL_ACCEPTANCE':
            assert evidence, 'candidate awaiting acceptance requires physical evidence'
            assert task['global_audit_status'] == 'PENDING_GLOBAL_AUDIT'
        assert task['global_audit_status'] == 'NOT_ASSESSED'
        if evidence:
            assert task['implementation_status'] in ('CANDIDATE_PREPARED','AWAITING_GLOBAL_ACCEPTANCE')
            assert task['pr_ref'] == evidence[-1]['pr_url']
            assert task['tested_sha'] == evidence[-1]['tested_sha']
            assert task['integrated_sha'] == evidence[-1]['integrated_sha']
        else:
            assert task['pr_ref'] is None and task['tested_sha'] is None and task['integrated_sha'] is None
        seen = set()
        for item in evidence:
            assert (item['list_id'], item['list_position'], item['task_id']) == (task['list_id'], task['list_position'], task['task_id'])
            assert PR.fullmatch(item['pr_url']) and RUN.fullmatch(item['ci_url'])
            assert SHA.fullmatch(item['tested_sha']) and SHA.fullmatch(item['checkout_sha'])
            assert item['ci_conclusion'] == 'SUCCESS' and item['coverage'].strip() and item['limitations'].strip()
            assert (item['pr_url'], item['tested_sha']) not in seen
            seen.add((item['pr_url'], item['tested_sha']))
            if item['tree_relation'] == 'EXACT_HEAD':
                assert item['checkout_sha'] == item['tested_sha'] and item.get('tree_proof_url') is None
            else:
                assert item['tree_relation'] == 'SYNTHETIC_EQUAL_TREE' and item['checkout_sha'] != item['tested_sha']
                assert item['tree_proof_url'] == ('https://github.com/Burn2288/FLOW-BRIDGE-GEN/compare/' + item['tested_sha'] + '...' + item['checkout_sha'])
            if item['integrated_sha'] is not None:
                assert SHA.fullmatch(item['integrated_sha'])
                assert item['integrated_sha'] == observed['integration_sha']
                assert item['integration_evidence_url'] == ('https://github.com/Burn2288/FLOW-BRIDGE-GEN/compare/' + item['tested_sha'] + '...' + item['integrated_sha'])
            else:
                assert item['integration_evidence_url'] is None
    return sum(bool(t.get('evidence')) for t in new)


def main():
    p = ROOT / 'docs/planning'
    old = json.loads((p / 'historical-tasks-v1.json').read_text(encoding='utf-8'))['tasks']
    new = json.loads((p / 'completion-level-register.json').read_text(encoding='utf-8'))
    count = validate(old, new)
    print(f'81 tasks; owners, positions and DAG valid; {count} evidence-bearing records structurally valid; remote evidence not checked')


if __name__ == '__main__':main()
