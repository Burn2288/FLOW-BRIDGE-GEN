"""Protocol/transport checks; synthetic HTTP responses are NOT live generation proof."""
import copy,time
from dataclasses import replace
import httpx,pytest
from elevenbot.aggregate import ClodexAdapter,ProviderRegistry,DiscoveryError,prepare_request,public_metadata,documented_functions
from elevenbot.discovery import SnapshotStore
from elevenbot.config import Config
from elevenbot.demo import DemoService,DemoApp
from test_ui import Bot,event

PRICING={'success':True,'data':[{'model_name':'unseen-model','supported_endpoint_types':['openai'],'model_price':0.5}],
 'supported_endpoint':{'openai':{'method':'POST','path':'/v1/chat/completions'}}}
DOCS={'schema_version':1,'sections':[{'id':'example','title':'Example','details':['POST /v1/responses','POST /v1/images/generations','POST /v1/audio/speech','GET /v1/new-catalogue'],'links':[],'examples':[]}]}

def transport(pricing=None,key=False,status=200,calls=None):
 def handle(r):
  if calls is not None:calls.append(r)
  assert r.method=='GET' and r.url.host=='clodex.xyz'
  if r.url.path=='/v1/models':
   assert r.headers['Authorization']=='Bearer test-only'
   return httpx.Response(status,json={'data':[{'id':'unseen-model'}]})
  assert 'Authorization' not in r.headers
  return httpx.Response(200,json=DOCS if r.url.path=='/docs-v2.json' else pricing or PRICING)
 return httpx.MockTransport(handle)

async def collect(pricing=None,key='',status=200):
 async with httpx.AsyncClient(transport=transport(pricing,key,status)) as client:
  reg=ProviderRegistry();reg.register('clodex',ClodexAdapter(key,client=client));return await reg.collect()

async def test_public_refresh_and_new_models_without_brand_mapping(tmp_path):
 first=await collect();p=copy.deepcopy(PRICING);p['data'].append({'model_name':'another-brand','supported_endpoint_types':['openai-video']})
 second=await collect(p)
 assert len(second['models'])==2 and first['version']!=second['version']
 assert all(not m['operations'] and m['availability']=='public_only' for m in second['models'])
 assert not second['models'][0]['public_pricing']['verified_for_billing']
 store=SnapshotStore(tmp_path/'snapshot.json');store.write(second);assert store.read()==second

async def test_authenticated_inventory_not_public_union_and_no_key_leak():
 p=copy.deepcopy(PRICING);p['data'].append({'model_name':'not-for-this-key'})
 calls=[]
 async with httpx.AsyncClient(transport=transport(p,True,calls=calls)) as client:
  data=await ClodexAdapter('test-only',client=client).collect()
 assert [m['id'] for m in data['models']]==['unseen-model']
 assert data['scope']=='key_available' and len(calls)==3

@pytest.mark.parametrize('status',[401,403,429,500])
async def test_auth_failure_does_not_downgrade_or_replace_cache(tmp_path,status):
 store=SnapshotStore(tmp_path/'snapshot.json');old=await collect();store.write(old)
 async with httpx.AsyncClient(transport=transport(status=status)) as client:
  with pytest.raises(DiscoveryError):await ClodexAdapter('test-only',client=client).refresh(store)
 assert store.read()==old

@pytest.mark.parametrize('operation,fields,path',[('chat',{'prompt':'hello'},'/v1/chat/completions'),('responses',{'prompt':'hello'},'/v1/responses'),('images.generate',{'prompt':'draw'},'/v1/images/generations'),('audio.speech',{'text':'hello','voice':'known-id'},'/v1/audio/speech')])
async def test_generic_request_preview_only(operation,fields,path):
 data=await collect();r=prepare_request(data,'clodex',operation,'unseen-model',fields)
 assert r['path']==path and r['body']['model']=='unseen-model'
 assert not r['model_operation_verified'] and not r['paid_execution_enabled']
 with pytest.raises(DiscoveryError):prepare_request(data,'other',operation,'unseen-model',fields)
 with pytest.raises(DiscoveryError):prepare_request(data,'clodex',operation,'missing',fields)
 with pytest.raises(DiscoveryError):prepare_request(data,'clodex',operation,'unseen-model',dict(fields,arbitrary='bad'))
 data['fresh_until']=time.time()-1
 with pytest.raises(DiscoveryError):prepare_request(data,'clodex',operation,'unseen-model',fields)

