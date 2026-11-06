import os,uuid
from urllib.parse import urlsplit,urlunsplit,quote
import asyncpg,pytest
from elevenbot.core import Service

async def test_nonsuperuser_runtime_permissions(env):
    pool,cfg,_,u=env;schema=await pool.fetchval('SELECT current_schema()');role='runtime_'+uuid.uuid4().hex
    secret='isolated-test-only';admin=await asyncpg.connect(os.environ['TEST_DATABASE_URL']);runtime=None
    try:
        await admin.execute(f"CREATE ROLE {role} LOGIN PASSWORD '{secret}' NOSUPERUSER NOCREATEDB NOCREATEROLE")
        await admin.execute(f'GRANT USAGE ON SCHEMA {schema} TO {role}')
        await admin.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {schema} TO {role}')
        await admin.execute(f'GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO {role}')
        parts=urlsplit(os.environ['TEST_DATABASE_URL'])
        netloc=f'{role}:{secret}@{parts.hostname}:{parts.port or 5432}'
        dsn=urlunsplit(parts._replace(netloc=netloc))
        runtime=await asyncpg.create_pool(dsn,min_size=1,max_size=2,server_settings={'search_path':schema})
        assert not await runtime.fetchval('SELECT rolsuper FROM pg_roles WHERE rolname=current_user')
        svc=Service(runtime,cfg);v=await svc.identity(999);await svc.accept(v)
        q,_=await svc.quote(v,'Runtime role','demo');await svc.confirm(v,q)
        assert (await svc.wallet(v))['reserved']==12
        async with runtime.acquire() as c:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):await c.execute('ALTER TABLE ledger DISABLE TRIGGER ALL')
            with pytest.raises(asyncpg.RaiseError):await c.execute('DELETE FROM ledger')
    finally:
        if runtime:await runtime.close()
        await admin.execute(f'DROP OWNED BY {role}');await admin.execute(f'DROP ROLE IF EXISTS {role}');await admin.close()
