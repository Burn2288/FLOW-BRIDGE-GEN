#!/bin/sh
set -eu
umask 077
: "${1:?usage: backup.sh /private/path/backup.dump}"
# Encrypt and transfer backup using your deployment's secret manager/off-host backup system.
docker compose exec -T db pg_dump -U elevenbot -d elevenbot -Fc > "$1"
