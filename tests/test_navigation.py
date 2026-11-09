import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import DeleteMessage, SendMessage

from elevenbot.aggregate import make_snapshot
from elevenbot.anymodel import model_store
from elevenbot.discovery import SnapshotStore
from elevenbot.tariff_admin import RUBLE_MENU
from elevenbot.telegram import MENU, TelegramApp
from test_admin_access import event
from test_ui import Bot


@pytest.fixture
def admin_already_signed_in():
    pass


class Transport(Bot):
    def __init__(self,pool):
        super().__init__()
        self.pool=pool
        self.next_id=1000
        self.messages={}
        self.events=[]
        self.fail_send=False
        self.deny_delete=set()

    async def send(self,kind,text,markup):
        self.events.append(('send',kind))
        await asyncio.sleep(0)
        if self.fail_send and kind=='text':
            self.events.append(('send_failed',kind))
            raise TelegramNetworkError(SendMessage(chat_id=100,text=text),'fixture timeout')
        self.next_id+=1
        self.messages[self.next_id]=(kind,text,markup)
        self.events.append(('new_id',self.next_id))
        return SimpleNamespace(message_id=self.next_id)

    async def send_message(self,chat,text,reply_markup=None):
        kind='keyboard' if hasattr(reply_markup,'keyboard') else 'text'
        return await self.send(kind,text,reply_markup)

    async def send_photo(self,chat,photo,*,caption,reply_markup):
        return await self.send('welcome',caption,reply_markup)

    async def send_animation(self,chat,animation,*,caption,reply_markup):
        return await self.send('gif',caption,reply_markup)

    async def edit_message_text(self,text,*,chat_id,message_id,reply_markup=None):
        kind=self.messages[message_id][0]
        self.events.append(('edit',message_id))
        self.messages[message_id]=(kind,text,reply_markup)

    async def edit_message_caption(self,*,chat_id,message_id,caption,reply_markup=None):
        await self.edit_message_text(caption,chat_id=chat_id,message_id=message_id,reply_markup=reply_markup)

    async def delete_message(self,chat,message_id):
        active=await self.pool.fetchval('SELECT active_id FROM telegram_navigation WHERE chat_id=$1',chat)
        self.events.append(('delete',message_id,active))
        if message_id in self.deny_delete:
            raise TelegramBadRequest(DeleteMessage(chat_id=chat,message_id=message_id),"message can't be deleted")
        self.messages.pop(message_id,None)
        return True

    async def edit_message_reply_markup(self,*,chat_id,message_id,reply_markup):
        kind,text,_=self.messages[message_id]
        self.messages[message_id]=(kind,text,reply_markup)
        self.events.append(('strip',message_id))


