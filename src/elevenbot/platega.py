"""Platega payment adapter. No public checkout or paid requests enabled by default.
Amounts in the application are integer kopecks; boundary JSON uses exact Decimal.
Callbacks are authenticated AND canonical status is re-read server-to-server.
"""
import asyncio,hashlib,hmac,json,uuid
from dataclasses import dataclass
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from urllib.parse import urlparse
import httpx
from .core import Service,Rejected,uid

class PaymentUnknown(Exception):pass
class PaymentInvalid(Exception):pass

def kopecks(value):
    if isinstance(value,bool):raise PaymentInvalid('Invalid amount')
    try:d=Decimal(str(value))
    except (InvalidOperation,TypeError,ValueError):raise PaymentInvalid('Invalid amount') from None
    if not d.is_finite() or d<=0 or d>Decimal('10000000') or d*100!=(d*100).to_integral_value():raise PaymentInvalid('Invalid amount')
    return int(d*100)

def money_json(value):
    if isinstance(value,Decimal):return format(value,'f')
    return json.dumps(value,ensure_ascii=False,separators=(',',':'))

def encode_payload(value):
    # Decimal must be a JSON number, not a binary float or quoted string.
    if isinstance(value,dict):return '{'+','.join(json.dumps(k)+':'+encode_payload(v) for k,v in value.items())+'}'
    if isinstance(value,list):return '['+','.join(encode_payload(v) for v in value)+']'
    return money_json(value)

@dataclass(frozen=True)
class PlategaConfig:
    merchant: str=''
    secret: str=''
    enabled: bool=False
    return_url: str=''
    failed_url: str=''
    method: int=2

class PlategaClient:
    def __init__(self,cfg,client=None):
        self.cfg=cfg;self.client=client or httpx.AsyncClient(timeout=httpx.Timeout(15,connect=5),follow_redirects=False)
    def authenticated(self,headers):
        return bool(self.cfg.merchant and self.cfg.secret and
            hmac.compare_digest(headers.get('X-MerchantId','').encode(),self.cfg.merchant.encode()) and
            hmac.compare_digest(headers.get('X-Secret','').encode(),self.cfg.secret.encode()))
    async def request(self,method,path,payload=None,*,allow_list=False):
        for attempt in range(3 if method=='GET' else 1):
            try:
                return await self.request_once(method,path,payload,allow_list=allow_list)
            except PaymentUnknown as error:
                if method!='GET' or attempt==2:
                    raise
                await asyncio.sleep(getattr(error,'retry_after',2**attempt))
    async def request_once(self,method,path,payload=None,*,allow_list=False):
        if not self.cfg.enabled:raise PaymentInvalid('Platega disabled')
        if not self.cfg.merchant or not self.cfg.secret:raise PaymentInvalid('Missing credentials')
        try:
            async with self.client.stream(method,'https://app.platega.io'+path,
                headers={'X-MerchantId':self.cfg.merchant,'X-Secret':self.cfg.secret,'Content-Type':'application/json'},
                content=encode_payload(payload).encode() if payload is not None else None) as r:
                if r.status_code!=200:
                    error=PaymentUnknown('Platega HTTP outcome')
                    error.http_status=r.status_code
                    raw=r.headers.get('retry-after','')
                    if r.status_code==429 and raw.isdigit():
                        error.retry_after=min(120,max(1,int(raw)))
                    raise error
                data=bytearray()
                async for chunk in r.aiter_bytes():
                    data.extend(chunk)
                    if len(data)>262144:raise PaymentUnknown('Response limit')
                result=json.loads(data,parse_float=Decimal)
                if not isinstance(result,dict) and not (allow_list and isinstance(result,list)):raise PaymentUnknown('Invalid response')
                return result
        except (httpx.HTTPError,ValueError):raise PaymentUnknown('Platega transport/response') from None
    async def create(self,order,external_user_id,amount_minor):
        remote,url,_=await self.create_details(order,external_user_id,amount_minor)
        return remote,url
    async def create_details(self,order,external_user_id,amount_minor):
        if type(amount_minor) is not int or not 1<=amount_minor<=1000000000:raise PaymentInvalid('Invalid tariff')
        for url in [self.cfg.return_url,self.cfg.failed_url]:
            parts=urlparse(url)
            if parts.scheme!='https' or not parts.hostname or parts.username or parts.password:raise PaymentInvalid('HTTPS return URL required')
        body={'paymentMethod':self.cfg.method,'paymentDetails':{'amount':Decimal(amount_minor)/100,'currency':'RUB'},
              'description':'DarkFlow | Gen balance top-up','return':self.cfg.return_url.replace('{order_id}',str(order)),'failedUrl':self.cfg.failed_url.replace('{order_id}',str(order)),'payload':str(order),
              'metadata':{'userId':str(external_user_id),'user_email':f'{external_user_id}@telegram.org'}}
        r=await self.request('POST','/transaction/process',body)
        try:remote=uuid.UUID(r['transactionId']);url=r['redirect'];parts=urlparse(url)
        except (KeyError,ValueError,TypeError):raise PaymentUnknown('Invalid creation response') from None
        if parts.scheme!='https' or not parts.hostname or parts.username or parts.password:raise PaymentUnknown('Invalid checkout URL')
        if r.get('merchantId') and str(uid(r['merchantId']))!=str(uid(self.cfg.merchant)):
            raise PaymentUnknown('Creation merchant mismatch')
        return remote,url,r.get('expiresIn')
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

    async def status(self,remote):return await self.request('GET','/transaction/'+str(uid(remote)))
    async def refund(self,remote):
        # No request body; accepted != completed. No POST retries.
        return await self.request('POST','/transaction/'+str(uid(remote))+'/cancel')
    async def close(self):await self.client.aclose()

