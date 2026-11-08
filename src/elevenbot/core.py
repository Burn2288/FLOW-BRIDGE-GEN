"""Application services. No messenger SDK imports. All money is ledger-driven."""
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone

class Rejected(Exception):
    pass

class ConsentRequired(Rejected):
    pass

def uid(value):
    try: return uuid.UUID(str(value))
    except (ValueError,TypeError,AttributeError): raise Rejected('Кнопка устарела. Откройте меню.') from None

class Service:
    def __init__(self,pool,config): self.pool,self.cfg=pool,config

    async def welcome_message(self,chat):
        return await self.pool.fetchval(
            "SELECT welcome_message_id FROM identities WHERE platform='telegram' AND external_id=$1",chat,
        )

    async def save_welcome_message(self,chat,message_id):
        await self.pool.execute(
            "UPDATE identities SET welcome_message_id=$2 WHERE platform='telegram' AND external_id=$1",chat,message_id,
        )

    async def identity(self,external,platform='telegram'):
        async with self.pool.acquire() as c,c.transaction():
            await c.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))',f'{platform}:{external}')
            u=await c.fetchval('SELECT user_id FROM identities WHERE platform=$1 AND external_id=$2',platform,external)
            if not u:
                u=uuid.uuid4()
                await c.execute('INSERT INTO users(id) VALUES($1)',u)
                await c.execute('INSERT INTO identities(platform,external_id,user_id) VALUES($1,$2,$3)',platform,external,u)
                await c.executemany('INSERT INTO wallets(user_id,mode) VALUES($1,$2)',[(u,'demo'),(u,'live')])
                await c.execute('INSERT INTO conversations(user_id) VALUES($1)',u)
            return u

    async def authorize(self,c,u,terms=True):
        r=await c.fetchrow('SELECT * FROM users WHERE id=$1',u)
        if not r or r['blocked']: raise Rejected('Доступ временно ограничен. Обратитесь в поддержку.')
        if terms and not await c.fetchval("SELECT EXISTS(SELECT 1 FROM identities WHERE user_id=$1 AND terms_version='1' AND accepted_at IS NOT NULL)",u):
            raise ConsentRequired('Сначала примите условия через /start.')

    async def accept(self,u):
        async with self.pool.acquire() as c,c.transaction():
            await self.authorize(c,u,False)
            await c.execute("UPDATE identities SET terms_version='1',accepted_at=now() WHERE user_id=$1",u)
            if self.cfg.mode=='mock':
                await self.movement(c,u,'demo',f'demo:{u}','demo_grant',10000,0)

    async def rate(self,u,*,navigation=False):
        column,limit=('navigation_n',60) if navigation else ('n',10)
        async with self.pool.acquire() as c:
            n=await c.fetchval(
                f"INSERT INTO rate_limits(user_id,minute,n,navigation_n) "
                f"VALUES($1,date_trunc('minute',now()),$2,$3) "
                f"ON CONFLICT(user_id,minute) DO UPDATE SET {column}=rate_limits.{column}+1 RETURNING {column}",
                u,int(not navigation),int(navigation),
            )
            if n>limit: raise Rejected('Слишком много действий. Подождите минуту.')

    async def movement(self,c,u,mode,key,kind,da,dr,job=None,payment=None):
        return await c.fetchval('INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,job_id,payment_id) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT(event_key) DO NOTHING RETURNING id',uuid.uuid4(),u,mode,key,kind,da,dr,job,payment)

    async def conversation(self,u,step=None,text=None,voice=None,speed=None):
        async with self.pool.acquire() as c:
            await self.authorize(c,u)
            if step is not None:
                await c.execute('UPDATE conversations SET step=$2,text_content=$3,voice=$4,speed=$5,aggregate_context=NULL,updated_at=now() WHERE user_id=$1',u,step,text,voice,Decimal(str(speed or 1.0)))
            return await c.fetchrow('SELECT * FROM conversations WHERE user_id=$1',u)

    async def aggregate_context(self,u,value=None):
        import json
        async with self.pool.acquire() as c:
            await self.authorize(c,u)
            if value is not None:
                await c.execute("UPDATE conversations SET step='aggregate',aggregate_context=$2::jsonb,updated_at=now() WHERE user_id=$1",u,json.dumps(value))
            raw=await c.fetchval('SELECT aggregate_context FROM conversations WHERE user_id=$1',u)
            return json.loads(raw) if raw else None

    async def reserve_interaction(self,u,update_id,*,operation,model_id):
        async with self.pool.acquire() as c,c.transaction():
            await self.authorize(c,u)
            unlimited=operation=='images.generate' and model_id=='nano-banana-2'
            return await self.reserve_interaction_on(c,u,update_id,unlimited=unlimited)

    async def reserve_interaction_on(self,c,u,update_id,*,unlimited):
        await c.execute('SELECT pg_advisory_xact_lock(921186)')
        if await c.fetchval('SELECT halted FROM settings WHERE id=1 FOR SHARE'):
            raise Rejected('Запуск временно остановлен.')
        if not unlimited and (
            await c.fetchval('SELECT count(*) FROM interaction_attempts WHERE NOT unlimited')>=self.cfg.interaction_limit
        ):
            raise Rejected('Лимит запросов пилота исчерпан.')
        return bool(await c.fetchval(
            'INSERT INTO interaction_attempts(update_id,user_id,unlimited) VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING update_id',
            update_id,u,unlimited,
        ))

    async def grant_speech_pilot_credit(self,external,amount):
        if (
            not self.cfg.speech_pilot or self.cfg.mode!='clodex'
            or not self.cfg.generation_enabled or self.cfg.access_mode!='private'
            or self.cfg.payments_enabled or external not in self.cfg.admin_ids
            or not 1<=amount<=3000
        ):
            raise Rejected('Пилотные кредиты доступны только администратору в закрытом режиме без платежей.')
        user=await self.identity(external)
        async with self.pool.acquire() as c,c.transaction():
            await self.authorize(c,user)
            return bool(await self.movement(c,user,'live',f'speech-pilot:{user}','pilot_grant',amount,0))

    async def quote(self,u,text,voice,speed=1.0):
        if not isinstance(text,str) or not 1<=len(text.strip())<=3000 or any(ord(x)<32 and x not in '\n\t\r' for x in text):
            raise Rejected('Отправьте текст длиной от 1 до 3000 символов.')
        if speed not in (.9,1.0,1.1): raise Rejected('Недоступная скорость.')
        from .providers import catalog
        if voice not in {v['id'] for v in catalog(self.cfg)}: raise Rejected('Этот голос недоступен.')
        q=uuid.uuid4();mode=self.cfg.wallet_mode
        price=max(1,len(text)*self.cfg.retail_per_char)
        cost=max(1,len(text)*(self.cfg.cost_per_char if mode=='live' else 1))
        async with self.pool.acquire() as c,c.transaction():
            await self.authorize(c,u)
            await c.execute('INSERT INTO quotes(id,user_id,mode,text_content,voice,speed,price,cost_bound,tariff) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)',q,u,mode,text,voice,Decimal(str(speed)),price,cost,'retail-v1')
        return q,price

    async def confirm(self,u,q):
        q=uid(q)
        async with self.pool.acquire() as c,c.transaction():
            await self.authorize(c,u)
            await c.fetchrow('SELECT * FROM wallets WHERE user_id=$1 AND mode=$2 FOR UPDATE',u,self.cfg.wallet_mode)
            old=await c.fetchrow('SELECT * FROM jobs WHERE quote_id=$1 AND user_id=$2',q,u)
            if old:return old['id']
            r=await c.fetchrow('SELECT * FROM quotes WHERE id=$1 AND user_id=$2 AND expires_at>now()',q,u)
            if not r or r['mode']!=self.cfg.wallet_mode: raise Rejected('Предложение устарело. Создайте новое.')
            if not self.cfg.generation_enabled: raise Rejected('Генерация временно выключена.')
            if await c.fetchval('SELECT halted FROM settings WHERE id=1 FOR SHARE'): raise Rejected('Сервис на проверке. Попробуйте позже.')
            if await c.fetchval("SELECT EXISTS(SELECT 1 FROM jobs WHERE user_id=$1 AND status IN ('queued','dispatching','uncertain'))",u): raise Rejected('Дождитесь завершения текущей работы.')
            money=await c.fetchval('SELECT available FROM wallets WHERE user_id=$1 AND mode=$2',u,r['mode'])
            if money<r['price']: raise Rejected('Недостаточно кредитов. Откройте «Баланс».')
            day=datetime.now(timezone.utc).date()
            await c.execute('INSERT INTO budgets(day) VALUES($1) ON CONFLICT DO NOTHING',day)
            spent=await c.fetchval('SELECT used FROM budgets WHERE day=$1 FOR UPDATE',day)
            limit=self.cfg.budget if r['mode']=='live' else 1000000
            if limit is not None and spent+r['cost_bound']>limit: raise Rejected('Дневной лимит сервиса исчерпан. Попробуйте позже.')
            await c.execute('UPDATE budgets SET used=used+$2 WHERE day=$1',day,r['cost_bound'])
            j=uuid.uuid4()
            await c.execute("INSERT INTO jobs(id,user_id,quote_id,mode,price,cost_bound,budget_day,status) VALUES($1,$2,$3,$4,$5,$6,$7,'queued')",j,u,q,r['mode'],r['price'],r['cost_bound'],day)
            await self.movement(c,u,r['mode'],f'reserve:{j}','reserve',-r['price'],r['price'],j)
            return j

    async def settle(self,j,kind,fence=None,storage=None,cancel=False,operator_release=False):
        if kind not in ('capture','release') or (operator_release and kind!='release'):raise ValueError('Invalid settlement')
        async with self.pool.acquire() as c,c.transaction():
            owner=await c.fetchrow('SELECT user_id,mode FROM jobs WHERE id=$1',uid(j))
            if not owner: raise Rejected('Работа не найдена.')
            await c.fetchrow('SELECT * FROM wallets WHERE user_id=$1 AND mode=$2 FOR UPDATE',owner['user_id'],owner['mode'])
            r=await c.fetchrow('SELECT * FROM jobs WHERE id=$1 FOR UPDATE',uid(j))
            if not r: raise Rejected('Работа не найдена.')
            if operator_release and r['status']!='uncertain':raise Rejected('Job not uncertain')
            if r['settlement']: return r['settlement']==kind
            if fence is not None and (r['fence']!=fence or r['status']!='dispatching' or not r['lease_until'] or r['lease_until']<=datetime.now(timezone.utc)):
                return False
            if cancel and r['status']!='queued': raise Rejected('Эту работу уже нельзя отменить.')
            await self.movement(c,r['user_id'],r['mode'],f'settlement:{j}',kind,r['price'] if kind=='release' else 0,-r['price'],r['id'])
            if kind=='release' and r['status']!='uncertain':
                await c.execute('UPDATE budgets SET used=used-$2 WHERE day=$1',r['budget_day'],r['cost_bound'])
            if kind=='capture':
                if not storage: raise ValueError('Artifact required')
                await c.execute("INSERT INTO files VALUES($1,$2,$3,$4,now()+interval '7 days',NULL)",r['id'],storage['key'],storage['sha256'],storage['size'])
                await c.execute('INSERT INTO deliveries(job_id) VALUES($1)',r['id'])
            await c.execute('UPDATE jobs SET status=$2,settlement=$3,completed_at=now(),lease_until=NULL WHERE id=$1',r['id'],'succeeded' if kind=='capture' else ('cancelled' if cancel else 'failed'),kind)
            if operator_release:
                await c.execute("INSERT INTO audit_events(action,target) VALUES('operator_release_possibly_billed',$1)",r['id'])
            return True

    async def cancel(self,u,j):
        await self.owned(u,j)
        return await self.settle(j,'release',cancel=True)

    async def owned(self,u,j):
        async with self.pool.acquire() as c:
            await self.authorize(c,u)
            r=await c.fetchrow('SELECT j.*,f.storage_key,f.expires_at,f.deleted_at FROM jobs j LEFT JOIN files f ON f.job_id=j.id WHERE j.id=$1 AND j.user_id=$2',uid(j),u)
            if not r: raise Rejected('Работа не найдена.')
            return r

    async def history(self,u,offset=0,model_id=None):
        async with self.pool.acquire() as c:
            await self.authorize(c,u)
            return await c.fetch("""
                SELECT * FROM (
                    SELECT j.id,j.status,j.price,j.created_at,'audio' AS kind,j.model_id,
                           (f.deleted_at IS NULL AND f.expires_at>now()) AS file_available
                    FROM jobs j LEFT JOIN files f ON f.job_id=j.id
                    WHERE j.user_id=$1 AND ($3::text IS NULL OR j.model_id=$3)
                    UNION ALL
                    SELECT id,'succeeded',NULL,created_at,'image',model_id,true
                    FROM image_works WHERE user_id=$1 AND expires_at>now()
                    AND ($3::text IS NULL OR model_id=$3)
                    UNION ALL
                    SELECT id,'succeeded',NULL,created_at,'video',model_id,true
                    FROM video_jobs WHERE user_id=$1 AND status='succeeded' AND expires_at>now()
                    AND ($3::text IS NULL OR model_id=$3)
                    UNION ALL
                    SELECT id,'succeeded',NULL,created_at,'audio',model_id,true
                    FROM task_speech_works WHERE user_id=$1 AND audio IS NOT NULL AND expires_at>now()
                    AND ($3::text IS NULL OR model_id=$3)
                    UNION ALL
                    SELECT q.id,'succeeded',NULL,w.created_at,'chat',q.model_id,true
                    FROM task_chat_works w JOIN task_price_quotes q ON q.id=w.quote_id
                    WHERE q.user_id=$1 AND w.expires_at>now() AND ($3::text IS NULL OR q.model_id=$3)
                ) works ORDER BY created_at DESC,id DESC LIMIT 10 OFFSET $2
                """,u,max(0,offset),model_id)

    async def save_image_work(self,u,update_id,model_id,prompt,result):
        async with self.pool.acquire() as c:
            return await self.save_image_work_on(c,u,update_id,model_id,prompt,result)

    async def save_image_work_on(self,c,u,update_id,model_id,prompt,result):
        await self.authorize(c,u)
        job=await c.fetchval("""
            INSERT INTO image_works(id,update_id,user_id,model_id,prompt,image,filename)
            VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT(update_id) DO NOTHING RETURNING id
            """,uuid.uuid4(),update_id,u,model_id,prompt,result.image,result.filename)
        return job or await c.fetchval(
            'SELECT id FROM image_works WHERE update_id=$1 AND user_id=$2',update_id,u
        )

    async def image_work(self,u,j):
        async with self.pool.acquire() as c:
            await self.authorize(c,u)
            row=await c.fetchrow("""
                SELECT prompt,image,filename FROM image_works
                WHERE id=$1 AND user_id=$2 AND expires_at>now()
                """,uid(j),u)
            if not row:raise Rejected('Файл недоступен или срок хранения истёк.')
            return row

    async def video_work(self,u,j):
        async with self.pool.acquire() as c:
            await self.authorize(c,u)
            row=await c.fetchrow("""
                SELECT prompt,video,
                       CASE WHEN provider='anymodel' THEN 'grok.mp4' ELSE 'veo.mp4' END AS filename,
                       CASE WHEN provider='anymodel' THEN 'Grok Imagine Video 1.5' ELSE 'Veo 3.1' END AS caption
                FROM video_jobs
                WHERE id=$1 AND user_id=$2 AND status='succeeded' AND expires_at>now()
                """,uid(j),u)
            if not row:raise Rejected('Файл недоступен или срок хранения истёк.')
            return row

    async def audio_work(self,u,j):
        async with self.pool.acquire() as c:
            await self.authorize(c,u)
            speech=await c.fetchrow("""
                SELECT input AS prompt,audio,provider || '.mp3' AS filename,title || ' · ИИ-озвучка' AS caption
                FROM task_speech_works WHERE id=$1 AND user_id=$2 AND audio IS NOT NULL AND expires_at>now()
                """,uid(j),u)
        if speech:
            return dict(speech)
        r=await self.owned(u,j)
        if r['status']!='succeeded' or not r['storage_key'] or r['deleted_at'] or r['expires_at']<=datetime.now(timezone.utc):
            raise Rejected('Файл недоступен или срок хранения истёк.')
        async with self.pool.acquire() as c:
            prompt=await c.fetchval('SELECT text_content FROM quotes WHERE id=$1',r['quote_id'])
        from .storage import Storage
        try:
            audio=await asyncio.to_thread(Storage(self.cfg.storage).path(r['storage_key']).read_bytes)
        except FileNotFoundError:
            raise Rejected('Файл недоступен или срок хранения истёк.') from None
        return {'prompt':prompt,'audio':audio,'filename':'ozvuchka.mp3'}

    async def chat_work(self,u,j):
        async with self.pool.acquire() as c:
            await self.authorize(c,u)
            row=await c.fetchrow("""
                SELECT w.answer FROM task_chat_works w JOIN task_price_quotes q ON q.id=w.quote_id
                WHERE q.id=$1 AND q.user_id=$2 AND w.expires_at>now()
                """,uid(j),u)
            if not row:raise Rejected('Ответ недоступен или срок хранения истёк.')
            return row['answer']

    async def wallet(self,u):
        async with self.pool.acquire() as c:
            await self.authorize(c,u)
            return await c.fetchrow('SELECT * FROM wallets WHERE user_id=$1 AND mode=$2',u,self.cfg.wallet_mode)

    async def redeliver(self,u,j):
        r=await self.owned(u,j)
        if r['status']!='succeeded' or not r['storage_key'] or r['deleted_at'] or r['expires_at']<=datetime.now(timezone.utc): raise Rejected('Файл пока недоступен или срок хранения истёк.')
        async with self.pool.acquire() as c:
            await c.execute("UPDATE deliveries SET status='pending',next_at=now(),attempts=0 WHERE job_id=$1 AND status IN ('sent','retry','expired','uncertain')",r['id'])

    async def order(self,u):
        if not self.cfg.payments_enabled or self.cfg.mode=='mock' or self.cfg.payment_backend!='stars': raise Rejected('Покупка временно недоступна.')
        async with self.pool.acquire() as c,c.transaction():
            await self.authorize(c,u)
            if await c.fetchval('SELECT halted FROM settings WHERE id=1 FOR SHARE'): raise Rejected('Покупка временно недоступна.')
            p=uuid.uuid4()
            await c.execute("INSERT INTO payments(id,user_id,amount,credits,currency,tariff,status) VALUES($1,$2,100,10000,'XTR','pack-v1','pending')",p,u)
            return p

    async def precheckout(self,u,p,amount,currency):
        if not self.cfg.payments_enabled or self.cfg.payment_backend!='stars':return False
        async with self.pool.acquire() as c:
            await self.authorize(c,u)
            r=await c.fetchrow("SELECT * FROM payments WHERE id=$1 AND user_id=$2 AND status='pending' AND provider='telegram'",uid(p),u)
            return bool(r and r['amount']==amount and r['currency']==currency and not await c.fetchval('SELECT halted FROM settings WHERE id=1'))

    async def payment(self,u,p,amount,currency,charge):
        # Must only be called by authenticated successful_payment transport handler.
        if self.cfg.mode=='mock': raise Rejected('Реальная оплата запрещена в деморежиме.')
        if not charge or len(charge)>512: raise Rejected('Не удалось проверить оплату.')
        async with self.pool.acquire() as c,c.transaction():
            await c.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))','charge:'+charge)
            existing=await c.fetchval('SELECT id FROM payments WHERE charge_id=$1',charge)
            if existing and existing!=uid(p): raise Rejected('Оплата требует проверки поддержкой.')
            r=await c.fetchrow('SELECT * FROM payments WHERE id=$1 FOR UPDATE',uid(p))
            if not r or r['provider']!='telegram' or r['user_id']!=u or r['amount']!=amount or r['currency']!=currency: raise Rejected('Оплата требует проверки поддержкой.')
            if r['status'] in ('succeeded','refunding','refunded'):
                if r['charge_id']!=charge: raise Rejected('Оплата требует проверки поддержкой.')
                return False
            if r['status']!='pending': raise Rejected('Оплата требует проверки поддержкой.')
            await c.execute("UPDATE payments SET charge_id=$2,status='succeeded' WHERE id=$1",r['id'],charge)
            await self.movement(c,u,'live',f'payment:{p}','payment',r['credits'],0,payment=r['id'])
            return True

    async def prepare_refund(self,p,provider=None):
        async with self.pool.acquire() as c,c.transaction():
            r=await c.fetchrow('SELECT * FROM payments WHERE id=$1 FOR UPDATE',uid(p))
            if not r or r['status']!='succeeded' or (provider is not None and r['provider']!=provider): raise Rejected('Возврат уже начат или недоступен.')
            # Conservative full refund: no consumed credits or open reservations across account.
            w=await c.fetchrow("SELECT * FROM wallets WHERE user_id=$1 AND mode='live' FOR UPDATE",r['user_id'])
            if w['reserved'] or w['available']<r['credits']: raise Rejected('Нужна ручная сверка использованных кредитов.')
            await self.movement(c,r['user_id'],'live',f'refund-hold:{p}','refund_hold',-r['credits'],r['credits'],payment=r['id'])
            await c.execute("UPDATE payments SET status='refunding' WHERE id=$1",r['id'])
            return dict(r)

    async def complete_refund(self,p):
        async with self.pool.acquire() as c,c.transaction():
            r=await c.fetchrow('SELECT * FROM payments WHERE id=$1 FOR UPDATE',uid(p))
            if r and r['status']=='refunded': return False
            if not r or r['status']!='refunding': raise Rejected('Возврат не подготовлен.')
            await self.movement(c,r['user_id'],'live',f'refund:{p}','refund',0,-r['credits'],payment=r['id'])
            await c.execute("UPDATE payments SET status='refunded' WHERE id=$1",r['id'])
            return True

    async def reconcile(self):
        async with self.pool.acquire() as c,c.transaction():
            bad=await c.fetchval('''SELECT count(*) FROM wallets w LEFT JOIN
              (SELECT user_id,mode,sum(da) a,sum(dr) r FROM ledger GROUP BY user_id,mode) l USING(user_id,mode)
              WHERE w.available<>coalesce(l.a,0) OR w.reserved<>coalesce(l.r,0)''')
            bad+=await c.fetchval('''SELECT count(*) FROM wallets w WHERE w.reserved<>
              coalesce((SELECT sum(j.price) FROM jobs j WHERE j.user_id=w.user_id AND j.mode=w.mode AND j.settlement IS NULL),0)
              + CASE WHEN w.mode='live' THEN coalesce((SELECT sum(p.credits) FROM payments p WHERE p.user_id=w.user_id AND p.status='refunding'),0) ELSE 0 END''')
            if bad: await c.execute('UPDATE settings SET halted=true WHERE id=1')
            return bad
