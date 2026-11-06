#!/usr/bin/env bash
set -euo pipefail
[[ ${EUID} -eq 0 && $# -eq 1 ]] || { echo 'Usage: sudo bash backup.sh /private/new-backup-directory' >&2; exit 1; }
[[ ! -e $1 ]] || { echo 'Backup destination must be new.' >&2; exit 1; }
ACTIVE=()
for component in bot worker; do
    if systemctl is-active --quiet "darkflow-${component}.service"; then ACTIVE+=("darkflow-${component}.service"); fi
done
resume() { if [[ ${#ACTIVE[@]} -gt 0 ]]; then systemctl start "${ACTIVE[@]}"; fi; }
trap resume EXIT
systemctl stop darkflow-bot.service darkflow-worker.service
if systemctl is-active --quiet darkflow-bot.service || systemctl is-active --quiet darkflow-worker.service; then echo 'Services did not stop; no backup taken.' >&2; exit 1; fi
umask 077
export PYTHONPATH=/opt/darkflow/src
/opt/darkflow/.venv/bin/python -m elevenbot.snapshot backup --config /etc/darkflow/runtime.env --output "$1"
