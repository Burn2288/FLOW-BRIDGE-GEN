"""Transport transition checks with a fake application service, NOT financial proof."""
from types import SimpleNamespace
import uuid
from datetime import datetime,timezone
from dataclasses import replace
from unittest.mock import AsyncMock
import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import SendAnimation, SendPhoto, SetMyCommands
from aiogram.types import BotCommandScopeChat, BotCommandScopeDefault, Update
from elevenbot import telegram
from elevenbot.telegram import TelegramApp,MENU,menu
from elevenbot.config import Config
from elevenbot.core import ConsentRequired,Rejected

class Bot:
    def __init__(self):self.sent=[];self.audio=[];self.answers=[];self.photos=[];self.deleted=[];self.animations=[]
    async def send_message(self,chat,text,reply_markup=None):self.sent.append((text,reply_markup));return SimpleNamespace(message_id=100+len(self.sent))
    async def edit_message_text(self,text,*,chat_id,message_id,reply_markup=None):
        self.sent.append((text,reply_markup))
        return SimpleNamespace(message_id=message_id)
    async def edit_message_caption(self,*,chat_id,message_id,caption,reply_markup=None):
        return await self.edit_message_text(caption,chat_id=chat_id,message_id=message_id,reply_markup=reply_markup)
    async def delete_message(self,chat,message_id):self.deleted.append(message_id);return True
    async def answer_callback_query(self,*args,**kw):self.answers.append(args)
    async def send_audio(self,*args,**kw):self.audio.append((args,kw));return SimpleNamespace(message_id=1)
    async def send_photo(self,chat,photo,*,caption=None,reply_markup=None):
        self.photos.append((photo,caption,reply_markup))
        return SimpleNamespace(message_id=1000+len(self.photos))
    async def send_animation(self,chat,animation,*,caption,reply_markup):
        self.animations.append(animation)
        return await self.send_message(chat,caption,reply_markup)
    async def answer_pre_checkout_query(self,*args,**kw):self.answers.append(kw)

class FakeService:
    def __init__(self):self.u=uuid.uuid4();self.state={'step':'home','text_content':None,'voice':None};self.confirmations=0;self.accepted=False;self.welcome=None
    async def identity(self,*a):return self.u
    async def rate(self,*a,navigation=False):pass
    async def accept(self,*a):self.accepted=True
    async def welcome_message(self,chat):return self.welcome
    async def save_welcome_message(self,chat,message_id):self.welcome=message_id
    async def conversation(self,u,step=None,text=None,voice=None,speed=None):
        if not self.accepted:raise ConsentRequired('Сначала примите условия через /start.')
        if step is not None:self.state={'step':step,'text_content':text,'voice':voice}
        return self.state
    async def quote(self,*args):return uuid.UUID(int=10),len(args[1])
    async def confirm(self,*args):self.confirmations+=1;return uuid.UUID(int=11)
    async def history(self,*args):return []
    async def wallet(self,*args):return {'available':10000,'reserved':0}

def event(text=None,callback=None,payment=None):
    message={'message_id':1,'date':int(datetime.now(timezone.utc).timestamp()),'chat':{'id':100,'type':'private'},'from':{'id':100,'is_bot':False,'first_name':'Test'}}
    if text is not None:message['text']=text
    if payment:message['successful_payment']=payment
    payload={'update_id':1}
    if callback is not None:payload['callback_query']={'id':'cb','from':message['from'],'chat_instance':'x','message':message,'data':callback}
    else:payload['message']=message
    return Update.model_validate(payload)

def app():
    bot=Bot();a=TelegramApp(None,Config(generation_enabled=True),bot);a.svc=FakeService();return a,bot


async def test_command_registration_scopes_and_failed_chat(capsys):
    error=TelegramBadRequest(SetMyCommands(commands=[]),'chat not found: fixture chat ID')
    network=TelegramNetworkError(SetMyCommands(commands=[]),'fixture timeout')
    bot=SimpleNamespace(set_my_commands=AsyncMock(side_effect=[network,True,error,True]))
    await telegram.register_commands(bot,(100,100,-101,102))

    calls=bot.set_my_commands.await_args_list
    assert [call.kwargs['scope'] for call in calls]==[
        BotCommandScopeDefault(),BotCommandScopeDefault(),BotCommandScopeChat(chat_id=100),BotCommandScopeChat(chat_id=102),
    ]
    base=[('start','Запустить бота'),('menu','Главное меню'),('cancel','Отменить текущее действие')]
    admin=[*base,('price_report','Отчёт по ценам и расходам'),
           ('admin','Войти в админку'),('admin_logout','Выйти из админки')]
    assert [[(command.command,command.description) for command in call.args[0]] for call in calls]==[base,base,admin,admin]
    output=capsys.readouterr().out
    assert output.count('telegram_commands_registered')==2
    assert output.count('telegram_commands_failed')==1 and 'fixture chat ID' not in output


