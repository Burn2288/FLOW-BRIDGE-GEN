"""Validate planning DAG and developer evidence packages, without network calls."""
from pathlib import Path
import copy
import hashlib
import json
import re
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILES = ['MANIFEST.json', 'SUMMARY.md', 'SOURCE_BASELINE.md', 'CHANGES.md',
                 'TEST_RESULTS.md', 'CONTRACT_COMPLIANCE.md', 'EVIDENCE.md',
                 'REGRESSION.md', 'RISKS_AND_LIMITATIONS.md', 'BRANCH_SYNC.md', 'AUDIT_REQUEST.md']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    registry = read(ROOT / 'docs/planning/tasks.json')
    tasks = registry['tasks']
    by_id = {t['task_id']: t for t in tasks}
    require(len(by_id) == len(tasks), 'Duplicate TASK_ID')
    visiting, visited = set(), set()

    def visit(task_id):
        require(task_id in by_id, f'Unknown dependency: {task_id}')
        require(task_id not in visiting, f'Dependency cycle: {task_id}')
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in by_id[task_id]['dependencies']:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    master = (ROOT / 'docs/planning/MASTER_WORK_BREAKDOWN.md').read_text(encoding='utf-8')
    contracts = set(re.findall(r'\| (C-\d{3}) \|', (ROOT / 'docs/contracts/CONTRACT_REGISTRY.md').read_text(encoding='utf-8')))
    snapshot = read(ROOT / 'docs/planning/evidence/github-snapshot.json')
    prs = {p['number']: p for p in snapshot['prs']}
    fields = ('task_id', 'epic_id', 'title', 'developer', 'reviewer', 'stage', 'priority',
              'dependencies', 'change', 'test', 'proof', 'acceptance', 'state', 'effort',
              'paths', 'contract_ids', 'source_pr', 'source_sha', 'status',
              'integration_owner', 'parallel_with', 'risk', 'artifacts')
    for task in tasks:
        task_id = task['task_id']
        visit(task_id)
        require(all(field in task for field in fields), f'{task_id}: missing card field')
        require(task['developer'] in ('Burn2288', 'vankhu21'), f'{task_id}: invalid owner')
        require(task['reviewer'] in ('Burn2288', 'vankhu21') and task['reviewer'] != task['developer'], f'{task_id}: self-review')
        require(task['stage'] in [f'S{i}' for i in range(9)], f'{task_id}: bad stage')
        require(task['priority'] in ('P0', 'P1', 'P2', 'P3'), f'{task_id}: bad priority')
        require(set(task['contract_ids']) <= contracts, f'{task_id}: unknown contract')
        require(task['source_sha'] == prs[task['source_pr']]['head_sha'], f'{task_id}: stale source SHA')
        require(set(task['parallel_with']) <= by_id.keys(), f'{task_id}: unknown parallel task')
        require(f'### {task_id}\n' in master, f'{task_id}: no full card')
        worklist = (ROOT / f'docs/workplans/{task["developer"].lower()}.md').read_text(encoding='utf-8')
        require(f'## {task_id} —' in worklist, f'{task_id}: missing personal worklist')

    schema = read(ROOT / 'docs/audit/MANIFEST.schema.json')
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    manifests = list((ROOT / 'docs/audit/handoffs').glob('*/MANIFEST.json'))
    require(bool(manifests), 'No handoff packages')
    for path in manifests:
        manifest = read(path)
        errors = sorted(validator.iter_errors(manifest), key=lambda e: str(e.path))
        require(not errors, f'{path}: ' + '; '.join(e.message for e in errors))
        require(manifest['developer'] != manifest['reviewer'], f'{path}: self-review')
        require(path.parent.name == manifest['task_id'], f'{path}: TASK_ID mismatch')
        for file in PACKAGE_FILES:
            require((path.parent / file).is_file(), f'{path}: missing {file}')
        for name in manifest['evidence_paths']:
            target = (ROOT / name).resolve()
            require(target.is_relative_to(ROOT), f'Evidence path escapes root: {name}')
            require(target.is_file(), f'Missing evidence: {name}')
            require(name in manifest['evidence_hashes'], f'Missing hash: {name}')
            require(hashlib.sha256(target.read_bytes()).hexdigest() == manifest['evidence_hashes'][name], f'Evidence checksum mismatch: {name}')
        require(set(manifest['evidence_hashes']) == set(manifest['evidence_paths']), 'Hash/path inventory differs')
        if manifest['ready_for_audit']:
            require(not any(r['status'] == 'FAIL' for r in manifest['test_results']), 'READY with failed check')
            require(any(r['type'] == 'documentation' and r['status'] == 'PASS' for r in manifest['test_results']), 'READY without docs proof')

    # Negative schema fixtures are in-memory copies, never published false evidence.
    example = read(manifests[0])
    mutations = []
    invalid = copy.deepcopy(example); del invalid['head_sha']; mutations.append(invalid)
    invalid = copy.deepcopy(example); invalid['head_sha'] = 'latest'; mutations.append(invalid)
    invalid = copy.deepcopy(example); invalid['ready_for_audit'] = True; invalid['pr_url'] = None; mutations.append(invalid)
    invalid = copy.deepcopy(example); invalid['ready_for_audit'] = True; invalid['publication_status'] = 'LOCAL_ONLY'; mutations.append(invalid)
    invalid = copy.deepcopy(example); invalid['test_results'][0]['status'] = 'GREEN'; mutations.append(invalid)
    invalid = copy.deepcopy(example); invalid['evidence_hashes'] = {}; mutations.append(invalid)
    require(all(not validator.is_valid(item) for item in mutations), 'Invalid fixture accepted')

    # Verify TASK_ID anchor links (the pre-existing checker validates relative files).
    links = 0
    for path in (ROOT / 'docs').rglob('*.md'):
        for target, anchor in re.findall(r'\]\(([^)#\s]+)#([A-Za-z][A-Za-z0-9-]+)\)', path.read_text(encoding='utf-8')):
            if '://' in target:
                continue
            if target.endswith('MASTER_WORK_BREAKDOWN.md'):
                require(anchor.upper() in by_id, f'{path}: invalid task anchor {anchor}')
                links += 1
    print(f'Planning: {len(tasks)} tasks, {len({t["epic_id"] for t in tasks})} epics, acyclic DAG, two worklists, {len(contracts)} contracts')
    print(f'Evidence: {len(manifests)} schema-valid packages, required files and hashes checked; {len(mutations)} invalid fixtures rejected')
    print(f'Task anchor links checked: {links}')


if __name__ == '__main__':
    main()
