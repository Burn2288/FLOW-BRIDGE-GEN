from pathlib import Path
import json
p = Path(__file__).resolve().parents[1] / 'docs/planning'
old = json.loads((p / 'historical-tasks-v1.json').read_text(encoding='utf-8'))['tasks']
new = json.loads((p / 'completion-level-register.json').read_text(encoding='utf-8'))['tasks']
assert len(old) == len(new) == 81
assert len({t['task_id'] for t in new}) == len(new)
assert [t['task_id'] for t in old] == [t['task_id'] for t in new]
assert all(a['dependencies'] == b['dependencies'] and a['developer'] == b['owner'] for a,b in zip(old,new))
assert all(set(t['dependencies']) <= {x['task_id'] for x in new} for t in new)
for owner, count in [('Burn2288', 40), ('vankhu21', 41)]:
    rows = [t for t in new if t['owner'] == owner]
    assert [t['list_position'] for t in rows] == list(range(1, count + 1))
assert [t['global_list_position'] for t in new] == list(range(1, 82))
assert all(t['target_level'] == 'FUNCTIONAL_TEST' and t['completed_level'] is None for t in new)
# Historical dependency graph must remain acyclic.
graph = {t['task_id']: t['dependencies'] for t in new}
def visit(node, active, done):
    if node in active: raise AssertionError('dependency cycle: ' + node)
    if node in done: return
    active.add(node)
    for dep in graph[node]: visit(dep, active, done)
    active.remove(node); done.add(node)
done=set()
for node in graph: visit(node,set(),done)
print('81 unique tasks; 40/41 positions; historical dependencies preserved; DAG valid')
