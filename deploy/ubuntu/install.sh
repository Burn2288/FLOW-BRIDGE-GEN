#!/usr/bin/env bash
# Fresh dedicated Ubuntu host only. Does not install/upgrade OS packages or start services.
set -euo pipefail
if [[ $# -gt 1 || ( $# -eq 1 && $1 != --check ) ]]; then echo 'Usage: sudo bash install.sh [--check]' >&2; exit 2; fi
if [[ ${EUID} -ne 0 ]]; then echo 'Run with sudo on the target Ubuntu host.' >&2; exit 1; fi
source /etc/os-release
if [[ ${ID:-} != ubuntu || ${VERSION_ID:-} != 24.04 ]]; then echo 'Target: Ubuntu 24.04 LTS only. No changes made.' >&2; exit 1; fi
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
for path in /opt/darkflow /etc/darkflow /var/lib/darkflow; do
    if [[ -e $path ]]; then echo "Existing $path: use documented update procedure; refusing overwrite." >&2; exit 1; fi
done
if getent passwd darkflow >/dev/null || getent group darkflow >/dev/null; then echo 'Existing darkflow identity: refusing changes.' >&2; exit 1; fi
for tool in python3.12 pg_dump pg_restore ffprobe systemctl; do
    command -v "$tool" >/dev/null || { echo 'Install required OS packages first: python3.12 python3.12-venv postgresql-16 postgresql-client-16 ffmpeg' >&2; exit 1; }
done
pg_dump --version | grep -Eq 'PostgreSQL\) 16\.' || { echo 'PostgreSQL client 16 required.' >&2; exit 1; }
python3.12 -m venv --help >/dev/null
python3.12 -c 'import ensurepip'
[[ -d /run/systemd/system ]] || { echo 'A booted systemd host is required.' >&2; exit 1; }
for component in migrate bot worker; do
    if [[ -e /etc/systemd/system/darkflow-${component}.service ]]; then echo 'Existing systemd unit; inspect installation before proceeding.' >&2; exit 1; fi
done
if [[ ${1:-} == --check ]]; then echo 'Fresh-host prerequisites OK; no changes made.'; exit 0; fi
umask 022
useradd --system --user-group --home-dir /var/lib/darkflow --no-create-home --shell /usr/sbin/nologin darkflow
install -d -m 0755 /opt/darkflow
install -d -m 0700 /etc/darkflow
install -d -o darkflow -g darkflow -m 0700 /var/lib/darkflow
# Explicit source allowlist: no .env, private-db, local venv, Git directory or audio/cache.
for name in src migrations assets deploy scripts tests; do
    tar -C "$SOURCE" --exclude=__pycache__ --exclude='*.pyc' -cf - "$name" | tar -C /opt/darkflow -xf -
done
for name in pyproject.toml uv.lock requirements-service.txt requirements-acceptance.txt tests/required_s2_cases.json RELEASE_METADATA.json; do
    if [[ -f $SOURCE/$name ]]; then install -m 0644 "$SOURCE/$name" "/opt/darkflow/$name"; fi
done
for name in "$SOURCE"/*.md; do [[ ! -f $name ]] || install -m 0644 "$name" /opt/darkflow/; done
python3.12 -m venv /opt/darkflow/.venv
/opt/darkflow/.venv/bin/python -m pip install -r /opt/darkflow/requirements-service.txt
chmod -R a+rX /opt/darkflow
chown -R root:root /opt/darkflow
PYTHONPATH=/opt/darkflow/src /opt/darkflow/.venv/bin/python -c 'from elevenbot.config import Config; from elevenbot.telegram import TelegramApp; from elevenbot.worker import Worker; print("Service imports OK")'
install -m 0644 /opt/darkflow/deploy/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
echo 'Installed code and inactive units. Next: sudo bash /opt/darkflow/deploy/ubuntu/configure.sh'
echo 'No Telegram token, public access, payments or service start was performed.'
