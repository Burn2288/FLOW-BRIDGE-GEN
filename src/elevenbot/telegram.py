"""Telegram transport. Durable inbox polling; business rules live in core."""
import asyncio,hashlib,json,time
from datetime import datetime,timezone
from pathlib import Path
from aiogram import Bot
from aiogram.types import (Message,Update,InlineKeyboardMarkup,InlineKeyboardButton,ReplyKeyboardMarkup,
                           KeyboardButton,FSInputFile,BufferedInputFile,LabeledPrice)
from .core import Service,Rejected,uid
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from .providers import catalog,refresh_pilot_voices
from .interaction import HIGH_QUALITY_IMAGE_MODELS,is_disabled_model,trace_interaction
import httpx

MENU=['🌐 Агрегаторы','📁 Мои работы','💳 Баланс','❓ Помощь']
DEVELOPER_CALLBACKS={'cat','mdl','pf','funcs','fn','choosefn','bind','voice-demo','runmodel','speak'}
CATALOGUE_CALLBACKS={'provider','cat','mdl','pf','funcs','fn','choosefn','store','slist','smodel','mwork'}
STORE_SECTIONS={
    'video':('🎬 Генерировать видео','video'),
    'image':('🖼 Генерировать изображение','images.generate'),
    'speech':('🎙 Озвучить текст','audio.speech'),
}
OPEN_CATALOGUE='Открыть каталог'
SCREEN_CALLBACKS=CATALOGUE_CALLBACKS|{'home','section','history','srun','speak','voice-demo','voices','voice','speed','confirm'}
CATALOGUE_COMMANDS=('/models','🧩 Модели','/aggregators','/functions','🛠 Функции',MENU[0],OPEN_CATALOGUE)
MODEL_ACTIONS={
    'chat':'💬 Начать диалог',
    'images.generate':'🖼 Создать изображение',
    'audio.speech':'🎙 Озвучить текст',
}
VOICE_ACTION='🎙 Создать озвучку'
STATUS={'queued':'В очереди','dispatching':'Создаётся','uncertain':'Требуется сверка оператором. Резерв удержан','succeeded':'Готово','failed':'Не удалось — резерв возвращён','cancelled':'Отменено'}

def buttons(rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t,callback_data=d) for t,d in row] for row in rows])

def menu():return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x)] for x in MENU],resize_keyboard=True,is_persistent=True)

