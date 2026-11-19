"""Mock external top-up followed by the same owner's real HTTP image flow."""
import base64
from dataclasses import replace
from uuid import uuid4

import httpx
from aiohttp.test_utils import TestClient, TestServer

from elevenbot.aggregate import make_snapshot
from elevenbot.discovery import SnapshotStore
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.telegram import TelegramApp
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import signed
from test_ft020_http_image import create, quote
from test_topups import fixture, MERCHANT, SECRET
from test_ui import Bot


async def test_external_topup_then_http_image_is_idempotent_and_owned(env, monkeypatch, tmp_path, confirmed_credit):
    pool, original, owner, existing_payments, gateway = await fixture(env)
    cfg = replace(original, token='fixture', mode='clodex', generation_enabled=True, economy_verified=True,
                  topup_mode='live', payments_enabled=True, platega_enabled=True,
                  public_image_models=('clodex:flux-schnell',), clodex_key='fixture-only',
                  interaction_mode='off', interaction_limit=100, catalogue_path=str(tmp_path/'catalogue.json'))
    snap = make_snapshot([{'provider':'clodex','id':'flux-schnell','title':'FLUX Schnell',
                           'operations':['images.generate'],'protocols':['image-generation'],
                           'availability':'key_available'}], [], [{'provider':'clodex','scope':'key_available'}])
    SnapshotStore(cfg.catalogue_path).write(snap)
    posts, deferred = [], []
    original_http = httpx.AsyncClient
    def provider_transport(request):
        assert request.method == 'POST' and request.url.host == 'clodex.xyz'
        assert request.url.path == '/v1/images/generations'
        posts.append(request.url.path)
        return httpx.Response(200, json={'data':[{'b64_json':base64.b64encode(MOCK_IMAGE).decode()}]})
    def mocked_http(*args, **kwargs):
        return original_http(*args, **(kwargs | {'transport':httpx.MockTransport(provider_transport)}))
    monkeypatch.setattr(httpx,'AsyncClient',mocked_http)
    app = TelegramApp(pool,cfg,Bot())
    await app.topups.client.close()
    app.topups.client = existing_payments.client
    other = await app.svc.identity(101)
    await app.svc.accept(other)
    await app.pricing.set_tariff(owner,100,'clodex','flux-schnell','images.generate',{'n':1},
                                 basis='request',unit='darkflow_token',amount='600',expires=None,evidence='fixture')
    try:
        order = await app.topups.quote(owner,100,10000,uuid4().hex[:12])
        await app.topups.create(owner,order['id'])
        callback = gateway.event(order['id'])
        headers = {'X-MerchantId':MERCHANT,'X-Secret':SECRET}
        await app.topups.callback(headers,callback)
        await app.topups.check(owner,order['id'])
        await app.topups.callback(headers,callback)
        assert len(gateway.posts)==1
        assert await pool.fetchval("SELECT count(*) FROM ledger WHERE user_id=$1 AND kind='topup'",owner)==1
        async with TestClient(TestServer(create_app(pool,cfg,view=app,job_scheduler=deferred.append))) as client:
            tokens=[]
            for external in (100,101):
                result = await client.post('/api/v1/session',json={'initData':signed(cfg.token,external)})
                assert result.status==200
                tokens.append({'Authorization':'Bearer '+(await result.json())['token']})
            q=await quote(client,tokens[0])
            response=await create(client,tokens[0],q)
            assert response.status==201, await response.text()
            assert (await create(client,tokens[0],q)).status==200
            assert len(deferred)==1
            await deferred.pop()()
            assert posts==['/v1/images/generations']
            data=await (await client.get('/api/v1/jobs/'+q,headers=tokens[0])).json()
            assert data['state']=='completed'
            assert await (await client.get(data['result_url'],headers=tokens[0])).read()==MOCK_IMAGE
            assert (await client.get('/api/v1/jobs/'+q,headers=tokens[1])).status==404
            assert (await client.get(data['result_url'],headers=tokens[1])).status==404
        rows=await pool.fetch('SELECT kind,da,dr FROM ledger WHERE user_id=$1 AND task_quote_id=$2::uuid ORDER BY kind',owner,q)
        assert [(r['kind'],r['da'],r['dr']) for r in rows]==[('task_capture',0,-600),('task_reserve',-600,600)]
        assert tuple(await pool.fetchrow("SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode='live'",owner))==(400,0)
        assert await app.svc.reconcile()==0
        # TG-03 history survives PY-02: RUB orders are actionable, XTR receipts are not.
        _, stars = await confirmed_credit(pool,cfg,owner,17,charge='fixture-ft028-stars')
        await app.topup_ui.history(owner,100,0)
        text, markup = app.bot.sent[-1]
        assert f'{str(stars)[:8]} · 100 XTR' in text
        assert f"{str(order['id'])[:8]} · 100 ₽" in text
        assert text.index(str(stars)[:8]) < text.index(str(order['id'])[:8])
        callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
        assert f"tuorder:{order['id']}" in callbacks
        assert f'tuorder:{stars}' not in callbacks
        await app.topup_ui.history(other,101,0)
        assert str(order['id'])[:8] not in app.bot.sent[-1][0]
    finally:
        await existing_payments.client.close()