async def test_new_operation_visible_but_cannot_execute():
 data=await collect();f=next(f for f in data['functions'] if f['path']=='/v1/new-catalogue')
 assert not f['request_preview_supported']
 with pytest.raises(DiscoveryError):prepare_request(data,'clodex',f['id'],'unseen-model',{})

async def test_multiple_provider_model_ids_are_isolated():
 class Fake:
  async def collect(self):return {'models':[{'id':'same','title':'same','operations':[]}],'functions':[],'scope':'public_only'}
 reg=ProviderRegistry();reg.register('one',Fake());reg.register('two',Fake());data=await reg.collect()
 assert {m['key'] for m in data['models']}=={'one:same','two:same'}
 with pytest.raises(DiscoveryError):reg.register('one',Fake())

@pytest.mark.parametrize('bad',[{}, {'success':True,'data':[None]}, {'success':True,'data':[{'model_name':'x'},{'model_name':'x'}]}, {'success':True,'data':[{'model_name':'x','model_price':'NaN'}]}])
def test_invalid_public_schema_fails_closed(bad):
 with pytest.raises(DiscoveryError):public_metadata(bad)

async def test_telegram_aggregate_preview_vertical_slice_and_cancel(tmp_path):
 data=await collect();path=tmp_path/'models.json';SnapshotStore(path).write(data)
 bot=Bot();svc=DemoService();app=DemoApp(replace(Config(),catalogue_path=str(path),admin_ids=(100,)),bot,svc)
 await app.handle(event('/start'));assert 'DarkFlow | Gen' in bot.sent[-1][0]
 await app.handle(event(callback='accept'))
 await app.handle(event('🌐 Агрегаторы'));assert 'Clodex' in bot.sent[-1][1].inline_keyboard[0][0].text
 await app.handle(event(callback=bot.sent[-1][1].inline_keyboard[0][0].callback_data))
 catalogue=next(b for row in bot.sent[-1][1].inline_keyboard for b in row if b.text=='Открыть каталог')
 await app.handle(event(callback=catalogue.callback_data))
 assert bot.sent[-1][0].startswith('clodex ·')
 await app.handle(event('🛠 Функции'))
 fi=next(i for i,f in enumerate(data['functions']) if f['id']=='chat')
 await app.handle(event(callback=f'fn:{data["version"]}:{fi}'))
 await app.handle(event(callback=f'choosefn:{data["version"]}:{fi}:0'))
 await app.handle(event(callback=f'bind:{data["version"]}:{fi}:0'))
 await app.handle(event('hello'))
 assert 'Запрос не отправлен' in bot.sent[-1][0] and 'hello' in bot.sent[-1][0]
 assert not svc.jobs and not svc.quotes
 await app.handle(event(callback=f'bind:{data["version"]}:{fi}:0'))
 await app.handle(event('/menu'));await app.handle(event('must not submit'))
 assert 'Выбери раздел' in bot.photos[-1][1]
 await app.handle(event(callback=f'bind:outdated:{fi}:0'))
 assert 'Каталог обновился' in bot.sent[-1][0]


def test_method_variants_templates_and_documentation_only():
 docs=copy.deepcopy(DOCS)
 docs['sections'][0]['details'] += ['GET /v1/audio/clones', 'POST /v1/audio/clones', 'GET /v1/audios/:task_id', 'POST /v1/audio/dubbing/upload/{init,chunk,complete}']
 docs['sections'].append({'id':'new-product','title':'Brand new functionality','summary':'No API contract yet'})
 functions=documented_functions(docs,PRICING)
 routes={(f['method'],f['path']) for f in functions}
 assert {('GET','/v1/audio/clones'),('POST','/v1/audio/clones'),('GET','/v1/audios/:task_id'),('POST','/v1/audio/dubbing/upload/complete')} <= routes
 f=next(f for f in functions if f['id']=='documentation-new-product')
 assert f['documentation_only'] and not f['request_preview_supported'] and f['path']==''
 with pytest.raises(DiscoveryError):documented_functions({'schema_version':1,'sections':[{'details':'bad'}]},PRICING)