async def test_one_navigation_panel_across_modes_and_restart(env,tmp_path):
    pool,cfg,_,_=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),admin_password='fixture-password',
                anymodel_test_enabled=True,catalogue_path=str(tmp_path/'catalogue.json'))
    SnapshotStore(cfg.catalogue_path).write(make_snapshot([],[],[{'provider':'clodex','scope':'key_available'}]))
    model_store(cfg).write(make_snapshot([],[],[{'provider':'anymodel','scope':'key_available'}]))
    bot=Transport(pool)
    app=TelegramApp(pool,cfg,bot)
    n=0

    async def send(text=None,callback=None):
        nonlocal n
        n+=1
        await app.handle(event(n,text,callback=callback))

    async def panel(*,admin=False):
        state=await app.navigation.read(100)
        panels={key for key,(_,_,markup) in bot.messages.items() if hasattr(markup,'inline_keyboard')}
        assert panels=={state.active_id}
        markup=bot.messages[state.active_id][2]
        labels=[button.text for row in markup.inline_keyboard for button in row]
        assert ('Тарифы моделей' in labels or '⚙️ Управление агрегатором' in labels)==admin
        assert (RUBLE_MENU in state.keyboard_labels)==admin
        return state

    async def replace_panel(text=None,callback=None,*,admin=False):
        old=(await app.navigation.read(100)).active_id
        start=len(bot.events)
        await send(text,callback)
        state=await panel(admin=admin)
        assert state.active_id!=old
        actions=bot.events[start:]
        if old is not None:
            cleanup=actions.index(('delete',old,state.active_id))
            assert actions.index(('new_id',state.active_id))<cleanup
            assert any(event[0]=='send' for event in actions[:cleanup])
        print('NAV_REPLACEMENT',actions,flush=True)
        return state

    await send('/start')
    welcome=await app.svc.welcome_message(100)
    protected=[welcome]
    for text in ('Ответ провайдера','⏳ Статус задачи'):
        protected.append((await bot.send_message(100,text)).message_id)
    first=await replace_panel('/menu')
    await app.navigation_keyboard(100,'Главное меню',await app.reply_menu(100),force=True)
    old_keyboard=(await app.navigation.read(100)).keyboard_id
    await app.navigation_keyboard(100,'Выберите агрегатор ниже.',await app.reply_menu(100),force=True)

    start=len(bot.events)
    await send('/menu')
    assert (await panel()).active_id==first.active_id
    assert bot.events[start:]==[('edit',first.active_id)]
    print('NAV_EDIT',bot.events[start:],flush=True)
    bot.deny_delete.add(first.active_id)
    await replace_panel(callback='agroot:clodex')
    assert ('strip',first.active_id) in bot.events
    assert old_keyboard not in bot.messages
    await replace_panel(callback='providers')
    await replace_panel(callback='am')
    await send('/admin')
    await replace_panel(cfg.admin_password,admin=True)
    password_id=n
    await replace_panel(callback='agroot:clodex',admin=True)
    logged_out=await replace_panel('/admin_logout')
    count=len(bot.events)
    await send(callback='agmanage:clodex')
    assert len(bot.events)==count
    assert not app.has_admin_session(100)

    app=TelegramApp(pool,cfg,bot)
    assert len(bot.events)==count
    await app.refresh_balance_keyboards()
    assert len(bot.events)==count
    await send('/menu')
    assert (await panel()).active_id==logged_out.active_id
    assert bot.events[count:]==[('edit',logged_out.active_id)]

    count=len(bot.events)
    bot.fail_send=True
    with pytest.raises(TelegramNetworkError):
        await send(callback='am')
    assert await panel()==logged_out
    assert bot.events[count:]==[('send','text'),('send_failed','text')]
    print('NAV_FAILED',bot.events[count:],flush=True)
    bot.fail_send=False

    count=len(bot.events)
    await asyncio.gather(send(callback='am'),send(callback='providers'),send(callback='agroot:clodex'))
    assert bot.messages[(await panel()).active_id][1].startswith('Агрегатор 1')
    assert sum(action[0]=='delete' for action in bot.events[count:])==3
    assert all(message_id in bot.messages for message_id in protected)
    assert [action[1] for action in bot.events if action[0]=='delete' and action[1]<1000]==[password_id]
    print('NAV_RAPID',bot.events[count:],flush=True)


@pytest.mark.parametrize('admin',[False,True])
@pytest.mark.parametrize('populated',[False,True])
async def test_reply_keyboard_and_history_home(env,tmp_path,admin,populated):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,),admin_password='fixture-password',
                anymodel_test_enabled=True,catalogue_path=str(tmp_path/'catalogue.json'))
    SnapshotStore(cfg.catalogue_path).write(make_snapshot([],[],[{'provider':'clodex','scope':'key_available'}]))
    model_store(cfg).write(make_snapshot([],[],[{'provider':'anymodel','scope':'key_available'}]))
    await exercise_reply_keyboard(pool,cfg,user,admin,populated)