async def test_price_report_handler_keeps_admin_check(env):
    pool,cfg,_,user=env
    cfg=replace(cfg,access_mode='private',admin_ids=(100,))
    bot=Bot()
    app=TelegramApp(pool,cfg,bot)
    await app.handle(event('/price_report'))
    assert 'Отчёт' in bot.sent[-1][0] and 'Подтверждённый расход' in bot.sent[-1][0]
    with pytest.raises(Rejected,match='только администратору'):
        await app.price_admin(user,101,'/price_report',[])


async def test_welcome_consent_start_and_menu():
    a,b=app()
    a.cfg=replace(a.cfg,admin_ids=(100,))
    await a.handle(event('/start'))
    assert not b.photos
    assert b.sent[-1][1].inline_keyboard[0][0].callback_data=='accept'

    await a.handle(event(callback='accept'))
    photo,caption,keyboard=b.photos[-1]
    assert photo.data==telegram.WELCOME_BANNER.read_bytes()
    assert caption==telegram.WELCOME_TEXT
    assert '🎵 Создавай музыку' in caption
    assert [row[0].text for row in keyboard.keyboard]==MENU

    for label in MENU:
        await a.handle(event(label))
        temporary=(await a.navigation.read(100)).active_id
        assert b.sent[-1][1].inline_keyboard[-1][0].callback_data=='home'
        await a.handle(event(callback='home'))
        current=(await a.navigation.read(100)).active_id
        assert current is not None and (temporary==current or temporary in b.deleted)
    assert len(b.photos)==1 and 1001 not in b.deleted
    await a.handle(event('/start'))
    assert len(b.photos)==2 and b.deleted.count(1001)==1
    assert 1002 not in b.deleted and a.svc.welcome==1002


@pytest.mark.parametrize('missing',[True,False])
async def test_welcome_fallback_retains_user_keyboard(monkeypatch,tmp_path,missing):
    a,b=app()
    await a.svc.accept(a.svc.u)
    if missing:
        monkeypatch.setattr(telegram,'WELCOME_BANNER',tmp_path/'missing.png')
    else:
        error=TelegramBadRequest(SendPhoto(chat_id=100,photo='fixture'),'fixture')
        b.send_photo=AsyncMock(side_effect=error)
    await a.handle(event('/start'))
    text,keyboard=b.sent[-1]
    assert text==telegram.WELCOME_TEXT
    assert [[button.text for button in row] for row in keyboard.keyboard]==[[label] for label in MENU]
    welcome=a.svc.welcome
    await a.handle(event(telegram.OPEN_CATALOGUE))
    assert b.sent[-1][1].inline_keyboard[-1][0].callback_data=='home'
    await a.handle(event(callback='home'))
    assert a.svc.welcome==welcome and welcome not in b.deleted
    assert (await a.navigation.read(100)).active_id is not None


async def test_welcome_replacement_survives_restart_and_send_failure(env):
    pool,cfg,_,user=env
    cfg=replace(cfg,admin_ids=(100,))
    bot=Bot()
    app=TelegramApp(pool,cfg,bot)
    await app.handle(event('/start'))
    assert await app.svc.welcome_message(100)==1001

    restarted=TelegramApp(pool,cfg,bot)
    await restarted.handle(event(MENU[0]))
    await restarted.handle(event(callback='home'))
    await restarted.handle(event(MENU[1]))
    assert len(bot.photos)==1 and 1001 not in bot.deleted

    failure=TelegramBadRequest(SendPhoto(chat_id=100,photo='fixture'),'fixture')
    send_photo,send_message=bot.send_photo,bot.send_message
    bot.send_photo=AsyncMock(side_effect=failure)
    bot.send_message=AsyncMock(side_effect=failure)
    await restarted.handle(event('/start'))
    assert await restarted.svc.welcome_message(100)==1001 and 1001 not in bot.deleted

    bot.send_photo,bot.send_message=send_photo,send_message
    await restarted.handle(event('/start'))
    assert await restarted.svc.welcome_message(100)==1002
    assert bot.deleted.count(1001)==1 and 1002 not in bot.deleted