async def test_metadata_updates_version_and_contract_tampering_rejected():
 first=await collect();p=copy.deepcopy(PRICING);p['data'][0]['model_price']=2
 second=await collect(p);assert first['version']!=second['version']
 fn=next(f for f in first['functions'] if f['id']=='chat');fn['path']='https://malicious.invalid'
 with pytest.raises(DiscoveryError):prepare_request(first,'clodex','chat','unseen-model',{'prompt':'hello'})

async def test_captured_real_public_schema_offline():
 import json
 from pathlib import Path
 root=Path(__file__).parent/'fixtures'/'clodex_public'
 pricing=json.loads((root/'pricing.json').read_text(encoding='utf-8'))
 docs=json.loads((root/'docs-v2.json').read_text(encoding='utf-8'))
 functions=documented_functions(docs,pricing);meta=public_metadata(pricing)
 assert len(meta)==154
 assert len([f for f in functions if not f.get('documentation_only')])==23
 assert len([f for f in functions if f.get('documentation_only')])==22
 assert all(not f['paid_execution_enabled'] for f in functions)
 assert next(f for f in functions if f['id']=='documentation-video')['path']==''
 assert all(not p['public_pricing']['verified_for_billing'] for p in meta.values())

async def test_provider_menu_isolation_with_identical_model_names(tmp_path):
 class Fake:
  def __init__(self,op):self.op=op
  async def collect(self):return {'models':[{'id':'same','title':'same','operations':[],'availability':'public_only'}],
   'functions':[{'id':self.op,'title':self.op,'method':'POST','path':'/v1/example','request_preview_supported':False}], 'scope':'public_only'}
 reg=ProviderRegistry();reg.register('clodex',Fake('chat'));reg.register('other',Fake('images.generate'));data=await reg.collect()
 path=tmp_path/'m.json';SnapshotStore(path).write(data)
 bot=Bot();svc=DemoService();app=DemoApp(replace(Config(),catalogue_path=str(path),admin_ids=(100,)),bot,svc)
 await app.handle(event('/start'));await app.handle(event(callback='accept'))
 await app.handle(event(callback='providers'))
 assert [row[0].text for row in bot.sent[-1][1].inline_keyboard[:2]]==['Clodex','other']
 v=data['version'];await app.handle(event(callback=f'provider:{v}:1'))
 assert bot.sent[-1][0].startswith('other\n')
 await app.handle(event(callback=f'pf:{v}:1:0'))
 labels=[row[0].text for row in bot.sent[-1][1].inline_keyboard]
 assert 'images.generate' in labels and 'chat' not in labels
 await app.handle(event(callback=f'cat:{v}:1:0'))
 cb=bot.sent[-1][1].inline_keyboard[0][0].callback_data
 assert cb==f'mdl:{v}:1:1:0'
 await app.handle(event(callback='providers'));assert 'Выберите агрегатор' in bot.sent[-1][0]
 await app.handle(event(callback=f'provider:{v}:9'));assert 'недоступен' in bot.sent[-1][0]

async def test_key_inventory_reaches_telegram_when_public_endpoints_fail(tmp_path):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        if request.url.path == '/v1/models':
            assert request.headers['Authorization'] == 'Bearer fixture-key'
            return httpx.Response(200, json={'data': [{'id': 'private-fixture-model'}]})
        assert 'Authorization' not in request.headers
        return httpx.Response(503)

    path = tmp_path / 'catalogue.json'
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await ClodexAdapter('fixture-key', client=client).refresh(SnapshotStore(path))
    assert calls[0] == '/v1/models'
    assert 'fixture-key' not in path.read_text()
    bot, service = Bot(), DemoService()
    app = DemoApp(replace(Config(), catalogue_path=str(path), admin_ids=(100,)), bot, service)
    await app.handle(event(callback='accept'))
    await app.handle(event('/models'))
    button = bot.sent[-1][1].inline_keyboard[0][0]
    await app.handle(event(callback=button.callback_data))
    assert bot.sent[-1][1].inline_keyboard[0][0].text == 'private-fixture-model'
