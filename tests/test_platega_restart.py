"""Kill the crediting process with its PostgreSQL transaction still open."""
import asyncio
import json
import os
from pathlib import Path
import sys
from uuid import UUID

import asyncpg
import httpx

from elevenbot.config import Config
from elevenbot.platega import PlategaConfig
from elevenbot.topups import CheckoutClient, Topups
from scripts.disposable_test_db import require_disposable_dsn
from test_topups import Gateway, MERCHANT, SECRET, fixture, quote


async def interrupt_credit():
    source = json.loads(sys.argv[1])
    gateway = Gateway()
    gateway.orders = source['orders']
    config = PlategaConfig(merchant=MERCHANT, secret=SECRET, enabled=True)
    async with asyncpg.create_pool(require_disposable_dsn(os.environ),
                                   server_settings={'search_path':source['schema']}) as pool:
        async with httpx.AsyncClient(transport=httpx.MockTransport(gateway.handler)) as http:
            payments = Topups(pool, Config(), CheckoutClient(config,http))
            movement = payments.svc.movement

            async def crash_after_insert(*args, **kwargs):
                await movement(*args, **kwargs)
                os._exit(73)  # Deliberately skip transaction cleanup and process shutdown.

            payments.svc.movement = crash_after_insert
            await payments.check(UUID(source['user']), UUID(source['order']))


async def test_restart_during_credit(env):
    pool, cfg, user, payments, gateway = await fixture(env)
    async def balance():
        return await pool.fetchval("SELECT available FROM wallets WHERE user_id=$1 AND mode='demo'", user)
    before = await balance()
    order = await quote(payments, user)
    try:
        await payments.create(user, order['id'], test_session=True)
        root = Path(__file__).resolve().parents[1]
        source = dict(schema=await pool.fetchval('SELECT current_schema()'), user=str(user),
                      order=str(order['id']), orders=gateway.orders)
        proc = await asyncio.create_subprocess_exec(
            sys.executable, __file__, json.dumps(source, default=str),
            env=os.environ | {'PYTHONPATH':os.pathsep.join(map(str,(root/'src', root)))})
        try:
            assert await asyncio.wait_for(proc.wait(), 15) == 73
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
        credits = "SELECT count(*) FROM ledger WHERE payment_id=$1 AND kind='topup'"
        assert await balance() == before
        assert await pool.fetchval(credits,order['id']) == 0
        restarted = Topups(pool,cfg,payments.client)
        await asyncio.gather(
            restarted.callback({'X-MerchantId':MERCHANT,'X-Secret':SECRET},gateway.event(order['id'])),
            restarted.check(user,order['id']))
        assert await balance() == before + order['credits']
        assert await pool.fetchval(credits,order['id']) == 1
        assert (await restarted.owned(user,order['id']))['state'] == 'paid'
        assert len(gateway.posts) == 1
    finally:
        await payments.client.close()


if __name__ == '__main__':
    asyncio.run(interrupt_credit())
