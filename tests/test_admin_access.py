from dataclasses import replace
from datetime import datetime, timezone

import pytest
from aiogram.types import ForceReply, Update

from elevenbot import admin_access
from elevenbot.admin_access import PASSWORD_PROMPT, SESSION_SECONDS
from elevenbot.telegram import TelegramApp
from test_ui import Bot


@pytest.fixture
def admin_already_signed_in():
    # This module exercises the real gate, including a fresh process.
    pass


def event(number, text=None, *, chat=100, callback=None, reply=None):
    actor={'id':chat,'is_bot':False,'first_name':'Fixture'}
    message={'message_id':number,'date':int(datetime.now(timezone.utc).timestamp()),
             'chat':{'id':chat,'type':'private'},'from':actor}
    if callback:
        return Update.model_validate({'update_id':number,'callback_query':{
            'id':str(number),'from':actor,'chat_instance':'fixture','message':message,'data':callback,
        }})
    message['text']=text
    if reply is not None:
        message['reply_to_message']={**message,'message_id':reply[0],'text':reply[1],
                                     'from':{'id':999,'is_bot':reply[1]==PASSWORD_PROMPT,'first_name':'Fixture'}}
    return Update.model_validate({'update_id':number,'message':message})


async def test_empty_password_and_unlisted_chat_are_closed(env):
    pool,cfg,_,_=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,))
    bot=Bot()
    app=TelegramApp(pool,cfg,bot)
    await app.handle(event(1,'/admin'))
    assert bot.sent[-1][0]=='Админ-доступ закрыт.' and not app.admin_access.prompts
    await app.handle(event(2,'/price_report'))
    assert bot.sent[-1][0]=='Админ-доступ закрыт.'
    app.cfg=replace(cfg,admin_password='fixture-password')
    await app.handle(event(3,'/admin',chat=101))
    assert bot.sent[-1][0]=='Админ-доступ закрыт.' and not app.admin_access.prompts
    await app.handle(event(4,'/price_report'))
    assert bot.sent[-1][0]=='Войдите через /admin.'


async def test_password_updates_skip_inbox_and_logout_blocks_old_buttons(env):
    pool,cfg,_,_=env
    password='fixture-admin-password'
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),admin_password=password)
    bot=Bot()
    app=TelegramApp(pool,cfg,bot)
    await app.enqueue_updates([event(0,f'/admin {password}'),event(1,'/admin')])
    assert isinstance(bot.sent[-1][1],ForceReply)
    prompt=app.admin_access.prompts[100][0]
    await app.enqueue_updates([event(2,'fixture-wrong'),event(3,password,reply=(prompt,PASSWORD_PROMPT))])
    assert any('Неверный пароль' in text for text,_ in bot.sent)
    assert {0,1,2,3}.issubset(bot.deleted)
    assert app.has_admin_session(100)
    assert await pool.fetchval('SELECT count(*) FROM inbox')==0
    assert await pool.fetchval('SELECT offset_id FROM poll_state WHERE id=1')==4

    await app.enqueue_updates([event(4,'/price_report',reply=(3,password))])
    payload=await pool.fetchval('SELECT payload::text FROM inbox WHERE update_id=4')
    assert password not in payload and 'reply_to_message' not in payload
    await app.handle(Update.model_validate_json(payload),from_inbox=True)
    assert 'Подтверждённый расход' in bot.sent[-1][0]
    await app.handle(event(5,'/admin_logout'))
    assert not app.has_admin_session(100)
    report=bot.sent[-1][0]
    await app.handle(event(6,callback='rates:clodex'))
    assert bot.sent[-1][0]==report
    await app.enqueue_updates([event(7,'fixture-stale',reply=(1001,PASSWORD_PROMPT))])
    assert not await pool.fetchval('SELECT 1 FROM inbox WHERE update_id=7') and 7 in bot.deleted


async def test_admin_attempt_limit_expiry_restart_and_password_change(env,monkeypatch):
    pool,cfg,_,_=env
    clock=[0]
    monkeypatch.setattr(admin_access,'monotonic',lambda:clock[0])
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),admin_password='fixture-password')
    bot=Bot()
    app=TelegramApp(pool,cfg,bot)
    await app.handle(event(1,'/admin'))
    for number in range(2,7):
        await app.handle(event(number,'incorrect'))
    assert 'Слишком много попыток' in bot.sent[-1][0]
    await app.handle(event(7,cfg.admin_password))
    assert not app.has_admin_session(100)
    clock[0]+=admin_access.ATTEMPT_WINDOW

    async def login(number):
        await app.handle(event(number,'/admin'))
        await app.handle(event(number+1,app.cfg.admin_password))
        assert app.has_admin_session(100)

    await login(8)
    assert not TelegramApp(pool,cfg,Bot()).has_admin_session(100)
    clock[0]+=SESSION_SECONDS-1
    assert app.has_admin_session(100)
    clock[0]+=1
    assert not app.has_admin_session(100)
    await login(10)
    app.cfg=replace(cfg,admin_password='rotated-fixture-password')
    assert not app.has_admin_session(100)

