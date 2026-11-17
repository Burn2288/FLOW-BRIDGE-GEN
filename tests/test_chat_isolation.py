from collections import Counter
from dataclasses import replace

import httpx
import pytest

from elevenbot import telegram
from elevenbot.broadcasts import BroadcastWorker
from elevenbot.telegram import MENU, buttons
from test_admin_access import event
from test_broadcasts import BroadcastTransport, routes
from test_provider_extensibility import app_with_fixture


@pytest.fixture
def admin_already_signed_in():
    pass


class IdleCycleComplete(Exception):
    pass


class Chats(BroadcastTransport):
    def __init__(self, pool):
        super().__init__(pool)
        self.calls = Counter()
        self.owners = {}

    async def sent_to(self, chat, send, *args, **kwargs):
        self.calls[chat, 'send'] += 1
        message = await send(chat, *args, **kwargs)
        self.owners[message.message_id] = chat
        return message

    async def send_message(self, chat, text, reply_markup=None, **kwargs):
        return await self.sent_to(chat, super().send_message, text, reply_markup, **kwargs)

    async def send_photo(self, chat, photo, **kwargs):
        return await self.sent_to(chat, super().send_photo, photo, **kwargs)

    async def send_animation(self, chat, animation, **kwargs):
        return await self.sent_to(chat, super().send_animation, animation, **kwargs)

    async def edit_message_text(self, text, *, chat_id, message_id, reply_markup=None):
        self.calls[chat_id, 'edit'] += 1
        assert self.owners[message_id] == chat_id
        await super().edit_message_text(text,chat_id=chat_id,message_id=message_id,reply_markup=reply_markup)

    async def delete_message(self, chat, message_id):
        self.calls[chat, 'delete'] += 1
        assert self.owners.get(message_id,chat) == chat
        return await super().delete_message(chat,message_id)

    async def edit_message_reply_markup(self, *, chat_id, message_id, reply_markup):
        self.calls[chat_id, 'edit'] += 1
        assert self.owners[message_id] == chat_id
        await super().edit_message_reply_markup(chat_id=chat_id,message_id=message_id,reply_markup=reply_markup)

    async def set_my_commands(self, *args, **kwargs):
        return True

    async def get_updates(self, **kwargs):
        raise IdleCycleComplete

    def totals(self, chat):
        return tuple(self.calls[chat, action] for action in ('send','edit','delete'))


