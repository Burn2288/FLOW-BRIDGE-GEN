from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import httpx

from elevenbot.clodex_pricing import ClodexPricing
from elevenbot.discovery import SnapshotStore, snapshot
from elevenbot.pricing import NoProviderPrice, ProviderCost, Request
from elevenbot.telegram import TelegramApp
from elevenbot.video import VIDEO_PARAMS, VideoAPI
from test_anymodel import routes
from test_ui import Bot, event


class Prices:
    async def cost(self, request):
        if request.model=='fixture/manual':
            raise NoProviderPrice()
        amount,unit = {
            'fixture/clodex': ('20000','clodex_balance_token'),
            'fixture/anymodel': ('20000','anymodel_balance_token'),
            'clodex-video/veo-3.1': ('0.45','USD'),
        }[request.model]
        return ProviderCost(Decimal(amount),unit,True,'fixture API','Параметры примера')


async def test_scoped_rates_and_manual_cost_through_telegram(env,tmp_path):
    pool,cfg,_,user = env
    cfg = replace(cfg,access_mode='private',admin_ids=(100,),catalogue_path=str(tmp_path/'models.json'),
                  interaction_mode='live',video_pilot=True)
    bot = Bot()
    app = TelegramApp(pool,cfg,bot)
    app.pricing.adapters.update(anymodel=Prices(),clodex=Prices())
    clodex = ('fixture/clodex','Fixture CLODEX','images.generate','image-generation')
    manual = ('fixture/manual','Fixture manual','images.generate','image-generation')
    veo = ('clodex-video/veo-3.1','Veo 3.1','video','openai-video')
    SnapshotStore(cfg.catalogue_path).write(snapshot([
        {'id':model,'title':title,'provider':'clodex','availability':'key_available',
         'operations':[operation],'protocols':[protocol]}
        for model,title,operation,protocol in (clodex,manual,veo)
    ]))
    await pool.execute('DELETE FROM approved_models')
    await pool.executemany('INSERT INTO approved_models VALUES($1,$2,$3,$4)',[
        ('clodex',model,operation,title) for model,title,operation,_ in (clodex,manual,veo)
    ]+[('anymodel','fixture/anymodel','images.generate','Fixture AnyModel')])

    async def click(label):
        await app.handle(event(callback=routes(bot)[label]))

    async def rate(provider,unit,source,target):
        await app.handle(event(callback=f'rates:{provider}'))
        label = next(label for label,value in routes(bot).items() if value==f'rateunit:{provider}:{unit}')
        await click(label)
        code = (await app.svc.aggregate_context(user))['price_rate']['code']
        await app.handle(event(f'/rate_set {code} {source} {target}'))

    async def rubles(source,target):
        await app.handle(event('Стоимость токенов бота'))
        code = (await app.svc.aggregate_context(user))['price_rate']['code']
        await app.handle(event(f'/ruble_set {code} {source} {target}'))
        assert f'{source} токенов DarkFlow | Gen = {target} ₽' in bot.sent[-1][0]

    async def our_models(provider):
        await app.handle(event(callback=f'ours:{provider}:0'))
        return bot.sent[-1][0]

    await app.pricing.set_rule(user,100,'clodex','','percent','25')
    text = await our_models('clodex')
    assert '20\u202f000 токенов CLODEX\nКурс не настроен' in text
    assert '0.45 USD\nКурс не настроен' in text
    assert 'Цена недоступна' in text and 'Задать себестоимость' in routes(bot)
    assert 'Настроить курс' in routes(bot) and 'Генерировать' not in routes(bot)
    await app.handle(event(callback='tariffs:clodex:0'))
    await click('Fixture CLODEX')
    await click('Изображение')
    assert '20\u202f000 токенов CLODEX\nКурс не настроен' in bot.sent[-1][0]
    assert routes(bot)['Настроить курс']=='rateunit:clodex:clodex_balance_token'
    await click('Настроить курс')
    code = (await app.svc.aggregate_context(user))['price_rate']['code']
    await app.handle(event(f'/rate_set {code} 0 100'))
    assert 'две положительные суммы' in bot.sent[-1][0]

    await rate('clodex','clodex_balance_token',20000,100)
    assert '20\u202f000 токенов CLODEX = 100 токенов DarkFlow | Gen' in bot.sent[-1][0]
    code = (await app.svc.aggregate_context(user))['price_rate']['code']
    await app.handle(event(f'/rate_calc {code} 40000'))
    assert '40\u202f000 токенов CLODEX ≈ 200 токенов DarkFlow | Gen' in bot.sent[-1][0]
    await rate('clodex','USD',1,1000)
    await rate('anymodel','anymodel_balance_token',10000,100)
    await rubles(100,100)
    text = await our_models('clodex')
    assert 'После пересчёта: 100 токенов DarkFlow | Gen' in text
    assert 'Общая наценка 25% · 25 токенов DarkFlow | Gen' in text
    assert 'Итоговая оценка: 125 токенов DarkFlow | Gen ≈ 125 ₽' in text
    assert '0.45 USD\nПосле пересчёта: 450' in text
    assert '563 токенов DarkFlow | Gen ≈ 563 ₽' in text
    print('CLODEX · Наши модели\n'+text)

    await app.handle(event(callback='tariffs:clodex:0'))
    await click('Fixture CLODEX')
    await click('Изображение')
    assert 'Итоговая оценка: 125 токенов DarkFlow | Gen ≈ 125 ₽' in bot.sent[-1][0]
    print('CLODEX · Тарифы моделей\n'+bot.sent[-1][0])

    await our_models('clodex')
    await click('Задать себестоимость')
    code = (await app.svc.aggregate_context(user))['tariff_admin']['code']
    await app.handle(event(f'/tariff_set {code} image darkflow_token 100 fixture'))
    assert 'наценка 25 токенов DarkFlow | Gen · итог 125 токенов DarkFlow | Gen' in bot.sent[-1][0]
    await click('Сохранить ставки')
    assert 'Наши модели · CLODEX' in bot.sent[-1][0]
    assert 'Ручная себестоимость: 100 токенов DarkFlow | Gen' in bot.sent[-1][0]
    assert await pool.fetchval("SELECT expires_at IS NULL FROM task_manual_tariffs WHERE model_id='fixture/manual'")

    await app.handle(event(callback='slist:current:image:0'))
    await click('Fixture manual')
    await click('🖼 Генерировать изображение')
    await app.handle(event('Тест изображения'))
    assert 'Оценка: 125 токенов DarkFlow | Gen ≈ 125 ₽' in bot.sent[-1][0]
    assert 'Ручная себестоимость: 100 токенов DarkFlow | Gen' in bot.sent[-1][0]
    assert set(routes(bot))=={'Генерировать','Отмена'}
    print('CLODEX · После промпта\n'+bot.sent[-1][0])

    assert '200 токенов DarkFlow | Gen ≈ 200 ₽' in await our_models('anymodel')
    await rate('clodex','clodex_balance_token',20000,120)
    assert '200 токенов DarkFlow | Gen ≈ 200 ₽' in await our_models('anymodel')
    await rubles(100,200)
    assert '200 токенов DarkFlow | Gen ≈ 400 ₽' in await our_models('anymodel')
    text = await our_models('clodex')
    assert '150 токенов DarkFlow | Gen ≈ 300 ₽' in text
    assert '125 токенов DarkFlow | Gen ≈ 250 ₽' in text

    req = Request('clodex',clodex[0],clodex[2],clodex[1],'Test',{'n':1})
    quote = await app.pricing.quote(user,req)
    await rate('clodex','clodex_balance_token',20000,200)
    await app.handle(event(callback=f'amconfirm:{quote.id}'))
    assert 'Оценка: 250 токенов DarkFlow | Gen ≈ 500 ₽' in bot.sent[-1][0]
    assert not await pool.fetchval('SELECT count(*) FROM interaction_attempts')
    restarted = TelegramApp(pool,cfg,Bot())
    restarted.pricing.adapters.update(app.pricing.adapters)
    assert (await restarted.pricing.preview_price(req))['total']=='250'


