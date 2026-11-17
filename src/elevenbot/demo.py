"""UI-only Telegram demo. No PostgreSQL, commercial wallet, payment or paid provider.
All state is in RAM and is reset on exit. Use a separate BotFather TEST bot.
"""
import asyncio,getpass,os,secrets,time,uuid
from datetime import datetime,timedelta,timezone
from dataclasses import replace
from pathlib import Path
from aiogram import Bot
from aiogram.exceptions import TelegramUnauthorizedError,TelegramConflictError,TelegramNetworkError
from .config import Config
from .core import ConsentRequired,Rejected,uid
from .telegram import TelegramApp,buttons

class DemoService:
    def __init__(self):
        self.users={};self.quotes={};self.jobs={};self.images={};self.requests=asyncio.Queue();self.lock=asyncio.Lock()
    async def identity(self,external,platform='telegram'):
        for u,r in self.users.items():
            if r['external']==external:return u
        u=uuid.uuid4();self.users[u]={'external':external,'accepted':False,'state':{'step':'home','text_content':None,'voice':None},'actions':[]}
        return u
    def authorize(self,u):
        if u not in self.users or not self.users[u]['accepted']:raise ConsentRequired('Сначала примите условия через /start.')
    async def accept(self,u):self.users[u]['accepted']=True

    async def welcome_message(self,chat):
        return self.users[await self.identity(chat)].get('welcome_message_id')

    async def save_welcome_message(self,chat,message_id):
        self.users[await self.identity(chat)]['welcome_message_id']=message_id
    async def rate(self,u,*,navigation=False):
        r=self.users[u];bucket='navigation' if navigation else 'actions';now=time.monotonic()
        r[bucket]=[x for x in r.get(bucket,[]) if now-x<60]
        if len(r[bucket])>=(60 if navigation else 30):raise Rejected('Подождите минуту.')
        r[bucket].append(now)
    async def conversation(self,u,step=None,text=None,voice=None,speed=None):
        self.authorize(u)
        if step is not None:self.users[u]['state']={'step':step,'text_content':text,'voice':voice,'speed':speed or 1.0}
        return self.users[u]['state']
    async def aggregate_context(self,u,value=None):
        self.authorize(u)
        if value is not None:self.users[u]["state"]={"step":"aggregate","aggregate_context":value}
        return self.users[u]["state"].get("aggregate_context")
    async def quote(self,u,text,voice,speed=1.0):
        self.authorize(u)
        if not isinstance(text,str) or not 1<=len(text.strip())<=3000 or any(ord(x)<32 and x not in '\r\n\t' for x in text):raise Rejected('Нужен текст от 1 до 3000 символов.')
        if voice!='demo' or speed not in (.9,1.0,1.1):raise Rejected('Настройка недоступна.')
        q=uuid.uuid4();self.quotes[q]={'user':u,'price':len(text),'prompt':text,'expires':time.monotonic()+600,'job':None}
        return q,len(text)
    async def confirm(self,u,q):
        self.authorize(u);q=uid(q)
        async with self.lock:
            r=self.quotes.get(q)
            if not r or r['user']!=u:raise Rejected('Предложение не найдено.')
            if r['job']:return r['job']
            if r['expires']<time.monotonic():raise Rejected('Предложение устарело.')
            if any(j['user']==u and j['status']=='queued' for j in self.jobs.values()):raise Rejected('Дождитесь текущей работы.')
            j=uuid.uuid4();self.jobs[j]={'id':j,'user':u,'status':'queued','price':r['price'],'mode':'demo','model_id':'demo','prompt':r['prompt'],'created_at':datetime.now(timezone.utc)}
            r['job']=j;self.requests.put_nowait(j);return j
    async def owned(self,u,j):
        self.authorize(u);j=uid(j)
        r=self.jobs.get(j)
        if not r or r['user']!=u:raise Rejected('Работа не найдена.')
        return r
    async def history(self,u,offset=0,model_id=None):
        self.authorize(u)
        works=[j for j in (*self.jobs.values(),*self.images.values())
               if j['user']==u and (model_id is None or j['model_id']==model_id)]
        return sorted(works,key=lambda j:j['created_at'],reverse=True)[max(0,offset):max(0,offset)+10]

    async def save_image_work(self,u,update_id,model_id,prompt,result):
        self.authorize(u)
        job=uuid.uuid4()
        return self.images.setdefault(update_id,{'id':job,'user':u,'kind':'image','status':'succeeded',
            'price':None,'model_id':model_id,'prompt':prompt,'image':result.image,
            'filename':result.filename,'created_at':datetime.now(timezone.utc)})['id']

    async def image_work(self,u,j):
        self.authorize(u)
        job=uid(j)
        for work in self.images.values():
            if work['id']==job and work['user']==u:return work
        raise Rejected('Работа не найдена.')

    async def audio_work(self,u,j):
        work=await self.owned(u,j)
        if work['status']!='succeeded':raise Rejected('Работа пока не готова.')
        return {'prompt':work['prompt'],'audio':Path('assets/demo.mp3').read_bytes(),
                'filename':'demo.mp3','caption':'ТЕСТ: демонстрационный звук. Clodex и оплата выключены.'}

    async def wallet(self,u):
        self.authorize(u)
        return {'available':10000,'reserved':0}  # Pure display fixture; no spendable balance/ledger.
    async def cancel(self,u,j):
        r=await self.owned(u,j)
        if r['status']!='queued':raise Rejected('Работа уже завершена.')
        r['status']='cancelled';return True
    async def order(self,*args):raise Rejected('Оплата в тестовом режиме выключена.')
    async def precheckout(self,*args):return False

