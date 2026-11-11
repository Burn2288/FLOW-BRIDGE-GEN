from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from elevenbot.core import Rejected
from elevenbot.pricing import Pricing, ProviderCost, Request
from elevenbot.telegram import TelegramApp
from test_anymodel import routes
from test_ui import Bot


class Prices:
    async def cost(self,req):
        return ProviderCost(Decimal(100 if req.model=='anymedia/fibo-2' else 200),
                            'anymodel_balance_token' if req.provider=='anymodel' else 'clodex_balance_token',
                            True,'fixture','1 единица')


async def test_modes_and_legacy_migration(env):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True)
    app=TelegramApp(pool,cfg,Bot())
    app.pricing.adapters.update(anymodel=Prices(),clodex=Prices())
    await app.pricing.set_rate(user,100,'clodex_balance_token','1')
    fibo=Request('anymodel','anymedia/fibo-2','images.generate','FIBO 2','Проверка тарифа')
    fish=Request('anymodel','fish-farm/s2.1-pro-free','audio.speech','Fish','Проверка тарифа')
    flux=Request('clodex','flux-schnell','images.generate','FLUX','Проверка тарифа',{'n':1})
    await pool.execute("""
        INSERT INTO task_price_rules(provider,model_id,kind,amount)
        VALUES('anymodel','fish-farm/s2.1-pro-free','fixed',15),('clodex','','percent',5)
        """)
    async with pool.acquire() as c,c.transaction():
        await c.execute('DROP TABLE task_markup_modes, approved_models')
        migration=Path(__file__).resolve().parents[1]/'migrations'/'024_approved_models.sql'
        await c.execute(migration.read_text(encoding='utf-8'))
    assert await pool.fetchval("SELECT mode FROM task_markup_modes WHERE model_id=$1",fish.model)=='manual'
    await app.callback(user,100,'ours:anymodel:0')
    assert 'Ручная наценка 15 токенов' in app.bot.sent[-1][0]
    await app.callback(user,100,routes(app.bot)['Изменить общую наценку'])
    draft=(await app.svc.aggregate_context(user))['our_markup']
    await app.models.command(user,100,'/markup_value',[draft['code'],'25'])
    text=app.bot.sent[-1][0]
    assert '125 токенов' in text and '215 токенов' in text
    assert (await app.pricing.preview_price(fibo))['total']=='125'
    assert (await app.pricing.preview_price(fish))['total']=='215'
    assert (await app.pricing.preview_price(flux))['total']=='210'
    button=next(value for name,value in routes(app.bot).items() if name.startswith('Fish Audio') and 'Ручная' in name)
    await app.callback(user,100,button)
    assert (await app.pricing.preview_price(fish))['total']=='250'
    await app.callback(user,100,button)
    assert (await Pricing(pool,cfg,app.pricing.adapters).preview_price(fish))['total']=='215'
    with pytest.raises(Rejected):
        await app.callback(user,101,'ours:anymodel:0')
