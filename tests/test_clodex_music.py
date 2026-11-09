import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from elevenbot.aggregate import make_snapshot
from elevenbot.clodex_music import AUDIOS, MODEL, MusicAPI, MusicPilot, request
from elevenbot.discovery import SnapshotStore
from elevenbot.telegram import MENU, TelegramApp
from test_admin_access import event
from test_broadcasts import BroadcastTransport, routes


@pytest.fixture
def admin_already_signed_in():
    pass


@pytest.mark.parametrize('outcome', ['success','refused','unknown'])
async def test_music_closed_pilot(env,tmp_path,outcome):
    pool,cfg,svc,owner=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,102),admin_password='fixture-password',
                clodex_music_owner=100,clodex_music_live=True,clodex_key='fixture',
                catalogue_path=str(tmp_path/'models.json'))
    SnapshotStore(cfg.catalogue_path).write(make_snapshot([],[],[{'provider':'clodex','scope':'key_available'}]))
    await pool.execute('UPDATE settings SET halted=true WHERE id=1')
    other=await svc.identity(102)
    await svc.accept(other)
    wallets=await pool.fetch('SELECT * FROM wallets ORDER BY user_id,mode')
    mp3=(Path(__file__).resolve().parents[1]/'assets'/'demo.mp3').read_bytes()
    creates=[]
    status_calls=[]
    price='0.20'

    async def transport(req):
        path=req.url.path
        if req.method=='POST':
            payload=json.loads(req.content)
            assert payload['model']==MODEL and payload['n']==1
            if path==AUDIOS+'/estimate':
                return httpx.Response(200,json={'success':True,'data':{'model':MODEL,'cost_usd':price}})
            assert path==AUDIOS
            assert tuple(await app.music.balance(owner))==(10,90)
            creates.append(payload)
            if outcome=='refused':
                return httpx.Response(400,json={'code':'invalid_request','data':None})
            if outcome=='unknown':
                raise httpx.ReadTimeout('fixture',request=req)
            return httpx.Response(202,json={'data':{'task_id':'fixture-audio-01'}})
        if path==AUDIOS+'/fixture-audio-01':
            status_calls.append(path)
            return httpx.Response(200,json={'data':{'status':'completed'}})
        assert path==AUDIOS+'/fixture-audio-01/content' and req.url.params['index']=='0'
        return httpx.Response(200,content=mp3,headers={'content-type':'audio/mpeg'})

    api=MusicAPI(cfg.clodex_key,transport=httpx.MockTransport(transport))
    bot=BroadcastTransport(pool)
    app=TelegramApp(pool,cfg,bot)
    app.music.api=api
    app.pricing.adapters['clodex'].music_api=api
    await app.pricing.set_rate(owner,100,'USD','500',provider='clodex')
    grant_quote=await app.pricing.quote(owner,request('funding quote'))
    assert await app.music.grant(owner,100,grant_quote.id)==100
    assert await app.music.grant(owner,100,grant_quote.id) is None
    assert tuple(await app.music.balance(other))==(0,0)
    n=0

    async def send(chat=100,text=None,callback=None):
        nonlocal n
        n+=1
        await app.handle(event(n,text,chat=chat,callback=callback))

    async def screen(chat=100):
        return bot.messages[(await app.navigation.read(chat)).active_id]

    await send(text=MENU[2])
    assert 'тестовый баланс' not in (await screen())[1]
    await send(text='/admin')
    await send(text=cfg.admin_password)
    await send(callback='agroot:clodex')
    assert routes(await screen())['🎵 Генерировать музыку']=='music'
    await send(callback='music')
    await send(callback=routes(await screen())['Leonardo Music'])
    await send(text='Short piano melody without vocals')
    old=routes(await screen())['Генерировать']
    assert '0.2 USD' in (await screen())[1]
    await send(text='/admin_logout')
    await send(callback=old)
    assert bot.answers[-1][1]['text']=='Войдите через /admin.'
    await send(callback='musicprompt')
    assert bot.answers[-1][1]['text']=='Войдите через /admin.'
    await send(text=MENU[2])
    assert 'тестовый баланс' not in (await screen())[1]
    await send(chat=102,text='/admin')
    await send(chat=102,text=cfg.admin_password)
    await send(chat=102,callback='music')
    assert not app.music_access(102)
    assert not await pool.fetchval('SELECT count(*) FROM clodex_music_jobs')

    await send(text='/admin')
    await send(text=cfg.admin_password)
    price='0.18'
    await send(callback=old)
    current=routes(await screen())['Генерировать']
    assert current!=old and '90 токенов' in (await screen())[1]
    await send(callback=current)
    await send(callback=current)
    assert not creates
    assert await app.music.tick(bot)
    assert len(creates)==1
    restarted=MusicPilot(pool,cfg,api=api)
    if outcome=='success':
        assert await pool.fetchval('SELECT provider_id FROM clodex_music_jobs')=='fixture-audio-01'
        assert await restarted.tick(bot) and await restarted.tick(bot)
        assert status_calls==[AUDIOS+'/fixture-audio-01']
        assert tuple(await restarted.balance(owner))==(10,0)
        assert await pool.fetchval('SELECT status FROM clodex_music_jobs')=='delivered'
        await send(text=MENU[1])
        await send(callback=routes(await screen())['Открыть работу №1'])
        assert len(bot.audio)==2
        assert all(args[0]==100 and args[1].data==mp3 for args,_ in bot.audio)
        await send(text='/admin_logout')
        await send(text=MENU[1])
        assert 'Работ пока нет' in (await screen())[1]
    elif outcome=='refused':
        assert tuple(await restarted.balance(owner))==(100,0)
        assert await pool.fetchval("SELECT count(*) FROM clodex_music_ledger WHERE kind='release'")==1
    else:
        assert tuple(await restarted.balance(owner))==(10,90)
        assert await pool.fetchval('SELECT status FROM clodex_music_jobs')=='unknown'
    assert not await restarted.tick(bot)
    assert len(creates)==1 and wallets==await pool.fetch('SELECT * FROM wallets ORDER BY user_id,mode')
    assert await pool.fetchval('SELECT halted FROM settings WHERE id=1') is True
