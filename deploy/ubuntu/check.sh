#!/usr/bin/env bash
# Run BEFORE install.sh from a private checkout as a normal developer account.
set -euo pipefail
[[ ${EUID} -ne 0 ]] || { echo 'Run this test harness as a normal user, not root.' >&2; exit 1; }
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$SOURCE"
if [[ ! -d .acceptance-venv ]]; then python3.12 -m venv .acceptance-venv; fi
.acceptance-venv/bin/python -m pip install -r requirements-acceptance.txt
exec .acceptance-venv/bin/python scripts/run_native_acceptance.py
