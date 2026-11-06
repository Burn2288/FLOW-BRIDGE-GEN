"""Actual pg_dump/pg_restore into an isolated newly created DB; never production."""
import os,uuid,asyncio
from urllib.parse import urlparse,unquote
import pytest
from elevenbot.worker import Worker
from elevenbot.providers import MockProvider

async def process(args,env,data=None):
    p=await asyncio.create_subprocess_exec(*args,stdin=asyncio.subprocess.PIPE if data else None,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=env)
    out,err=await p.communicate(data)
    assert p.returncode==0, 'PostgreSQL backup tool failed (details excluded to avoid DSN disclosure)'
    return out

async def test_A18_restore_isolated(env):
    pool,cfg,s,u=env
    import asyncpg
    dsn=os.environ['TEST_DATABASE_URL'];parsed=urlparse(dsn)
    pg_env=os.environ|{'PGHOST':parsed.hostname or 'localhost','PGPORT':str(parsed.port or 5432),
                      'PGUSER':unquote(parsed.username or 'postgres'),'PGPASSWORD':unquote(parsed.password or ''),
                      'PGDATABASE':parsed.path.lstrip('/')}
    schema=await pool.fetchval('SELECT current_schema()')
    q,_=await s.quote(u,'Restore','demo');j=await s.confirm(u,q)
    w=Worker(pool,cfg,MockProvider());await w.claim()
    dump=await process(['pg_dump','-Fc','-n',schema],pg_env)
    database='restore_test_'+uuid.uuid4().hex
    admin=await asyncpg.connect(dsn);target=None
    try:
        await admin.execute(f'CREATE DATABASE {database}')
        await process(['pg_restore','--exit-on-error','-d',database],pg_env,dump)
        target=await asyncpg.connect(dsn.rsplit('/',1)[0]+'/'+database,server_settings={'search_path':schema})
        await target.execute('UPDATE settings SET halted=true WHERE id=1')
        await target.execute("UPDATE jobs SET status='uncertain',error_code='RESTORE_REVIEW' WHERE status IN ('queued','dispatching')")
        assert await target.fetchval('SELECT status FROM jobs WHERE id=$1',j)=='uncertain'
        assert await target.fetchval("SELECT reserved FROM wallets WHERE user_id=$1 AND mode='demo'",u)==7
        assert await target.fetchval('SELECT halted FROM settings WHERE id=1')
    finally:
        if target:await target.close()
        await admin.execute(f'DROP DATABASE IF EXISTS {database} WITH (FORCE)');await admin.close()
