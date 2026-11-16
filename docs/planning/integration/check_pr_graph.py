"""Validate graph offline; --verify-live compares public GitHub PR state and refs."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--verify-live', action='store_true')
args = parser.parse_args()
graph = json.loads((Path(__file__).parent / 'pr-graph.json').read_text(encoding='utf8'))
prs = {p['pr']: p for p in graph['prs']}
assert set(prs) == {1, 2, 4, 6, 7, *range(8, 20)}
for n, p in prs.items():
    for dep in p['depends_on']:
        assert dep in prs and prs[dep]['head_branch'] == p['base_branch']
    if args.verify_live:
        req = Request(f'https://api.github.com/repos/Burn2288/FLOW-BRIDGE-GEN/pulls/{n}', headers={'User-Agent': 'FlowBridge-IN01', 'Accept': 'application/vnd.github+json'})
        with urlopen(req, timeout=15) as f:
            actual = json.load(f)
        expected = (p['base_branch'], p['base_sha'], p['head_branch'], p['head_sha'], p['state'], p['draft'], p['merged'])
        observed = (actual['base']['ref'], actual['base']['sha'], actual['head']['ref'], actual['head']['sha'], actual['state'], actual['draft'], actual['merged'])
        if expected != observed:
            raise SystemExit(f'PR #{n} changed: expected {expected}, got {observed}')
print(f'PR graph: {len(prs)} PRs; dependency references valid; live={args.verify_live}')