async def test_admin_balance_keyboard_uses_current_wallet_and_opens_stale_labels(env):
    pool,cfg,_,user=env
    cfg=replace(cfg,mode='catalogue',access_mode='private',admin_ids=(100,))
    bot=Bot()
    app=TelegramApp(pool,cfg,bot)

    def check_keyboard(markup,balance):
        assert [[button.text for button in row] for row in markup.keyboard]==[
            [MENU[0]],[MENU[1]],[balance],[telegram.RUBLE_MENU],[MENU[3]],
        ]

    await app.handle(event('/start'))
    check_keyboard(bot.photos[-1][2],'💳 0 токенов')
    await app.pricing.set_ruble_rate(user,100,'100','10')
    await app.refresh_balance_keyboards()
    check_keyboard(bot.sent[-1][1],'💳 0 токенов ≈ 0 ₽')
    first_refresh=(await app.navigation.read(100)).keyboard_id
    async with pool.acquire() as conn:
        await app.svc.movement(conn,user,'live','fixture:wallet-top-up','pilot_grant',1250,0)
    await app.refresh_balance_keyboards()
    label='💳 1\u202f250 токенов ≈ 125 ₽'
    check_keyboard(bot.sent[-1][1],label)
    assert bot.sent[-1][0]=='Главное меню' and first_refresh not in bot.deleted
    published=len(bot.sent)
    await app.refresh_balance_keyboards()
    assert len(bot.sent)==published

    async with pool.acquire() as conn:
        await app.svc.movement(conn,user,'live','fixture:second-top-up','pilot_grant',500,0)
    await app.handle(event(label))
    assert bot.sent[-1][0]=='Кредиты: 1750\nЗарезервировано: 0'
    check_keyboard(bot.sent[-2][1],'💳 1\u202f750 токенов ≈ 175 ₽')
    await app.handle(event('💳 Баланс'))
    assert bot.sent[-1][0]=='Кредиты: 1750\nЗарезервировано: 0'

    await pool.execute('DELETE FROM task_ruble_equivalent')
    await app.handle(event(MENU[0]))
    check_keyboard(bot.sent[-2][1],'💳 1\u202f750 токенов')
    assert first_refresh in bot.deleted
    restarted=TelegramApp(pool,cfg,bot)
    previous=len(bot.sent)
    await restarted.refresh_balance_keyboards()
    assert len(bot.sent)==previous


@pytest.mark.parametrize('rejected',[False,True])
async def test_aggregators_animation_navigation(monkeypatch,rejected):
    a,b=app()
    a.cfg=replace(a.cfg,access_mode='private',admin_ids=(100,),anymodel_test_enabled=True)
    await a.svc.accept(a.svc.u)
    monkeypatch.setattr(a,'catalogue_snapshot',lambda: {'sources':[]})
    monkeypatch.setattr(a,'anymodel_snapshot',lambda *args: {'models':[],'sources':[{'scope':'public_only'}]})
    monkeypatch.setattr(a,'anymodel_status',lambda data: 'Тестовый каталог')
    monkeypatch.setattr(a.tariffs,'authorize',AsyncMock())
    monkeypatch.setattr(a.models,'list',AsyncMock(return_value=[]))
    if rejected:
        error=TelegramBadRequest(SendAnimation(chat_id=100,animation='fixture'),'fixture')
        b.send_animation=AsyncMock(side_effect=error)
    await a.handle(event('/start'))
    await a.handle(event(MENU[0]))
    keyboard=b.photos[-1][2]
    assert [[button.text for button in row] for row in keyboard.keyboard]==[[label] for label in MENU]
    first=(await a.navigation.read(100)).active_id
    text,markup=b.sent[-1]
    assert text.startswith('DarkFlow | Gen\nВыберите агрегатор')
    options={button.text:button.callback_data for row in markup.inline_keyboard for button in row}
    assert options['AnyModel']=='am' and telegram.OPEN_CATALOGUE not in options
    await a.handle(event(callback='am'))
    assert b.sent[-1][0]=='AnyModel\nВыберите, что хотите сделать.'
    await a.handle(event(callback='agmanage:anymodel'))
    _,markup=b.sent[-1]
    assert any(button.text=='Все модели' and button.callback_data=='amcat:current:0'
               for row in markup.inline_keyboard for button in row)
    if not rejected:
        assert b.animations[0].data==telegram.AGGREGATORS_ANIMATION.read_bytes()
        assert first in b.deleted
    await a.handle(event(callback='providers'))
    second=(await a.navigation.read(100)).active_id
    assert (second==first)==rejected
    await a.handle(event(callback='home'))
    assert (await a.navigation.read(100)).active_id==second
    assert second not in b.deleted and 1001 not in b.deleted
    assert len(b.photos)==1 and len(b.animations)==(0 if rejected else 2)