@pytest.mark.parametrize('scenario', ['card','prompt','quote'])
async def test_admin_and_background_preserve_another_chat(funded_env, monkeypatch, scenario):
    pool,cfg,_,admin=funded_env
    cfg=replace(cfg,mode='catalogue',admin_password='fixture-password')
    existing,added='fixture/original','fixture/added'
    posts=[]

    def respond(request):
        if request.url.path=='/catalogue':
            return httpx.Response(200,json={'scope':'key_available','functions':[],'models':[
                {'id':model,'title':title,'availability':'key_available','operations':['chat'],
                 'capabilities_known':True}
                for model,title in [(existing,'Original'),(added,'Added')]
            ]})
        if request.url.path=='/price':
            return httpx.Response(200,json={'amount':100})
        assert request.url.path=='/generate'
        posts.append(request)
        return httpx.Response(200,json={'answer':'Private result'})

    async with httpx.AsyncClient(base_url='https://fixture.invalid',transport=httpx.MockTransport(respond)) as http:
        bot=Chats(pool)
        app=app_with_fixture(pool,cfg,bot,http)
        guest=await app.svc.identity(101)
        await app.svc.accept(guest)
        async with pool.acquire() as conn:
            await app.svc.movement(conn,guest,'live','isolation:test-credit','pilot_grant',1000,0)
        await app.pricing.set_rate(admin,100,'fixture_token','1',provider='fixture')
        await pool.execute("INSERT INTO approved_models VALUES('fixture',$1,'chat','Original')",existing)
        n=0

        async def send(chat,text=None,*,callback=None):
            nonlocal n
            n+=1
            await app.handle(event(n,text,chat=chat,callback=callback))

        async def panel(chat):
            return bot.messages[(await app.navigation.read(chat)).active_id]

        async def click(chat,label):
            await send(chat,callback=routes(await panel(chat))[label])

        async def model_list():
            await send(101,'/menu')
            await click(101,'Агрегатор 3')
            await click(101,'💬 Классический чат')

        async def state():
            nav=await app.navigation.read(101)
            return (nav,bot.messages[nav.active_id],await app.svc.conversation(guest),
                    await pool.fetch('SELECT * FROM task_price_quotes WHERE user_id=$1 ORDER BY id',guest))

        async def idle_cycle():
            with monkeypatch.context() as patch:
                patch.setattr(telegram,'TelegramApp',lambda *_:app)
                with pytest.raises(IdleCycleComplete):
                    await telegram.poll(pool,app.cfg,bot)

        await send(101,'/start')
        await model_list()
        assert 'Added' not in routes(await panel(101))
        await click(101,'Original')
        if scenario!='card':
            await click(101,'Рассчитать стоимость · Диалог')
        if scenario=='quote':
            await send(101,'private prompt')
            quote_route=routes(await panel(101))['Генерировать']
            assert 'Оценка: 100' in (await panel(101))[1]
        before=await state()
        bot.calls.clear()

        await send(100,'/admin')
        await send(100,cfg.admin_password)
        assert app.has_admin_session(100)
        await send(100,'/menu')
        await send(100,telegram.RUBLE_MENU)
        code=(await app.svc.aggregate_context(admin))['price_rate']['code']
        await send(100,f'/ruble_set {code} 100 20')
        await send(100,'/price_rate fixture fixture_token 100 200')
        await send(100,f'/tariff fixture {added} chat {{}} request darkflow_token 80 fixture-source')
        await click(100,'Сохранить ставки')
        assert await pool.fetchval('SELECT amount FROM task_manual_tariffs WHERE model_id=$1',added)==80
        await send(100,'/markup fixture * percent 25')
        await send(100,f'/admit fixture {added} chat')
        await send(100,callback='brlist')
        await click(100,'Создать рассылку')
        await send(100,'Fixture preview')
        assert bot.posts[-1][0]==100 and bot.posts[-1][-1] is not None
        preview=bot.next_id
        await send(100,'/admin_logout')
        assert not app.has_admin_session(100)
        await idle_cycle()
        assert await app.broadcasts.queue.claim() is None
        print(f'ISOLATION {scenario} admin+idle admin={bot.totals(100)} user={bot.totals(101)}',flush=True)
        assert await state()==before
        assert bot.totals(101)==(0,0,0)

        bot.calls.clear()
        app=app_with_fixture(pool,cfg,bot,http)
        await idle_cycle()
        assert await state()==before
        assert bot.totals(100)==bot.totals(101)==(0,0,0)
        print(f'ISOLATION {scenario} restart admin={bot.totals(100)} user={bot.totals(101)}',flush=True)

        if scenario=='quote':
            await send(101,callback=quote_route)
            assert 'Оценка: 250' in (await panel(101))[1] and not posts
            refreshed=routes(await panel(101))['Генерировать']
            # Lift only the local pilot restriction for the fixture provider.
            async def fixture_launch(conn,user,chat):
                assert (user,chat)==(guest,101)
            app.launch.authorize=fixture_launch
            bot.calls.clear()
            await send(101,callback=refreshed)
            assert len(posts)==1 and bot.totals(100)==(0,0,0)
            assert any(text=='Private result' and bot.owners[mid]==101
                       for mid,(_,text,_) in bot.messages.items())
            print(f'ISOLATION task-result admin={bot.totals(100)} user={bot.totals(101)}',flush=True)
            accepted=refreshed.partition(':')[2]
            await send(100,'/admin')
            await send(100,cfg.admin_password)
            await send(100,'/markup fixture * percent 50')
            assert await pool.fetchval("SELECT price->>'total' FROM task_price_quotes WHERE id=$1::text::uuid",
                                       accepted)=='250'
            await model_list()
            await click(101,'Original')
            stale=routes(await panel(101))['Рассчитать стоимость · Диалог']
            await click(101,'Рассчитать стоимость · Диалог')
            await send(101,'another prompt')
            old_quote=routes(await panel(101))['Генерировать']
            await send(100,'/markup fixture * percent 75')
            await send(100,f'/revoke fixture {existing} chat')
            await send(101,callback=old_quote)
            assert 'Модель не допущена' in (await panel(101))[1]
            await send(101,callback=stale)
            assert any('Модель недоступна' in text and bot.owners[mid]==101
                       for mid,(_,text,_) in bot.messages.items())
            assert len(posts)==1

        await model_list()
        assert 'Added' in routes(await panel(101))
        await send(101,MENU[2])
        assert (await app.navigation.read(101)).keyboard_labels[2].endswith('≈ 200 ₽' if scenario!='quote' else '≈ 150 ₽')

        await send(100,'/admin')
        if not app.has_admin_session(100):
            await send(100,cfg.admin_password)
        await send(100,callback=routes(bot.messages[preview])['Выбрать получателей'])
        await click(100,'Всем пользователям бота')
        await click(100,'Разослать 2 пользователям')
        queue=app.broadcasts.queue
        worker=BroadcastWorker(queue,bot,buttons)
        bot.calls.clear()
        for _ in range(2):
            await worker.deliver(await queue.claim())
        assert await queue.claim() is None
        assert bot.totals(100)==bot.totals(101)==(1,0,0)
        print(f'ISOLATION {scenario} explicit-broadcast admin={bot.totals(100)} user={bot.totals(101)}',flush=True)


async def test_private_update_must_belong_to_sender(env):
    pool,cfg,_,_=env
    app=telegram.TelegramApp(pool,cfg,Chats(pool))
    update=event(1,MENU[0])
    message=update.message.model_copy(update={'chat':update.message.chat.model_copy(update={'id':101})})
    await app.handle(update.model_copy(update={'message':message}))
    update=event(2,callback='providers')
    callback=update.callback_query.model_copy(update={'message':message})
    await app.handle(update.model_copy(update={'callback_query':callback}))
    assert not app.bot.calls
    assert not app.bot.answers
    assert await app.navigation.read(100)==await app.navigation.read(101)
