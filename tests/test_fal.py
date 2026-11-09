import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from elevenbot.clodex_music import OPERATION
from elevenbot.fal import LYRIA, FalMusicPilot, FalProvider
from elevenbot.pricing import BOT_TOKEN, MissingRate, MissingTariff, Request
from elevenbot.telegram import MENU, TelegramApp
from test_admin_access import event
from test_broadcasts import BroadcastTransport, routes


@pytest.fixture
def admin_already_signed_in():
    pass


def entry(model, category='text-to-audio'):
    return {'endpoint_id':model,'metadata':{
        'display_name':'Lyria 3.5' if model==LYRIA else model,
        'category':category,'status':'active',
    }}


@pytest.mark.parametrize('timeout', [False,True])
async def test_fal_registered_pilot(env, timeout):
    pool,cfg,svc,owner=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),admin_password='fixture-password',
                fal_music_owner=100,fal_music_live=True,fal_key='fixture-fal')
    await pool.execute('UPDATE settings SET halted=true WHERE id=1')
    mp3=(Path(__file__).resolve().parents[1]/'assets'/'demo.mp3').read_bytes()
    task='fixture-fal-01'
    requests=[]
    pages=[]
    price=0.10
    unit='generation'
    estimate_status=200

    async def transport(req):
        requests.append((req.method,req.url.host,req.url.path))
        path=req.url.path
        if req.url.host=='v3.fal.media':
            assert 'authorization' not in req.headers
            return httpx.Response(200,content=mp3,headers={'content-type':'audio/mpeg'})
        assert req.headers['authorization']=='Key fixture-fal'
        if path=='/v1/models':
            cursor=req.url.params.get('cursor')
            pages.append(cursor)
            if cursor is None:
                return httpx.Response(200,json={'models':[entry(f'fal-ai/model-{i}','text-to-image')
                    for i in range(10)],'has_more':True,'next_cursor':'second'})
            assert cursor=='second'
            return httpx.Response(200,json={'models':[entry(LYRIA),entry('minimax/music-3')],
                                           'has_more':False,'next_cursor':None})
        if path=='/v1/models/pricing':
            assert req.url.params['endpoint_id']==LYRIA
            return httpx.Response(200,json={'prices':[{'endpoint_id':LYRIA,'currency':'USD',
                                                     'unit':unit,'unit_price':price}]})
        if path=='/v1/models/pricing/estimate':
            assert req.method=='POST' and json.loads(req.content)=={
                'estimate_type':'unit_price','endpoints':{LYRIA:{'unit_quantity':1}}}
            return httpx.Response(estimate_status,json={'estimate_type':'unit_price','currency':'USD','total_cost':price})
        if req.method=='POST':
            assert path==f'/{LYRIA}' and json.loads(req.content)=={'prompt':'A piano track'}
            assert tuple(await pilot.balance(owner))==(20,80)
            if timeout:
                raise httpx.ReadTimeout('fixture',request=req)
            return httpx.Response(200,json={'request_id':task})
        if path==f'/{LYRIA}/requests/{task}/status':
            return httpx.Response(200,json={'status':'COMPLETED'})
        assert path==f'/{LYRIA}/requests/{task}'
        return httpx.Response(200,json={'audio':{'url':'https://v3.fal.media/files/music.mp3'}})

    adapter=FalProvider(cfg.fal_key,transport=httpx.MockTransport(transport))
    bot=BroadcastTransport(pool)
    app=TelegramApp(pool,cfg,bot)
    app.providers.adapters['fal']=app.providers.prices['fal']=adapter
    pilot=app.providers.launches['fal']=FalMusicPilot(pool,cfg,api=adapter)
    req=Request('fal',LYRIA,OPERATION,'Lyria 3.5','A piano track',{})
    await app.pricing.set_rate(owner,100,'USD','750',provider='clodex')
    await app.pricing.set_rate(owner,100,'anymodel_balance_token','2',provider='anymodel')
    with pytest.raises(MissingRate):
        await app.pricing.quote(owner,req)
    await app.pricing.set_rate(owner,100,'USD','1000',provider='fal')
    assert (await app.pricing.rate(pool,'clodex','USD'))['target_amount']==750
    assert (await app.pricing.rate(pool,'anymodel','anymodel_balance_token'))['target_amount']==2
    unit='second'
    with pytest.raises(MissingTariff):
        await app.pricing.quote(owner,req)
    await app.pricing.set_tariff(owner,100,'fal',LYRIA,OPERATION,{},
                                basis='request',unit=BOT_TOKEN,amount='100',expires=None,evidence='fixture source')
    assert (await app.pricing.quote(owner,req)).price['total']=='100'
    unit='generation'
    estimate_status=405
    assert (await app.pricing.preview_price(req))['source']=='fal /v1/models/pricing'
    estimate_status=200
    grant=await app.pricing.quote(owner,req)
    assert await pilot.grant(owner,100,grant.id)==100
    n=0

    async def send(text=None,callback=None):
        nonlocal n
        n+=1
        await app.handle(event(n,text,chat=100,callback=callback))

    async def screen():
        return bot.messages[(await app.navigation.read(100)).active_id]

    await send(text='/menu')
    assert routes(await screen())['Агрегатор 3']=='pentry:fal:0'
    await send(callback='pentry:fal:0')
    assert list(routes(await screen()))==['📁 Мои работы','← Агрегаторы']
    assert not pages
    await send(text='/admin')
    await send(text=cfg.admin_password)
    assert 'fal' in routes(await screen())
    await send(callback='agmanage:fal')
    management=routes(await screen())
    assert list(management)==['Наши модели','Курс и калькулятор','Все модели','← К агрегатору']
    await send(callback=management['Все модели'])
    await send(callback=routes(await screen())['Далее →'])
    await send(callback=routes(await screen())[LYRIA])
    assert LYRIA in (await screen())[1] and 'text-to-audio' in (await screen())[1]
    assert pages==[None,'second']
    await send(text='/admit fal minimax/music-3 audio.generate')
    assert not await pool.fetchval("SELECT 1 FROM approved_models WHERE provider='fal'")
    await send(text='/admit fal '+LYRIA+' audio.generate')
    assert 'Lyria 3.5' in (await screen())[1]
    await send(callback='agroot:fal')
    await send(callback=routes(await screen())['🎵 Генерировать музыку'])
    await send(callback=routes(await screen())['Lyria 3.5'])
    await send(callback=routes(await screen())['Рассчитать стоимость · Аудио и музыка'])
    await send(text='A piano track')
    old=routes(await screen())['Генерировать']
    await send(text='/admin_logout')
    await send(callback=old)
    assert not await pool.fetchval("SELECT 1 FROM clodex_music_jobs WHERE provider='fal'")
    await send(text='/admin')
    await send(text=cfg.admin_password)
    price=0.08
    await send(callback=old)
    current=routes(await screen())['Генерировать']
    assert old!=current and '80 токенов' in (await screen())[1]
    await send(callback=current)
    await send(callback=current)
    create=('POST','queue.fal.run',f'/{LYRIA}')
    assert requests.count(create)==0
    assert await pilot.tick(bot)
    restarted=FalMusicPilot(pool,cfg,api=adapter)
    if timeout:
        assert await pool.fetchval("SELECT status FROM clodex_music_jobs WHERE provider='fal'")=='unknown'
        assert tuple(await restarted.balance(owner))==(20,80)
    else:
        assert await pool.fetchval("SELECT provider_id FROM clodex_music_jobs WHERE provider='fal'")==task
        assert await restarted.tick(bot) and await restarted.tick(bot)
        assert tuple(await restarted.balance(owner))==(20,0)
        await send(text=MENU[1])
        await send(callback=routes(await screen())['Открыть работу №1'])
        assert len(bot.audio)==2 and all(args[1].data==mp3 for args,_ in bot.audio)
    assert not await restarted.tick(bot)
    assert requests.count(create)==1 and await pool.fetchval('SELECT halted FROM settings WHERE id=1')