async def test_user_and_admin_editions_share_catalogue_and_settings(env,tmp_path,manual_tariff):
    from elevenbot.aggregate import make_snapshot
    from elevenbot.anymodel import FIBO_MODEL, IMAGE_OP, model_store
    from elevenbot.discovery import SnapshotStore
    from elevenbot.telegram import EMPTY_MODELS, MENU
    from elevenbot.tariff_admin import RUBLE_MENU
    from test_aggregator_menu import NoPrice, model
    from test_anymodel import routes

    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),video_pilot=True,interaction_mode='live',
                anymodel_test_enabled=True,catalogue_path=str(tmp_path/'catalogue.json'))
    clodex=[model('clodex','clodex-video/veo-3.1','video','openai-video'),
            model('clodex','fixture/not-admitted','chat','openai')]
    anymodel=[model('anymodel',FIBO_MODEL,IMAGE_OP,'image-generation'),
              model('anymodel','fixture/not-admitted',IMAGE_OP,'image-generation')]
    for name,store,models in [('clodex',SnapshotStore(cfg.catalogue_path),clodex),
                              ('anymodel',model_store(cfg),anymodel)]:
        store.write(make_snapshot(models,[],[{'provider':name,'scope':'key_available'}]))
    bot=Bot()
    app=TelegramApp(pool,cfg,bot)
    app.pricing.adapters['anymodel']=NoPrice()
    await manual_tariff(app,user,FIBO_MODEL,IMAGE_OP,{},provider='anymodel')
    await app.pricing.set_rule(user,100,'anymodel','','percent','25')
    rules=await pool.fetch('SELECT * FROM task_price_rules')
    tariff=await pool.fetch('SELECT * FROM task_manual_tariffs')
    number=0

    async def send(text=None,*,callback=None,chat=100):
        nonlocal number
        number+=1
        await app.handle(event(number,text,callback=callback,chat=chat))

    user_tabs=['🎬 Генерировать видео','🎆 Генерировать изображение','🎙 Озвучить текст','💬 Классический чат']

    async def screens(*,admin=False,chat=100):
        await send('/menu',chat=chat)
        chooser=routes(bot)
        titles=('CLODEX','AnyModel') if admin else ('Агрегатор 1','Агрегатор 2')
        assert list(chooser)[:2]==list(titles)
        assert ('Тарифы моделей' in chooser)==admin
        assert (RUBLE_MENU in [row[0].text for row in bot.sent[-2][1].keyboard])==admin
        for title,section in zip(titles,('🎬 Генерировать видео','🎆 Генерировать изображение')):
            await send(callback=chooser[title],chat=chat)
            assert bot.sent[-1][0]==title+'\nВыберите, что хотите сделать.'
            assert section in routes(bot) and '📁 Мои работы' in routes(bot)
            assert ('⚙️ Управление агрегатором' in routes(bot))==admin
            if not admin:
                root=routes(bot)
                assert list(root)==user_tabs+['📁 Мои работы','← Агрегаторы']
                await send(callback=root[section],chat=chat)
                expected='Veo 3.1' if title==titles[0] else 'FIBO 2'
                assert list(routes(bot))==[expected,'← К агрегатору']
                await send(callback=routes(bot)['← К агрегатору'],chat=chat)
                empty='💬 Классический чат' if title==titles[0] else '🎬 Генерировать видео'
                await send(callback=root[empty],chat=chat)
                assert bot.sent[-1][0].endswith(EMPTY_MODELS)
                assert list(routes(bot))==['← К агрегатору']
                await send(callback=routes(bot)['← К агрегатору'],chat=chat)
                assert routes(bot)==root
        return routes(bot)

    await send('/admin')
    assert bot.sent[-1][0]=='Админ-доступ закрыт.'
    await screens()
    app.cfg=replace(cfg,admin_password='fixture-password')
    await send('/admin')
    await send('wrong')
    assert 'Неверный пароль' in bot.sent[-1][0]
    image=await screens()
    await send(callback=image['🎆 Генерировать изображение'])
    await send(callback=routes(bot)['FIBO 2'])
    assert 'ID:' not in bot.sent[-1][0] and 'Протоколы:' not in bot.sent[-1][0]
    await send(callback=routes(bot)['🖼 Генерировать изображение'])
    await send('test image')
    quote=bot.sent[-1][0]
    assert '125 токенов DarkFlow | Gen' in quote
    assert 'Себестоимость' not in quote and 'Наценка' not in quote
    await send(callback=routes(bot)['Отмена'])

    await send('/admin')
    await send(app.cfg.admin_password)
    image=await screens(admin=True)
    stale=image['⚙️ Управление агрегатором']
    await send(callback=stale)
    await send(callback=routes(bot)['Наши модели'])
    assert 'наценка' in bot.sent[-1][0].lower()
    await send('/admin_logout')
    assert list(routes(bot))[:2]==['Агрегатор 1','Агрегатор 2']
    assert [row[0].text for row in bot.sent[-2][1].keyboard][:2]==MENU[:2]
    assert RUBLE_MENU not in [row[0].text for row in bot.sent[-2][1].keyboard]
    count=len(bot.sent)
    await send(callback=stale)
    assert len(bot.sent)==count and bot.answers[-1]==(str(number),)
    await send('/price_report@FixtureBot')
    assert bot.sent[-1][0]=='Войдите через /admin.'

    guest=await app.svc.identity(101)
    await app.svc.accept(guest)
    await screens(chat=101)
    await send('/admin',chat=101)
    assert bot.sent[-1][0]=='Админ-доступ закрыт.'
    assert await pool.fetch('SELECT * FROM task_manual_tariffs')==tariff
    assert await pool.fetch('SELECT * FROM task_price_rules')==rules
    assert await pool.fetchval('SELECT count(*) FROM interaction_attempts')==0
