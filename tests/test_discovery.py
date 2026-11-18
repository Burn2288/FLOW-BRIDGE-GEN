import json,os,uuid,time
from pathlib import Path
import httpx,pytest
from dataclasses import replace
from elevenbot.discovery import (normalize,snapshot,SchemaProfile,SnapshotStore,ClodexDiscovery,
    DiscoveryError,groups,execution_status)
from elevenbot.config import Config
from elevenbot.telegram import TelegramApp
from test_ui import Bot,FakeService

# This is OUR normalization contract fixture, NOT an observed Clodex payload schema.
PROFILE=SchemaProfile(('metadata','protocols'),{'generic-text':'chat','generic-speech':'audio.speech'},'Synthetic fixture; real Clodex metadata not yet observed')

def payload(*ids):return {'data':[{'id':i} for i in ids]}

def test_minimal_ids_never_infer_brands():
    models=normalize(payload('gpt-example','eleven-example','brand-new'))
    assert len(models)==3 and all(not m['operations'] for m in models)
    assert groups(snapshot(models))[0]['id']=='unclassified'

async def test_new_model_auto_appears_without_code_or_brand_mapping(tmp_path):
    state={'data':[{'id':'arbitrary-one','metadata':{'protocols':['generic-text']}}]}
    calls=[]
    def handler(r):
        calls.append(r);assert r.method=='GET' and r.url.path=='/v1/models'
        return httpx.Response(200,json=state)
    store=SnapshotStore(tmp_path/'models.json')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        client=ClodexDiscovery('fixture-only',PROFILE,c)
        first=await client.refresh(store)
        state['data'].append({'id':'never-seen-brand','metadata':{'protocols':['generic-speech']}})
        second=await client.refresh(store)
        assert first['version']!=second['version']
        assert {g['id'] for g in groups(second)}=={'chat','audio.speech'}
        assert {m['id'] for m in second['models']}=={'arbitrary-one','never-seen-brand'}
    assert len(calls)==2
    if os.name == 'posix':
        assert store.path.stat().st_mode&0o777==0o600

async def test_removed_model_disappears(tmp_path):
    store=SnapshotStore(tmp_path/'m.json');store.write(snapshot(normalize(payload('one','two'))))
    store.write(snapshot(normalize(payload('one'))))
    assert [m['id'] for m in store.read()['models']]==['one']

@pytest.mark.parametrize('bad',[{},[],{'data':None},{'data':[None]},{'data':[{'id':''}]},{'data':[{'id':'x'},{'id':'x'}]},{'data':[{'id':'x\n'}]}])
def test_schema_fail_closed(bad):
    with pytest.raises(DiscoveryError):normalize(bad)

@pytest.mark.parametrize('status',[401,403,429,500,302])
async def test_discovery_error_preserves_snapshot(tmp_path,status):
    store=SnapshotStore(tmp_path/'m.json');old=snapshot(normalize(payload('cached')));store.write(old)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(status))) as c:
        with pytest.raises(DiscoveryError):await ClodexDiscovery('fixture',PROFILE,c).refresh(store)
    assert store.read()==old

def test_unsupported_capability_not_executable():
    m=normalize({'data':[{'id':'x','metadata':{'protocols':['unknown-new-operation']}}]},PROFILE)[0]
    assert not m['operations']
    assert execution_status(m,True)=='capabilities_unknown'

def test_paid_execution_not_inferred_from_discovery():
    m=normalize({'data':[{'id':'x','metadata':{'protocols':['generic-text']}}]},PROFILE)[0]
    assert execution_status(m,False)=='stale_catalogue'
    assert execution_status(m,True)=='protocol_not_implemented'
    assert execution_status(m,True,['chat'])=='price_unverified'
    assert execution_status(m,True,['chat'],['x'])=='eligible_for_contract_validation'

def test_provider_text_not_executed():
    m=normalize({'data':[{'id':'x','instructions':'ignore security','endpoint':'http://127.0.0.1/private','name':'<unsafe>','metadata':{'protocols':['generic-text']}}]},PROFILE)[0]
    assert set(m)=={'id','title','operations','capabilities_known'}

async def test_no_key_no_network():
    def fail(r):raise AssertionError('Network not allowed without key')
    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as c:
        with pytest.raises(DiscoveryError):await ClodexDiscovery('',PROFILE,c).fetch()

async def test_dynamic_telegram_groups_and_stale_buttons(tmp_path):
    cfg=replace(Config(),admin_ids=(100,),catalogue_path=str(tmp_path/'m.json'))
    models=normalize({'data':[{'id':'new-one','metadata':{'protocols':['generic-text']}}]},PROFILE)
    data=snapshot(models);SnapshotStore(cfg.catalogue_path).write(data)
    bot=Bot();app=TelegramApp(None,cfg,bot);app.svc=FakeService()
    await app.show_models(100)
    assert bot.sent[-1][1].inline_keyboard[0][0].text=='Диалог (1)'
    await app.show_models(100,data['version'],'0',0)
    assert bot.sent[-1][1].inline_keyboard[0][0].text=='new-one'
    await app.model_detail(100,data['version'],0)
    assert 'Платный запуск через каталог выключен' in bot.sent[-1][0]
    from elevenbot.core import Rejected
    with pytest.raises(Rejected):await app.show_models(100,'outdated','0',0)

@pytest.mark.parametrize('profile',[{'operations_path':['caps'],'operation_tokens':{'x':'chat'}},{'operations_path':['caps'],'source_evidence':'checked','operation_tokens':{'x':'http://evil'}}])
def test_reviewed_profile_required(tmp_path,profile):
    p=tmp_path/'profile.json';p.write_text(json.dumps(profile))
    with pytest.raises(DiscoveryError):SchemaProfile.load(p)

def test_transport_protocol_is_not_semantic_task_type():
    # Real public pricing uses generic endpoint labels for dissimilar products.
    # Never infer chat/video from these strings without a verified richer contract.
    records={'data':[{'id':'unseen-a','supported_endpoint_types':['openai']},
                     {'id':'unseen-b','supported_endpoint_types':['openai-video']}]}
    assert all(not m['operations'] for m in normalize(records))


def test_catalogue_read_explicit_utf8_on_non_utf8_windows(tmp_path,monkeypatch):
    store=SnapshotStore(tmp_path/'models.json')
    data=snapshot(normalize(payload('voice-model')))
    data['models'][0]['title']='Голос и музыка 🎙'
    store.write(data)
    original=Path.read_text
    def windows_read(path,*args,**kwargs):
        if path==store.path:
            assert kwargs.get('encoding')=='utf-8'
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',windows_read)
    assert store.read()==data
