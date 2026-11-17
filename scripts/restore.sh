#!/bin/sh
set -eu
: "${1:?usage: restore.sh backup.dump new_isolated_database}"
: "${2:?provide NEW isolated database name; never production}"
case "$2" in restore_test_*) ;; *) echo 'Only restore_test_* DB names allowed' >&2; exit 1;; esac
# Caller stops bot/worker first. Never restores over production.
docker compose exec -T db createdb -U elevenbot "$2"
docker compose exec -T db pg_restore -U elevenbot -d "$2" --exit-on-error < "$1"
# Upgrade the isolated copy before writing states added by newer migrations.
docker compose run --rm --no-deps --build -e DARKFLOW_RESTORE_DB="$2" --entrypoint python migrate -c '
import asyncio, os
from urllib.parse import urlsplit
from elevenbot.db import connect, migrate

async def main():
    dsn = urlsplit(os.environ["DATABASE_URL"])
    target = dsn._replace(path="/" + os.environ["DARKFLOW_RESTORE_DB"]).geturl()
    pool = await connect(target)
    try:
        await migrate(pool)
    finally:
        await pool.close()

asyncio.run(main())
'
# Snapshot may predate a provider dispatch/payment: never resume it automatically.
docker compose exec -T db psql -U elevenbot -d "$2" -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
UPDATE settings SET halted=true WHERE id=1;
UPDATE jobs SET status='uncertain',error_code='RESTORE_REVIEW',lease_until=NULL WHERE status IN ('queued','dispatching');
UPDATE payments SET status='review' WHERE status='pending';
UPDATE deliveries SET status='uncertain',lease_until=NULL WHERE status IN ('sending','retry');
COMMIT;
SQL