async def exercise_reply_keyboard(pool,cfg,user,admin,populated):
    from aiogram.types import Document

    from elevenbot.interaction import MOCK_IMAGE
    from elevenbot.telegram import WELCOME_TEXT

    class NoWelcome(Transport):
        async def send_photo(self,*args,**kwargs):
            raise AssertionError('Navigation must not attempt a welcome photo')

        async def send_message(self,chat,text,reply_markup=None):
            assert text!=WELCOME_TEXT
            return await super().send_message(chat,text,reply_markup)

    bot=NoWelcome(pool)
    app=TelegramApp(pool,cfg,bot)
    if populated:
        await app.svc.save_image_work(user,-6001,'fixture/image','fixture',
                                      SimpleNamespace(image=MOCK_IMAGE,filename='test.png'))
    n=0

    async def text(value,*,button=False):
        nonlocal n
        n+=1
        start=len(bot.events)
        await app.handle(event(n,value))
        actions=bot.events[start:]
        deletions=[item for item in actions if item[0]=='delete' and item[1]==n]
        assert bool(deletions)==button
        if button:
            assert actions[-1]==deletions[0]
            assert any(item[0] in ('edit','new_id') for item in actions[:-1])
        return actions

    async def click(route):
        nonlocal n
        n+=1
        await app.handle(event(n,callback=route))

    async def panel():
        state=await app.navigation.read(100)
        assert [i for i,(_,_,markup) in bot.messages.items() if hasattr(markup,'inline_keyboard')]==[state.active_id]
        assert state.keyboard_id in bot.messages
        screen=bot.messages[state.active_id]
        return screen[1],{button.text:button.callback_data for row in screen[2].inline_keyboard for button in row}

    if admin:
        await text('/admin')
        n+=1
        await app.handle(event(n,cfg.admin_password))
        assert app.has_admin_session(100)

    aggregates=await text(MENU[0],button=True)
    chooser=await panel()
    assert 'Выберите агрегатор.' in chooser[0]
    assert ('Тарифы моделей' in chooser[1])==admin
    assert ('CLODEX' if admin else 'Агрегатор 1') in chooser[1]
    assert ('AnyModel' if admin else 'Агрегатор 2') in chooser[1]
    assert (RUBLE_MENU in (await app.navigation.read(100)).keyboard_labels)==admin

    old_panel=(await app.navigation.read(100)).active_id
    bot.fail_send=True
    n+=1
    with pytest.raises(TelegramNetworkError):
        await app.handle(event(n,MENU[1]))
    assert not any(action[0]=='delete' and action[1]==n for action in bot.events)
    assert (await app.navigation.read(100)).active_id==old_panel
    bot.fail_send=False

    works=await text(MENU[1],button=True)
    history,routes=await panel()
    assert ('Работ пока нет.' in history)==(not populated)
    assert ('Открыть работу №1' in routes)==populated
    route=routes['Главное меню']
    await click(route)
    assert await panel()==chooser
    await click('home')  # Existing history buttons keep working.
    assert await panel()==chooser
    balance=await text('💳 0 токенов',button=True)
    assert 'Зарезервировано: 0' in (await panel())[0]
    help_screen=await text(MENU[3],button=True)
    ruble_screen=await text(RUBLE_MENU,button=admin)
    if admin:
        assert RUBLE_MENU in (await panel())[0]
        await click('home')
    await text('/menu')
    assert await app.svc.welcome_message(100) is None
    await app.svc.save_welcome_message(100,999)
    await text('Обычное сообщение')
    n+=1
    document=event(n)
    document=document.model_copy(update={'message':document.message.model_copy(update={
        'document':Document(file_id='fixture',file_unique_id='fixture'), 'caption':MENU[1],
    })})
    await app.handle(document)
    assert not any(action[0]=='delete' and action[1]==n for action in bot.events)
    assert await app.svc.welcome_message(100)==999
    print('MENU_ACTIONS',{'admin':admin,'populated':populated,'history_route':route,'one_panel':True,
                          'aggregators':aggregates,'works':works,'balance':balance,'help':help_screen,
                          'ruble':ruble_screen,'failed_input_retained':True},
          flush=True)
