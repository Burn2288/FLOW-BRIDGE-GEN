import asyncio
import base64
import hashlib
import time
import json
from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from elevenbot.aggregate import make_snapshot
from elevenbot.discovery import SnapshotStore
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.telegram import TelegramApp
from test_admin_access import event
from test_topups import fixture
from test_ui import Bot


@pytest.mark.parametrize('deferred', [False, True])
async def test_funded_regular_user_with_one_config(env, monkeypatch, tmp_path, deferred):
    pool, cfg, admin, payments, gateway = await fixture(env)
    model_id = 'flux-schnell'
    cfg = replace(cfg, mode='clodex', generation_enabled=True, economy_verified=True,
                  topup_mode='live', payments_enabled=True, platega_enabled=True,
                  public_image_models=(f'clodex:{model_id}',), clodex_key='fixture',
                  interaction_mode='off', interaction_limit=1, catalogue_path=str(tmp_path/'catalogue.json'))
    model = {'provider':'clodex','id':model_id,'title':'FLUX Schnell',
             'operations':['images.generate'],'protocols':['image-generation'],
             'availability':'key_available'}
    snapshot = make_snapshot([model], [], [{'provider':'clodex','scope':'key_available'}])
    SnapshotStore(cfg.catalogue_path).write(snapshot)
    assert await pool.fetchval("SELECT 1 FROM approved_models WHERE provider='clodex' AND model_id=$1 AND operation='images.generate'",model_id)
    posts = []
    provider_started = asyncio.Event()
    provider_release = asyncio.Event()
    provider_timing = []

    async def transport(req):
        if req.url.host == 'clodex.xyz':
            assert req.method == 'POST' and req.url.path == '/v1/images/generations'
            assert json.loads(req.content)['model'] == model_id
            assert await wallet() == (400, 600)
            posts.append(req.url.path)
            started = time.monotonic()
            provider_started.set()
            if deferred:
                await asyncio.wait_for(provider_release.wait(),3)
            else:
                await asyncio.sleep(.35)
            provider_timing.append(round((time.monotonic()-started)*1000))
            return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(MOCK_IMAGE).decode()}]})
        if req.url.path == '/transaction/process':
            payload = json.loads(req.content)
            assert payload['metadata']['userId'] == '101'
            remote = str(uuid4())
            gateway.orders[payload['payload']] = {'remote':remote,'payload':payload}
            return httpx.Response(200,json={'transactionId':remote,'redirect':'https://pay.platega.io/test',
                                          'expiresIn':'00:15:00','merchantId':payments.client.cfg.merchant})
        return gateway.handler(req)

    make_client = httpx.AsyncClient
    def client_with_transport(*args, **kwargs):
        return make_client(*args, **(kwargs | {'transport':httpx.MockTransport(transport)}))
    monkeypatch.setattr(httpx,'AsyncClient',client_with_transport)
    bot = Bot()
    bot.send_photo = AsyncMock(return_value=type('Message',(),{'message_id':300})())
    app = TelegramApp(pool,cfg,bot)
    # Keep the real checkout adapter and simulate only HTTP.
    app.topups.client.cfg = payments.client.cfg
    user = await app.svc.identity(101)
    await app.svc.accept(user)
    await app.pricing.set_tariff(admin,100,'clodex',model_id,'images.generate',{'n':1},
                                 basis='request',unit='darkflow_token',amount='600',
                                 expires=None,evidence='fixture',temporary=False)
    n = 500
    async def press(text=None, callback=None, target=None, *, inbox=False):
        nonlocal n
        n += 1
        await (target or app).handle(event(n,text,chat=101,callback=callback),from_inbox=inbox)
    def route(prefix):
        return next(b.callback_data for _, markup in reversed(bot.sent) if hasattr(markup,'inline_keyboard')
                    for row in markup.inline_keyboard for b in row if (b.callback_data or '').startswith(prefix))
    async def wallet():
        row = await app.svc.wallet(user)
        return row['available'],row['reserved']

    try:
        assert await wallet() == (0,0)
        # Platega checkout is external. Telegram only checks the existing order.
        order = await app.topups.quote(user,101,10000,uuid4().hex[:12])
        await app.topups.create(user,order['id'])
        check = f"tucheck:{order['id']}"
        await press(callback=check)
        await press(callback=check)
        assert await wallet() == (1000,0)
        await press(callback=f'smodel:{snapshot["version"]}:image:0:0')
        await press(callback=route('srun:'))
        await press('Проверка изображения')
        confirm = route('amconfirm:')
        submission = asyncio.create_task(press(callback=confirm,inbox=deferred))
        await asyncio.wait_for(provider_started.wait(),2)
        begin = time.monotonic()
        await asyncio.wait_for(press('/menu'),2)
        menu_ms = round((time.monotonic()-begin)*1000)
        if deferred:
            assert provider_timing == []
            await press(callback=confirm,inbox=True)
            await asyncio.sleep(.35)
            provider_release.set()
            await asyncio.gather(*tuple(app.running_tasks))
        await submission
        if not deferred:
            await press(callback=confirm)
        assert await wallet() == (400,0) and len(posts)==1 and len(gateway.orders)==1, [text for text, _ in bot.sent]
        assert await pool.fetchval("SELECT status FROM payments WHERE user_id=$1",user)=='succeeded'
        assert await pool.fetchval("SELECT count(*) FROM ledger WHERE user_id=$1",user)==3
        ledger_before=await pool.fetch("SELECT id,event_key,kind,da,dr FROM ledger WHERE user_id=$1 ORDER BY id",user)
        restarted = TelegramApp(pool,cfg,bot)
        await press(callback='history:0',target=restarted)
        await press(callback=route('image:'),target=restarted)
        assert bot.send_photo.await_count==2
        assert all(call.args[1].data == MOCK_IMAGE for call in bot.send_photo.await_args_list)
        stored = await pool.fetchval("SELECT image FROM image_works WHERE user_id=$1", user)
        expected = hashlib.sha256(MOCK_IMAGE).digest()
        assert hashlib.sha256(stored).digest() == expected
        assert hashlib.sha256(bot.send_photo.await_args.args[1].data).digest() == expected
        assert await pool.fetchval("SELECT count(*) FROM ledger WHERE user_id=$1 AND kind='task_capture'", user) == 1
        assert len(posts)==1 and (await restarted.svc.wallet(user))['available']==400
        assert await pool.fetch("SELECT id,event_key,kind,da,dr FROM ledger WHERE user_id=$1 ORDER BY id",user)==ledger_before
        print('wallet=0->1000->400 payment=succeeded posts=1 debit=1 reopened=1',
              f'deferred={deferred} menu_ms={menu_ms} provider_ms={provider_timing[0]}')
    finally:
        await app.topups.client.close()
        await payments.client.close()