async def test_migration_keeps_unambiguous_rates(env):
    pool,_,_,_ = env
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute('DROP TABLE task_price_conversions,task_ruble_equivalent')
        await conn.execute('ALTER TABLE task_manual_tariffs ADD CONSTRAINT task_manual_tariffs_source_unit_fkey '
                           'FOREIGN KEY(source_unit) REFERENCES task_price_rates(source_unit)')
        await conn.execute("INSERT INTO task_price_rates(source_unit,multiplier) VALUES ('USD',12.5),('ambiguous',10)")
        path = Path(__file__).resolve().parents[1]/'migrations'/'025_scoped_price_rates.sql'
        await conn.execute(path.read_text(encoding='utf-8'))
        rows = await conn.fetch('SELECT provider,source_unit,source_amount,target_amount FROM task_price_conversions')
        assert {tuple(row) for row in rows}=={
            ('anymodel','anymodel_balance_token',1,1),('clodex','USD',1,Decimal('12.5')),
        }


async def test_clodex_estimate_preserves_explicit_currency():
    model = 'clodex-video/veo-3.1'
    payloads = iter([{'cost_tokens':20000},{'cost_usd':'0.45','cost_tokens':20000}])

    def estimate(request):
        assert request.url.path=='/v1/videos/estimate'
        return httpx.Response(200,json={'success':True,'data':{'model':model,**next(payloads)}})

    api = VideoAPI('fixture',transport=httpx.MockTransport(estimate))
    req = Request('clodex',model,'video','Veo','Test',VIDEO_PARAMS)
    pricing = ClodexPricing(api)
    token,usd = await pricing.cost(req),await pricing.cost(req)
    assert (token.amount,token.unit)==(20000,'clodex_balance_token')
    assert (usd.amount,usd.unit)==(Decimal('0.45'),'USD')
