"""Exercise Veo from Telegram through the documented HTTP routes and PostgreSQL."""

import asyncio
from dataclasses import replace
from decimal import Decimal
import json
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from elevenbot.core import Rejected
from elevenbot.clodex_pricing import ClodexPricing
from elevenbot.discovery import SnapshotStore, snapshot
from elevenbot.telegram import TelegramApp
from elevenbot.video import DEFAULT_VIDEO_MODELS, MODES, VideoAPI, VideoPilot
from test_anymodel import routes
from test_ui import Bot, event


def catalogue(path, modes):
    SnapshotStore(path).write(snapshot([
        {'id': MODES[mode][0], 'title': MODES[mode][0], 'provider': 'clodex',
         'availability': 'key_available', 'operations': ['video'], 'protocols': ['openai-video']}
        for mode in modes
    ]))


def button(bot, label):
    _, keyboard = bot.sent[-1]
    return next(key.callback_data for row in keyboard.inline_keyboard for key in row if key.text == label)


def settings(config, path):
    return replace(config, video_pilot=True, access_mode='private', admin_ids=(100, 101),
                   catalogue_path=str(path), interaction_mode='live', interaction_limit=3, clodex_key='fixture-only')


@pytest.fixture(scope='module')
def video():
    return subprocess.check_output([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=blue:s=64x64:d=0.1',
        '-c:v', 'libx264', '-f', 'mp4', '-movflags', 'frag_keyframe+empty_moov', 'pipe:1',
    ])


@pytest.mark.parametrize('mode', ['standard', 'fast'])
async def test_video_quote_confirmation_recovery_and_library(env, tmp_path, video, mode):
    pool, cfg, service, user = env
    path = tmp_path / 'catalogue.json'
    catalogue(path, MODES)
    cfg = settings(cfg, path)
    bot = Bot()
    bot.send_video = AsyncMock(return_value=SimpleNamespace(message_id=30))
    model, label, action = MODES[mode]
    requests = []
    task = 'task_fixture_1'
    statuses = iter(['pending', 'done'])

    def respond(request):
        assert request.headers['Authorization'] == 'Bearer fixture-only'
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        if request.url.path.endswith('/estimate'):
            return httpx.Response(200, json={'success': True, 'data': {'model': model, 'cost_usd': 0.45}})
        if request.method == 'POST':
            return httpx.Response(200, json={'id': task})
        if request.url.path.endswith('/content'):
            return httpx.Response(200, content=video, headers={'content-type': 'video/mp4'})
        return httpx.Response(200, json={'status': next(statuses)})

    api = VideoAPI(cfg.clodex_key, transport=httpx.MockTransport(respond))
    app = TelegramApp(pool, cfg, bot)
    app.video = VideoPilot(pool, cfg, api=api)
    app.pricing.adapters['clodex']=ClodexPricing(api)
    await app.pricing.set_rate(user,100,'USD','1000')
    await app.pricing.set_rule(user,100,'clodex',model,'fixed','50')
    await app.handle(event(callback='store'))
    await app.handle(event(callback=button(bot, '🎬 Генерировать видео')))
    assert sum(key.text == 'Veo 3.1' for row in bot.sent[-1][1].inline_keyboard for key in row) == 1
    await app.handle(event(callback=button(bot, 'Veo 3.1')))
    assert button(bot, MODES['standard'][2])
    assert button(bot, MODES['fast'][2])
    await app.handle(event(callback=button(bot, action)))
    assert 'Опишите' in bot.sent[-1][0]
    assert label in bot.sent[-1][0]
    await app.handle(event('A blue square'))
    assert f'Veo 3.1 · {label}' in bot.sent[-1][0]
    assert '0.45 USD' in bot.sent[-1][0] and 'Оценка: 500' in bot.sent[-1][0]
    confirmation = button(bot, 'Генерировать')
    expected = {'model': model, 'prompt': 'A blue square', 'duration': 4, 'resolution': '720p', 'aspect_ratio': '16:9'}
    assert requests == [('POST', '/v1/videos/estimate', expected)]

    await asyncio.gather(*(app.callback(user, 100, confirmation, request_id=i) for i in (2, 3)),
                         return_exceptions=True)
    assert [r for r in requests if not r[1].endswith('/estimate')]==[('POST','/v1/videos',expected)]
    assert await pool.fetchval('SELECT count(*) FROM interaction_attempts') == 1
    row = await pool.fetchrow('SELECT provider_id,status FROM video_jobs')
    assert (row['provider_id'], row['status']) == (task, 'polling')
    assert await app.video.poll_one(bot)
    bot.send_video.assert_not_awaited()

    await pool.execute('UPDATE video_jobs SET next_poll_at=now()')
    restarted = TelegramApp(pool, cfg, bot)
    restarted.video = VideoPilot(pool, cfg, api=api)
    assert await restarted.video.poll_one(bot)
    assert [r for r in requests if r[0]=='GET'] == [
        ('GET', f'/v1/videos/{task}', None), ('GET', f'/v1/videos/{task}', None),
        ('GET', f'/v1/videos/{task}/content', None),
    ]
    assert bot.send_video.await_args.args[1].data == video
    await restarted.handle(event(callback='history:0'))
    work = button(bot, 'Открыть работу №1')
    await restarted.handle(event(callback=work))
    assert bot.send_video.await_count == 2
    assert bot.send_video.await_args.args[1].data == video
    stranger = await service.identity(101)
    await service.accept(stranger)
    with pytest.raises(Rejected):
        await restarted.callback(stranger, 101, work)


