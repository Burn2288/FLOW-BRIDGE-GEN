"""Durable external top-ups using the shared wallets and immutable ledger."""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from math import ceil
from uuid import UUID, uuid4

from aiogram.exceptions import TelegramRetryAfter

from .core import Rejected, Service, uid
from .platega import PlategaClient, PlategaConfig, PaymentInvalid, PaymentUnknown, kopecks
from .pricing import display

LOG = logging.getLogger(__name__)
STATES = {'PENDING','CONFIRMED','CANCELED','DISPUTED','PARTIALLY_REFUNDED','CHARGEBACKED'}
ORDER = """SELECT p.*,t.chat_id,t.mode,t.state,t.rate_tokens,t.rate_rubles,t.expires_at,t.merchant_id,
 t.returned_minor,t.returned_tokens,t.notice_state,t.last_error,t.next_check_at
 FROM payments p JOIN topup_orders t ON t.payment_id=p.id"""


def amount(text):
    if not isinstance(text,str) or not re.fullmatch(r'[0-9]{1,8}(?:[.,][0-9]{1,2})?',text.strip()):
        raise Rejected('Введите положительную сумму в рублях, до двух знаков после запятой.')
    try:
        return kopecks(text.strip().replace(',','.'))
    except PaymentInvalid:
        raise Rejected('Некорректная сумма.') from None


def rubles(minor):
    return format(Decimal(minor)/100,'.2f').rstrip('0').rstrip('.')


def client_config(cfg):
    return PlategaConfig(merchant=cfg.platega_merchant,secret=cfg.platega_secret,
                         enabled=cfg.topup_mode=='live' and cfg.platega_enabled,return_url=cfg.platega_return,
                         failed_url=cfg.platega_failed,method=cfg.platega_method)


class CheckoutClient(PlategaClient):
    async def checkout(self,order,chat,minor):
        # The shared adapter owns the create payload and validates the payment URL.
        remote,url,expiry=await self.create_details(order,chat,minor)
        if not isinstance(expiry,str) or not re.fullmatch(r'[0-9]{2}:[0-9]{2}:[0-9]{2}',expiry):
            raise PaymentUnknown('Creation expiry missing')
        hours,minutes,seconds=map(int,expiry.split(':'))
        duration=hours*3600+minutes*60+seconds
        if not 0<duration<=86400 or minutes>59 or seconds>59:
            raise PaymentUnknown('Creation expiry invalid')
        return remote,url,datetime.now(timezone.utc)+timedelta(seconds=duration)

    async def find(self,order,created):
        # A lost create response never authorizes another /transaction/process.
        body={'from':created.isoformat(),'to':datetime.now(timezone.utc).isoformat(),'timeZoneId':'UTC'}
        rows=await self.request('POST','/transaction/export/json',body,allow_list=True)
        if not isinstance(rows,list):
            raise PaymentUnknown('Export response contract')
        matches={uid(row['recordId']) for row in rows
                 if isinstance(row,dict) and row.get('payload')==str(order)}
        if len(matches)>1:
            raise PaymentInvalid('Multiple transactions for order')
        return next(iter(matches),None)