async def test_UI_full_dialog():
    a,b=app()
    await a.handle(event('/start'));assert 'деморежим' in b.sent[-1][0]
    await a.handle(event(callback='accept'));assert a.svc.accepted
    await a.handle(event("🎙 Создать озвучку"));assert a.svc.state['step']=='text'
    await a.handle(event('Привет'));assert a.svc.state['step']=='voice'
    await a.handle(event(callback='preview:0'));assert len(b.audio)==1
    await a.handle(event(callback='voice:0'));assert a.svc.state['step']=='settings'
    await a.handle(event(callback='speed:1.0'));assert a.svc.state['step']=='confirm'
    assert 'Цена: 6' in b.sent[-1][0]
    markup=b.sent[-1][1];callback=markup.inline_keyboard[0][0].callback_data
    assert len(callback.encode())<=64
    await a.handle(event(callback=callback));assert a.svc.confirmations==1
    assert 'Озвучиваю текст' in b.sent[-1][0]

@pytest.mark.parametrize('callback',['voice:-1','voice:999','preview:999','speed:bad','voices:bad','nonsense'])
async def test_UI_stale_callbacks(callback):
    a,b=app();await a.svc.accept();await a.handle(event(callback=callback))
    assert a.svc.confirmations==0 and b.sent

async def test_UI_menu_cancels_draft():
    a,b=app();await a.svc.accept();await a.handle(event("🎙 Создать озвучку"));await a.handle(event('/menu'))
    assert a.svc.state['step']=='home'
    await a.handle(event(callback='voice:0'));assert 'устарела' in b.sent[-1][0]

@pytest.mark.parametrize('command',['/terms','/privacy','/support','/paysupport'])
async def test_UI_help_without_accept(command):
    a,b=app();await a.handle(event(command));assert b.sent

async def test_UI_empty_and_oversized():
    a,b=app();await a.svc.accept();await a.handle(event("🎙 Создать озвучку"))
    for t in ('','a'*3001):
        await a.handle(event(t));assert a.svc.state['step']=='text'

@pytest.mark.parametrize("failed_screen", ["progress", "ready"])
async def test_image_delivery_survives_menu_failure(monkeypatch, failed_screen):
    from unittest.mock import AsyncMock
    from aiogram.exceptions import TelegramNetworkError
    from aiogram.methods import SendMessage
    from elevenbot.demo import DemoService
    from elevenbot.interaction import MOCK_IMAGE

    bot = Bot()
    bot.send_photo = AsyncMock(return_value=SimpleNamespace(message_id=20))
    app = TelegramApp(None, Config(interaction_mode="mock"), bot)
    app.svc = DemoService()
    user = await app.svc.identity(100)
    await app.svc.accept(user)
    model = {"provider": "clodex", "id": "test-image"}
    monkeypatch.setattr(app, "catalogue_snapshot", lambda: {"models": [model]})
    monkeypatch.setattr(app, "work_rows", lambda *args: [])

    async def render(chat, text, *args, **kwargs):
        stage = "progress" if "идёт генерация" in text else "ready"
        if stage == failed_screen:
            raise TelegramNetworkError(
                method=SendMessage(chat_id=chat, text=text), message="test timeout",
            )

    monkeypatch.setattr(app, "catalogue_screen", render)
    await app.interaction_input(
        user, 100, event("Тестовое изображение"),
        {"interaction": "images.generate", "model_id": model["id"], "history": []},
    )

    work, = await app.svc.history(user)
    assert work["image"] == MOCK_IMAGE
    bot.send_photo.assert_awaited_once()
    assert bot.send_photo.await_args.args[1].data == MOCK_IMAGE

def test_menu_core_and_discovery():
    assert len(menu().keyboard)==4
    assert [r[0].text for r in menu().keyboard]==MENU
