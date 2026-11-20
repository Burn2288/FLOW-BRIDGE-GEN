"""PY-01: ordinary Telegram user funds and spends one live-mode test wallet."""
import base64
import json
from dataclasses import replace
from itertools import count
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from aiogram.types import Update

from elevenbot.aggregate import make_snapshot
from elevenbot.discovery import SnapshotStore
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.telegram import TelegramApp
from test_admin_access import event
from test_ui import Bot


@pytest.fixture
def admin_already_signed_in():
    # This scenario exercises the ordinary user's real session checks.
    pass


async def test_stars_wallet_flux_and_library(env, tmp_path, monkeypatch):
    pool, defaults, _, tariff_admin = env
    chat, model = 101, 'flux-schnell'
    cfg = replace(defaults, mode='clodex', access_mode='public', admin_ids=(100,),
                  generation_enabled=True, interaction_mode='off', interaction_limit=1,
                  payments_enabled=True, payment_backend='stars', economy_verified=True,
                  public_image_models=(f'clodex:{model}',), clodex_key='fixture',
                  catalogue_path=str(tmp_path/'catalogue.json'))
    catalogue = make_snapshot([dict(provider='clodex', id=model, title='FLUX Schnell',
                                    operations=['images.generate'], protocols=['image-generation'],
                                    availability='key_available')], [], [dict(provider='clodex', scope='key_available')])
    SnapshotStore(cfg.catalogue_path).write(catalogue)
    bot = Bot()
    bot.send_invoice = AsyncMock()
    bot.answer_pre_checkout_query = AsyncMock()
    bot.send_photo = AsyncMock(return_value=SimpleNamespace(message_id=300))
    posts = []

    async def generate(request):
        assert (request.method, request.url.host, request.url.path) == ('POST','clodex.xyz','/v1/images/generations')
        assert json.loads(request.content)['model'] == model
        assert await wallet() == (9400, 600)
        posts.append(request.url.path)
        return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(MOCK_IMAGE).decode()}]})

    make_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda *a, **kw: make_client(*a, **(kw | {'transport':httpx.MockTransport(generate)})))
    app = TelegramApp(pool, cfg, bot)
    user = await app.svc.identity(chat)
    await app.svc.accept(user)
    assert not app.has_admin_session(chat)
    seq = count(500)

    async def press(text=None, callback=None):
        await app.handle(event(next(seq), text, chat=chat, callback=callback))

    def button(prefix):
        return next(b.callback_data for _, markup in reversed(bot.sent) if hasattr(markup,'inline_keyboard')
                    for row in markup.inline_keyboard for b in row if (b.callback_data or '').startswith(prefix))

    async def wallet():
        row = await app.svc.wallet(user)
        return row['available'], row['reserved']

    async def ledger():
        return await pool.fetch("SELECT id,kind,da,dr,payment_id,task_quote_id FROM ledger "
                                "WHERE user_id=$1 AND mode='live' ORDER BY kind,id", user)

    try:
        await app.pricing.set_tariff(tariff_admin,100,'clodex',model,'images.generate',{'n':1},
                                     basis='request',unit='darkflow_token',amount='600',evidence='fixture')
        assert await wallet() == (0, 0)
        await press('💳 Баланс')
        await press(callback=button('buy'))
        bot.send_invoice.assert_awaited_once()
        call = bot.send_invoice.await_args
        assert call.args == (chat,)
        invoice = call.kwargs
        assert invoice['currency'] == 'XTR' and sum(p.amount for p in invoice['prices']) == 100
        fields = dict(currency=invoice['currency'], total_amount=100, invoice_payload=invoice['payload'])
        actor = {'id':chat,'is_bot':False,'first_name':'Fixture'}
        await app.handle(Update.model_validate({'update_id':next(seq), 'pre_checkout_query':{
            'id':'fixture-check','from':actor,**fields}}))
        bot.answer_pre_checkout_query.assert_awaited_once_with('fixture-check', ok=True, error_message=None)
        assert await wallet() == (0, 0) and not await ledger()

        payment = dict(fields, telegram_payment_charge_id='fixture-stars-charge', provider_payment_charge_id='')
        for _ in range(2):
            number = next(seq)
            await app.handle(Update.model_validate({'update_id':number,'message':{
                'message_id':number,'date':1700000000,'chat':{'id':chat,'type':'private'},
                'from':actor,'successful_payment':payment}}))
            assert await wallet() == (10000, 0)
            credit, = await ledger()
            assert (credit['kind'],credit['da'],credit['dr'],credit['payment_id']) == (
                'payment',10000,0,UUID(invoice['payload']))

        await press(callback=f'smodel:{catalogue["version"]}:image:0:0')
        await press(callback=button('srun:'))
        await press('Fixture image')
        confirm = button('amconfirm:')
        quote_id = UUID(confirm.split(':')[1])
        await press(callback=confirm)
        before = await ledger()
        assert [(r['kind'],r['da'],r['dr']) for r in before] == [
            ('payment',10000,0),('task_capture',0,-600),('task_reserve',-600,600)], [msg for msg, _ in bot.sent]
        assert all(r['task_quote_id'] == quote_id for r in before[1:])
        assert await wallet() == (9400, 0) and len(posts) == 1
        bot.send_photo.assert_awaited_once()
        await press('📁 Мои работы')
        await press(callback=button('image:'))
        assert bot.send_photo.await_count == 2
        assert all(c.args[0] == chat and c.args[1].data == MOCK_IMAGE for c in bot.send_photo.await_args_list)
        assert await wallet() == (9400, 0) and await ledger() == before and len(posts) == 1
    finally:
        await app.topups.client.close()