class Topups:
    def __init__(self,pool,cfg,client=None):
        self.pool,self.cfg=pool,cfg
        self.svc=Service(pool,cfg)
        self.client=client or CheckoutClient(client_config(cfg))

    def enabled(self):
        return bool(self.cfg.topup_mode=='live' and self.cfg.payments_enabled
                    and self.cfg.payment_backend=='platega' and self.cfg.platega_merchant
                    and self.cfg.platega_secret and self.client.cfg.enabled)

    async def settings(self):
        return await self.pool.fetchrow('SELECT * FROM topup_settings WHERE id=1')

    async def quote(self,user,chat,minor,key,*,test_session=False):
        if self.cfg.topup_mode=='test' and (chat not in self.cfg.admin_ids or not test_session):
            raise Rejected('Тестовое пополнение доступно администратору.')
        if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{12}',key):
            raise Rejected('Откройте панель пополнения заново.')
        if type(minor) is not int:
            raise Rejected('Некорректная сумма.')
        mode='demo' if self.cfg.topup_mode=='test' else 'live'
        merchant=uid(self.client.cfg.merchant) if self.client.cfg.merchant else UUID(int=0)
        async with self.pool.acquire() as conn,conn.transaction():
            await self.svc.authorize(conn,user)
            identity=await conn.fetchval("SELECT user_id FROM identities WHERE platform='telegram' AND external_id=$1",chat)
            if chat<=0 or identity!=user:
                raise Rejected('Владелец платежа не совпадает.')
            await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1,0))','topup-quote:'+str(user)+':'+key)
            old=await conn.fetchrow(ORDER+' WHERE p.user_id=$1 AND t.request_key=$2',user,key)
            if old:
                if old['amount']!=minor:
                    raise Rejected('Сумма уже выбрана. Откройте пополнение заново.')
                return old
            limits=await conn.fetchrow('SELECT * FROM topup_settings WHERE id=1')
            if not limits['minimum']<=minor<=limits['maximum']:
                raise Rejected(f"Допустимая сумма от {rubles(limits['minimum'])} до {rubles(limits['maximum'])} ₽.")
            rate=await conn.fetchrow('SELECT * FROM task_ruble_equivalent WHERE id=1 FOR SHARE')
            if not rate:
                raise Rejected('Стоимость токенов бота пока не настроена.')
            tokens=int(Fraction(minor)*Fraction(rate['bot_amount'])/(100*Fraction(rate['rubles'])))
            if not 1<=tokens<=10**12:
                raise Rejected('Для этой суммы нельзя рассчитать зачисление.')
            order=uuid4()
            await conn.execute("""INSERT INTO payments(id,user_id,amount,credits,currency,tariff,status,provider,creation_state)
                VALUES($1,$2,$3,$4,'RUB','topup-v1','pending','platega','new')""",order,user,minor,tokens)
            await conn.execute("""INSERT INTO topup_orders(payment_id,user_id,chat_id,request_key,mode,merchant_id,rate_tokens,rate_rubles)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",order,user,chat,key,mode,merchant,rate['bot_amount'],rate['rubles'])
            return await conn.fetchrow(ORDER+' WHERE p.id=$1',order)

    async def owned(self,user,order):
        row=await self.pool.fetchrow(ORDER+' WHERE p.id=$1 AND p.user_id=$2',uid(order),user)
        if not row:
            raise Rejected('Платёж не найден.')
        return row

    async def create(self,user,order,*,test_session=False):
        row=await self.owned(user,order)
        if row['mode']=='demo':
            if not (self.cfg.topup_mode=='test' and user==row['user_id']
                    and row['chat_id'] in self.cfg.admin_ids and test_session):
                raise Rejected('Тестовый запуск недоступен.')
            if not self.client.cfg.enabled:
                raise Rejected('Тестовый платёжный транспорт не подключён.')
        elif not self.enabled():
            raise Rejected('Пополнение пока не подключено.')
        if str(row['merchant_id'])!=str(uid(self.client.cfg.merchant)):
            raise Rejected('Заказ выставлен для другого магазина.')
        if row['state']=='new' and row['expires_at']<=datetime.now(timezone.utc):
            await self.pool.execute("UPDATE topup_orders SET state='expired' WHERE payment_id=$1 AND state='new'",row['id'])
            return await self.owned(user,row['id'])
        claimed=await self.pool.fetchval("""UPDATE topup_orders SET state='creating',next_check_at=now()+interval '1 minute'
            WHERE payment_id=$1 AND state='new' AND expires_at>now() RETURNING payment_id""",row['id'])
        if claimed:
            try:
                remote,url,expires=await self.client.checkout(row['id'],row['chat_id'],row['amount'])
                async with self.pool.acquire() as conn,conn.transaction():
                    await conn.execute("""UPDATE payments SET remote_id=$2,checkout_url=$3,creation_state='created'
                        WHERE id=$1""",row['id'],remote,url)
                    await conn.execute("""UPDATE topup_orders SET state=CASE WHEN state='creating' THEN 'pending' ELSE state END,
                        expires_at=$2,next_check_at=now() WHERE payment_id=$1""",row['id'],expires)
            except Exception as error:
                rejected=isinstance(error,PaymentInvalid) or getattr(error,'http_status',None) in (400,401,403,422)
                await self.pool.execute("""UPDATE topup_orders SET state=$2,last_error=$3
                    WHERE payment_id=$1 AND state='creating'""",row['id'],
                    'error' if rejected else 'unknown','create_rejected' if rejected else 'create_outcome_unknown')
                await self.pool.execute("UPDATE payments SET creation_state='uncertain' WHERE id=$1 AND remote_id IS NULL",row['id'])
                if rejected:
                    raise Rejected('Платёж отклонён. Обратитесь в поддержку.') from None
                raise Rejected('Исход создания платежа неизвестен. Проверяем состояние, повторного платежа не создаём.') from None
        return await self.owned(user,row['id'])

    async def check(self,user,order):
        row=await self.owned(user,order)
        if row['remote_id']:
            await self.sync(row['remote_id'])
        elif row['state'] in ('creating','unknown'):
            await self.recover(row)
        return await self.owned(user,row['id'])

    async def recover(self,row):
        remote=await self.client.find(row['id'],row['created_at'])
        if remote:
            await self.sync(remote)
        # An empty or delayed export is not evidence that creation never happened.

    async def sync(self,remote,event=None):
        remote=uid(remote)
        async with self.pool.acquire() as conn:
            lock='topup-sync:'+str(remote)
            await conn.execute('SELECT pg_advisory_lock(hashtextextended($1,0))',lock)
            try:
                status=await self.client.status(remote)
                try:
                    order=uid(status['payload'])
                    if uid(status['id'])!=remote:
                        raise PaymentInvalid('Transaction identity mismatch')
                    merchant=uid(status.get('merchantId',status.get('mechantId')))
                    minor=kopecks(status['paymentDetails']['amount'])
                    currency=status['paymentDetails']['currency']
                    state=status['status']
                    if state not in STATES:
                        raise PaymentInvalid('Unknown payment state')
                except (KeyError,TypeError,Rejected):
                    raise PaymentInvalid('Malformed canonical status') from None
                row=await conn.fetchrow(ORDER+' WHERE p.id=$1',order)
                if not row or merchant!=row['merchant_id'] or str(merchant)!=str(uid(self.client.cfg.merchant)):
                    raise PaymentInvalid('Merchant/order mismatch')
                if row['amount']!=minor or currency!='RUB' or row['remote_id'] not in (None,remote):
                    raise PaymentInvalid('Amount/currency/transaction mismatch')
                if event is not None and (uid(event['id'])!=remote or uid(event['payload'])!=order
                        or kopecks(event['amount'])!=minor or event['currency']!='RUB'):
                    raise PaymentInvalid('Callback mismatch')
                returned=None
                if state=='PARTIALLY_REFUNDED':
                    # Only authenticated callback/canonical refund totals are eligible.
                    value=status.get('refundedAmount')
                    if value is None and event and event.get('status')=='PARTIALLY_REFUNDED':
                        value=event.get('refundedAmount')
                    if value is not None:
                        returned=0 if Decimal(str(value))==0 else kopecks(value)
                        if returned>minor:
                            raise PaymentInvalid('Refund exceeds payment')
                elif state=='CHARGEBACKED':
                    returned=minor
                async with conn.transaction():
                    await conn.fetchrow('SELECT * FROM wallets WHERE user_id=$1 AND mode=$2 FOR UPDATE',row['user_id'],row['mode'])
                    row=await conn.fetchrow(ORDER+' WHERE p.id=$1 FOR UPDATE OF p,t',order)
                    await conn.execute("UPDATE payments SET remote_id=$2,remote_status=$3,creation_state='created' WHERE id=$1",order,remote,state)
                    credited=await conn.fetchval("SELECT EXISTS(SELECT 1 FROM ledger WHERE payment_id=$1 AND kind='topup')",order)
                    if state in ('CONFIRMED','PARTIALLY_REFUNDED') and row['returned_minor']<row['amount'] and not credited:
                        await self.svc.movement(conn,row['user_id'],row['mode'],'topup:'+str(remote),'topup',row['credits'],0,payment=order)
                        await self.repay(conn,row)
                        await conn.execute("UPDATE topup_orders SET notice_state='pending' WHERE payment_id=$1",order)
                        credited=True
                    target={'PENDING':'pending','CANCELED':'cancelled','CONFIRMED':'paid',
                            'PARTIALLY_REFUNDED':'paid','CHARGEBACKED':'refunded','DISPUTED':'review'}[state]
                    if state=='PENDING' and row['expires_at']<=datetime.now(timezone.utc):
                        target='expired'
                    if state=='PARTIALLY_REFUNDED' and returned is None:
                        target='review'
                    if returned is not None and returned>row['returned_minor']:
                        await self.reverse(conn,row,returned,credited)
                    if row['returned_minor']==row['amount']:
                        target='refunded'
                    if state in ('PENDING','CANCELED') and credited:
                        target=row['state'] if row['state']!='paid' else 'review'
                    await conn.execute("""UPDATE topup_orders SET state=$2,last_error=NULL WHERE payment_id=$1""",order,target)
                    await conn.execute("""UPDATE payments SET status=$2,charge_id=$3 WHERE id=$1""",
                                       order,'succeeded' if target=='paid' else 'refunded' if target=='refunded' else
                                       'review' if target=='review' else row['status'],'platega:'+str(remote) if credited else row['charge_id'])
                    if event is not None:
                        await conn.execute("""INSERT INTO payment_callback_events(provider,remote_id,status)
                            VALUES('platega',$1,$2)""",remote,event['status'])
                return target
            finally:
                await conn.execute('SELECT pg_advisory_unlock(hashtextextended($1,0))',lock)

    async def repay(self,conn,row):
        debt=await conn.fetchval('SELECT amount FROM wallet_debts WHERE user_id=$1 AND mode=$2 FOR UPDATE',row['user_id'],row['mode'])
        paid=min(debt or 0,row['credits'])
        if paid:
            await self.svc.movement(conn,row['user_id'],row['mode'],'topup-debt:'+str(row['id']),
                                    'topup_debt_repay',-paid,0,payment=row['id'])
            await conn.execute('UPDATE wallet_debts SET amount=amount-$3 WHERE user_id=$1 AND mode=$2',row['user_id'],row['mode'],paid)

    async def reverse(self,conn,row,returned,credited):
        tokens=ceil(Fraction(row['credits'])*returned/row['amount'])
        delta=tokens-row['returned_tokens']
        available=await conn.fetchval('SELECT available FROM wallets WHERE user_id=$1 AND mode=$2',row['user_id'],row['mode'])
        debit=min(delta,available) if credited else 0
        debt=delta-debit if credited else 0
        if debit:
            await self.svc.movement(conn,row['user_id'],row['mode'],f"topup-reverse:{row['id']}:{returned}",
                                    'topup_reversal',-debit,0,payment=row['id'])
        if debt:
            await conn.execute("""INSERT INTO wallet_debts VALUES($1,$2,$3)
                ON CONFLICT(user_id,mode) DO UPDATE SET amount=wallet_debts.amount+excluded.amount""",row['user_id'],row['mode'],debt)
        await conn.execute('INSERT INTO topup_adjustments(payment_id,returned_minor,tokens,debited,debt) VALUES($1,$2,$3,$4,$5)',
                           row['id'],returned,delta,debit,debt)
        await conn.execute('UPDATE topup_orders SET returned_minor=$2,returned_tokens=$3 WHERE payment_id=$1',row['id'],returned,tokens)

    async def callback(self,headers,body):
        if not self.client.authenticated(headers):
            raise PermissionError('Unauthorized')
        try:
            event=json.loads(body,parse_float=Decimal)
            if not isinstance(event,dict) or event.get('status') not in STATES-{'PENDING'}:
                raise PaymentInvalid('Unsupported callback')
            uid(event['payload'])
            kopecks(event['amount'])
            if event['currency']!='RUB':
                raise PaymentInvalid('Wrong callback currency')
            return await self.sync(uid(event['id']),event)
        except (KeyError,ValueError,TypeError,Rejected):
            raise PaymentInvalid('Malformed callback') from None

    async def tick(self):
        if self.cfg.topup_mode=='off' or not self.client.cfg.enabled:
            return
        row=await self.pool.fetchrow("""UPDATE topup_orders t SET next_check_at=now()+interval '60 seconds'
            FROM (SELECT payment_id FROM topup_orders WHERE next_check_at<=now() AND state<>'new'
                  ORDER BY next_check_at FOR UPDATE SKIP LOCKED LIMIT 1) due
            WHERE t.payment_id=due.payment_id RETURNING t.payment_id""")
        if not row:
            return
        order=await self.pool.fetchrow(ORDER+' WHERE p.id=$1',row['payment_id'])
        try:
            if order['remote_id']:
                await self.sync(order['remote_id'])
            elif order['state'] in ('creating','unknown'):
                await self.recover(order)
        except (PaymentInvalid,PaymentUnknown,Rejected):
            await self.pool.execute("UPDATE topup_orders SET last_error='reconcile_unavailable' WHERE payment_id=$1",order['id'])

    async def notify(self,bot,keyboard=None):
        # Claim before send. A lost Telegram response is never silently replayed.
        row=await self.pool.fetchrow("""UPDATE topup_orders t SET notice_state='sending',notice_at=now()+interval '60 seconds'
            FROM (SELECT payment_id FROM topup_orders WHERE notice_state='pending' AND state='paid' AND notice_at<=now()
                  ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1) due
            WHERE t.payment_id=due.payment_id RETURNING t.payment_id""")
        if not row:
            return
        order=await self.pool.fetchrow(ORDER+' WHERE p.id=$1',row['payment_id'])
        wallet=await self.pool.fetchrow('SELECT available,reserved FROM wallets WHERE user_id=$1 AND mode=$2',order['user_id'],order['mode'])
        rate=await self.pool.fetchrow('SELECT * FROM task_ruble_equivalent WHERE id=1')
        balance=display(wallet['available'])+' токенов'
        if rate:
            rub=Decimal(wallet['available'])*rate['rubles']/rate['bot_amount']
            balance+=' ≈ '+format(rub.quantize(Decimal('.01')),'f')+' ₽'
        text=('Тестовый кошелёк\n' if order['mode']=='demo' else '')+(
            f"✅ Баланс пополнен\nЗачислено {display(order['credits'])} токенов\nБаланс {balance}")
        try:
            markup=await keyboard(order['chat_id']) if keyboard and order['mode']=='live' else None
            await bot.send_message(order['chat_id'],text,reply_markup=markup)
        except TelegramRetryAfter as error:
            await self.pool.execute("UPDATE topup_orders SET notice_state='pending',notice_at=now()+$2*interval '1 second' WHERE payment_id=$1",
                                    order['id'],int(error.retry_after))
            return
        except Exception:
            await self.pool.execute("UPDATE topup_orders SET notice_state='unknown' WHERE payment_id=$1",order['id'])
            raise
        await self.pool.execute("UPDATE topup_orders SET notice_state='sent' WHERE payment_id=$1",order['id'])

    async def loop(self,bot,keyboard):
        while True:
            try:
                await self.pool.execute("""UPDATE topup_orders SET notice_state='unknown'
                    WHERE notice_state='sending' AND notice_at<=now()""")
                await self.tick()
                await self.notify(bot,keyboard)
            except Exception as error:
                LOG.warning('topup worker error: %s',type(error).__name__)
            await asyncio.sleep(2)

