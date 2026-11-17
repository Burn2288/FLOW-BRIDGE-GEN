"""Offline cross-document checks for the foundation reconciliation candidate."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / 'docs/planning/FOUNDATION_CONTRACT_AS_IS.md'
OWNER = ROOT / 'docs/planning/CONTRACT_OWNERSHIP.md'
REGISTRY = ROOT / 'docs/contracts/CONTRACT_REGISTRY.md'


def validate(matrix, owners, registry):
    expected = {f'C-{i:03}' for i in range(1, 32)}
    def ids(text):
        return re.findall(r'^\| (C-\d{3}) \|', text, re.M)
    for label, value in [('matrix', matrix), ('owners', owners), ('registry', registry)]:
        found = ids(value)
        if len(found) != 31 or set(found) != expected:
            raise ValueError(f'{label}: missing or duplicate contract ID')
    for line in matrix.splitlines():
        if re.match(r'^\| C-\d{3} \|', line):
            if not ('| PARTIAL:' in line or '| DESIGN_DRAFT:' in line):
                raise ValueError('unproven implementation status')
            for relative in re.findall(r'\]\((\.\./contracts/[^)]+)\)', line):
                if not (MATRIX.parent / relative).is_file():
                    raise ValueError(f'broken definition link: {relative}')
    for key in ('ADMIN_TELEGRAM_IDS', 'GENERATION_ENABLED', 'PAYMENTS_ENABLED',
                'DATABASE_URL', 'MINIAPP_URL', 'PROVIDER_MODE'):
        if f'`{key}`' not in matrix:
            raise ValueError(f'missing documented source configuration: {key}')
    if 'OWNER_DECISION_REQUIRED' not in matrix or 'D-02' not in matrix or 'D-04' not in matrix:
        raise ValueError('unresolved owner decisions lost')
    if 'new separate key/alias' not in matrix:
        raise ValueError('unimplemented admin alias must remain explicit')


def main():
    validate(*(p.read_text(encoding='utf-8') for p in (MATRIX, OWNER, REGISTRY)))
    print('Foundation contract IDs, links, conservative status and env inventory: PASS')


if __name__ == '__main__':
    main()
