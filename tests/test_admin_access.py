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
