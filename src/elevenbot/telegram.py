"""Telegram transport. Durable inbox polling; business rules live in core."""
import asyncio,hashlib,json,re,time
from datetime import datetime,timezone
from hmac import compare_digest
from pathlib import Path
from uuid import uuid4
from aiogram import Bot
from aiogram.types import (Message,Update,InlineKeyboardMarkup,InlineKeyboardButton,ReplyKeyboardMarkup,
                           KeyboardButton,FSInputFile,BufferedInputFile,LabeledPrice,BotCommand,
                           BotCommandScopeDefault,BotCommandScopeChat,ForceReply)
from .admin_access import AdminAccess, PASSWORD_PROMPT, digest
from .core import ConsentRequired,Service,Rejected,uid
from aiogram.exceptions import ClientDecodeError, TelegramAPIError, TelegramBadRequest, TelegramNetworkError
from .providers import catalog,refresh_pilot_voices
from .interaction import HIGH_QUALITY_IMAGE_MODELS,is_disabled_model,trace_interaction
from .video import DEFAULT_VIDEO_MODELS,VIDEO_PARAMS,VideoPilot,catalogue_video_ids,video_modes
from .anymodel_video import AnyModelVideoPilot,MODEL as ANYMODEL_VIDEO_MODEL,TITLE as ANYMODEL_VIDEO_TITLE
from .anymodel import AnyModelProvider,AnyModelError,FIBO_MODEL,IMAGE_OP,can_image,available as anymodel_available,model_store
from .anymodel_speech import FISH,FISH_TITLE,SpeechPilot,voice_key
from .anymodel_image_jobs import AnyModelImageJobs
from .anymodel_pricing import AnyModelPricing
from .model_policy import ModelPolicy,ROUTES as MODEL_POLICY_ROUTES
from .pricing import BOT_UNIT,MissingRate,PriceUnavailable,Pricing,Request,decimal_text,display,ruble_value
from .clodex_pricing import ClodexPricing
from .task_launch import TaskLaunch,notify_interrupted,recover_interrupted
from .provider_execution import AnyModelExecution,ClodexExecution
from .aggregate import ProviderRegistry
from .tariff_admin import ROUTES as TARIFF_ROUTES,RUBLE_MENU,TariffAdmin,default_params,rate_button,tariff_fields,tariff_params
from .progress import ReportedTaskError,TaskProgress,UNKNOWN,WAITING
import httpx

MENU=['🌐 Агрегаторы','📁 Мои работы','💳 Баланс','❓ Помощь']
MODEL_LIST_BACK='← К списку моделей'
BALANCE_BUTTON=re.compile(r'💳 [0-9][0-9 \u00a0\u202f]* токенов(?: ≈ [0-9][0-9 \u00a0\u202f]*(?:[.,][0-9]{1,2})? ₽)?')
DEVELOPER_CALLBACKS={'cat','mdl','pf','funcs','fn','choosefn','bind','voice-demo','runmodel','speak'}
SPEECH_ROUTES={'amspeech','amvoices','amvoice','amsconfirm','amvprices','amvpick','amvready'}
ANYMODEL_ROUTES={'am','amcat','ammdl','amrun','amwork','amworkrun','amsection','amimage','amvideo','amvconfirm','amparams'}|SPEECH_ROUTES
REGISTERED_ROUTES={'pentry','pall','pview','pcat','pcard','prun'}
AGGREGATOR_ROUTES={'agroot','agmanage','agfunctions','agfunction'}
CATALOGUE_CALLBACKS=MODEL_POLICY_ROUTES|ANYMODEL_ROUTES|TARIFF_ROUTES|REGISTERED_ROUTES|AGGREGATOR_ROUTES|{'amconfirm','amcancel','provider','cat','mdl','pf','funcs','fn','choosefn','store','slist','smodel','mwork','veo','veoprompt','veoconfirm'}
STORE_SECTIONS={
    'video':('🎬 Генерировать видео','video'),
    'image':('🖼 Генерировать изображение','images.generate'),
    'speech':('🎙 Озвучить текст','audio.speech'),
    'chat':('💬 Классический чат','chat'),
}
OPEN_CATALOGUE='Открыть каталог'
WELCOME_BANNER=Path(__file__).with_name('welcome.png')
AGGREGATORS_ANIMATION=Path(__file__).with_name('darkflow-energy-strip.gif')
WELCOME_TEXT=(
    'Добро пожаловать в DarkFlow | Gen 🔮\n\n'
    'Создавай контент с помощью нейросетей прямо в Telegram.\n\n'
    '🎆 Генерируй изображения\n'
    '🎬 Создавай видео\n'
    '🎵 Создавай музыку\n'
    '🎙 Озвучивай текст\n'
    '💬 Общайся с ИИ-ассистентами\n\n'
    'Выбери раздел, чтобы начать.'
)
ANYMODEL_SECTIONS={key:title for key,(title,_) in STORE_SECTIONS.items()}
ANYMODEL_SECTIONS.update(chat='💬 Классический чат',tools='🛠 Инструменты')
SCREEN_CALLBACKS=CATALOGUE_CALLBACKS|{'home','section','history','srun','speak','voice-demo','voices','voice','speed','confirm'}
CATALOGUE_COMMANDS=('/models','🧩 Модели','/aggregators','/functions','🛠 Функции',MENU[0],OPEN_CATALOGUE)
RATE_COMMANDS={'/rate_set','/rate_calc','/ruble_set'}
ADMIN_COMMANDS=RATE_COMMANDS|{'/models','/functions','/admit','/revoke','/markup_value','/refund',
    '/markup','/price_rate','/price_report','/price_account','/tariff','/voice_tariff','/tariff_set','/tariff_scope'}
ADMIN_CALLBACKS=MODEL_POLICY_ROUTES|TARIFF_ROUTES|DEVELOPER_CALLBACKS|{
    'agmanage','agfunctions','agfunction','pall','pview','amcat','ammdl','amvprices','amvpick','amvready',
}


def admin_callback(data):
    return data.partition(':')[0] in ADMIN_CALLBACKS or (data.startswith('mwork:') and data.split(':')[2:3]==['dev'])
MODEL_ACTIONS={
    'chat':'💬 Начать диалог',
    'images.generate':'🖼 Создать изображение',
    'audio.speech':'🎙 Озвучить текст',
}
VOICE_ACTION='🎙 Создать озвучку'
STATUS={'queued':'В очереди','dispatching':'Создаётся','uncertain':'Требуется сверка оператором. Резерв удержан','succeeded':'Готово','failed':'Не удалось — резерв возвращён','cancelled':'Отменено'}

def buttons(rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t,callback_data=d) for t,d in row] for row in rows])

def store_rows():
    rows=[[(title,f'slist:current:{section}:0')] for section,(title,_) in STORE_SECTIONS.items() if section!='chat']
    rows.extend([[('📁 Мои работы','history:0')],[(STORE_SECTIONS['chat'][0],'slist:current:chat:0')]])
    return rows

def menu(*,admin_rates=False,balance=None):
    labels=[MENU[0],MENU[1],balance or MENU[2],MENU[3]]
    if admin_rates:labels.insert(3,RUBLE_MENU)
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x)] for x in labels],resize_keyboard=True,is_persistent=True)