class TelegramApp:
    def __init__(self,pool,cfg,bot):
        self.pool,self.cfg,self.bot=pool,cfg,bot;self.svc=Service(pool,cfg)
        self.catalogue_messages = {}
        self.home_screens = set()
        self.work_previews = {}
        self.pending_speech = {}
    async def say(self,chat,text,markup=None):
        if isinstance(markup,ReplyKeyboardMarkup) and chat not in self.cfg.admin_ids:
            markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=OPEN_CATALOGUE)]],resize_keyboard=True,is_persistent=True)
        return await self.bot.send_message(chat,text,reply_markup=markup)
    async def catalogue_screen(self, chat, text, markup=None, *, after_message_id=None):
        self.pending_speech.pop(chat,None)
        await self.close_work_preview(chat)
        message_id = self.catalogue_messages.get(chat)
        reply_keyboard = isinstance(markup, ReplyKeyboardMarkup)
        if (message_id is not None and not reply_keyboard and chat not in self.home_screens
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
        message = await self.say(chat, text, markup)
        self.catalogue_messages[chat] = message.message_id
        if reply_keyboard:
            self.home_screens.add(chat)
        else:
            self.home_screens.discard(chat)
        if message_id is not None:
            await self.remove_menu_message(chat, message_id)

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
        work=await (self.svc.image_work(u,job) if kind=='image' else self.svc.audio_work(u,job))
        await self.close_work_preview(ext)
        prompt=work['prompt']
        if prompt_only:
            if not prompt:raise Rejected('Текст этой работы недоступен.')
            message=await self.bot.send_document(ext,BufferedInputFile(prompt.encode(),filename='prompt.txt'))
        else:
            caption=work.get('caption') or ('Изображение' if kind=='image' else 'Озвучка')
            markup=None
            if show_prompt and prompt:
                caption+='\nПромпт: '+prompt[:450]+('…' if len(prompt)>450 else '')
                if len(prompt)>450:
                    markup=buttons([[('Полный промпт',f'prompt:{kind}:{job}')]])
            send=self.bot.send_photo if kind=='image' else self.bot.send_audio
            message=await send(ext,BufferedInputFile(work[kind],filename=work['filename']),
                               caption=caption,reply_markup=markup)
        self.work_previews[ext]=message.message_id

    def work_rows(self,ext,section,model_id,snapshot=None):
        rows=[]
        if snapshot is None:
            try:
                snapshot=self.catalogue_snapshot()
            except Rejected:
                snapshot=None
        if snapshot:
            published=self.store_models(snapshot,section,ext)
            for index,model in enumerate(snapshot['models']):
                if model.get('provider')!='clodex' or model['id']!=model_id:
                    continue
                scope=section if index in published else 'dev' if ext in self.cfg.admin_ids else None
                if scope:
                    rows.append([('История модели',f'mwork:{snapshot["version"]}:{scope}:{index}:0')])
                    break
        return rows+[[('Мои работы','history:0')],[('Главное меню','home')]]

    async def refresh_speech_results(self):
        # Runs in the same event loop as navigation, between batches of updates.
        for ext,(u,job,rows) in list(self.pending_speech.items()):
            try:
                status=(await self.svc.owned(u,job))['status']
                if status in ('queued','dispatching'):
                    continue
                if status=='succeeded':
                    await self.catalogue_screen(ext,'Озвучка готова.',buttons(rows))
                    await self.open_work(u,ext,'audio',str(job),show_prompt=True)
                    trace_interaction(str(job),'result_notified')
                else:
                    await self.catalogue_screen(ext,'Статус озвучки: '+STATUS[status],buttons(rows))
            except (Rejected,TelegramBadRequest,TelegramNetworkError) as error:
                self.pending_speech.pop(ext,None)
                trace_interaction(str(job),'result_display_failed',error_type=type(error).__name__)

    async def handle(self,update):
        event=update.pre_checkout_query or update.callback_query or update.message
        if not event or not event.from_user or event.from_user.is_bot:return
        ext=event.from_user.id
        if update.message and update.message.chat.type!='private':return
        if update.callback_query and (not update.callback_query.message or update.callback_query.message.chat.type!='private'):return
        financial_receipt=bool(update.message and (update.message.successful_payment or update.message.refunded_payment))
        if self.cfg.access_mode=='private' and ext not in self.cfg.admin_ids and not financial_receipt:
            if update.pre_checkout_query:await self.bot.answer_pre_checkout_query(event.id,ok=False,error_message='Доступ закрыт.')
            elif update.callback_query:await self.bot.answer_callback_query(event.id,text='Доступ закрыт.')
            else:await self.say(ext,'Бот работает в закрытом режиме.')
            return
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
            command=text.lstrip().split(maxsplit=1)
            command=command[0].lower() if command else ''
            navigation=(data in ('providers','home') or data.partition(':')[0] in CATALOGUE_CALLBACKS
                        or data.startswith(('voices:','history:','section:','get:','image:','mget:','mimage:','prompt:'))
                        or text in CATALOGUE_COMMANDS or text in MENU or text in ('/menu','/cancel'))
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
                if catalogue_callback and bot_screen:
                    self.catalogue_messages.setdefault(ext, e.message.message_id)
                await self.callback(u,ext,data,request_id=update.update_id)
                if (data=='home' and bot_screen and e.message.message_id not in
                        (previous_screen, self.catalogue_messages.get(ext)) and previous_screen is not None):
                    await self.remove_menu_message(ext,e.message.message_id)
                return
            if text==OPEN_CATALOGUE or (
                ext not in self.cfg.admin_ids and text in ('/models','🧩 Модели','/functions','🛠 Функции')
            ):
                await self.svc.conversation(u,'home');await self.show_store(ext)
                await self.remove_menu_message(ext,update.message.message_id);return
            if text in ('/models','🧩 Модели'):
                await self.svc.conversation(u,'home');await self.show_models(ext)
                await self.remove_menu_message(ext,update.message.message_id);return
            if text in ('/aggregators','/functions','🛠 Функции',MENU[0]):
                await self.svc.conversation(u,'home')
                await self.show_providers(ext,after_message_id=update.message.message_id)
                await self.remove_menu_message(ext,update.message.message_id);return
            if command=='/start':
                try:
                    await self.svc.conversation(u,'home')
                except Rejected:
                    # New users need to see the consent screen before conversation access.
                    pass
                await self.catalogue_screen(ext,self.cfg.brand+' — агрегатор моделей и функций. Выберите агрегатор, затем его модели или функции.\n'+('Сейчас работает деморежим: тестовый звук, без оплаты.\n' if self.cfg.mode=='mock' else '')+'\nУсловия: '+self.cfg.terms+'\nПолитика: '+self.cfg.privacy,buttons([[('Принять','accept')]]))
                await self.remove_menu_message(ext,update.message.message_id);return
            if text in ('/terms','/privacy','/support','/paysupport'):
                await self.say(ext, self.cfg.terms if text=='/terms' else self.cfg.privacy if text=='/privacy' else self.cfg.support+'\nПо покупкам обращайтесь владельцу сервиса, а не поддержке Telegram.');return
            if text.startswith('/refund '):
                if ext not in self.cfg.admin_ids:raise Rejected('Действие недоступно.')
                p=await self.svc.prepare_refund(text.split(maxsplit=1)[1],provider='telegram')
                try: ok=await self.bot.refund_star_payment(ext if p['user_id']==u else await self.external(p['user_id']),p['charge_id'])
                except Exception:
                    await self.say(ext,'Исход возврата неизвестен. Резерв удержан; требуется сверка.');return
                if ok:await self.svc.complete_refund(p['id'])
                await self.say(ext,'Возврат завершён.' if ok else 'Возврат требует сверки.');return
            if text in MENU or text==VOICE_ACTION or text in ('/menu','/cancel'):
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
                if context and 'interaction' in context:
                    await self.interaction_input(u,ext,update,context);return
                if ext not in self.cfg.admin_ids:
                    raise Rejected('Этот раздел доступен только разработчику.')
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
            if ext not in self.home_screens:
                await self.show_home(ext)
        except Rejected as e:
            if update.message and update.message.successful_payment:
                async with self.pool.acquire() as c,c.transaction():
                    await c.execute("UPDATE inbox SET error_code='PAYMENT_REVIEW' WHERE update_id=$1",update.update_id)
                    await c.execute('UPDATE settings SET halted=true WHERE id=1')
                    await c.execute("INSERT INTO audit_events(action,target) VALUES('payment_review',$1)",u)
            if update.pre_checkout_query:
                await self.bot.answer_pre_checkout_query(update.pre_checkout_query.id,ok=False,error_message=str(e))
            elif catalogue_callback and data.startswith('confirm:') and isinstance(update.callback_query.message,Message):
                await self.catalogue_screen(ext,str(e),update.callback_query.message.reply_markup)
            elif catalogue_callback:
                await self.catalogue_screen(ext,str(e),buttons([[(OPEN_CATALOGUE,'store')]] if ext not in self.cfg.admin_ids else [[('← Агрегаторы','providers')],[(OPEN_CATALOGUE,'store')]]))
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
            raise Rejected('Не удалось загрузить голоса ElevenLabs из CLODEX. Откройте модель и попробуйте ещё раз.')

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
            name='Изображение' if kind=='image' else 'Озвучка'
            price=f" · {r['price']} кредитов" if r['price'] is not None else ''
            lines.append(f"{index}. {r['created_at']:%d.%m %H:%M} UTC · {name} · {STATUS[r['status']]}{price}")
            if r['status']=='succeeded' and r.get('file_available',True):
                route='image' if kind=='image' else 'get'
                if model:route='m'+route
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
            text=f"{'Демо-кредиты' if self.cfg.mode=='mock' else 'Кредиты'}: {w['available']}\nЗарезервировано: {w['reserved']}"
            if self.cfg.payments_enabled and self.cfg.payment_backend=='stars':
                rows.append([('Пополнить','buy')])
        else:
            text=self.cfg.brand+'\nОткройте каталог и выберите нужное действие.\n/terms /privacy /support /paysupport'
        rows.append([('Главное меню','home')])
        await self.catalogue_screen(ext,text,buttons(rows),after_message_id=after_message_id)

    async def callback(self,u,ext,data,*,request_id=None):
        route=data.partition(':')[0]
        if route in DEVELOPER_CALLBACKS and ext not in self.cfg.admin_ids:
            raise Rejected('Этот раздел доступен только разработчику.')
        if data=='store':
            await self.svc.conversation(u,'home');await self.show_store(ext);return
        if route=='mwork':
            _,version,section,index,page=data.split(':')
            snapshot=self.catalogue_snapshot(version)
            index=int(index)
            if section=='dev':
                allowed=ext in self.cfg.admin_ids and 0<=index<len(snapshot['models'])
            else:
                allowed=index in self.store_models(snapshot,section,ext)
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
            if index not in self.store_models(snapshot,section,ext):
                raise Rejected('Модель больше не доступна в этом разделе.')
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
            _,version,index=data.split(':');await self.svc.conversation(u,'home');await self.provider_detail(ext,version,int(index));return
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
            try:
                job=await self.svc.confirm(u,arg)
            except Rejected:
                trace_interaction(request_id,'reservation_failed',operation='audio.speech',
                                  model=self.cfg.clodex_model or 'demo')
                raise
            trace_interaction(str(job),'queued',operation='audio.speech',model=self.cfg.clodex_model or 'demo')
            await self.svc.conversation(u,'home')
            rows=self.work_rows(ext,'speech',self.cfg.clodex_model)
            await self.catalogue_screen(ext,'Работа принята. ⏳ Подождите, идёт озвучка…',buttons(rows))
            self.pending_speech[ext]=(u,job,rows)
            return
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

    async def show_home(self,ext):
        await self.catalogue_screen(ext,self.cfg.brand+' · Главное меню\nВыберите действие в меню.',menu())

    async def show_providers(self,ext,*,after_message_id=None):
        if ext not in self.cfg.admin_ids:
            await self.catalogue_screen(ext,self.cfg.brand,buttons([[(OPEN_CATALOGUE,'store')]]));return
        try:
            data=self.catalogue_snapshot()
            rows=[[(('Clodex' if s['provider']=='clodex' else s['provider']),f"provider:{data['version']}:{i}")] for i,s in enumerate(data.get('sources',[]))]
            text=self.cfg.brand+'\nВыберите агрегатор. Здесь показаны подключённые сервисы; модели и функции внутри каждого обновляются через его API.'
        except Rejected as e:
            text=str(e)
            rows=[[('↻ Обновить экран','providers')]]
        rows.append([(OPEN_CATALOGUE,'store')])
        rows.append([(label,f'section:{index}') for index,label in enumerate(MENU[1:],1)])
        await self.catalogue_screen(ext,text,buttons(rows),after_message_id=after_message_id)

    async def provider_detail(self,ext,version,index):
        if ext not in self.cfg.admin_ids:
            await self.catalogue_screen(ext,self.cfg.brand,buttons([[(OPEN_CATALOGUE,'store')]]));return
        data=self.catalogue_snapshot(version);sources=data.get('sources',[])
        if not 0<=index<len(sources):raise Rejected('Агрегатор недоступен.')
        source=sources[index];provider=source['provider']
        models=[m for m in data['models'] if m.get('provider')==provider and not is_disabled_model(m)]
        functions=[f for f in data.get('functions',[]) if f.get('provider')==provider and not f.get('documentation_only')]
        docs=[f for f in data.get('functions',[]) if f.get('provider')==provider and f.get('documentation_only')]
        scope='Публичный каталог. Доступность по ключу ещё не проверена.' if source['scope']=='public_only' else 'Список получен через /v1/models для ключа сервиса.'
        if data['fresh_until']<time.time():scope+=' Данные устарели.'
        if source.get('evidence',{}).get('unavailable_metadata'):scope+=' Часть метаданных временно недоступна.'
        await self.catalogue_screen(ext,('Clodex' if provider=='clodex' else provider)+f"\nМоделей: {len(models)} · операций API: {len(functions)} · разделов документации: {len(docs)}\n"+scope+( '\nОткройте модель, чтобы увидеть доступные действия.' if self.cfg.interaction_mode!='off' else '\nГенерация через каталог пока выключена.'),buttons([
            [('🧩 Модели',f'cat:{version}:{index}:0')],
            [('🛠 Функции и возможности',f'pf:{version}:{index}:0')],
            [('← Агрегаторы','providers')],
            [(OPEN_CATALOGUE,'store')]]))

    async def show_store(self,ext):
        rows=[[(title,f'slist:current:{section}:0')] for section,(title,_) in STORE_SECTIONS.items()]
        rows.append([('📁 Мои работы','history:0')])
        if ext in self.cfg.admin_ids:
            rows.append([('← Агрегаторы','providers')])
        await self.catalogue_screen(ext,'Каталог моделей. Выберите, что хотите сделать.',buttons(rows))

    def store_models(self,snapshot,section,ext):
        if section not in STORE_SECTIONS:
            raise Rejected('Раздел недоступен.')
        published=set(self.cfg.public_catalogue_models)
        return [
            index for index,model in enumerate(snapshot['models'])
            if model.get('provider')=='clodex'
            and model.get('availability')=='key_available'
            and not is_disabled_model(model)
            and (
                f"{section}:{model['id']}" in published
                or (section=='speech' and self.cfg.speech_pilot and ext in self.cfg.admin_ids
                    and model['id'].replace('-','_')=='eleven_v4')
            )
        ]

    async def show_store_models(self,ext,version,section,page):
        snapshot=self.catalogue_snapshot(None if version=='current' else version)
        models=self.store_models(snapshot,section,ext)
        page_count=max(1,(len(models)+9)//10)
        if not 0<=page<page_count:
            raise Rejected('Страница недоступна.')
        version=snapshot['version']
        title=STORE_SECTIONS[section][0]
        rows=[[(snapshot['models'][i]['title'],f'smodel:{version}:{section}:{page}:{i}')]
              for i in models[page*10:page*10+10]]
        nav=[]
        if page:
            nav.append(('← Назад',f'slist:{version}:{section}:{page-1}'))
        if page+1<page_count:
            nav.append(('Далее →',f'slist:{version}:{section}:{page+1}'))
        if nav:
            rows.append(nav)
        rows.append([('← Каталог','store')])
        status=f'Моделей: {len(models)} · Страница {page+1} из {page_count}' if models else 'В этом разделе пока нет опубликованных моделей.'
        await self.catalogue_screen(ext,title+'\n'+status,buttons(rows))

    async def show_store_model(self,ext,snapshot,section,page,index):
        model=snapshot['models'][index]
        title,operation=STORE_SECTIONS[section]
        version=snapshot['version']
        rows=[]
        status='Запуск этой модели пока недоступен.'
        if self.model_can_run(model,operation):
            rows.append([(('Выбрать голос' if operation=='audio.speech' and self.cfg.speech_pilot else title),f'srun:{version}:{section}:{page}:{index}')])
            if operation=='images.generate' and model['id'] in HIGH_QUALITY_IMAGE_MODELS:
                rows.append([('Качество: high',f'srun:{version}:{section}:{page}:{index}:high')])
            status='Выберите действие, чтобы продолжить.'
        if section in ('image','speech'):
            rows.append([('Работы этой модели',f'mwork:{version}:{section}:{index}:0')])
        rows.extend([[('← К списку моделей',f'slist:{version}:{section}:{page}')],[('← Каталог','store')]])
        await self.catalogue_screen(ext,model['title']+'\n'+status,buttons(rows))

    async def show_models(self,ext,version=None,group=None,page=0):
        from .discovery import groups
        import time
        try:data=self.catalogue_snapshot(version)
        except Rejected as e:
            if version:raise
            await self.catalogue_screen(ext,str(e));return
        if data.get('sources'):
            categories=[{'title':s['provider']+' · '+('публичный каталог' if s['scope']=='public_only' else 'доступно ключу'),
                         'models':[m for m in data['models'] if m.get('provider')==s['provider'] and not is_disabled_model(m)]} for s in data['sources']]
        else:categories=groups({**data,'models':[m for m in data['models'] if not is_disabled_model(m)]})
        if group is None:
            rows=[[(g['title']+f" ({len(g['models'])})",f"cat:{data['version']}:{i}:0")] for i,g in enumerate(categories)]
            label='Каталог провайдеров и моделей:'
            if data['fresh_until']<time.time():label+='\nДанные устарели; запуск по ним недоступен.'
            await self.catalogue_screen(ext,label,buttons(rows) if rows else None);return
        index=int(group)
        if not 0<=index<len(categories) or not 0<=page<=2000:raise Rejected('Раздел недоступен.')
        models=categories[index]['models'];rows=[]
        page_size=10
        for m in models[page*page_size:(page+1)*page_size]:
            rows.append([(m['title'],f"mdl:{data['version']}:{data['models'].index(m)}:{index}:{page}")])
        back = f"cat:{data['version']}:{index}:{page-1}" if page else (
            f"provider:{data['version']}:{index}" if data.get('sources') else 'providers'
        )
        nav=[('← Назад',back)]
        if len(models)>(page+1)*page_size:nav.append(('Далее →',f"cat:{data['version']}:{index}:{page+1}"))
        rows.append(nav)
        rows.append([('← Агрегаторы','providers')])
        label=f"{categories[index]['title']}\nМоделей: {len(models)} · Страница {page+1} из {max(1,(len(models)+page_size-1)//page_size)}"
        await self.catalogue_screen(ext,label,buttons(rows))

    async def model_detail(self,ext,version,index,origin=()):
        from .discovery import OPERATIONS
        data=self.catalogue_snapshot(version)
        if not 0<=index<len(data['models']):raise Rejected('Модель недоступна.')
        m=data['models'][index]
        if is_disabled_model(m):raise Rejected('Модель недоступна.')
        availability='Доступность для ключа не проверена (публичная витрина).'
        if m.get('availability')=='key_available':availability='Модель возвращена API для ключа сервиса.'
        protocols=', '.join(m.get('protocols',[])) or 'не указаны'
        capabilities=', '.join(OPERATIONS[x][0] for x in m['operations']) or 'точные операции для модели не подтверждены'
        price=m.get('public_pricing',{})
        metrics={k:v for k,v in price.items() if k!='verified_for_billing'}
        price_label=json.dumps(metrics,ensure_ascii=False)[:800] if metrics else 'нет данных'
        rows = [[('← Агрегаторы', 'providers')]]
        if len(origin) == 2:
            group, page = map(int, origin)
            rows.insert(0, [('← К списку моделей', f'cat:{version}:{group}:{page}')])
        actions=[
            [(label,f'runmodel:{version}:{index}:{operation}')]
            for operation,label in MODEL_ACTIONS.items() if self.model_can_run(m,operation)
        ]
        if self.model_can_run(m,'images.generate') or self.model_can_run(m,'audio.speech'):
            rows.insert(0,[('Работы этой модели',f'mwork:{version}:dev:{index}:0')])
        launch_status='' if actions else ' Платный запуск через каталог выключен для этой модели.'
        await self.catalogue_screen(ext,m['title']+'\n'+availability+'\nПротоколы: '+protocols+'\nВозможности: '+capabilities+
            '\nПубличные ценовые метрики: '+price_label+'\nЭто не цена заказа.'+launch_status,buttons(actions+rows))

    async def show_functions(self,ext,version=None,page=0,provider_index=None):
        data=self.catalogue_snapshot(version)
        if not 0<=page<=1000:raise Rejected('Страница недоступна.')
        functions=list(enumerate(data.get('functions',[])));rows=[]
        if provider_index is not None:
            sources=data.get('sources',[])
            if not 0<=provider_index<len(sources):raise Rejected('Агрегатор недоступен.')
            functions=[(i,f) for i,f in functions if f.get('provider')==sources[provider_index]['provider']]
        route=f'pf:{data["version"]}:{provider_index}' if provider_index is not None else f'funcs:{data["version"]}'
        for i,f in functions[page*7:page*7+7]:
            rows.append([(f['title'],f"fn:{data['version']}:{i}")])
        nav=[]
        if page:nav.append(('Назад',f"{route}:{page-1}"))
        if len(functions)>(page+1)*7:nav.append(('Далее',f"{route}:{page+1}"))
        if nav:rows.append(nav)
        if self.cfg.mode=='mock':rows.append([('🧪 Тест отправки аудио','voice-demo')])
        if provider_index is not None:rows.append([('← К агрегатору',f"provider:{data['version']}:{provider_index}")])
        rows.append([('← Агрегаторы','providers')])
        await self.catalogue_screen(ext,'Функции, опубликованные API. Наличие в документации не подтверждает совместимость каждой модели.\nПодготовка запроса бесплатна и не запускает генерацию.',buttons(rows))

    async def function_detail(self,ext,version,index):
        data=self.catalogue_snapshot(version);functions=data.get('functions',[])
        if not 0<=index<len(functions):raise Rejected('Функция недоступна.')
        f=functions[index];rows=[]
        if f['request_preview_supported']:rows.append([('Подготовить запрос без отправки',f"choosefn:{version}:{index}:0")])
        pi=next((i for i,s in enumerate(data.get('sources',[])) if s['provider']==f['provider']),None)
        rows.append([('Все функции',f'pf:{version}:{pi}:0' if pi is not None else f'funcs:{version}:0')])
        await self.catalogue_screen(ext,f['title']+'\nПровайдер: '+f['provider']+('\n'+f.get('summary','')[:1000]+'\nЭто описание из документации, контракт исполнения не подтверждён.' if f.get('documentation_only') else '\nМетод: '+f['method']+' '+f['path'])+
                       ('\nМожно проверить заполнение запроса. Реальный вызов выключен.' if f['request_preview_supported'] else '\nВозможность опубликована. Исполнитель ещё не подключён.'),buttons(rows))

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
        return mode in ('mock','live') and supports(model,operation,live=mode=='live') and (
            mode=='mock' or f'{operation}:{model["id"]}' in self.cfg.interaction_pairs
        )

    async def begin_interaction(self,u,ext,version,index,operation,*,request_id=None,quality=None):
        models=self.catalogue_snapshot(version)['models']
        if self.cfg.interaction_mode=='live' and operation!='audio.speech' and (
            self.cfg.access_mode!='private' or ext not in self.cfg.admin_ids
        ):
            raise Rejected('Запуск доступен только администратору.')
        model=models[index] if 0<=index<len(models) else None
        if not model or not self.model_can_run(model,operation):
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
        context={'interaction':operation,'model_id':model['id'],'history':[]}
        if quality is not None:
            context['quality']=quality
        await self.svc.aggregate_context(u,context)
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
            await self.catalogue_screen(ext,text,buttons(self.work_rows(ext,'image',model['id'])))
        else:
            await self.say(ext,model['title']+'\n'+mode+'Пришлите текст или UTF-8 файл .txt. Для выхода отправьте /menu.')

    async def interaction_input(self,u,ext,update,context):
        from .interaction import execute,TEXT_LIMIT
        operation=context['interaction']
        snapshot=self.catalogue_snapshot()
        model=next((m for m in snapshot['models'] if m.get('provider')=='clodex' and m['id']==context['model_id']),None)
        if not model or not self.model_can_run(model,operation):
            raise Rejected('Модель больше не доступна. Откройте каталог.')
        mode=self.cfg.interaction_mode
        if mode=='live' and (self.cfg.access_mode!='private' or ext not in self.cfg.admin_ids or snapshot['fresh_until']<time.time()):
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
            try:
                reserved=await self.svc.reserve_interaction(u,request_id,operation=operation,model_id=model['id'])
            except Exception as error:
                trace_interaction(request_id,'reservation_failed',error_type=type(error).__name__)
                raise
            if not reserved:
                trace_interaction(request_id,'duplicate')
                raise Rejected('Запрос уже был принят. Автоматический повтор отключён.')
            trace_interaction(request_id,'reserved')
        history=context['history']
        if operation=='images.generate':
            await self.remove_menu_message(ext,message.message_id)
            await self.image_status_screen(
                ext, request_id, 'progress', '⏳ Подождите, идёт генерация…',
                after_message_id=message.message_id,
            )
        try:
            result=await execute(operation,model,prompt,history,mode=mode,key=self.cfg.clodex_key,
                                 request_id=request_id,quality=context.get('quality'))
        except Rejected:
            trace_interaction(request_id,'generation_failed')
            if operation!='images.generate':
                raise
            await self.catalogue_screen(
                ext,'Не удалось создать изображение.',
                buttons([[('Главное меню','home')]]),after_message_id=message.message_id,
            )
            return
        if result.text:
            context['history']=[*history,{'role':'user','content':prompt[:2000]},
                                {'role':'assistant','content':result.text[:2000]}][-6:]
            await self.svc.aggregate_context(u,context)
            if len(result.text)>3500:
                await self.bot.send_document(ext,BufferedInputFile(result.text.encode(),filename='answer.txt'))
            else:
                await self.say(ext,result.text)
            trace_interaction(request_id,'result_notified')
        else:
            try:
                job=await self.svc.save_image_work(u,request_id,model['id'],prompt,result)
            except Exception as error:
                trace_interaction(request_id,'save_failed',error_type=type(error).__name__)
                raise
            trace_interaction(request_id,'image_saved')
            rows=self.work_rows(ext,'image',model['id'],snapshot)
            await self.image_status_screen(
                ext, request_id, 'ready', 'Картинка готова. Можно отправить следующее описание.',
                buttons(rows),after_message_id=message.message_id,
            )
            if job:
                try:
                    await self.open_work(u,ext,'image',str(job),show_prompt=True)
                except (Rejected,TelegramBadRequest,TelegramNetworkError) as error:
                    trace_interaction(request_id,'result_display_failed',error_type=type(error).__name__)
                    return
                trace_interaction(request_id,'result_notified')

    async def image_status_screen(self, chat, request_id, screen, text, markup=None, *, after_message_id):
        try:
            await self.catalogue_screen(chat, text, markup, after_message_id=after_message_id)
        except (TelegramBadRequest, TelegramNetworkError) as error:
            trace_interaction(request_id, 'image_status_screen_failed',
                              screen=screen, error_type=type(error).__name__)

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
        q,price=await self.svc.quote(u,text,voice,speed)
        if after_message_id is not None:
            await self.remove_menu_message(ext,after_message_id)
        name=next(v['name'] for v in catalog(self.cfg) if v['id']==voice)
        await self.svc.conversation(u,'confirm')
        await self.catalogue_screen(ext,f"Голос: {name}\nОбъём: {len(text)} символов\nЦена: {price} {'демо-кредитов' if self.cfg.mode=='mock' else 'кредитов'}\nПредложение действует 10 минут. Сначала резерв; списание после успешной генерации.",buttons([[(f'Создать за {price}',f'confirm:{q}')],[('Главное меню','home')]]),after_message_id=after_message_id)

async def poll(pool,cfg,bot):
    app=TelegramApp(pool,cfg,bot)
    # Session-level lock prevents two polling consumers of the same deployment.
    async with pool.acquire() as lock:
        if not await lock.fetchval('SELECT pg_try_advisory_lock(921183)'):raise RuntimeError('Polling already running')
        while True:
            async with pool.acquire() as c:
                pending=await c.fetch('SELECT update_id,payload FROM inbox WHERE NOT done ORDER BY update_id LIMIT 100')
            for r in pending:
                try:await app.handle(Update.model_validate_json(r['payload']))
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
                try:updates=await bot.get_updates(offset=offset,timeout=2 if app.pending_speech else 20,allowed_updates=['message','callback_query','pre_checkout_query'])
                except TelegramNetworkError:
                    print(json.dumps({'event':'telegram_network_retry'}),flush=True)
                    await asyncio.sleep(5);continue
                if updates:
                    async with pool.acquire() as c,c.transaction():
                        for u in updates:
                            await c.execute('INSERT INTO inbox(update_id,payload) VALUES($1,$2::jsonb) ON CONFLICT DO NOTHING',u.update_id,u.model_dump_json())
                        await c.execute('UPDATE poll_state SET offset_id=$1 WHERE id=1',max(u.update_id for u in updates)+1)
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
