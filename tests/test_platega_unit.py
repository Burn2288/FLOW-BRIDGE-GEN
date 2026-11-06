import uuid,json
from decimal import Decimal
from dataclasses import replace
from types import SimpleNamespace
import pytest,httpx
from aiohttp import web,ClientSession
from elevenbot.platega import PlategaClient,PlategaConfig,kopecks,PaymentInvalid,PaymentUnknown
from elevenbot.platega_web import create_app
from elevenbot.config import Config

MERCHANT=str(uuid.UUID(int=88));REMOTE=uuid.UUID(int=89)
CFG=PlategaConfig(merchant=MERCHANT,secret='local-fixture-only',enabled=True,return_url='https://example.org/success',failed_url='https://example.org/fail')

@pytest.mark.parametrize('value,expected',[('100.01',10001),(100,10000),(Decimal('0.01'),1),('1500.25',150025)])
def test_exact_money(value,expected):assert kopecks(value)==expected

@pytest.mark.parametrize('value',[True,0,-1,'nan','Infinity','0.001','bad',None,'10000001'])
def test_bad_money(value):
    with pytest.raises(PaymentInvalid):kopecks(value)

async def test_create_contract_and_exact_serialization():
    calls=[]
    def handler(r):
        calls.append(r);data=json.loads(r.content,parse_float=Decimal)
        assert data['paymentDetails']=={'amount':Decimal('1500.25'),'currency':'RUB'}
        assert data['metadata']['user_email']=='123@telegram.org'
        assert 'id' not in data
        assert r.headers['X-MerchantId']==MERCHANT
        return httpx.Response(200,json={'transactionId':str(REMOTE),'redirect':'https://pay.platega.io/pay'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        remote,url=await PlategaClient(CFG,c).create(uuid.uuid4(),123,150025)
        assert remote==REMOTE and url.startswith('https:')
    assert len(calls)==1

@pytest.mark.parametrize('code',[302,401,429,500])
async def test_no_post_retry(code):
    calls=[]
    def handler(r):calls.append(r);return httpx.Response(code,headers={'Location':'http://127.0.0.1/'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(PaymentUnknown):await PlategaClient(CFG,c).create(uuid.uuid4(),123,10000)
    assert len(calls)==1

async def test_timeout_not_recreated():
    calls=[]
    def handler(r):calls.append(r);raise httpx.ReadTimeout('fixture')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(PaymentUnknown):await PlategaClient(CFG,c).create(uuid.uuid4(),123,10000)
    assert len(calls)==1

async def test_full_refund_bodyless_pending():
    def handler(r):
        assert r.method=='POST' and r.url.path.endswith('/cancel') and not r.content
        return httpx.Response(200,json={'transactionId':str(REMOTE),'accepted':True,'refundOperationId':str(uuid.UUID(int=90))})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        r=await PlategaClient(CFG,c).refund(REMOTE);assert r['accepted']

@pytest.mark.parametrize('headers,expected',[
 ({},False),({'X-MerchantId':MERCHANT,'X-Secret':'wrong'},False),
 ({'X-MerchantId':MERCHANT,'X-Secret':'local-fixture-only'},True)])
def test_callback_auth(headers,expected):
    assert PlategaClient(CFG).authenticated(headers)==expected

async def test_local_callback_listener_auth_and_ack():
    class Payments:
        client=PlategaClient(CFG)
        def __init__(self):self.calls=0
        async def callback(self,headers,body):self.calls+=1;assert json.loads(body)['id']==str(REMOTE)
    payments=Payments();runner=web.AppRunner(create_app(payments),access_log=None);await runner.setup()
    site=web.TCPSite(runner,'127.0.0.1',0);await site.start();port=site._server.sockets[0].getsockname()[1]
    try:
        async with ClientSession() as c:
            url=f'http://127.0.0.1:{port}/payments/platega/callback'
            async with c.post(url,json={'id':str(REMOTE)}) as r:assert r.status==401
            async with c.post(url,json={'id':str(REMOTE)},headers={'X-MerchantId':MERCHANT,'X-Secret':'local-fixture-only'}) as r:assert r.status==200
        assert payments.calls==1
    finally:await runner.cleanup();await payments.client.close()

@pytest.mark.parametrize('mode,allow,payments,base',[
 ('clodex','true','false','http://127.0.0.1:1234'),
 ('mock','false','false','http://127.0.0.1:1234'),
 ('mock','true','false','https://evil.example'),
 ('mock','true','true','http://127.0.0.1:1234')])
def test_local_telegram_transport_guard(monkeypatch,mode,allow,payments,base):
    monkeypatch.setenv('PROVIDER_MODE',mode);monkeypatch.setenv('ALLOW_LOCAL_TELEGRAM_STUB',allow)
    monkeypatch.setenv('TELEGRAM_API_BASE',base);monkeypatch.setenv('PAYMENTS_ENABLED',payments)
    with pytest.raises(ValueError):Config.env()

async def test_http_clients_support_socks_environment(monkeypatch):
    from elevenbot.providers import ClodexProvider
    monkeypatch.setenv('ALL_PROXY','socks5h://127.0.0.1:12345')
    for cls,cfg in [(PlategaClient,CFG),(ClodexProvider,Config())]:
        c=cls(cfg);await c.close()
