"""Offline structural checks; links do not prove runtime behavior or remote availability."""
from pathlib import Path
import re

REPORT = Path(__file__).resolve().parents[1] / 'docs/planning/DC_01_CONTRACT_EVIDENCE.md'
SHA = 'd691d54e0266c3d519d66575555fa45895ef40ac'


def validate(text):
    rows = re.findall(r'^\| (C-\d{3}) \|(.+)$', text, re.M)
    expected = {f'C-{n:03}' for n in range(1, 32)}
    if len(rows) != 31 or {row[0] for row in rows} != expected:
        raise ValueError('missing or duplicate contract')
    for cid, body in rows:
        if not ('PARTIAL:' in body or 'DESIGN_DRAFT:' in body):
            raise ValueError(f'{cid}: unsupported status')
        if 'IMPLEMENTED' in body or 'ACCEPTED' in body:
            raise ValueError(f'{cid}: unproven acceptance')
        links = re.findall(r'https://github\.com/Burn2288/FLOW-BRIDGE-GEN/blob/([^/]+)/', body)
        if any(sha != SHA for sha in links):
            raise ValueError(f'{cid}: source not pinned')
        if 'NOT_ESTABLISHED' not in body and not links:
            raise ValueError(f'{cid}: missing evidence')


if __name__ == '__main__':
    validate(REPORT.read_text(encoding='utf-8'))
    print('DC-01: 31 unique conservative source-to-test rows; immutable SHA syntax OK')
