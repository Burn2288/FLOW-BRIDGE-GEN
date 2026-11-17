from pathlib import Path
import hashlib
import asyncpg

async def connect(dsn):
    return await asyncpg.create_pool(dsn,min_size=1,max_size=25,command_timeout=20)

async def migrate(pool):
    files=sorted((Path(__file__).resolve().parents[2]/'migrations').glob('*.sql'))
    if not files:raise RuntimeError('Migration files unavailable')
    async with pool.acquire() as c, c.transaction():
        await c.execute('SELECT pg_advisory_xact_lock(921181)')
        await c.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY, sha256 text NOT NULL)')
        for f in files:
            sql=f.read_text(encoding="utf-8"); digest=hashlib.sha256(sql.encode()).hexdigest()
            old=await c.fetchval('SELECT sha256 FROM schema_migrations WHERE version=$1',f.name)
            if old and old!=digest: raise RuntimeError('Migration checksum mismatch')
            if not old:
                await c.execute(sql)
                await c.execute('INSERT INTO schema_migrations VALUES($1,$2)',f.name,digest)