class DemoApp(TelegramApp):
    def __init__(self,cfg,bot,service):
        super().__init__(None,cfg,bot);self.svc=service
    async def handle(self,update):
        # Never enter production payment/refund handlers backed by PostgreSQL.
        m=update.message
        if update.pre_checkout_query:
            await self.bot.answer_pre_checkout_query(update.pre_checkout_query.id,ok=False,error_message='Это тестовый бот, оплаты выключены.');return
        if m and (m.successful_payment or m.refunded_payment or (m.text or '').startswith('/refund')):
            await self.bot.send_message(m.chat.id,'Это демонстрационный режим. Финансовые операции не выполняются.');return
        await super().handle(update)

    async def menu_section(self,u,ext,section):
        if section!=3:
            await super().menu_section(u,ext,section)
            return
        await self.catalogue_screen(
            ext,'DarkFlow | Gen: модели и функции загружаются из Clodex. Доступен предпросмотр запросов без отправки. '
            'Генерация и оплаты выключены. История и виртуальные данные сбрасываются при закрытии окна.',
            buttons([[('Главное меню','home')]]),
        )

    async def make_quote(self,u,ext,text,voice,speed):
        q,price=await self.svc.quote(u,text,voice,speed)
        await self.svc.conversation(u,'confirm')
        await self.catalogue_screen(ext,f'ТЕСТ ИНТЕРФЕЙСА\nОбъём: {len(text)} символов\nУсловная стоимость: {price} демо-кредитов.\nНикаких списаний нет. Будет отправлен демонстрационный звук вместо озвучки.',
                       buttons([[('Получить тестовый звук',f'confirm:{q}')],[('Главное меню','home')]]))

class Pairing:
    def __init__(self):self.code=secrets.token_urlsafe(18);self.owner=None
    def allow(self,external,text=''):
        if self.owner is not None:return external==self.owner
        if text.startswith('/start ') and secrets.compare_digest(text.partition(' ')[2].strip().encode(),self.code.encode()):
            self.owner=external;self.code='';return True
        return False

async def deliver(service):
    while True:
        j=await service.requests.get()
        try:
            r=service.jobs[j]
            if r['status']!='cancelled':
                r['status']='succeeded'
        finally:
            service.requests.task_done()