@pytest.mark.parametrize('available', ['standard', 'fast'])
async def test_veo_shows_only_available_mode(env, tmp_path, available):
    pool, cfg, _, user = env
    path = tmp_path / 'catalogue.json'
    catalogue(path, [available])
    bot = Bot()
    app = TelegramApp(pool, settings(cfg, path), bot)
    await app.callback(user, 100, 'slist:current:video:0')
    await app.callback(user, 100, button(bot, 'Veo 3.1'))
    labels = [key.text for row in bot.sent[-1][1].inline_keyboard for key in row]
    assert labels == [MODES[available][2], '← К списку моделей']


async def test_uncertain_create_never_retries(env, tmp_path):
    pool, cfg, _, user = env
    api = AsyncMock()
    api.estimate.return_value = Decimal('0.45')
    api.create.side_effect = httpx.ReadTimeout('lost response')
    pilot = VideoPilot(pool, settings(cfg, tmp_path / 'unused'), api=api)
    model = MODES['fast'][0]
    quote_id, _ = await pilot.quote(user, model, 'A blue square')
    for update_id in (1, 2):
        with pytest.raises(Rejected):
            await pilot.confirm(user, quote_id, update_id, model)
    assert await pool.fetchval('SELECT status FROM video_jobs') == 'uncertain'
    api.create.assert_awaited_once()
    assert not await pilot.poll_one(Bot())


async def test_non_veo_video_admission_launch_and_revoke(env, tmp_path, video):
    pool,cfg,_,user=env
    path=tmp_path/'catalogue.json'
    cfg=settings(cfg,path)
    supported,unsupported='fixture-video/working','fixture-video/catalogue-only'
    titles={supported:'Fixture video',unsupported:'Catalogue only'}
    data=snapshot([
        {'id':ident,'title':title,'provider':'clodex','availability':'key_available',
         'operations':['video'],'protocols':['openai-video']}
        for ident,title in titles.items()
    ])
    SnapshotStore(path).write(data)
    requests=[]

    def respond(req):
        body=json.loads(req.content) if req.content else None
        requests.append((req.method,req.url.path,body))
        if req.url.path=='/v1/videos/estimate':
            assert body['model']==supported
            return httpx.Response(200,json={'success':True,'data':{'model':supported,'cost_usd':'0.4'}})
        if req.url.path=='/v1/videos':
            assert req.method=='POST'
            return httpx.Response(202,json={'request_id':'fixture-video'})
        if req.url.path.endswith('/content'):
            return httpx.Response(200,content=video,headers={'content-type':'video/mp4'})
        return httpx.Response(200,json={'status':'done'})

    api=VideoAPI(cfg.clodex_key,transport=httpx.MockTransport(respond),
                 supported_models=DEFAULT_VIDEO_MODELS|{supported})
    bot=Bot()
    bot.send_video=AsyncMock(return_value=SimpleNamespace(message_id=30))
    app=TelegramApp(pool,cfg,bot)
    app.video=VideoPilot(pool,cfg,api=api)
    app.pricing.adapters['clodex']=ClodexPricing(api)
    await app.pricing.set_rate(user,100,'USD','1000')
    args=['clodex',supported,'video']

    await app.callback(user,100,'slist:current:video:0')
    assert titles[supported] not in routes(bot)
    with pytest.raises(Rejected,match='не подключён маршрут запуска'):
        await app.models.command(user,100,'/admit',['clodex',unsupported,'video'])
    assert not requests and not await pool.fetchval('SELECT 1 FROM approved_models WHERE model_id=$1',unsupported)

    await app.models.command(user,100,'/admit',args)
    assert titles[supported] in bot.sent[-1][0] and '400' in bot.sent[-1][0]
    assert titles[unsupported] not in bot.sent[-1][0]
    await app.callback(user,100,'slist:current:video:0')
    card=routes(bot)[titles[supported]]
    await app.callback(user,100,card)
    start=routes(bot)['🎬 Генерировать видео']
    await app.callback(user,100,start)
    await app.handle(event('Fixture prompt'))
    confirm=routes(bot)['Генерировать']
    assert not any(path=='/v1/videos' for _,path,_ in requests)
    await app.callback(user,100,confirm,request_id=2)
    with pytest.raises(Rejected):
        await app.callback(user,100,confirm,request_id=3)
    expected={'model':supported,'prompt':'Fixture prompt','duration':4,'resolution':'720p','aspect_ratio':'16:9'}
    assert [r for r in requests if r[1]=='/v1/videos']==[('POST','/v1/videos',expected)]
    assert await app.video.poll_one(bot)
    assert bot.send_video.await_args.args[1].data==video

    await app.callback(user,100,start)
    await app.handle(event('Second prompt'))
    stale_confirm=routes(bot)['Генерировать']
    await app.models.command(user,100,'/revoke',args)
    assert titles[supported] not in bot.sent[-1][0]
    assert not await pool.fetchval('SELECT 1 FROM approved_models WHERE model_id=$1',supported)
    await app.callback(user,100,'slist:current:video:0')
    assert titles[supported] not in routes(bot)
    for stale in (card,start,stale_confirm):
        with pytest.raises(Rejected):
            await app.callback(user,100,stale,request_id=4)
    assert [r for r in requests if r[1]=='/v1/videos']==[('POST','/v1/videos',expected)]
    await app.callback(user,100,'history:0')
    await app.callback(user,100,routes(bot)['Открыть работу №1'])
    assert bot.send_video.await_count==2 and bot.send_video.await_args.args[1].data==video
