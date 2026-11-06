import asyncio,json,uuid
from pathlib import Path
from dataclasses import replace
import httpx,pytest
from elevenbot.config import Config
from elevenbot.providers import ClodexProvider,UnknownOutcome,DefinitiveFailure,MockProvider,catalog
from elevenbot.storage import Storage
from elevenbot.core import uid,Rejected

@pytest.mark.parametrize('value',['bad','',None,'../x'])
def test_bad_identifier(value):
    with pytest.raises(Rejected):uid(value)

@pytest.mark.parametrize('key',['../secret.mp3','/tmp/a.mp3','http://a.mp3','bad.mp3'])
def test_storage_path(tmp_path,key):
    with pytest.raises((ValueError,IndexError)):Storage(tmp_path).path(key)

def test_audio_storage(tmp_path):
    s=Storage(tmp_path);data=Path('assets/demo.mp3').read_bytes();j,f=uuid.uuid4(),uuid.uuid4()
    r=s.save(j,f,data)
    assert s.path(r['key']).read_bytes()==data
    assert (s.path(r['key']).stat().st_mode&0o777)==0o600

@pytest.mark.parametrize('data',[b'',b'not audio'*100,b'ID3'+b'x'*300])
def test_invalid_audio(tmp_path,data):
    with pytest.raises(Exception):Storage(tmp_path).save(uuid.uuid4(),uuid.uuid4(),data)
    assert not list(tmp_path.glob('*.tmp'))

@pytest.mark.parametrize('status,mime',[(500,'audio/mpeg'),(429,'application/json'),(401,'application/json'),(302,'audio/mpeg'),(200,'text/html')])
async def test_A21_provider_errors(status,mime):
    calls=[]
    def handler(req):calls.append(req);return httpx.Response(status,headers={'Content-Type':mime,'Location':'http://127.0.0.1/private'},content=b'x')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        p=ClodexProvider(Config(),c)
        with pytest.raises(UnknownOutcome):await p.synthesize('private','id',1.0)
    assert len(calls)==1

async def test_provider_contract_stub():
    data=Path('assets/demo.mp3').read_bytes();seen=[]
    def handler(req):
        seen.append(req)
        assert req.url==httpx.URL('https://clodex.xyz/v1/audio/speech')
        assert json.loads(req.content)=={'model':'documented_model','voice':'id','input':'test'}
        return httpx.Response(200,headers={'Content-Type':'audio/mpeg'},content=data)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        p=ClodexProvider(replace(Config(),clodex_model='documented_model'),c)
        assert await p.synthesize('test','id',1.0)==data
        with pytest.raises(DefinitiveFailure):await p.synthesize('test','id',.9)
    assert len(seen)==1

async def test_network_timeout_no_retry():
    calls=[]
    def handler(req):calls.append(req);raise httpx.ReadTimeout('fake')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(UnknownOutcome):await ClodexProvider(Config(),c).synthesize('test','id',1.0)
    assert len(calls)==1

async def test_oversized_provider():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,headers={'Content-Type':'audio/mpeg'},content=b'x'*(20*1024*1024+1)))) as c:
        with pytest.raises(UnknownOutcome):await ClodexProvider(Config(),c).synthesize('test','id',1.0)

@pytest.mark.parametrize('mode,payments,generation',[('mock','true','false'),('clodex','false','true'),('bad','false','false')])
def test_config_fails_closed(monkeypatch,mode,payments,generation):
    monkeypatch.setenv('PROVIDER_MODE',mode);monkeypatch.setenv('PAYMENTS_ENABLED',payments);monkeypatch.setenv('GENERATION_ENABLED',generation)
    with pytest.raises(ValueError):Config.env()

def test_core_independence():
    import ast
    for n in ['core.py','worker.py','db.py','providers.py','storage.py']:
        tree=ast.parse((Path('src/elevenbot')/n).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):assert 'aiogram' not in (node.module or '')
            if isinstance(node,ast.Import):assert all('aiogram' not in a.name for a in node.names)

def test_migrations_parse():
    from pglast import parse_sql,parse_plpgsql
    for f in Path('migrations').glob('*.sql'):
        assert parse_sql(f.read_text());parse_plpgsql(f.read_text())