async def run():
    print('DarkFlow | Gen TEST MODE | Real Telegram UI | No Docker/PostgreSQL/paid requests',flush=True)
    print('Use a NEW test bot created in @BotFather. Do not reuse an active production token.',flush=True)
    token=os.getenv('DARKFLOW_DEMO_TOKEN') or os.getenv('ELEVENBOT_DEMO_TOKEN') or getpass.getpass('BotFather token (hidden, not saved): ').strip()
    if not token:raise ValueError('Empty token')
    cfg=Config(mode='mock',generation_enabled=True,payments_enabled=False,
        terms='Тест интерфейса. Реальных списаний и генерации речи нет. Состояние исчезает после закрытия программы.',
        privacy='Не отправляйте личные данные. Сообщения проходят через Telegram, состояние хранится только в памяти программы.',
        support='Свяжитесь с владельцем тестового бота.')
    from .aggregate import refresh_aggregate
    cfg=replace(cfg,clodex_key=os.getenv('CLODEX_API_KEY',''),catalogue_enabled=True)
    print('Loading public Clodex catalogue (GET only)...',flush=True)
    try:
        data=await refresh_aggregate(cfg,once=True)
        print(f"Models: {len(data['models'])}; functions: {len(data['functions'])}. No paid requests.",flush=True)
    except Exception:
        print('Catalogue refresh unavailable. Cached catalogue may be displayed; no paid calls.',flush=True)
    async with Bot(token) as bot:
        print('Connecting to Telegram...',flush=True)
        me=await bot.get_me(request_timeout=15)
        webhook=await bot.get_webhook_info(request_timeout=15)
        if webhook.url:
            print('BLOCKED: bot already has a webhook. Create a separate test bot; existing webhook was not changed.');return
        pairing=Pairing();service=DemoService();app=DemoApp(cfg,bot,service)
        print('\nOpen this link in Telegram to bind your account (keep it private):',flush=True)
        print(f'https://t.me/{me.username}?start={pairing.code}',flush=True)
        print('Press START in Telegram. Stop the program: Ctrl+C. Messages and token are not saved. Public catalogue is cached.',flush=True)
        worker=asyncio.create_task(deliver(service));refresher=asyncio.create_task(refresh_aggregate(cfg));offset=None
        try:
            while True:
                await app.refresh_speech_results()
                try:updates=await bot.get_updates(offset=offset,timeout=2 if app.pending_speech else 20,allowed_updates=['message','callback_query','pre_checkout_query'])
                except TelegramNetworkError:
                    print('Telegram network unavailable. Retrying in 5 seconds.',flush=True);await asyncio.sleep(5);continue
                for update in updates:
                    offset=update.update_id+1  # RAM-only UI demo: skip unrelated updates safely.
                    e=update.pre_checkout_query or update.callback_query or update.message
                    text=(update.message.text or '') if update.message else ''
                    external=e.from_user.id if e and e.from_user else None
                    if update.message and update.message.chat.type!='private':continue
                    if update.callback_query and (not update.callback_query.message or update.callback_query.message.chat.type!='private'):continue
                    if external and pairing.allow(external,text):
                        try:await app.handle(update)
                        except TelegramNetworkError:print('Reply could not be delivered. Try again in Telegram.',flush=True)
                    elif update.callback_query:await bot.answer_callback_query(update.callback_query.id,text='Этот тестовый бот закрыт.')
                    elif update.pre_checkout_query:await bot.answer_pre_checkout_query(update.pre_checkout_query.id,ok=False,error_message='Тестовый режим. Оплата выключена.')
                    elif update.message and update.message.chat.type=='private':await bot.send_message(external,'Закрытый тестовый бот. Откройте ссылку подключения из окна запуска.')
                    offset=update.update_id+1
        finally:
            worker.cancel();refresher.cancel();await asyncio.gather(worker,refresher,return_exceptions=True)

def main():
    try:asyncio.run(run())
    except KeyboardInterrupt:print('\nTest bot stopped. State cleared.')
    except TelegramUnauthorizedError:print('Invalid/revoked BotFather token. Restart and enter a valid TEST token.')
    except TelegramConflictError:print('Another process is using this bot token. Stop it or create a separate TEST bot.')
    except Exception as e:print('Stopped:',type(e).__name__,'(secret details hidden).')

if __name__=='__main__':main()
