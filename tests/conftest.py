import os,uuid
from dataclasses import replace
import pytest_asyncio,pytest
from elevenbot.db import connect,migrate
from elevenbot.config import Config
from elevenbot.core import Service

@pytest_asyncio.fixture
async def env(tmp_path):
    dsn=os.getenv('TEST_DATABASE_URL')
    if not dsn:pytest.skip('BLOCKED: genuine PostgreSQL TEST_DATABASE_URL not provided')
    # Must be explicitly isolated. No automatic production DB truncation.
    import asyncpg
    admin=await asyncpg.connect(dsn);schema='test_'+uuid.uuid4().hex
    await admin.execute(f'CREATE SCHEMA {schema}')
    pool=await asyncpg.create_pool(dsn,min_size=1,max_size=25,server_settings={'search_path':schema})
    await migrate(pool)
    cfg=Config(generation_enabled=True,storage=tmp_path/'audio')
    svc=Service(pool,cfg)
    u=await svc.identity(100);await svc.accept(u)
    try:yield pool,cfg,svc,u
    finally:
        await pool.close();await admin.execute(f'DROP SCHEMA {schema} CASCADE');await admin.close()


@pytest.fixture
def manual_tariff():
    from datetime import datetime, timedelta, timezone

    async def save(app, user, model, operation, params, *, provider='clodex',
                   basis='request', amount='100', external=100):
        expires=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        await app.pricing.set_tariff(user,external,provider,model,operation,params,
            basis=basis,unit='darkflow_token',amount=amount,expires=expires,evidence='fixture-evidence',temporary=True)
    return save
