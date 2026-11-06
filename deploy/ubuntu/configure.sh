#!/usr/bin/env bash
# Configure only an installation made by install.sh. Never shell-source secrets.
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
[[ -x /opt/darkflow/.venv/bin/python ]] || { echo 'Run install.sh first.' >&2; exit 1; }
[[ ! -e /etc/darkflow/runtime.env ]] || { echo 'runtime.env already exists; nothing overwritten.' >&2; exit 1; }
umask 077
export PYTHONPATH=/opt/darkflow/src
cd /opt/darkflow
if [[ ! -e /etc/darkflow/db-private/database-result.json ]]; then
    .venv/bin/python -m elevenbot.database_setup --folder /etc/darkflow/db-private
fi
.venv/bin/python -c 'import json;from pathlib import Path;r=json.loads(Path("/etc/darkflow/db-private/database-result.json").read_text());assert r["status"]=="READY", "Partial database setup needs review"'
[[ ! -e /etc/darkflow/migration.env ]] || { echo 'Existing migration.env; review partial setup.' >&2; exit 1; }
install -o root -g root -m 0600 /etc/darkflow/db-private/migration.env /etc/darkflow/migration.env
.venv/bin/python -m elevenbot.setup_service --env-file /etc/darkflow/runtime.env --database-file /etc/darkflow/db-private/database.env --state-dir /var/lib/darkflow
chmod 0600 /etc/darkflow/runtime.env
.venv/bin/python -m elevenbot --env-file /etc/darkflow/runtime.env doctor
echo 'Configuration and DB doctor complete. Review acceptance results before enabling services.'
echo 'Start only when ready: sudo systemctl enable --now darkflow-bot darkflow-worker'