class PlategaPayments:
    def __init__(self,pool,app_cfg,client):
        self.pool=pool;self.svc=Service(pool,app_cfg);self.client=client
        self._reconcile_cursor=(None,None)
    async def create_order(self,u,amount_minor=10000,credits=10000):
        # Trusted external checkout use case, not exposed as a Telegram payment button.
        if not self.client.cfg.enabled or self.svc.cfg.mode=='mock' or not self.svc.cfg.payments_enabled or self.svc.cfg.payment_backend!='platega':raise PaymentInvalid('Real payments disabled')
        if type(amount_minor) is not int or not 1<=amount_minor<=1000000000 or type(credits) is not int or credits<=0:raise PaymentInvalid('Invalid tariff')
        p=uuid.uuid4()
        async with self.pool.acquire() as c,c.transaction():
            await self.svc.authorize(c,u)
            if await c.fetchval('SELECT halted FROM settings WHERE id=1 FOR SHARE'):raise PaymentInvalid('Intake halted')
            external=await c.fetchval("SELECT external_id FROM identities WHERE user_id=$1 AND platform='telegram'",u)
            if external is None:raise PaymentInvalid('Buyer identity missing')
            await c.execute("INSERT INTO payments(id,user_id,amount,credits,currency,tariff,status,provider,creation_state) VALUES($1,$2,$3,$4,'RUB','platega-v1','pending','platega','sending')",p,u,amount_minor,credits)
        # Persist attempt BEFORE network. Crash/timeout cannot cause automatic recreation.
        try:remote,url=await self.client.create(p,external,amount_minor)
        except Exception:
            async with self.pool.acquire() as c:await c.execute("UPDATE payments SET creation_state='uncertain' WHERE id=$1",p)
            raise
        async with self.pool.acquire() as c,c.transaction():
            await c.execute("UPDATE payments SET remote_id=$2,checkout_url=$3,creation_state='created' WHERE id=$1",p,remote,url)
        return p,url
    async def sync(self,remote,event=None,*,expected_order=None):
        remote=uid(remote)
        # Serializes canonical GET + commit, prevents a slower stale snapshot winning.
        async with self.pool.acquire() as c:
            lock=hashlib.sha256(('platega:'+str(remote)).encode()).digest()[:8]
            lock=int.from_bytes(lock,'big',signed=True)
            await c.execute('SELECT pg_advisory_lock($1)',lock)
            try:
                r=await self.client.status(remote)
                try:
                    if uid(r['id'])!=remote:raise PaymentInvalid('Wrong remote ID')
                    p=uid(r['payload']);amount=kopecks(r['paymentDetails']['amount']);currency=r['paymentDetails']['currency'];status=r['status']
                    if expected_order is not None and p!=expected_order:
                        raise PaymentInvalid('Recovered order mismatch')
                    if event is not None and (
                        ('payload' in event and uid(event['payload']) != p)
                        or ('amount' in event and kopecks(event['amount']) != amount)
                        or ('currency' in event and event['currency'] != currency)
                    ):
                        raise PaymentInvalid('Callback mismatch')
                    if await c.fetchval('SELECT EXISTS(SELECT 1 FROM topup_orders WHERE payment_id=$1)',p):
                        from .topups import Topups
                        return await Topups(self.pool,self.svc.cfg,self.client).sync(remote,expected_order=p)
                    merchant=r.get('mechantId',r.get('merchantId'))
                    if merchant and str(uid(merchant))!=str(uid(self.client.cfg.merchant)):raise PaymentInvalid('Merchant mismatch')
                except (KeyError,TypeError,Rejected):raise PaymentInvalid('Invalid status response') from None
                if status not in ('PENDING','CONFIRMED','CANCELED','DISPUTED','PARTIALLY_REFUNDED','CHARGEBACKED'):raise PaymentInvalid('Unknown status')
                async with c.transaction():
                    row=await c.fetchrow("SELECT * FROM payments WHERE id=$1 AND provider='platega' FOR UPDATE",p)
                    if not row or row['amount']!=amount or row['currency']!=currency or (row['remote_id'] and row['remote_id']!=remote):raise PaymentInvalid('Order mismatch')
                    await c.execute("UPDATE payments SET remote_id=$2,creation_state='created',remote_status=$3 WHERE id=$1",p,remote,status)
                    credited=await c.fetchval("SELECT EXISTS(SELECT 1 FROM ledger WHERE payment_id=$1 AND kind='payment')",p)
                    if status=='CONFIRMED':
                        if row['status'] in ('refunded','refunding'):return 'review'
                        if not credited:
                            await self.svc.movement(c,row['user_id'],'live',f'platega:{remote}','payment',row['credits'],0,payment=p)
                        await c.execute("UPDATE payments SET charge_id=$2,status='succeeded' WHERE id=$1",p,'platega:'+str(remote))
                    elif status=='CHARGEBACKED' and row['status']=='refunded':
                        return status
                    elif status=='CHARGEBACKED' and row['status']=='refunding':
                        await self.svc.movement(c,row['user_id'],'live',f'refund:{p}','refund',0,-row['credits'],payment=p)
                        await c.execute("UPDATE payments SET status='refunded' WHERE id=$1",p)
                    elif status in ('DISPUTED','PARTIALLY_REFUNDED','CHARGEBACKED') or (status=='CANCELED' and credited):
                        await c.execute("UPDATE payments SET status='review' WHERE id=$1 AND status NOT IN ('refunded','refunding')",p)
                        await c.execute('UPDATE users SET blocked=true WHERE id=$1',row['user_id'])
                        await c.execute('UPDATE settings SET halted=true WHERE id=1')
                        await c.execute("INSERT INTO audit_events(action,target) VALUES('platega_review',$1)",p)
                    # PENDING/CANCELED never mint credits, and do not undo prior confirmed funds.
                    return status
            finally:await c.execute('SELECT pg_advisory_unlock($1)',lock)
    async def callback(self,headers,body):
        if not self.client.authenticated(headers):raise PermissionError('Unauthorized')
        try:
            event=json.loads(body,parse_float=Decimal);remote=uid(event['id'])
            if event['status'] not in ('CONFIRMED','CANCELED','DISPUTED','PARTIALLY_REFUNDED','CHARGEBACKED'):raise ValueError()
        except (KeyError,ValueError,TypeError,Rejected):raise PaymentInvalid('Malformed callback') from None
        result=await self.sync(remote,event)
        async with self.pool.acquire() as c:await c.execute("INSERT INTO payment_callback_events(provider,remote_id,status) VALUES('platega',$1,$2)",remote,event['status'])
        return result
    async def reconcile_pending(self,limit=100):
        if not 1<=limit<=1000:raise PaymentInvalid('Invalid reconciliation limit')
        async with self.pool.acquire() as c:
            rows=await c.fetch("""
                SELECT p.id,p.remote_id,p.created_at FROM payments p
                WHERE p.provider='platega' AND p.status IN ('pending','refunding','review')
                AND (p.remote_id IS NOT NULL OR (p.creation_state IN ('sending','uncertain')
                    AND NOT EXISTS (SELECT 1 FROM topup_orders WHERE payment_id=p.id)))
                ORDER BY coalesce((p.created_at,p.id)<=($2::timestamptz,$3::uuid),false),p.created_at,p.id
                LIMIT $1
                """,limit,*self._reconcile_cursor)
        checked=0;failed=0
        for row in rows:
            # Continue past empty/failed lookups next time, wrapping at the end.
            # A new service starts at the oldest order; payment state is unchanged.
            self._reconcile_cursor=(row['created_at'],row['id'])
            try:
                remote=row['remote_id']
                if remote is None:
                    remote=await self.client.find(row['id'],row['created_at'])
                    if remote is None:
                        continue
                await self.sync(remote,expected_order=row['id'])
                checked+=1
            except (PaymentUnknown,PaymentInvalid):failed+=1
        return {'checked':checked,'failed':failed,'limit':limit}

    async def refund(self,p):
        if not self.client.cfg.enabled or self.svc.cfg.mode=='mock':raise PaymentInvalid('Refund disabled')
        async with self.pool.acquire() as c:
            row=await c.fetchrow("SELECT * FROM payments WHERE id=$1 AND provider='platega'",uid(p))
        if not row or not row['remote_id']:raise PaymentInvalid('Missing remote payment')
        await self.svc.prepare_refund(p,provider='platega')
        # Pending/unknown refund retains reservation; repeated prepare_refund rejects.
        r=await self.client.refund(row['remote_id'])
        if str(r.get('transactionId'))!=str(row['remote_id']):raise PaymentUnknown('Refund identity mismatch')
        if r.get('refundOperationId'):
            async with self.pool.acquire() as c:await c.execute('UPDATE payments SET refund_remote_id=$2 WHERE id=$1',uid(p),uid(r['refundOperationId']))
        return {'pending':True}  # Completion only from canonical CHARGEBACKED state.