class TelegramApp:
    def __init__(self,pool,cfg,bot,*,providers=None):
        self.pool,self.cfg,self.bot=pool,cfg,bot;self.svc=Service(pool,cfg)
        self.admin_access=AdminAccess()
        self.catalogue_messages = {}
        self.catalogue_animations = set()
        self.aggregator_keyboard_messages = {}
        self.balance_keyboard_labels = {}
        self.balance_keyboard_messages = {}
        self.work_previews = {}
        self.pending_speech = {}
        self.progress = TaskProgress(bot,pool)
        self.video = VideoPilot(pool,cfg)
        self.anymodel_video = AnyModelVideoPilot(pool,cfg)
        self.anymodel_speech = SpeechPilot(pool,cfg)
        self.anymodel_images = AnyModelImageJobs(pool,cfg)
        self.providers = providers if providers is not None else ProviderRegistry()
        self.providers.register('anymodel',price=AnyModelPricing(cfg.anymodel_key),
            launch=AnyModelExecution(self,lambda:AnyModelProvider(self.cfg.anymodel_key)))
        self.providers.register('clodex',price=ClodexPricing(self.video.api),launch=ClodexExecution(self))
        self.pricing = Pricing(pool,cfg,self.providers.prices)
        self.launch = TaskLaunch(self.pricing,self.providers.launches)
        self.tariffs = TariffAdmin(self,buttons)
        self.models = ModelPolicy(self,buttons)
    async def say(self,chat,text,markup=None):
        if not isinstance(markup,ReplyKeyboardMarkup):
            return await self.bot.send_message(chat,text,reply_markup=markup)
        markup=await self.reply_menu(chat)
        message=await self.bot.send_message(chat,text,reply_markup=markup)
        self.remember_balance_keyboard(chat,markup)
        return message

    async def balance_menu_rows(self,chats):
        if self.pool is None or not chats:
            return []
        return await self.pool.fetch("""
            SELECT i.external_id,i.welcome_message_id,w.available,r.bot_amount,r.rubles
            FROM identities i JOIN users u ON u.id=i.user_id JOIN wallets w ON w.user_id=u.id
            LEFT JOIN task_ruble_equivalent r ON r.id=1
            WHERE i.platform='telegram' AND i.external_id=ANY($1::bigint[]) AND w.mode=$2
                AND i.terms_version='1' AND i.accepted_at IS NOT NULL AND NOT u.blocked
            """,chats,self.cfg.wallet_mode)

    @staticmethod
    def balance_label(row):
        label=f"💳 {display(row['available'])} токенов"
        if row['bot_amount'] is not None:
            label+=f" ≈ {decimal_text(ruble_value(row['available'],row))} ₽"
        return label

    async def reply_menu(self,chat):
        rows=await self.balance_menu_rows([chat])
        return self.role_keyboard(chat,self.balance_label(rows[0]) if rows else None)

    def role_keyboard(self,chat,balance=None):
        return menu(admin_rates=self.has_admin_session(chat) and self.pool is not None
                    and self.cfg.access_mode=='private',balance=balance)

    def remember_balance_keyboard(self,chat,markup):
        if len(markup.keyboard)>=3:
            self.balance_keyboard_labels[chat]=tuple(row[0].text for row in markup.keyboard)

    async def refresh_balance_keyboards(self,chat=None):
        chats=list(dict.fromkeys((*self.cfg.admin_ids,*self.balance_keyboard_labels))) if chat is None else [chat]
        for row in await self.balance_menu_rows(chats):
            ext=row['external_id']
            if row['welcome_message_id'] is None and ext not in self.balance_keyboard_labels and chat is None:
                continue
            markup=self.role_keyboard(ext,self.balance_label(row))
            labels=tuple(row[0].text for row in markup.keyboard)
            if self.balance_keyboard_labels.get(ext)==labels:
                continue
            try:
                message=await self.bot.send_message(ext,'Главное меню',reply_markup=markup)
            except (ClientDecodeError,TelegramAPIError):
                continue
            self.balance_keyboard_labels[ext]=labels
            previous=self.balance_keyboard_messages.get(ext)
            self.balance_keyboard_messages[ext]=message.message_id
            if previous is not None:
                try:
                    await self.remove_menu_message(ext,previous)
                except (ClientDecodeError,TelegramAPIError):
                    pass
    async def catalogue_screen(self, chat, text, markup=None, *, after_message_id=None, animation=None):
        await self.close_work_preview(chat)
        message_id = self.catalogue_messages.get(chat)
        if (animation is None and message_id is not None and chat not in self.catalogue_animations
                and not isinstance(markup, ReplyKeyboardMarkup)
                and (after_message_id is None or message_id > after_message_id)):
            try:
                await self.bot.edit_message_text(text, chat_id=chat, message_id=message_id, reply_markup=markup)
                return
            except TelegramBadRequest as error:
                reason = str(error).lower()
                if 'message is not modified' in reason:
                    return
                if not any(detail in reason for detail in ('message to edit not found', "message can't be edited")):
                    raise
        message = None
        if animation is not None:
            try:
                data=await asyncio.to_thread(animation.read_bytes)
                message=await self.bot.send_animation(
                    chat,BufferedInputFile(data,filename=animation.name),
                    caption=text,reply_markup=markup,
                )
            except (OSError,ClientDecodeError,TelegramAPIError):
                pass
        if message is None:
            message=await self.say(chat,text,markup)
            self.catalogue_animations.discard(chat)
        else:
            self.catalogue_animations.add(chat)
        self.catalogue_messages[chat]=message.message_id
        if message_id is not None and message_id!=message.message_id:
            await self.remove_menu_message(chat,message_id)

    async def remove_menu_message(self, chat, message_id):
        try:
            await self.bot.delete_message(chat, message_id)
        except (TelegramBadRequest, TelegramNetworkError):
            pass

    async def close_work_preview(self,ext):
        previous=self.work_previews.pop(ext,None)
        if previous is not None:
            await self.remove_menu_message(ext,previous)

    async def open_work(self,u,ext,kind,job,*,prompt_only=False,show_prompt=False):
        work=await getattr(self.svc,f'{kind}_work')(u,job)
        await self.close_work_preview(ext)
        prompt=work['prompt']
        if prompt_only:
            if not prompt:raise Rejected('Текст этой работы недоступен.')
            message=await self.bot.send_document(ext,BufferedInputFile(prompt.encode(),filename='prompt.txt'))
        else:
            caption=work.get('caption') or {'image':'Изображение','audio':'Озвучка','video':'Veo 3.1'}[kind]
            markup=None
            if show_prompt and prompt:
                caption+='\nПромпт: '+prompt[:450]+('…' if len(prompt)>450 else '')
                if len(prompt)>450:
                    markup=buttons([[('Полный промпт',f'prompt:{kind}:{job}')]])
            send=getattr(self.bot,{'image':'send_photo','audio':'send_audio','video':'send_video'}[kind])
            message=await send(ext,BufferedInputFile(work[kind],filename=work['filename']),
                               caption=caption,reply_markup=markup)
        self.work_previews[ext]=message.message_id

    async def work_rows(self,ext,section,model_id,snapshot=None):
        rows=[]
        if snapshot is None:
            try:
                snapshot=self.catalogue_snapshot()
            except Rejected:
                snapshot=None
        if snapshot:
            published=await self.store_models(snapshot,section,ext)
            for index,model in enumerate(snapshot['models']):
                if model.get('provider')!='clodex' or model['id']!=model_id:
                    continue
                scope=section if index in published else 'dev' if self.has_admin_session(ext) else None
                if scope:
                    rows.append([('История модели',f'mwork:{snapshot["version"]}:{scope}:{index}:0')])
                    break
        return rows+[[('Мои работы','history:0')],[('Главное меню','home')]]

    async def refresh_speech_results(self):
        # Runs in the same event loop as navigation, between batches of updates.
        for job,(ext,u,model,message,last_status) in list(self.pending_speech.items()):
            try:
                status=(await self.svc.owned(u,job))['status']
                if status in ('queued','dispatching'):
                    if status!=last_status and await self.progress.edit(
                        ext,message,f'⏳ {model} · Озвучиваю текст…',
                    ):
                        self.pending_speech[job]=(ext,u,model,message,status)
                    continue
                self.pending_speech.pop(job,None)
                if status=='succeeded':
                    await self.progress.finish(ext,message,model,success=True)
                    await self.open_work(u,ext,'audio',str(job),show_prompt=True)
                    trace_interaction(str(job),'result_notified')
                else:
                    await self.progress.finish(ext,message,model,UNKNOWN if status=='uncertain' else STATUS[status])
            except (Rejected,TelegramBadRequest,TelegramNetworkError) as error:
                self.pending_speech.pop(job,None)
                await self.progress.finish(ext,message,model,'Не удалось получить озвучку.')
                trace_interaction(str(job),'result_display_failed',error_type=type(error).__name__)

    def has_admin_session(self,ext):
        return ext in self.cfg.admin_ids and self.admin_access.active(ext,self.cfg.admin_password)

    async def delete_auth_message(self,message):
        try:
            await self.bot.delete_message(message.chat.id,message.message_id)
        except (ClientDecodeError,TelegramAPIError):
            pass

    async def intercept_admin_update(self,update,*,allow_login=True):
        event=update.pre_checkout_query or update.callback_query or update.message
        if not event or not event.from_user or event.from_user.is_bot:
            return False
        ext=event.from_user.id
        message=update.message
        text=(message.text or '') if message else ''
        words=text.lstrip().split(maxsplit=1)
        command=words[0].lower().partition('@')[0] if words else ''
        login_command=command in ('/admin','/admin_logout')
        reply=message.reply_to_message if message else None
        password_reply=bool(reply and reply.from_user and reply.from_user.is_bot and reply.text==PASSWORD_PROMPT)
        password=self.cfg.admin_password
        content=(message.text or message.caption or '') if message else ''
        literal_secret=bool(password and content and compare_digest(digest(content),digest(password)))
        waiting=ext in self.admin_access.prompts
        if message and (message.chat.type!='private' or message.chat.id!=ext):
            return login_command or password_reply or literal_secret
        if message and (message.successful_payment or message.refunded_payment):
            return False

        eligible=ext in self.cfg.admin_ids
        # Navigating away abandons the challenge so the next prompt stays a user request.
        user_navigation=bool(update.callback_query or command.startswith('/') or text in MENU
                             or text==OPEN_CATALOGUE or BALANCE_BUTTON.fullmatch(text))
        if waiting and user_navigation and not (login_command or password_reply or literal_secret):
            self.admin_access.prompts.pop(ext,None)
            waiting=False
        if message and (password_reply or (waiting and not login_command) or (literal_secret and not login_command)):
            if not allow_login:return True
            try:
                status=(self.admin_access.verify(ext,password,text,reply.message_id if password_reply else None)
                        if eligible and message.text is not None else 'expired')
            finally:
                await self.delete_auth_message(message)
            if status=='ok':
                u=await self.svc.identity(ext)
                try:
                    await self.svc.conversation(u,'home')
                except Rejected as error:
                    await self.say(ext,str(error))
                else:
                    await self.say(ext,'Вход выполнен на 8 часов.',menu())
                    await self.show_providers(ext)
            else:
                feedback={'incorrect':'Неверный пароль. Попробуйте ещё раз.',
                          'locked':'Слишком много попыток. Попробуйте позже.',
                          'expired':'Откройте новый запрос на вход через /admin.'}
                await self.say(ext,feedback[status] if eligible and password else 'Админ-доступ закрыт.')
            return True

        if message and login_command:
            if not allow_login:return True
            await self.delete_auth_message(message)
            if not eligible:
                await self.say(ext,'Админ-доступ закрыт.')
            elif command=='/admin_logout':
                self.admin_access.logout(ext)
                self.balance_keyboard_labels.pop(ext,None)
                try:
                    u=await self.svc.identity(ext)
                    await self.svc.conversation(u,'home')
                except Rejected as error:
                    await self.say(ext,str(error),menu())
                else:
                    await self.say(ext,'Вы вышли из админки.',menu())
                    await self.show_providers(ext)
            elif not password:
                await self.say(ext,'Админ-доступ закрыт.')
            elif len(words)>1:
                await self.say(ext,'Отправьте /admin без пароля и ответьте на запрос бота.')
            elif self.has_admin_session(ext):
                await self.show_providers(ext)
            elif self.admin_access.locked(ext):
                await self.say(ext,'Слишком много попыток. Попробуйте позже.')
            else:
                prompt=await self.bot.send_message(ext,PASSWORD_PROMPT,reply_markup=ForceReply(selective=True))
                self.admin_access.challenge(ext,prompt.message_id)
            return True

        return False

    def admin_denial(self,ext):
        if ext in self.cfg.admin_ids and self.cfg.admin_password:
            return 'Войдите через /admin.'
        return 'Админ-доступ закрыт.'

    async def enqueue_updates(self,updates):
        pending=[]
        for update in sorted(updates,key=lambda item:item.update_id):
            try:
                handled=await self.intercept_admin_update(update)
            except (ClientDecodeError,TelegramAPIError):
                # Auth events never enter the inbox, including when the response fails.
                handled=True
            if not handled:
                pending.append(update)
        # Reply/quote data is not used for dispatch and can contain a previous secret.
        quoted={'reply_to_message','quote','external_reply','pinned_message'}
        exclude={'message':quoted,'callback_query':{'message':quoted}}
        async with self.pool.acquire() as c,c.transaction():
            for update in pending:
                await c.execute('INSERT INTO inbox(update_id,payload) VALUES($1,$2::jsonb) ON CONFLICT DO NOTHING',
                                update.update_id,update.model_dump_json(exclude=exclude))
            await c.execute('UPDATE poll_state SET offset_id=$1 WHERE id=1',max(u.update_id for u in updates)+1)

    async def handle(self,update,*,from_inbox=False):
        if await self.intercept_admin_update(update,allow_login=not from_inbox):return
        event=update.pre_checkout_query or update.callback_query or update.message
        if not event or not event.from_user or event.from_user.is_bot:return
        ext=event.from_user.id
        if update.message and update.message.chat.type!='private':return
        if update.callback_query and (not update.callback_query.message or update.callback_query.message.chat.type!='private'):return
        u=await self.svc.identity(ext)
        catalogue_callback = False
        try:
            if update.pre_checkout_query:
                e=update.pre_checkout_query
                ok=await self.svc.precheckout(u,e.invoice_payload,e.total_amount,e.currency)
                await self.bot.answer_pre_checkout_query(e.id,ok=ok,error_message=None if ok else 'Покупка недоступна. Откройте «Баланс».')
                return
            if update.message and update.message.successful_payment:
                e=update.message.successful_payment
                await self.svc.payment(u,e.invoice_payload,e.total_amount,e.currency,e.telegram_payment_charge_id)
                await self.say(ext,'Оплата получена, кредиты зачислены.',menu());return
            if update.message and update.message.refunded_payment:
                # External refund notification needs local order match, never user-provided charge.
                e=update.message.refunded_payment
                async with self.pool.acquire() as c:
                    p=await c.fetchrow('SELECT * FROM payments WHERE charge_id=$1 AND user_id=$2',e.telegram_payment_charge_id,u)
                if p and p['status']=='refunding':await self.svc.complete_refund(p['id'])
                elif p and p['status']!='refunded':
                    async with self.pool.acquire() as c,c.transaction():
                        await c.execute('UPDATE users SET blocked=true WHERE id=$1',u)
                        await c.execute("UPDATE payments SET status='review' WHERE id=$1",p['id'])
                        await c.execute('UPDATE settings SET halted=true WHERE id=1')
                return
            data=(update.callback_query.data or '') if update.callback_query else ''
            text=(update.message.text or '') if update.message else ''
            if BALANCE_BUTTON.fullmatch(text):
                text=MENU[2]
            command=text.lstrip().split(maxsplit=1)
            command=command[0].lower().partition('@')[0] if command else ''
            if not self.has_admin_session(ext):
                if update.callback_query and admin_callback(data):
                    await self.bot.answer_callback_query(update.callback_query.id,text=self.admin_denial(ext))
                    return
                if command in ADMIN_COMMANDS or text in (RUBLE_MENU,'🧩 Модели','🛠 Функции'):
                    await self.say(ext,self.admin_denial(ext),menu())
                    return
            aggregator_menu=text==MENU[0] or command=='/menu'
            navigation=(data in ('providers','home') or data.partition(':')[0] in CATALOGUE_CALLBACKS
                        or data.startswith(('voices:','history:','section:','get:','image:','mget:','mimage:','video:','prompt:','chatwork:'))
                        or aggregator_menu or text in CATALOGUE_COMMANDS or text in MENU or text in ('/cancel',RUBLE_MENU)
                        or command in RATE_COMMANDS)
            await self.svc.rate(u,navigation=navigation)
            if update.callback_query:
                e=update.callback_query
                try:
                    await self.bot.answer_callback_query(e.id)
                except TelegramBadRequest as error:
                    if not any(reason in str(error).lower() for reason in ('query is too old', 'query id is invalid')):
                        raise
                catalogue_callback = data=='accept' or data=='providers' or data.partition(':')[0] in SCREEN_CALLBACKS
                bot_screen = isinstance(e.message, Message) and e.message.from_user and e.message.from_user.is_bot
                previous_screen = self.catalogue_messages.get(ext)
                if catalogue_callback and bot_screen and previous_screen is None:
                    self.catalogue_messages[ext]=e.message.message_id
                    if e.message.animation:
                        self.catalogue_animations.add(ext)
                await self.callback(u,ext,data,request_id=update.update_id)
                if (data=='home' and bot_screen and e.message.message_id not in
                        (previous_screen, self.catalogue_messages.get(ext)) and previous_screen is not None):
                    await self.remove_menu_message(ext,e.message.message_id)
                return
            if text==OPEN_CATALOGUE:
                await self.svc.conversation(u,'home')
                if self.has_admin_session(ext):
                    await self.show_store(ext)
                else:
                    await self.show_providers(ext)
                await self.remove_menu_message(ext,update.message.message_id);return
            if command=='/models' or text=='🧩 Модели':
                await self.svc.conversation(u,'home');await self.show_models(ext)
                await self.remove_menu_message(ext,update.message.message_id);return
            if aggregator_menu or command in ('/aggregators','/functions') or text=='🛠 Функции':
                await self.svc.conversation(u,'home')
                if aggregator_menu:
                    message=await self.say(ext,'Выберите агрегатор ниже.',menu())
                    previous=self.aggregator_keyboard_messages.get(ext)
                    self.aggregator_keyboard_messages[ext]=message.message_id
                    if previous is not None:
                        await self.remove_menu_message(ext,previous)
                await self.show_providers(ext,after_message_id=update.message.message_id)
                await self.remove_menu_message(ext,update.message.message_id);return
            if command=='/start':
                try:
                    await self.svc.conversation(u,'home')
                except ConsentRequired:
                    await self.catalogue_screen(ext,self.cfg.brand+' — агрегатор моделей и функций. Выберите агрегатор, затем его модели или функции.\n'+('Сейчас работает деморежим: тестовый звук, без оплаты.\n' if self.cfg.mode=='mock' else '')+'\nУсловия: '+self.cfg.terms+'\nПолитика: '+self.cfg.privacy,buttons([[('Принять','accept')]]))
                else:
                    await self.show_home(ext,replace_welcome=True)
                await self.remove_menu_message(ext,update.message.message_id);return
            if text in ('/terms','/privacy','/support','/paysupport'):
                await self.say(ext, self.cfg.terms if text=='/terms' else self.cfg.privacy if text=='/privacy' else self.cfg.support+'\nПо покупкам обращайтесь владельцу сервиса, а не поддержке Telegram.');return
            if command in ('/admit','/revoke','/markup_value'):
                await self.models.command(u,ext,command,text.split()[1:]);return
            if command in RATE_COMMANDS:
                await self.tariffs.rate_command(u,ext,command,text.split()[1:]);return
            if text==RUBLE_MENU:
                await self.tariffs.callback(u,ext,'rublerate','');return
            if command in ('/markup','/price_rate','/price_report','/price_account','/tariff','/voice_tariff','/tariff_set','/tariff_scope'):
                await self.price_admin(u,ext,command,text.split()[1:]);return
            if text.startswith('/refund '):
                if not self.has_admin_session(ext):raise Rejected(self.admin_denial(ext))
                p=await self.svc.prepare_refund(text.split(maxsplit=1)[1],provider='telegram')
                try: ok=await self.bot.refund_star_payment(ext if p['user_id']==u else await self.external(p['user_id']),p['charge_id'])
                except Exception:
                    await self.say(ext,'Исход возврата неизвестен. Резерв удержан; требуется сверка.');return
                if ok:await self.svc.complete_refund(p['id'])
                await self.say(ext,'Возврат завершён.' if ok else 'Возврат требует сверки.');return
            if text in MENU or text==VOICE_ACTION or text=='/cancel':
                await self.svc.conversation(u,'home')
                if text==VOICE_ACTION:
                    await self.svc.conversation(u,'text');await self.catalogue_screen(ext,'Отправьте текст до 3000 символов.',buttons([[('Главное меню','home')]]))
                    await self.remove_menu_message(ext,update.message.message_id);return
                if text in MENU[1:]:
                    await self.menu_section(u,ext,MENU.index(text),after_message_id=update.message.message_id)
                else:
                    await self.show_home(ext)
                await self.remove_menu_message(ext,update.message.message_id);return
            if command.startswith('/'):
                await self.say(ext,'Команда не распознана. Откройте меню через /menu.',menu());return
            state=await self.svc.conversation(u)
            if state['step']=='aggregate':
                context=await self.svc.aggregate_context(u)
                if context and any(key in context for key in ('tariff_admin','tariff_preview','our_markup','anyvoice_tariff_selection','price_rate')):
                    raise Rejected('Используйте команду с экрана настройки тарифа.')
                if context and context.get('provider') in self.providers.interactive:
                    request=Request(context['provider'],context['model_id'],context['interaction'],
                                    context['title'],text,context.get('params',{}),context.get('history',[]))
                    await self.show_price(ext,await self.pricing.quote(u,request));return
                if context and context.get('provider')=='anymodel':
                    await self.anymodel_input(u,ext,text,context);return
                if context and ('video_mode' in context or 'clodex_video_model' in context):
                    await self.video_prompt(u,ext,text,context);return
                if context and 'interaction' in context:
                    await self.interaction_input(u,ext,update,context);return
                if not self.has_admin_session(ext):
                    raise Rejected(self.admin_denial(ext))
                await self.aggregate_input(u,ext,text,request_id=update.update_id);return
            if state['step']=='text':
                if not text.strip() or len(text)>3000:raise Rejected('Отправьте текст от 1 до 3000 символов.')
                if self.cfg.speech_pilot and state.get('voice'):
                    await self.make_quote(u,ext,text,state['voice'],1.0,after_message_id=update.message.message_id)
                    return
                if self.cfg.speech_pilot:
                    await self.load_pilot_voices()
                await self.svc.conversation(u,'voice',text)
                await self.remove_menu_message(ext,update.message.message_id)
                await self.voices(ext,after_message_id=update.message.message_id)
                return
            await self.show_home(ext)
        except ReportedTaskError:
            return
        except Rejected as e:
            if update.message and update.message.successful_payment:
                async with self.pool.acquire() as c,c.transaction():
                    await c.execute("UPDATE inbox SET error_code='PAYMENT_REVIEW' WHERE update_id=$1",update.update_id)
                    await c.execute('UPDATE settings SET halted=true WHERE id=1')
                    await c.execute("INSERT INTO audit_events(action,target) VALUES('payment_review',$1)",u)
            if update.pre_checkout_query:
                await self.bot.answer_pre_checkout_query(update.pre_checkout_query.id,ok=False,error_message=str(e))
            elif isinstance(e,PriceUnavailable):
                admin=self.has_admin_session(ext)
                rows=[[rate_button(e.provider,e.cost.unit)]] if admin and isinstance(e,MissingRate) else []
                message=str(e) if admin else 'Цена недоступна. Запуск закрыт.'
                await self.catalogue_screen(ext,message,buttons(rows+[[('← Агрегаторы','providers')]]))
            elif str(e).startswith(('AnyModel:','CLODEX:')) and not self.has_admin_session(ext):
                await self.catalogue_screen(ext,str(e).partition(': ')[2],buttons([[('← Агрегаторы','providers')]]))
            elif str(e).startswith('AnyModel:') and anymodel_available(self.cfg):
                await self.catalogue_screen(ext,str(e),buttons([[('← AnyModel','am')]]))
            elif catalogue_callback and data.startswith('confirm:') and isinstance(update.callback_query.message,Message):
                await self.catalogue_screen(ext,str(e),update.callback_query.message.reply_markup)
            elif catalogue_callback:
                await self.catalogue_screen(ext,str(e),buttons([[('← Агрегаторы','providers')]]))
            else:await self.say(ext,str(e),menu())
        except (ValueError,TypeError,IndexError) as error:
            if update.pre_checkout_query:
                await self.bot.answer_pre_checkout_query(update.pre_checkout_query.id,ok=False,error_message='Заказ недоступен.')
            elif update.callback_query:
                await self.say(ext,'Кнопка устарела. Откройте меню.',menu())
            else:
                print(json.dumps({'event':'message_processing_failed','update_id':update.update_id,
                                  'error_type':type(error).__name__}),flush=True)
                await self.catalogue_screen(
                    ext,'Не удалось обработать сообщение.',
                    buttons([[('Главное меню','home')]]),after_message_id=update.message.message_id,
                )

    async def external(self,u):
        async with self.pool.acquire() as c:return await c.fetchval("SELECT external_id FROM identities WHERE user_id=$1 AND platform='telegram'",u)

    async def load_pilot_voices(self):
        try:
            available=await refresh_pilot_voices(self.cfg)
        except (httpx.HTTPError,ValueError,OSError):
            available=False
        if not available:
            raise Rejected('Не удалось загрузить голоса ElevenLabs. Откройте модель и попробуйте ещё раз.')

    @staticmethod
    def voice_version(voices):
        return hashlib.sha256(json.dumps(voices,sort_keys=True).encode()).hexdigest()[:12]

    async def voices(self,ext,page=0,*,after_message_id=None):
        voices=catalog(self.cfg);page=max(0,page)
        rows=[]
        version=self.voice_version(voices)+':' if self.cfg.speech_pilot else ''
        for i,v in enumerate(voices[page*5:page*5+5],start=page*5):
            row=[(v['name'],f'voice:{version}{i}')]
            if v.get('preview'):row.append(('▶ Образец',f'preview:{i}'))
            rows.append(row)
        nav=[]
        if page:nav.append(('Назад',f'voices:{page-1}'))
        if len(voices)>(page+1)*5:nav.append(('Далее',f'voices:{page+1}'))
        if nav:rows.append(nav)
        rows.append([('Главное меню','home')])
        await self.catalogue_screen(ext,'Выберите голос.' if voices else 'Проверенные голоса пока не подключены.',buttons(rows),after_message_id=after_message_id)

    async def history(self,u,ext,page=0,*,after_message_id=None,model=None):
        await self.svc.conversation(u,'home')
        model_id,origin=model if model else (None,'history')
        jobs=await (self.svc.history(u,page*10,model_id) if model else self.svc.history(u,page*10))
        lines=[f'Работы модели {model_id}:' if model else 'Ваши работы:'] if jobs else ['Работ пока нет.']
        rows=[]
        for index,r in enumerate(jobs,start=page*10+1):
            kind=r.get('kind','audio')
            name={'image':'Изображение','audio':'Озвучка','video':'Видео','chat':'Ответ чата'}[kind]
            price=f" · {r['price']} кредитов" if r['price'] is not None else ''
            lines.append(f"{index}. {r['created_at']:%d.%m %H:%M} UTC · {name} · {STATUS[r['status']]}{price}")
            if r['status']=='succeeded' and r.get('file_available',True):
                route={'image':'image','audio':'get','video':'video','chat':'chatwork'}[kind]
                if model and kind in ('audio','image'):route='m'+route
                rows.append([(f"Открыть работу №{index}",f"{route}:{r['id']}")])
            if r['status']=='queued':
                rows.append([(f'Отменить №{index}',f"cancel:{r['id']}")])
        nav=[]
        if page:nav.append(('Назад',f'{origin}:{page-1}'))
        if len(jobs)==10:nav.append(('Далее',f'{origin}:{page+1}'))
        if nav:rows.append(nav)
        if model:
            _,version,section,index=origin.split(':')
            back=f'mdl:{version}:{index}' if section=='dev' else f'smodel:{version}:{section}:0:{index}'
            rows.append([('← К модели',back)])
        rows.append([('Главное меню','home')])
        await self.catalogue_screen(ext,'\n'.join(lines),buttons(rows),after_message_id=after_message_id)

    async def menu_section(self,u,ext,section,*,after_message_id=None):
        if section==1:await self.history(u,ext,after_message_id=after_message_id);return
        rows=[]
        if section==2:
            w=await self.svc.wallet(u)
            await self.refresh_balance_keyboards(ext)
            text=f"{'Демо-кредиты' if self.cfg.mode=='mock' else 'Кредиты'}: {w['available']}\nЗарезервировано: {w['reserved']}"
            if self.cfg.payments_enabled and self.cfg.payment_backend=='stars':
                rows.append([('Пополнить','buy')])
        else:
            text=self.cfg.brand+'\nОткройте каталог и выберите нужное действие.\n/terms /privacy /support /paysupport'
        rows.append([('Главное меню','home')])
        await self.catalogue_screen(ext,text,buttons(rows),after_message_id=after_message_id)

    async def callback(self,u,ext,data,*,request_id=None):
        route=data.partition(':')[0]
        if admin_callback(data) and not self.has_admin_session(ext):
            raise Rejected('Действие доступно только администратору.')
        if route in AGGREGATOR_ROUTES:
            await self.aggregator_callback(u,ext,route,data.split(':')[1:]);return
        if route in MODEL_POLICY_ROUTES:
            await self.models.callback(u,ext,route,data.split(':')[1:]);return
        if route in REGISTERED_ROUTES:
            await self.registered_callback(u,ext,route,data.split(':')[1:]);return
        if route in TARIFF_ROUTES:
            await self.tariffs.callback(u,ext,route,data.partition(':')[2]);return
        if route in ('amconfirm','amcancel'):
            quote_id=uid(data.partition(':')[2])
            if route=='amconfirm' and request_id is not None:
                await self.confirm_price(u,ext,quote_id,request_id);return
            if route=='amcancel':
                if not await self.pricing.cancel(u,quote_id):
                    raise Rejected('Оценка уже закрыта.')
                await self.catalogue_screen(ext,'Оценка отменена.',buttons([[('← Агрегаторы','providers')]]));return
            raise Rejected('Кнопка устарела. Откройте меню.')
        if route in ANYMODEL_ROUTES:
            await self.anymodel_callback(u,ext,data,request_id=request_id);return
        if data=='store':
            await self.svc.conversation(u,'home')
            if self.has_admin_session(ext):
                await self.show_store(ext)
            else:
                await self.show_providers(ext)
            return
        if route=='veo':
            await self.show_veo(ext,data.split(':')[1]);return
        if route=='veoprompt':
            _,version,mode=data.split(':')
            selected=await self.veo_mode(ext,version,mode)
            await self.svc.aggregate_context(u,{'video_mode':mode,'version':version})
            await self.catalogue_screen(ext,f'Veo 3.1 · {selected[1]}\nОпишите, какое видео хотите создать.',
                                        buttons([[('Отмена','home')]]));return
        if route=='veoconfirm':
            raise Rejected('Оценка устарела. Откройте карточку модели заново.')
        if route=='mwork':
            _,version,section,index,page=data.split(':')
            snapshot=self.catalogue_snapshot(version)
            index=int(index)
            if section=='dev':
                allowed=self.has_admin_session(ext) and 0<=index<len(snapshot['models'])
            else:
                allowed=index in await self.store_models(snapshot,section,ext)
            if not allowed:
                raise Rejected('Модель больше не доступна в этом разделе.')
            model_id=snapshot['models'][index]['id']
            if model_id.replace('-','_')==self.cfg.clodex_model.replace('-','_'):
                model_id=self.cfg.clodex_model
            await self.history(u,ext,min(10000,max(0,int(page))),
                               model=(model_id,f'mwork:{version}:{section}:{index}'));return
        if route=='slist':
            _,version,section,page=data.split(':')
            await self.show_store_models(ext,version,section,int(page));return
        if route in ('smodel','srun'):
            _,version,section,page,index,*options=data.split(':')
            if options and (route!='srun' or options!=['high']):
                raise Rejected('Этот режим недоступен.')
            snapshot=self.catalogue_snapshot(version)
            index=int(index)
            if index not in await self.store_models(snapshot,section,ext):
                raise Rejected('Модель больше не доступна в этом разделе.')
            if route=='srun' and section=='video':
                if options:
                    raise Rejected('Этот режим недоступен.')
                model=snapshot['models'][index]
                await self.svc.aggregate_context(u,{'clodex_video_model':model['id'],'version':version})
                await self.catalogue_screen(ext,f"{model['title']}\nОпишите, какое видео хотите создать.",
                                            buttons([[('Отмена','home')]]));return
            if route=='srun':
                await self.begin_interaction(u,ext,version,index,STORE_SECTIONS[section][1],
                                             request_id=request_id,quality=options[0] if options else None);return
            await self.show_store_model(ext,snapshot,section,int(page),index);return
        if data=='accept':
            await self.svc.accept(u);await self.show_home(ext);return
        if data in ('section:1','section:2','section:3'):
            await self.svc.conversation(u,'home')
            await self.menu_section(u,ext,int(data[-1]));return
        if data=='home':await self.svc.conversation(u,'home');await self.show_home(ext);return
        if data=='providers':
            await self.svc.conversation(u,'home');await self.show_providers(ext);return
        if data.startswith('provider:'):
            _,version,index=data.split(':');await self.provider_detail(u,ext,version,int(index));return
        if data.startswith('pf:'):
            _,version,index,page=data.split(':');await self.show_functions(ext,version,int(page),int(index));return
        if data=='buy':
            p=await self.svc.order(u)
            await self.bot.send_invoice(ext,title='Пакет кредитов',description='10 000 кредитов DarkFlow | Gen',payload=str(p),currency='XTR',prices=[LabeledPrice(label='10 000 кредитов',amount=100)],provider_token='',start_parameter='credits');return
        if data=='voice-demo':
            if self.cfg.mode!='mock':raise Rejected('Тестовая операция недоступна.')
            await self.svc.conversation(u,'text');await self.say(ext,'Отправьте текст для тестового аудиосценария.');return
        if data.startswith('funcs:'):
            _,version,page=data.split(':');await self.show_functions(ext,version,int(page));return
        if data.startswith('fn:'):
            _,version,index=data.split(':');await self.function_detail(ext,version,int(index));return
        if data.startswith('choosefn:'):
            _,version,index,page=data.split(':');await self.choose_function_model(ext,version,int(index),int(page));return
        if data.startswith('speak:'):
            _,version,index=data.split(':')
            await self.begin_interaction(u,ext,version,int(index),'audio.speech',request_id=request_id);return
        if data.startswith('runmodel:'):
            _,version,index,operation=data.split(':')
            await self.begin_interaction(u,ext,version,int(index),operation,request_id=request_id);return
        if data.startswith('bind:'):
            _,version,fi,mi=data.split(':');await self.begin_aggregate(u,ext,version,int(fi),int(mi));return
        if data.startswith('cat:'):
            _,version,group,page=data.split(':')
            await self.show_models(ext,version=version,group=group,page=int(page));return
        if data.startswith('mdl:'):
            _,version,index,*origin=data.split(':')
            await self.model_detail(ext,version,int(index),origin);return
        kind,_,arg=data.partition(':')
        if kind=='confirm':
            if self.cfg.speech_pilot and self.cfg.mode=='clodex':
                raise Rejected('Оценка устарела. Откройте карточку модели заново.')
            try:
                job=await self.svc.confirm(u,arg)
            except Rejected:
                trace_interaction(request_id,'reservation_failed',operation='audio.speech',
                                  model=self.cfg.clodex_model or 'demo')
                raise
            trace_interaction(str(job),'queued',operation='audio.speech',model=self.cfg.clodex_model or 'demo')
            await self.svc.conversation(u,'home')
            if job not in self.pending_speech:
                model=self.cfg.clodex_model or 'Демо-озвучка'
                message=await self.progress.start(ext,model,'audio.speech')
                self.pending_speech[job]=(ext,u,model,message,'queued')
            return
        if kind=='chatwork':
            await self.send_chat_answer(ext,await self.svc.chat_work(u,arg));return
        if kind=='video':
            await self.open_work(u,ext,'video',arg);return
        if kind in ('get','image','mget','mimage'):
            await self.open_work(u,ext,'image' if kind.endswith('image') else 'audio',arg,
                                 show_prompt=kind.startswith('m'));return
        if kind=='prompt':
            work_kind,job=arg.split(':')
            if work_kind not in ('image','audio'):raise Rejected('Работа недоступна.')
            await self.open_work(u,ext,work_kind,job,prompt_only=True);return
        if kind=='cancel':await self.svc.cancel(u,arg);await self.say(ext,'Работа отменена, резерв возвращён.');return
        if kind=='history':await self.history(u,ext,min(10000,max(0,int(arg))));return
        state=await self.svc.conversation(u)
        if kind=='voices':
            if state['step'] not in ('voice','settings'):raise Rejected('Кнопка устарела. Начните новую озвучку.')
            await self.voices(ext,min(10000,max(0,int(arg))));return
        if kind in ('voice','preview'):
            if state['step'] not in ('voice','settings'):raise Rejected('Кнопка устарела. Начните новую озвучку.')
            voices=catalog(self.cfg)
            if self.cfg.speech_pilot:
                version,_,arg=arg.partition(':')
                if kind!='voice' or version!=self.voice_version(voices):
                    raise Rejected('Список голосов обновился. Откройте выбор голоса заново.')
            try:
                index=int(arg)
                if index<0:raise IndexError()
                v=voices[index]
            except (ValueError,IndexError):raise Rejected('Голос недоступен.') from None
            if kind=='preview':
                preview=Path(v.get('preview',''))
                if not preview.is_file():raise Rejected('Образец пока недоступен.')
                await self.bot.send_audio(ext,FSInputFile(preview),caption='Образец голоса');return
            if self.cfg.speech_pilot and state['text_content'] is None:
                await self.svc.conversation(u,'text',voice=v['id'])
                await self.catalogue_screen(ext,f"Голос: {v['name']}. Отправьте текст до 3000 символов.",buttons([[("Главное меню","home")]]))
                return
            await self.svc.conversation(u,'settings',state['text_content'],v['id'])
            if self.cfg.mode=='mock':
                await self.catalogue_screen(ext,'Скорость:',buttons([[('0.9×','speed:0.9'),('1×','speed:1.0'),('1.1×','speed:1.1')],[('Назад к голосам','voices:0')]]));return
            await self.make_quote(u,ext,state['text_content'],v['id'],1.0);return
        if kind=='speed' and state['step']=='settings':
            await self.make_quote(u,ext,state['text_content'],state['voice'],float(arg));return
        raise Rejected('Кнопка устарела. Откройте меню.')

    def catalogue_snapshot(self,version=None):
        from .discovery import SnapshotStore
        data=SnapshotStore(self.cfg.catalogue_path).read()
        if not data:raise Rejected('Каталог ещё не загружен. Дождитесь обновления и откройте меню снова.')
        if version and version!=data['version']:raise Rejected('Каталог обновился. Откройте раздел заново.')
        return data

    async def show_home(self,ext,*,replace_welcome=False):
        previous=await self.svc.welcome_message(ext)
        if previous is None or replace_welcome:
            markup=await self.reply_menu(ext)
            try:
                photo=BufferedInputFile(await asyncio.to_thread(WELCOME_BANNER.read_bytes),filename='welcome.png')
                message=await self.bot.send_photo(ext,photo,caption=WELCOME_TEXT,reply_markup=markup)
            except (OSError,ClientDecodeError,TelegramAPIError):
                try:
                    message=await self.bot.send_message(ext,WELCOME_TEXT,reply_markup=markup)
                except (ClientDecodeError,TelegramAPIError):
                    if previous is None:
                        raise
                    return
            await self.svc.save_welcome_message(ext,message.message_id)
            self.remember_balance_keyboard(ext,markup)
            keyboard_message=self.aggregator_keyboard_messages.pop(ext,None)
            if keyboard_message is not None:
                await self.remove_menu_message(ext,keyboard_message)
            if previous is not None and previous!=message.message_id:
                await self.remove_menu_message(ext,previous)
        else:
            await self.refresh_balance_keyboards(ext)

        await self.close_work_preview(ext)
        temporary=self.catalogue_messages.pop(ext,None)
        self.catalogue_animations.discard(ext)
        if temporary is not None and temporary!=previous:
            await self.remove_menu_message(ext,temporary)

    def provider_title(self,ext,key):
        titles={'clodex':'Clodex' if self.pool is None else 'CLODEX','anymodel':'AnyModel',**self.providers.interactive}
        if self.has_admin_session(ext):
            return titles.get(key,key)
        number=list(titles).index(key)+1 if key in titles else None
        return f'Агрегатор {number}' if number else 'Агрегатор'

    async def show_providers(self,ext,*,after_message_id=None):
        admin=self.has_admin_session(ext)
        text=self.cfg.brand+'\nВыберите агрегатор.'
        if admin:
            text+=' Здесь показаны подключённые сервисы; модели и функции внутри каждого обновляются через его API.'
        try:
            data=self.catalogue_snapshot()
            rows=[[(self.provider_title(ext,s['provider']),f"provider:{data['version']}:{i}")]
                  for i,s in enumerate(data.get('sources',[]))]
        except Rejected as error:
            if admin:
                text=str(error)
            rows=[[('↻ Обновить экран','providers')]]
        if anymodel_available(self.cfg):
            rows.append([(self.provider_title(ext,'anymodel'),'am')])
        if self.cfg.access_mode=='private':
            rows.extend([(self.provider_title(ext,key),f'pentry:{key}:0')] for key in self.providers.interactive)
            if admin:
                rows.append([('Тарифы моделей','tariffs')])
        rows.append([(label,f'section:{index}') for index,label in enumerate(MENU[1:],1)])
        rows.append([('Главное меню','home')])
        await self.catalogue_screen(ext,text,buttons(rows),after_message_id=after_message_id,
                                    animation=AGGREGATORS_ANIMATION)

    async def registered_callback(self,u,ext,route,parts):
        key=parts[0]
        if key not in self.providers.interactive:
            raise Rejected('Агрегатор недоступен.')
        if route=='pentry':
            await self.aggregator_callback(u,ext,'agroot',[key])
            return
        full=route in ('pall','pview')
        if full:
            await self.tariffs.authorize(u,ext)
        snapshot=await self.providers.collect(key)
        admitted={(row['model_id'],row['operation']) for row in await self.models.list(key)}
        selected=parts[2] if route=='pcat' and len(parts)>2 else parts[3] if len(parts)>3 else None
        models=[row for row in snapshot['models'] if full or self.registered_operations(row,admitted,selected)]
        page=max(0,min(int(parts[1]),max(0,(len(models)-1)//10)))
        prefix='pall' if full else 'pcat'
        suffix=f':{selected}' if selected else ''
        if route in ('pcat','pall'):
            card='pview' if full else 'pcard'
            rows=[[(m['title'],f"{card}:{key}:{page}:{voice_key(m['id'])[:20]}{suffix}")]
                  for m in models[page*10:(page+1)*10]]
            nav=[]
            if page:nav.append(('← Назад',f'{prefix}:{key}:{page-1}{suffix}'))
            if (page+1)*10<len(models):nav.append(('Далее →',f'{prefix}:{key}:{page+1}{suffix}'))
            if nav:rows.append(nav)
            parent=f'agmanage:{key}' if full else f'agroot:{key}'
            await self.catalogue_screen(ext,self.provider_title(ext,key),buttons(rows+[[('← К агрегатору',parent)]]))
            return
        model=next((row for row in models if voice_key(row['id'])[:20]==parts[2]),None)
        if model is None:
            raise Rejected('Модель недоступна.')
        operations=self.registered_operations(model,admitted,selected)
        back=[(MODEL_LIST_BACK,f'{prefix}:{key}:{page}{suffix}')]
        if full:
            await self.render_model_detail(ext,model,f'pall:{key}:{page}',[]);return
        if route=='pcard':
            from .discovery import OPERATIONS
            rows=[[(f'Рассчитать стоимость · {OPERATIONS[op][0]}',f"prun:{key}:{page}:{parts[2]}:{op}")]
                  for op in operations]
            text=model['title']
            if self.has_admin_session(ext):
                text+=f"\nID: {model['id']}"
            await self.catalogue_screen(ext,text,buttons(rows+[back]))
            return
        operation=parts[3]
        if operation not in operations:
            raise Rejected('Операция недоступна.')
        params=model.get('defaults',{}).get(operation,{})
        await self.svc.aggregate_context(u,{'provider':key,'model_id':model['id'],'title':model['title'],
                                            'interaction':operation,'params':params})
        await self.catalogue_screen(ext,f"{model['title']}\nОтправьте промпт для расчёта.",buttons([back]))

    @staticmethod
    def registered_operations(model,admitted,selected=None):
        return [op for op in model['operations'] if model.get('availability')=='key_available'
                and op in WAITING and (model['id'],op) in admitted and (selected is None or selected==op)]

    def anymodel_snapshot(self,ext,version=None):
        if not anymodel_available(self.cfg):
            raise Rejected('AnyModel: раздел недоступен.')
        data=model_store(self.cfg).read()
        if not data:
            raise Rejected('AnyModel: каталог пока недоступен.')
        if version is not None and data['version']!=version:
            raise Rejected('AnyModel: каталог обновился. Откройте раздел заново.')
        return data

    def anymodel_status(self,data):
        if data['sources'][0]['scope']=='public_only':
            lines=['Публичный каталог. Доступ по ключу не подтверждён.']
            label='Обновление публичного снимка'
        else:
            lines=['Каталог по тестовому ключу.']
            label='Последнее успешное обновление'
        if data['fresh_until']<=time.time():
            lines.append('Каталог устарел')
        if data.get('refresh_error'):
            lines.append('Обновление по ключу: '+data['refresh_error'])
        updated=datetime.fromtimestamp(data['fetched_at'],timezone.utc).strftime('%d.%m.%Y %H:%M UTC')
        return '\n'.join([f'{label}: {updated}',*lines])

    async def anymodel_callback(self,u,ext,value,*,request_id=None):
        if not anymodel_available(self.cfg):
            raise Rejected('AnyModel: раздел недоступен.')
        route,*parts=value.split(':')
        if route in SPEECH_ROUTES and route!='amsconfirm':
            await self.anymodel_speech_callback(u,ext,route,value.partition(':')[2],request_id);return
        if route=='am':
            await self.aggregator_callback(u,ext,'agroot',['anymodel']);return
        if route=='amsection':
            await self.anymodel_section(ext,parts[0]);return
        if route=='amvideo':
            await self.anymodel_video_card(u,ext,start=parts==['run']);return
        if route in ('amvconfirm','amsconfirm'):
            raise Rejected('Оценка устарела. Откройте карточку модели заново.')
        if route=='amparams':
            await self.anymodel_params(u,ext,parts);return
        if route=='amimage':
            data=self.anymodel_snapshot(ext)
            model=next((m for m in data['models'] if m['id']==FIBO_MODEL),None)
            if not model:raise Rejected('AnyModel: FIBO 2 недоступна в каталоге.')
            allowed=await self.models.allowed('anymodel',FIBO_MODEL,IMAGE_OP)
            if parts==['run']:
                if not allowed or not can_image(model,data):
                    raise Rejected('AnyModel: тестовый запуск FIBO 2 недоступен.')
                await self.svc.aggregate_context(u,{'interaction':IMAGE_OP,'provider':'anymodel','model_id':FIBO_MODEL,'title':model['title']})
                await self.catalogue_screen(ext,'FIBO 2 · '+self.provider_title(ext,'anymodel')+'\nПришлите описание изображения.',
                                            buttons([[('Параметры','amparams')],[('← FIBO 2','amimage:detail')]]));return
            actions=[('🖼 Генерировать изображение','amimage:run')] if allowed and can_image(model,data) else []
            await self.render_model_detail(ext,model,'amsection:image',actions,provider='AnyModel');return
        version=None if parts[0]=='current' else parts[0]
        data=self.anymodel_snapshot(ext,version)
        version=data['version']
        if route=='amcat':
            await self.catalogue_page(ext,data,data['models'],'AnyModel',int(parts[1]),
                                      f'amcat:{version}',f'ammdl:{version}','agmanage:anymodel',self.anymodel_status(data));return
        index,page=map(int,parts[1:3])
        if not 0<=index<len(data['models']):raise Rejected('AnyModel: модель недоступна.')
        model=data['models'][index]
        back=f'amcat:{version}:{page}'
        if route=='ammdl':
            await self.render_model_detail(ext,model,back,[],provider='AnyModel');return
        operation=parts[3] if len(parts)>3 else next((op for op in ('chat',IMAGE_OP,'video','audio.speech')
                                                       if op in model['operations']),None)
        if (operation not in model['operations'] or model['availability']!='key_available'
                or data['fresh_until']<=time.time() or not await self.models.allowed('anymodel',model['id'],operation)):
            raise Rejected('AnyModel: модель не допущена к этой операции.')
        section=next((section for section,(_,op) in STORE_SECTIONS.items() if op==operation),None)
        if section is None:
            raise Rejected('Операция недоступна.')
        work_back=f'amsection:{section}'
        if route=='amwork':
            action=f'amworkrun:{version}:{index}:{page}:{operation}'
            await self.render_model_detail(ext,model,work_back,[('Рассчитать стоимость',action)],provider='AnyModel');return
        await self.svc.aggregate_context(u,{'interaction':operation,'provider':'anymodel',
                                             'model_id':model['id'],'title':model['title'],'history':[]})
        rows=[[(MODEL_LIST_BACK,work_back)]]
        if operation!='audio.speech':rows.insert(0,[('Параметры','amparams')])
        await self.catalogue_screen(ext,f"{model['title']} · {self.provider_title(ext,'anymodel')}\nОтправьте текст для расчёта стоимости.",buttons(rows))

    async def anymodel_section(self,ext,section):
        if section not in ANYMODEL_SECTIONS:raise Rejected('AnyModel: раздел недоступен.')
        approved=await self.models.list('anymodel')
        try:
            data=self.anymodel_snapshot(ext)
        except Rejected:
            data=None
        rows=self.anymodel_work_rows(section,data,approved,available_only=not self.has_admin_session(ext))
        title=f"{self.provider_title(ext,'anymodel')} · {ANYMODEL_SECTIONS[section]}"
        if not rows:title+='\nВ этом разделе пока нет подключённых операций.'
        rows.append([('← К агрегатору','am')])
        await self.catalogue_screen(ext,title,buttons(rows))

    @staticmethod
    def anymodel_work_rows(section,data,approvals,*,available_only=False):
        rows=[]
        operation=STORE_SECTIONS.get(section,('',section))[1]
        approved={item['model_id'] for item in approvals if item['operation']==operation}
        available={model['id'] for model in (data or {}).get('models',[])
                   if model['availability']=='key_available' and operation in model['operations']}
        if section=='video' and ANYMODEL_VIDEO_MODEL in approved and (not available_only or ANYMODEL_VIDEO_MODEL in available):
            rows.append([(ANYMODEL_VIDEO_TITLE,'amvideo:detail')])
        if section=='speech':
            if FISH in approved and (not available_only or FISH in available):
                rows.append([(FISH_TITLE,'amspeech:fish')])
            if any(model.startswith('anyvoice/') for model in approved):
                rows.append([('AnyVoice','amspeech:anyvoice')])
        if data:
            if section=='image' and FIBO_MODEL in approved and FIBO_MODEL in available:
                rows.append([('FIBO 2','amimage:detail')])
            for index,model in enumerate(data['models']):
                if (model['id'] in approved and operation in model['operations'] and model['availability']=='key_available'
                        and model['id'] not in (FIBO_MODEL,ANYMODEL_VIDEO_MODEL,FISH)):
                    rows.append([(model['title'],f"amwork:{data['version']}:{index}:{index//10}:{operation}")])
        return rows

    async def anymodel_speech_callback(self,u,ext,route,arg,request_id):
        pilot=self.anymodel_speech
        back=[(MODEL_LIST_BACK,'amsection:speech')]
        try:
            if route in ('amvoices','amvprices','amvpick','amvready'):
                await self.anyvoice_picker(u,ext,route,arg)
                return
            if route=='amspeech' and arg=='anyvoice':
                await self.svc.conversation(u,'home')
                rows=[[('Выбрать голос','amvoices:0')]]
                if self.has_admin_session(ext):
                    rows.append([('Назначить тариф голосам','amvprices:0')])
                await self.catalogue_screen(ext,f"AnyVoice · {self.provider_title(ext,'anymodel')}\nВыберите голос для ИИ-озвучки.",
                                            buttons(rows+[back]))
                return
            if route!='amvoice' and arg!='fish':
                raise Rejected('AnyModel: карточка недоступна.')
            if route=='amvoice':
                page,_,key=arg.partition(':')
                if not page.isdecimal() or not key:
                    key,page=arg,'0'
                back=[(MODEL_LIST_BACK,f'amvoices:{page}')]
                voices=await pilot.voices()
                model=self.anyvoice_id(voices,key)
                title=pilot.voice_title(voices[model])
            else:
                model=FISH
                title=await pilot.title(model)
        except AnyModelError as error:
            trace_interaction(request_id,'anymodel_speech_metadata_failed',reason=error.code)
            await self.svc.conversation(u,'home')
            await self.catalogue_screen(ext,'Не удалось проверить каталог или тариф. Запуск закрыт.',
                                        buttons([back]))
            return
        if not await self.models.allowed('anymodel',model,'audio.speech'):
            raise Rejected('AnyModel: голос или модель не допущены к озвучке.')
        await self.svc.aggregate_context(u,{'provider':'anymodel','interaction':'audio.speech',
                                            'model_id':model,'title':title})
        text=f"{title} · {self.provider_title(ext,'anymodel')}"
        if self.has_admin_session(ext):
            text+=f'\nID: {model}'
        text+='\nПришлите текст для расчёта стоимости.'
        await self.catalogue_screen(ext,text,buttons([back]))

    @staticmethod
    def anyvoice_id(voices,key):
        matches=[model for model in voices if key in (model,voice_key(model))]
        if len(matches)!=1:
            raise Rejected('AnyVoice: голос отсутствует в актуальном каталоге.')
        return matches[0]

    async def anyvoice_picker(self,u,ext,route,arg):
        voices=await self.anymodel_speech.voices()
        batch=route!='amvoices'
        context={}
        selection=set()
        page=0
        if not batch:
            allowed={row['model_id'] for row in await self.models.list('anymodel','audio.speech')}
            voices={key:voice for key,voice in voices.items() if key in allowed}
            await self.svc.conversation(u,'home')
        else:
            context=await self.svc.aggregate_context(u) or {}
            selection=set(context.get('anyvoice_tariff_selection',[]))
        if route=='amvpick':
            page_arg,key=arg.split(':',1)
            page=int(page_arg)
            if 'anyvoice_tariff_selection' not in context:
                raise Rejected('AnyVoice: откройте выбор голосов для тарифа заново.')
            selection.symmetric_difference_update([self.anyvoice_id(voices,key)])
        elif route=='amvready':
            if not selection or not selection.issubset(voices):
                raise Rejected('AnyVoice: проверьте выбор по актуальному каталогу.')
            code=uuid4().hex[:12]
            await self.svc.aggregate_context(u,{'anyvoice_tariff_selection':sorted(selection),'tariff_code':code})
            selected='\n'.join(sorted(selection))
            if len(selected)>2800:
                selected=selected[:2800]+'…'
            await self.catalogue_screen(ext,f'Выбрано голосов: {len(selection)}\n{selected}\n\n'
                f'/voice_tariff {code} utf16 darkflow_token СТАВКА [СРОК] studio:ИСТОЧНИК\n'
                f'/voice_tariff {code} test utf16 darkflow_token СТАВКА СРОК ИСТОЧНИК\n'
                'Подтверждение поддержки можно указать как support:ИСТОЧНИК. Срок в ISO 8601 с часовым поясом.' ,
                buttons([[('← Изменить выбор','amvprices:0')],[('← AnyVoice','amspeech:anyvoice')]]))
            return
        else:
            page=int(arg)
        if batch:
            selection.intersection_update(voices)
            await self.svc.aggregate_context(u,{'anyvoice_tariff_selection':sorted(selection)})
        entries=list(voices.items())
        page=min(max(page,0),max(0,(len(entries)-1)//10))
        rows=[]
        for model,voice in entries[page*10:(page+1)*10]:
            name=voice['name'][:80]+(' · ИИ-имитация' if voice.get('imitation') is True else '')
            if voice.get('lang')=='en':
                name+=' · EN'
            if batch and model in selection:
                name='✓ '+name
            key=voice_key(model)
            rows.append([(name,f'amvpick:{page}:{key}' if batch else f'amvoice:{page}:{key}')])
        nav=[]
        prefix='amvprices' if batch else 'amvoices'
        if page>0:
            nav.append(('← Назад',f'{prefix}:{page-1}'))
        if (page+1)*10<len(entries):
            nav.append(('Далее →',f'{prefix}:{page+1}'))
        if nav:
            rows.append(nav)
        if batch and selection:
            rows.append([(f'Продолжить · {len(selection)}','amvready')])
        rows.append([('↻ Обновить каталог',f'{prefix}:{page}')])
        rows.append([('← AnyVoice','amspeech:anyvoice')])
        text=f'AnyVoice · Голоса ({len(entries)})' if self.has_admin_session(ext) else 'AnyVoice · Выберите голос'
        if batch:
            text+=f'\nВыберите голоса для одной ставки. Выбрано: {len(selection)}.'
        await self.catalogue_screen(ext,text,buttons(rows))

    async def anyvoice_save_tariff(self,u,ext,args):
        await self.tariffs.authorize(u,ext)
        if not anymodel_available(self.cfg):
            raise Rejected('Действие доступно только администратору.')
        context=await self.svc.aggregate_context(u) or {}
        ids=context.get('anyvoice_tariff_selection',[])
        if not ids or not args or args[0]!=context.get('tariff_code'):
            raise Rejected('AnyVoice: сначала выберите голоса и нажмите «Продолжить».')
        voices=await self.anymodel_speech.voices()
        if not set(ids).issubset(voices):
            raise Rejected('AnyVoice: список изменился. Проверьте выбор голосов.')
        spec=args[1:]
        if spec in (['remove'],['disable']):
            fields={}
        else:
            temporary=bool(spec and spec[0]=='test')
            if temporary:
                spec=spec[1:]
            if not spec or spec[0] not in ('request','utf16'):
                raise Rejected('Для AnyVoice выберите request или utf16.')
            fields=tariff_fields(spec,temporary=temporary)
        if fields:
            await self.tariffs.preview(u,ext,'anymodel',ids,'audio.speech',{},fields)
            return
        await self.pricing.set_tariffs(u,ext,'anymodel',ids,'audio.speech',{})
        await self.svc.conversation(u,'home')
        await self.say(ext,f'Тарифы обновлены. Голосов: {len(ids)}.')

    async def anymodel_video_card(self,u,ext,*,start):
        if not await self.models.allowed('anymodel',ANYMODEL_VIDEO_MODEL,'video'):
            raise Rejected('AnyModel: модель не допущена к видео.')
        rows=[[(MODEL_LIST_BACK,'amsection:video')]]
        text=f"{ANYMODEL_VIDEO_TITLE} · {self.provider_title(ext,'anymodel')}\n4 с · 480p · 16:9"
        if start:
            await self.svc.aggregate_context(u,{'provider':'anymodel','interaction':'video',
                'model_id':ANYMODEL_VIDEO_MODEL,'title':ANYMODEL_VIDEO_TITLE})
            text+='\nПришлите описание ролика для расчёта стоимости.'
            rows.insert(0,[('Параметры','amparams')])
        else:
            rows.insert(0,[('🎬 Генерировать видео','amvideo:run')])
        await self.catalogue_screen(ext,text,buttons(rows))

    async def price_admin(self,u,ext,command,args):
        if not self.has_admin_session(ext):
            raise Rejected('Действие доступно только администратору.')
        if command in ('/tariff_set','/tariff_scope'):
            await self.tariffs.command(u,ext,command,args)
            return
        if command=='/voice_tariff':
            try:
                await self.anyvoice_save_tariff(u,ext,args)
            except AnyModelError:
                raise Rejected('AnyVoice: не удалось сверить каталог. Тарифы не изменены.') from None
            return
        if command=='/price_report' and not args:
            row=await self.pricing.report(u,ext)
            def amount(value):
                return 'нет данных' if value is None else f'{value.normalize():f}'
            await self.say(ext,f'Отчёт · {BOT_UNIT}\nПринято задач: {row["jobs"]}'
                f'\nСверено списаний: {row["reconciled"]}\nПодтверждено расходов: {row["cost_count"]}'
                f'\nВыручка за вычетом возвратов: {amount(row["revenue"])}'
                f'\nПодтверждённый расход: {amount(row["actual_cost"])}'
                f'\nВаловая маржа по полностью сверенным задачам: {amount(row["actual_margin"])}'
                f'\nРасчётная маржа по задачам без подтверждённого расхода: {amount(row["estimated_margin"])}')
            return
        if command=='/markup' and len(args) in (3,4):
            provider,model,kind=args[:3]
            if provider=='*' and model!='*':
                raise Rejected('У правила модели должен быть указан агрегатор.')
            await self.pricing.set_rule(u,ext,'' if provider=='*' else provider,'' if model=='*' else model,
                                        kind,args[3] if len(args)==4 else None)
        elif command=='/tariff' and len(args)>=5:
            provider,model,operation,raw=args[:4]
            params=tariff_params(raw)
            spec=args[4:]
            if spec in (['remove'],['disable']):
                fields={}
            else:
                temporary=spec[0]=='test'
                fields=tariff_fields(spec[1:] if temporary else spec,temporary=temporary)
            if fields:
                await self.tariffs.preview(u,ext,provider,[model],operation,params,fields)
                return
            await self.pricing.set_tariff(u,ext,provider,model,operation,params)
        elif command=='/price_rate' and len(args)==2:
            await self.pricing.set_rate(u,ext,*args)
        elif command=='/price_rate' and len(args)==4:
            provider,unit,source,target=args
            if provider not in self.pricing.adapters:
                raise Rejected('Агрегатор недоступен.')
            await self.pricing.set_rate(u,ext,unit,target,provider=provider,source_amount=source)
        elif command=='/price_account' and len(args)==5:
            await self.pricing.reconcile(u,ext,uid(args[0]),*args[1:])
        else:
            raise Rejected('Формат: /markup агрегатор|* модель|* percent|fixed сумма или remove; '
                           '/price_rate единица курс; /price_account оценка списано возвращено расход|- ссылка; '
                           '/price_report; /tariff агрегатор модель операция JSON [test] основание единица ставка [срок] источник или disable. Основания: request, utf16, image, second, started_minute, token (вход:выход)')
        await self.say(ext,'Настройки учёта обновлены.')

    async def provider_detail(self,u,ext,version,index):
        data=self.catalogue_snapshot(version);sources=data.get('sources',[])
        if not 0<=index<len(sources):raise Rejected('Агрегатор недоступен.')
        provider=sources[index]['provider']
        if self.pool is not None:
            await self.aggregator_callback(u,ext,'agroot',[provider],snapshot=data)
            return
        await self.svc.conversation(u,'home')
        if not self.has_admin_session(ext):
            await self.catalogue_screen(ext,self.provider_title(ext,provider)+'\nВыберите, что хотите сделать.',
                                        buttons([[('← Агрегаторы','providers')]]))
            return
        full=f'cat:{version}:{index}:0'
        rows=(store_rows()+[[('Наши модели','ours:clodex:0')],[('Курс и калькулятор','rates:clodex')],[('Все модели',full)]]
              if provider=='clodex' else [[(OPEN_CATALOGUE,full)]])
        rows += [[('🛠 Функции и возможности',f'pf:{version}:{index}:0')],[('← Агрегаторы','providers')]]
        title='Clodex' if provider=='clodex' else provider
        models=sum(m.get('provider')==provider and not is_disabled_model(m) for m in data['models'])
        functions=[f for f in data.get('functions',[]) if f.get('provider')==provider]
        docs=sum(bool(f.get('documentation_only')) for f in functions)
        source=sources[index]
        scope='Публичный каталог. Доступность по ключу ещё не проверена.' if source['scope']=='public_only' else 'Список получен через /v1/models для ключа сервиса.'
        if data['fresh_until']<time.time():scope+=' Данные устарели.'
        if source.get('evidence',{}).get('unavailable_metadata'):scope+=' Часть метаданных временно недоступна.'
        guidance='Откройте модель, чтобы увидеть доступные действия.' if self.cfg.interaction_mode!='off' else 'Генерация через каталог пока выключена.'
        await self.catalogue_screen(ext,f'{title}\nМоделей: {models} · операций API: {len(functions)-docs} · разделов документации: {docs}\n{scope}\n{guidance}',buttons(rows))

    async def aggregator_callback(self,u,ext,route,parts,*,snapshot=None):
        if route!='agroot':
            await self.tariffs.authorize(u,ext)
        key=parts[0]
        title=self.provider_title(ext,key)
        if key=='anymodel':
            if not anymodel_available(self.cfg):raise Rejected('Агрегатор недоступен.')
            try:snapshot=self.anymodel_snapshot(ext)
            except Rejected:snapshot=None
            full='amcat:current:0'
        elif key=='clodex':
            snapshot=snapshot or self.catalogue_snapshot()
            source_index=next((i for i,s in enumerate(snapshot.get('sources',[])) if s['provider']==key),None)
            if source_index is None:raise Rejected('Агрегатор недоступен.')
            full=f"cat:{snapshot['version']}:{source_index}:0"
        elif key in self.providers.interactive:
            snapshot=await self.providers.collect(key)
            full=f'pall:{key}:0'
        else:
            raise Rejected('Агрегатор недоступен.')

        if route=='agfunctions':
            if not snapshot:raise Rejected('Каталог недоступен.')
            await self.show_functions(ext,page=int(parts[1]),snapshot=snapshot,provider=key)
            return
        if route=='agfunction':
            if not snapshot or snapshot['version']!=parts[1]:
                raise Rejected('Каталог обновился. Откройте раздел заново.')
            await self.function_detail(ext,parts[1],int(parts[2]),snapshot=snapshot,provider=key)
            return

        await self.svc.conversation(u,'home')
        if route=='agmanage':
            data=snapshot or {}
            models=sum(m.get('provider')==key for m in data.get('models',[]))
            functions=[f for f in data.get('functions',[]) if f.get('provider')==key]
            docs=sum(bool(f.get('documentation_only')) for f in functions)
            rows=[[('Наши модели',f'ours:{key}:0')],[('Курс и калькулятор',f'rates:{key}')],[('Все модели',full)]]
            if functions:
                target=f"pf:{snapshot['version']}:{source_index}:0" if key=='clodex' else f'agfunctions:{key}:0'
                rows.append([('Функции и возможности',target)])
            rows.append([('← К агрегатору',f'agroot:{key}')])
            text=f'{title} · Управление агрегатором\nМоделей: {models} · операций API: {len(functions)-docs} · разделов документации: {docs}'
            if key=='anymodel' and snapshot:
                text+='\n'+self.anymodel_status(snapshot)
            await self.catalogue_screen(ext,text,buttons(rows))
            return

        work={}
        if key=='clodex':
            for section in STORE_SECTIONS:
                if await self.store_models(snapshot,section,ext):
                    work[section]=f'slist:current:{section}:0'
        elif key=='anymodel':
            admitted=await self.models.list(key)
            work={section:f'amsection:{section}' for section in STORE_SECTIONS
                  if self.anymodel_work_rows(section,snapshot,admitted,available_only=not self.has_admin_session(ext))}
        else:
            admitted={(row['model_id'],row['operation']) for row in await self.models.list(key)}
            available={op for model in snapshot['models'] for op in self.registered_operations(model,admitted)}
            work={section:f'pcat:{key}:0:{op}' for section,(_,op) in STORE_SECTIONS.items() if op in available}
        rows=[[('🎆 Генерировать изображение' if section=='image' else label,work[section])]
              for section,(label,_) in STORE_SECTIONS.items() if section in work]
        rows.append([('📁 Мои работы','history:0')])
        if self.has_admin_session(ext):
            rows.append([('⚙️ Управление агрегатором',f'agmanage:{key}')])
        rows.append([('← Агрегаторы','providers')])
        await self.catalogue_screen(ext,title+'\nВыберите, что хотите сделать.',buttons(rows))

    async def show_store(self,ext):
        rows=store_rows()
        if self.has_admin_session(ext):
            rows.append([('← Агрегаторы','providers')])
        rows.append([('Главное меню','home')])
        await self.catalogue_screen(ext,'Каталог моделей. Выберите, что хотите сделать.',buttons(rows))

    def clodex_video_ids(self,snapshot):
        if not self.video.enabled():
            return set()
        return {model for model in catalogue_video_ids(snapshot) if self.video.api.supports_model(model)}

    async def store_models(self,snapshot,section,ext):
        if section not in STORE_SECTIONS:
            raise Rejected('Раздел недоступен.')
        from .model_policy import canonical
        operation=STORE_SECTIONS[section][1]
        approved={row['model_id'] for row in await self.models.list('clodex',operation,snapshot=snapshot)} if self.pool else set()
        return [index for index,model in enumerate(snapshot['models'])
                if model.get('provider')=='clodex' and model.get('availability')=='key_available'
                and not is_disabled_model(model) and canonical('clodex',model['id'],operation) in approved
                and (self.has_admin_session(ext) or operation=='video' or self.model_can_run(model,operation))]

    async def admitted_veo_modes(self,snapshot):
        if self.pool is None:return {}
        approved={row['model_id'] for row in await self.models.list('clodex','video',snapshot=snapshot)}
        return {key:value for key,value in video_modes(self.cfg,snapshot).items()
                if value[0] in approved}

    async def show_store_models(self,ext,version,section,page):
        snapshot=self.catalogue_snapshot(None if version=='current' else version)
        models=await self.store_models(snapshot,section,ext)
        veo = False
        if section=='video':
            veo=bool(await self.admitted_veo_modes(snapshot))
            models=[i for i in models if snapshot['models'][i]['id'] not in DEFAULT_VIDEO_MODELS]
        page_count=max(1,(len(models)+9)//10)
        if not 0<=page<page_count:
            raise Rejected('Страница недоступна.')
        version=snapshot['version']
        title=STORE_SECTIONS[section][0]
        rows=[[(snapshot['models'][i]['title'],f'smodel:{version}:{section}:{page}:{i}')]
              for i in models[page*10:page*10+10]]
        if veo and page==0:
            rows.insert(0,[('Veo 3.1',f'veo:{version}')])
        nav=[]
        if page:
            nav.append(('← Назад',f'slist:{version}:{section}:{page-1}'))
        if page+1<page_count:
            nav.append(('Далее →',f'slist:{version}:{section}:{page+1}'))
        if nav:
            rows.append(nav)
        if any(
            source['provider']=='clodex' for source in snapshot.get('sources',[])
        ):
            rows.append([('← К агрегатору','agroot:clodex')])
        else:
            rows.append([('← Каталог','store')])
        if not models and not veo:
            title+='\nВ этом разделе пока нет опубликованных моделей.'
        elif self.has_admin_session(ext):
            title+=f'\nМоделей: {len(models)+int(veo)} · Страница {page+1} из {page_count}'
        await self.catalogue_screen(ext,title,buttons(rows))

    async def veo_mode(self,ext,version,mode):
        selected=(await self.admitted_veo_modes(self.catalogue_snapshot(version))).get(mode)
        if selected is None:
            raise Rejected('Этот режим Veo недоступен. Обновите каталог.')
        return selected

    async def show_veo(self,ext,version):
        modes=await self.admitted_veo_modes(self.catalogue_snapshot(version))
        if not modes:raise Rejected('Veo 3.1 недоступна. Обновите каталог.')
        rows=[[(label,f'veoprompt:{version}:{mode}')] for mode,(_,_,label) in modes.items()]
        rows.append([(MODEL_LIST_BACK,f'slist:{version}:video:0')])
        await self.catalogue_screen(ext,'Veo 3.1 · Текст → видео',buttons(rows))

    async def video_prompt(self,u,ext,text,context):
        if 'video_mode' in context:
            model,label,_=await self.veo_mode(ext,context['version'],context['video_mode'])
            title=f'Veo 3.1 · {label}'
        else:
            snapshot=self.catalogue_snapshot(context['version'])
            indexes=await self.store_models(snapshot,'video',ext)
            model=context['clodex_video_model']
            selected=next((snapshot['models'][i] for i in indexes if snapshot['models'][i]['id']==model),None)
            if selected is None:
                raise Rejected('Модель не допущена к видео или недоступна.')
            title=selected['title']
        request=Request('clodex',model,'video',title,text.strip(),VIDEO_PARAMS.copy())
        await self.show_price(ext,await self.pricing.quote(u,request))

    async def show_store_model(self,ext,snapshot,section,page,index):
        model=snapshot['models'][index]
        title,operation=STORE_SECTIONS[section]
        version=snapshot['version']
        rows=[]
        status='Запуск этой модели пока недоступен.'
        if operation=='video' or self.model_can_run(model,operation):
            rows.append([(('Выбрать голос' if operation=='audio.speech' and self.cfg.speech_pilot else title),f'srun:{version}:{section}:{page}:{index}')])
            if operation=='images.generate' and model['id'] in HIGH_QUALITY_IMAGE_MODELS:
                rows.append([('Качество: high',f'srun:{version}:{section}:{page}:{index}:high')])
            status='Выберите действие, чтобы продолжить.'
        if section in ('image','speech'):
            rows.append([('Работы этой модели',f'mwork:{version}:{section}:{index}:0')])
        rows.append([(MODEL_LIST_BACK,f'slist:{version}:{section}:{page}')])
        await self.catalogue_screen(ext,model['title']+'\n'+status,buttons(rows))

    @staticmethod
    def catalogue_groups(data):
        from .discovery import groups
        if data.get('sources'):
            return [{'title':s['provider']+' · '+('публичный каталог' if s['scope']=='public_only' else 'доступно ключу'),
                     'models':[m for m in data['models'] if m.get('provider')==s['provider']]} for s in data['sources']]
        return groups(data)

    async def show_models(self,ext,version=None,group=None,page=0):
        try:data=self.catalogue_snapshot(version)
        except Rejected as e:
            if version:raise
            await self.catalogue_screen(ext,str(e));return
        categories=self.catalogue_groups(data)
        if group is None:
            rows=[[(g['title']+f" ({len(g['models'])})",f"cat:{data['version']}:{i}:0")] for i,g in enumerate(categories)]
            label='Каталог провайдеров и моделей:'
            if data['fresh_until']<time.time():label+='\nДанные устарели; запуск по ним недоступен.'
            await self.catalogue_screen(ext,label,buttons(rows) if rows else None);return
        index=int(group)
        if not 0<=index<len(categories) or not 0<=page<=2000:raise Rejected('Раздел недоступен.')
        version=data['version']
        parent='providers'
        if data.get('sources'):
            parent=(f"agmanage:{data['sources'][index]['provider']}" if self.pool is not None and self.cfg.access_mode=='private'
                    else f'provider:{version}:{index}')
        await self.catalogue_page(ext,data,categories[index]['models'],categories[index]['title'],page,
                                  f'cat:{version}:{index}',f'mdl:{version}',parent,group=index)

    async def catalogue_page(self,ext,data,models,title,page,list_prefix,detail_prefix,parent,status='',group=None):
        if not 0<=page<=2000:raise Rejected('Страница недоступна.')
        page_size=10
        indexes={(m.get('provider'),m['id']):i for i,m in enumerate(data['models'])}
        rows=[]
        for model in models[page*page_size:(page+1)*page_size]:
            index=indexes[(model.get('provider'),model['id'])]
            middle=f':{group}' if group is not None else ''
            rows.append([(model['title'],f'{detail_prefix}:{index}{middle}:{page}')])
        nav=[('← Назад',f'{list_prefix}:{page-1}' if page else parent)]
        if len(models)>(page+1)*page_size:nav.append(('Далее →',f'{list_prefix}:{page+1}'))
        rows.extend([nav,[('← Агрегаторы','providers')]])
        label=f'{title}\nМоделей: {len(models)} · Страница {page+1} из {max(1,(len(models)+page_size-1)//page_size)}'
        await self.catalogue_screen(ext,label+('\n'+status if status else ''),buttons(rows))

    async def model_detail(self,ext,version,index,origin=()):
        data=self.catalogue_snapshot(version)
        if not 0<=index<len(data['models']):raise Rejected('Модель недоступна.')
        model=data['models'][index]
        if len(origin)==2:
            group,page=map(int,origin)
        else:
            location=next(((i,category['models'].index(model)//10)
                           for i,category in enumerate(self.catalogue_groups(data)) if model in category['models']),None)
            if location is None:raise Rejected('Список моделей недоступен.')
            group,page=location
        back=f'cat:{version}:{group}:{page}'
        await self.render_model_detail(ext,model,back,[])

    async def render_model_detail(self,ext,model,back,actions,provider=None):
        rows=[[(label,route)] for label,route in actions]
        rows.append([(MODEL_LIST_BACK,back)])
        if not self.has_admin_session(ext):
            await self.catalogue_screen(ext,model['title'],buttons(rows))
            return
        from .discovery import OPERATIONS
        availability=('Модель возвращена API для ключа сервиса.' if model.get('availability')=='key_available'
                      else 'Доступ по ключу не подтверждён')
        protocols=', '.join(model.get('protocols',[])) or 'не указаны'
        capabilities=', '.join(OPERATIONS[x][0] for x in model['operations']) or 'точные операции для модели не подтверждены'
        title=(provider+' · ' if provider else '')+model['title']
        text=f"{title}\nID: {model['id']}\n{availability}\nПротоколы: {protocols}\nВозможности: {capabilities}"
        if not provider:
            metrics={k:v for k,v in model.get('public_pricing',{}).items() if k!='verified_for_billing'}
            price=json.dumps(metrics,ensure_ascii=False)[:800] if metrics else 'нет данных'
            text+=f'\nПубличные ценовые метрики: {price}\nЭто не цена заказа.'
        if not actions:text+='\nПлатный запуск через каталог выключен для этой модели.'
        await self.catalogue_screen(ext,text,buttons(rows))

    async def show_functions(self,ext,version=None,page=0,provider_index=None,*,snapshot=None,provider=None):
        data=snapshot if snapshot is not None else self.catalogue_snapshot(version)
        if not 0<=page<=1000:raise Rejected('Страница недоступна.')
        functions=list(enumerate(data.get('functions',[])));rows=[]
        detail=f"fn:{data['version']}"
        route=f"funcs:{data['version']}"
        if provider_index is not None:
            sources=data.get('sources',[])
            if not 0<=provider_index<len(sources):raise Rejected('Агрегатор недоступен.')
            provider=sources[provider_index]['provider']
            route=f"pf:{data['version']}:{provider_index}"
        elif provider is not None:
            route=f'agfunctions:{provider}'
            detail=f"agfunction:{provider}:{data['version']}"
        if provider is not None:
            functions=[(i,f) for i,f in functions if f.get('provider')==provider]
        for i,f in functions[page*7:page*7+7]:
            rows.append([(f['title'],f'{detail}:{i}')])
        nav=[]
        if page:nav.append(('Назад',f"{route}:{page-1}"))
        if len(functions)>(page+1)*7:nav.append(('Далее',f"{route}:{page+1}"))
        if nav:rows.append(nav)
        if self.cfg.mode=='mock' and snapshot is None:rows.append([('🧪 Тест отправки аудио','voice-demo')])
        if provider is not None:
            if snapshot is not None or (self.pool is not None and self.cfg.access_mode=='private'):
                rows.append([('← К управлению',f'agmanage:{provider}')])
            else:
                rows.append([('← К агрегатору',f"provider:{data['version']}:{provider_index}")])
        rows.append([('← Агрегаторы','providers')])
        await self.catalogue_screen(ext,'Функции, опубликованные API. Наличие в документации не подтверждает совместимость каждой модели.\nПодготовка запроса бесплатна и не запускает генерацию.',buttons(rows))

    async def function_detail(self,ext,version,index,*,snapshot=None,provider=None):
        data=snapshot if snapshot is not None else self.catalogue_snapshot(version)
        functions=data.get('functions',[])
        if not 0<=index<len(functions):raise Rejected('Функция недоступна.')
        f=functions[index];rows=[]
        if provider is not None and f['provider']!=provider:raise Rejected('Функция недоступна.')
        preview=snapshot is None and f.get('request_preview_supported')
        if preview:rows.append([('Подготовить запрос без отправки',f"choosefn:{version}:{index}:0")])
        pi=next((i for i,s in enumerate(data.get('sources',[])) if s['provider']==f['provider']),None)
        back=f'agfunctions:{provider}:0' if provider else f'pf:{version}:{pi}:0' if pi is not None else f'funcs:{version}:0'
        rows.append([('Все функции',back)])
        await self.catalogue_screen(ext,f['title']+'\nПровайдер: '+f['provider']+('\n'+f.get('summary','')[:1000]+'\nЭто описание из документации, контракт исполнения не подтверждён.' if f.get('documentation_only') else '\nМетод: '+f['method']+' '+f['path'])+
                       ('\nМожно проверить заполнение запроса. Реальный вызов выключен.' if preview else '\nВозможность опубликована. Исполнитель ещё не подключён.'),buttons(rows))

    async def choose_function_model(self,ext,version,index,page=0):
        data=self.catalogue_snapshot(version);functions=data.get('functions',[])
        if not 0<=index<len(functions) or not 0<=page<=2000:raise Rejected('Функция недоступна.')
        fn=functions[index]
        models=[(i,m) for i,m in enumerate(data['models']) if m.get('provider')==fn['provider'] and not is_disabled_model(m)]
        rows=[[(m['title'],f'bind:{version}:{index}:{i}')] for i,m in models[page*5:page*5+5]]
        nav=[]
        if page:nav.append(('Назад',f'choosefn:{version}:{index}:{page-1}'))
        if len(models)>(page+1)*5:nav.append(('Далее',f'choosefn:{version}:{index}:{page+1}'))
        if nav:rows.append(nav)
        rows.append([('Главное меню','home')])
        await self.catalogue_screen(ext,'Выберите модель для проверки формы. Совместимость с операцией ещё нужно подтвердить.',buttons(rows))

    def model_can_run(self,model,operation):
        if is_disabled_model(model):return False
        if operation=='audio.speech':
            # The configured TTS model is an operator-approved binding for this operation.
            return (
                model.get('provider')=='clodex' and model.get('availability')=='key_available'
                and self.cfg.mode=='clodex' and self.cfg.generation_enabled
                and self.cfg.economy_verified and self.cfg.clodex_key
                and model['id'].replace('-','_')==self.cfg.clodex_model.replace('-','_')
                and (self.cfg.speech_pilot or bool(catalog(self.cfg)))
            )
        from .interaction import supports
        mode=self.cfg.interaction_mode
        return mode in ('mock','live') and supports(model,operation,live=mode=='live')

    async def begin_interaction(self,u,ext,version,index,operation,*,request_id=None,quality=None):
        models=self.catalogue_snapshot(version)['models']
        if self.cfg.interaction_mode=='live' and operation!='audio.speech' and (
            self.cfg.access_mode!='private'
        ):
            raise Rejected('Запуск недоступен.')
        model=models[index] if 0<=index<len(models) else None
        if (not model or not self.model_can_run(model,operation)
                or not await self.models.allowed('clodex',model['id'],operation)):
            trace_interaction(request_id,'operation_unavailable',operation=operation,model=model['id'] if model else None)
            raise Rejected('Для этой модели запуск пока недоступен.')
        if quality is not None and (quality!='high' or operation!='images.generate'
                                    or model['id'] not in HIGH_QUALITY_IMAGE_MODELS):
            raise Rejected('Это качество недоступно для выбранной модели.')
        if operation=='audio.speech':
            if self.cfg.speech_pilot:
                await self.load_pilot_voices()
                await self.svc.conversation(u,'voice')
                await self.voices(ext)
                return
            await self.svc.conversation(u,'text')
            await self.catalogue_screen(ext,'Отправьте текст до 3000 символов. Затем выберите голос.',buttons([[('Главное меню','home')]]))
            return
        context={'interaction':operation,'provider':model['provider'],'model_id':model['id'],'history':[]}
        if quality is not None:
            context['quality']=quality
        await self.svc.aggregate_context(u,context)
        mode=''
        if self.has_admin_session(ext):
            mode='Тест без отправки в CLODEX. ' if self.cfg.interaction_mode=='mock' else 'Запрос будет отправлен в CLODEX. '
        if operation=='images.generate':
            title = model['title']
            if quality is not None:
                title += '\nКачество: '+quality
            text = (
                title+'\n\n'
                'Опишите, какую картинку хотите, и отправьте сообщение. '
                'Добавьте детали: что в кадре, стиль и освещение.\n\n'
                'Например: «Кот-космонавт на Луне, Земля на горизонте, стиль мультфильма».\n\n'
                'Картинка появится здесь и сохранится в «Моих работах».'
            )
            if self.cfg.interaction_mode=='mock':
                text += '\n\nСейчас включён тестовый режим. Бот сохранит пример изображения.'
            await self.catalogue_screen(ext,text,buttons(await self.work_rows(ext,'image',model['id'])))
        else:
            await self.say(ext,model['title']+'\n'+mode+'Пришлите текст или UTF-8 файл .txt. Для выхода отправьте /menu.')

    async def interaction_input(self,u,ext,update,context):
        from .interaction import execute,TEXT_LIMIT
        operation=context['interaction']
        provider=context.get('provider','clodex')
        if provider=='anymodel':
            await self.anymodel_input(u,ext,update.message.text,context);return
        if provider!='clodex':raise Rejected('Агрегатор недоступен.')
        snapshot=self.catalogue_snapshot()
        model=next((m for m in snapshot['models'] if m.get('provider')==provider and m['id']==context['model_id']),None)
        if (not model or not self.model_can_run(model,operation)
                or not await self.models.allowed('clodex',model['id'],operation)):
            raise Rejected('Модель больше не доступна. Откройте каталог.')
        mode=self.cfg.interaction_mode
        if mode=='live' and (self.cfg.access_mode!='private' or snapshot['fresh_until']<time.time()):
            raise Rejected('Запуск недоступен. Проверьте доступ и обновите каталог.')
        message=update.message
        prompt=message.text
        if message.document:
            import io
            doc=message.document
            if not (doc.file_name or '').lower().endswith('.txt') or not 0<(doc.file_size or 0)<=24000:
                raise Rejected('Прикрепите UTF-8 файл .txt до 24 КБ.')
            stream=await self.bot.download(doc.file_id,destination=io.BytesIO(),timeout=10)
            try:
                raw=stream.getvalue()
                if len(raw)>24000:
                    raise Rejected('Файл превышает 24 КБ.')
                prompt=raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise Rejected('Файл должен быть в кодировке UTF-8.') from None
        if not prompt or not prompt.strip() or len(prompt)>TEXT_LIMIT or '\x00' in prompt:
            raise Rejected('Пришлите текст от 1 до 6000 символов или файл .txt.')
        request_id=update.update_id
        trace_interaction(request_id,'input_validated',model=model['id'],operation=operation,mode=mode)
        if mode=='live':
            params=default_params('clodex',operation)
            if context.get('quality'):
                params['quality']=context['quality']
            request=Request('clodex',model['id'],operation,model['title'],prompt,params,context['history'])
            await self.show_price(ext,await self.pricing.quote(u,request))
            return
        history=context['history']
        if operation=='images.generate':
            await self.remove_menu_message(ext,message.message_id)
        title=model.get('title') or model['id']
        job=None
        try:
            async with self.progress.track(ext,title,operation):
                result=await execute(operation,model,prompt,history,mode=mode,key=self.cfg.clodex_key,
                                     request_id=request_id,quality=context.get('quality'))
                if not result.text:
                    job=await self.svc.save_image_work(u,request_id,model['id'],prompt,result)
                    trace_interaction(request_id,'image_saved')
        except Rejected:
            trace_interaction(request_id,'generation_failed')
            raise
        if result.text:
            context['history']=[*history,{'role':'user','content':prompt[:2000]},
                                {'role':'assistant','content':result.text[:2000]}][-6:]
            await self.svc.aggregate_context(u,context)
            if len(result.text)>3500:
                await self.bot.send_document(ext,BufferedInputFile(result.text.encode(),filename='answer.txt'))
            else:
                await self.say(ext,result.text)
            trace_interaction(request_id,'result_notified')
        elif job:
            try:
                await self.open_work(u,ext,'image',str(job),show_prompt=True)
            except (Rejected,TelegramBadRequest,TelegramNetworkError) as error:
                trace_interaction(request_id,'result_display_failed',error_type=type(error).__name__)
                return
            trace_interaction(request_id,'result_notified')

    async def anymodel_params(self,u,ext,parts):
        context=await self.svc.aggregate_context(u)
        if not context or context.get('provider')!='anymodel':
            raise Rejected('AnyModel: откройте карточку модели.')
        operation=context['interaction']
        opts=await self.pricing.adapters['anymodel'].options(context['model_id'],operation)
        safe={key:[value for value in values if re.fullmatch(r'[a-zA-Z0-9_.:-]{1,24}',str(value))] for key,values in opts.items()}
        selected=context.get('params',{})
        if parts:
            key,value=parts[0],':'.join(parts[1:])
            matches=[choice for choice in safe.get(key,[]) if str(choice)==value]
            if not matches:
                raise Rejected('AnyModel: параметр недоступен.')
            await self.pricing.invalidate(u,'anymodel',context['model_id'],operation)
            selected=selected|{key:matches[0]}
            await self.svc.aggregate_context(u,context|{'params':selected})
        labels={'duration':'Секунды','aspect_ratio':'Пропорции','resolution':'Разрешение',
                'mode':'Режим','quality':'Качество','size':'Размер','max_tokens':'Лимит ответа'}
        rows=[[(f'{labels[key]} · {value}'+(' ✓' if selected.get(key)==value else ''),
                f'amparams:{key}:{value}')] for key,values in safe.items() for value in values[:10]]
        text='Параметры · '+context['title']+'\nОтправьте текст, чтобы рассчитать стоимость.'
        if not rows:text+='\nДля этой операции используются стандартные параметры.'
        await self.catalogue_screen(ext,text,buttons(rows+[[('← К агрегатору','am')]]))

    async def anymodel_input(self,u,ext,prompt,context):
        if not anymodel_available(self.cfg):
            raise Rejected('AnyModel: раздел недоступен.')
        operation=context['interaction']
        if not await self.models.allowed('anymodel',context['model_id'],operation):
            raise Rejected('AnyModel: модель не допущена к этой операции.')
        parameters=default_params('anymodel',operation)
        req=Request('anymodel',context['model_id'],operation,context.get('title') or context['model_id'],
                    prompt or '',parameters|context.get('params',{}),context.get('history',[]))
        await self.show_price(ext,await self.pricing.quote(u,req))

    async def show_price(self,ext,quote):
        await self.catalogue_screen(ext,quote.card(admin=self.has_admin_session(ext)),buttons([[
            ('Генерировать',f'amconfirm:{quote.id}'),('Отмена',f'amcancel:{quote.id}'),
        ]]))

    def clodex_launch_model(self,ext,req):
        snapshot=self.catalogue_snapshot()
        if snapshot['fresh_until']<=time.time():
            return None
        if req.operation!='audio.speech' and self.cfg.interaction_mode!='live':
            return None
        if req.operation=='video':
            return {'id':req.model} if req.model in self.clodex_video_ids(snapshot) else None
        if req.operation=='audio.speech' and (
            req.model!=self.cfg.clodex_model or not self.cfg.speech_pilot or req.params.get('voice') not in {v['id'] for v in catalog(self.cfg)}
        ):
            return None
        model=next((m for m in snapshot['models'] if m.get('provider')=='clodex' and
                    (m['id']==req.model or req.operation=='audio.speech' and req.model==self.cfg.clodex_model
                     and m['id'].replace('-','_')==req.model.replace('-','_'))),None)
        if req.operation==IMAGE_OP and req.params.get('n')!=1:
            return None
        if model and self.model_can_run(model,req.operation):
            return model
        return None

    async def confirm_price(self,u,ext,quote_id,update_id):
        quote,accepted,result=await self.launch.confirm(u,ext,quote_id,update_id,
            progress=lambda req:self.progress.track(ext,req.title,req.operation),
            background=lambda req,kind,job:self.progress.start(ext,req.title,req.operation,**{kind+'_id':job}))
        if not accepted:
            await self.show_price(ext,quote)
            return
        if result is None:
            return
        req=quote.request
        if result.kind=='audio':
            audio=await self.svc.audio_work(u,result.value)
            await self.bot.send_audio(ext,BufferedInputFile(audio['audio'],filename=audio['filename']),
                                      caption=audio['caption'])
        elif result.kind=='image':
            await self.open_work(u,ext,'image',str(result.value),show_prompt=True)
        else:
            reply=result.value
            context=await self.svc.aggregate_context(u)
            if context and (context.get('provider'),context.get('interaction'),context.get('model_id'),
                            context.get('history',[]))==(req.provider,'chat',req.model,req.history):
                context['history']=[*req.history,{'role':'user','content':req.prompt[:2000]},
                                    {'role':'assistant','content':reply[:2000]}][-6:]
                await self.svc.aggregate_context(u,context)
            await self.send_chat_answer(ext,(result.label+'\n' if result.label and self.has_admin_session(ext) else '')+reply)

    async def send_chat_answer(self,ext,reply):
        if len(reply)>3500:
            await self.bot.send_document(ext,BufferedInputFile(reply.encode(),filename='answer.txt'))
        else:
            await self.say(ext,reply)

    async def begin_aggregate(self,u,ext,version,fi,mi):
        data=self.catalogue_snapshot(version)
        if not 0<=fi<len(data.get('functions',[])) or not 0<=mi<len(data['models']):raise Rejected('Действие устарело.')
        fn=data['functions'][fi];model=data['models'][mi]
        if fn['provider']!=model.get('provider') or is_disabled_model(model) or not fn['request_preview_supported']:raise Rejected('Операция недоступна.')
        context={'version':version,'fi':fi,'mi':mi,'values':{},'field_index':0}
        await self.svc.aggregate_context(u,context)
        labels={'prompt':'Введите запрос','text':'Введите текст для озвучки','voice':'Введите проверенный Voice ID'}
        await self.say(ext,labels.get(fn['fields'][0],'Введите значение')+' (до 2000 символов). Для отмены: /menu.')

    async def aggregate_input(self,u,ext,value,*,request_id=None):
        from .aggregate import prepare_request
        from .discovery import DiscoveryError
        context=await self.svc.aggregate_context(u)
        if not context:raise Rejected('Начните заполнение заново.')
        data=self.catalogue_snapshot(context['version']);fn=data['functions'][context['fi']];model=data['models'][context['mi']]
        if not isinstance(value,str) or not 1<=len(value.strip())<=2000:raise Rejected('Введите от 1 до 2000 символов.')
        field=fn['fields'][context['field_index']];context['values'][field]=value;context['field_index']+=1
        if context['field_index']<len(fn['fields']):
            await self.svc.aggregate_context(u,context)
            await self.say(ext,'Введите '+fn['fields'][context['field_index']]+' (до 2000 символов).');return
        try:request=prepare_request(data,fn['provider'],fn['id'],model['id'],context['values'])
        except DiscoveryError as e:
            trace_interaction(request_id,'preview_failed',model=model['id'],operation=fn['id'])
            raise Rejected('Не удалось подготовить запрос: '+str(e)) from None
        trace_interaction(request_id,'preview_only',model=model['id'],operation=fn['id'],
                          method=request['method'],endpoint=request['path'])
        await self.svc.conversation(u,'home')
        body=json.dumps(request['body'],ensure_ascii=False,indent=2)
        if len(body)>2800:body=body[:2800]+'\n… (предпросмотр сокращён)'
        await self.say(ext,'Подготовлено без отправки в API:\n'+request['method']+' '+request['path']+'\n'+body+
            '\nСовместимость модели: '+('подтверждена метаданными' if request['model_operation_verified'] else 'не подтверждена')+
            '\nЗапрос не отправлен, списаний нет.',menu())

    async def make_quote(self,u,ext,text,voice,speed,*,after_message_id=None):
        if self.cfg.speech_pilot and self.cfg.mode=='clodex':
            if speed!=1.0:
                raise Rejected('CLODEX: тестовая озвучка недоступна.')
            name=next((v['name'] for v in catalog(self.cfg) if v['id']==voice),None)
            if not name or not text or not text.strip() or len(text)>3000 or '\x00' in text:
                raise Rejected('CLODEX: укажите голос и текст до 3000 символов.')
            model=next((m for m in self.catalogue_snapshot()['models'] if m.get('provider')=='clodex'
                        and m['id'].replace('-','_')==self.cfg.clodex_model.replace('-','_')),None)
            if not model or not self.model_can_run(model,'audio.speech'):
                raise Rejected('CLODEX: тестовая озвучка недоступна.')
            request=Request('clodex',self.cfg.clodex_model,'audio.speech',f"{model['title']} · {name}",text,{'voice':voice})
            await self.show_price(ext,await self.pricing.quote(u,request))
            return
        q,price=await self.svc.quote(u,text,voice,speed)
        if after_message_id is not None:
            await self.remove_menu_message(ext,after_message_id)
        name=next(v['name'] for v in catalog(self.cfg) if v['id']==voice)
        await self.svc.conversation(u,'confirm')
        await self.catalogue_screen(ext,f"Голос: {name}\nОбъём: {len(text)} символов\nЦена: {price} {'демо-кредитов' if self.cfg.mode=='mock' else 'кредитов'}\nПредложение действует 10 минут. Сначала резерв; списание после успешной генерации.",buttons([[(f'Создать за {price}',f'confirm:{q}')],[('Главное меню','home')]]),after_message_id=after_message_id)

async def register_commands(bot, admin_ids):
    base = [BotCommand(command='start',description='Запустить бота'),
            BotCommand(command='menu',description='Главное меню'),
            BotCommand(command='cancel',description='Отменить текущее действие')]
    admin = [*base,BotCommand(command='price_report',description='Отчёт по ценам и расходам'),
             BotCommand(command='admin',description='Войти в админку'),
             BotCommand(command='admin_logout',description='Выйти из админки')]
    scopes = [(BotCommandScopeDefault(),base)]
    scopes.extend((BotCommandScopeChat(chat_id=chat_id),admin)
                  for chat_id in dict.fromkeys(admin_ids) if chat_id>0)
    for scope, commands in scopes:
        for attempt in range(2):
            try:
                async with asyncio.timeout(10):
                    registered = await bot.set_my_commands(commands,scope=scope)
            except (ClientDecodeError,TelegramAPIError,TimeoutError) as error:
                if attempt==0 and isinstance(error,(TelegramNetworkError,TimeoutError)):
                    await asyncio.sleep(1)
                    continue
                print(json.dumps({'event':'telegram_commands_failed','scope':scope.type,
                                  'error_type':type(error).__name__}),flush=True)
            else:
                print(json.dumps({'event':'telegram_commands_registered' if registered else 'telegram_commands_failed',
                                  'scope':scope.type}),flush=True)
            break


async def poll(pool,cfg,bot):
    app=TelegramApp(pool,cfg,bot)
    # Session-level lock prevents two polling consumers of the same deployment.
    async with pool.acquire() as lock:
        if not await lock.fetchval('SELECT pg_try_advisory_lock(921183)'):raise RuntimeError('Polling already running')
        if cfg.access_mode=='private':
            await register_commands(bot,cfg.admin_ids)
        await recover_interrupted(pool)
        while True:
            await notify_interrupted(pool,bot)
            async with pool.acquire() as c:
                pending=await c.fetch('SELECT update_id,payload FROM inbox WHERE NOT done ORDER BY update_id LIMIT 100')
            for r in pending:
                try:await app.handle(Update.model_validate_json(r['payload']),from_inbox=True)
                except (ValueError,TypeError,IndexError):
                    # malformed stale callback cannot poison inbox; safe generic response
                    pass
                except Exception:
                    print(json.dumps({'event':'update_failed','update_id':r['update_id']}),flush=True)
                    await asyncio.sleep(2);break
                async with pool.acquire() as c:await c.execute('UPDATE inbox SET done=true WHERE update_id=$1',r['update_id'])
            else:
                async with pool.acquire() as c:offset=await c.fetchval('SELECT offset_id FROM poll_state WHERE id=1')
                await app.refresh_speech_results()
                await app.refresh_balance_keyboards()
                try:updates=await bot.get_updates(offset=offset,timeout=2 if app.pending_speech else 20,allowed_updates=['message','callback_query','pre_checkout_query'])
                except TelegramNetworkError:
                    print(json.dumps({'event':'telegram_network_retry'}),flush=True)
                    await asyncio.sleep(5);continue
                if updates:
                    await app.enqueue_updates(updates)
            async with pool.acquire() as c:await c.execute("INSERT INTO heartbeat VALUES('bot',now()) ON CONFLICT(component) DO UPDATE SET seen_at=now()")

async def reconcile_stars(pool,bot,max_pages=100):
    """Read-only bounded statement comparison. Never invent credits from statement data."""
    checked=0;issues=0;complete=False
    for page in range(max_pages):
        batch=await bot.get_star_transactions(offset=page*100,limit=100)
        for tx in batch.transactions:
            partner=tx.source or tx.receiver
            if not partner or partner.type!='user' or partner.transaction_type!='invoice_payment':continue
            checked+=1
            async with pool.acquire() as c:
                p=await c.fetchrow("SELECT p.*,i.external_id FROM payments p JOIN identities i ON i.user_id=p.user_id AND i.platform='telegram' WHERE p.charge_id=$1",tx.id)
            valid=bool(p and partner.user.id==p['external_id'] and abs(tx.amount)==p['amount'])
            if tx.source:valid=valid and p['status'] in ('succeeded','refunding','refunded') if valid else False
            else:valid=valid and p['status']=='refunded' if valid else False
            if not valid:issues+=1
        if len(batch.transactions)<100:complete=True;break
    if issues:
        async with pool.acquire() as c,c.transaction():
            await c.execute('UPDATE settings SET halted=true WHERE id=1')
            await c.execute("INSERT INTO audit_events(action) VALUES('stars_statement_review')")
    return {'checked':checked,'issues':issues,'complete':complete}


def make_bot(cfg):
    if not cfg.telegram_api_base:return Bot(cfg.token)
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.client.telegram import TelegramAPIServer
    return Bot(cfg.token,session=AiohttpSession(api=TelegramAPIServer.from_base(cfg.telegram_api_base)))
