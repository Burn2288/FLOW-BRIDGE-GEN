import os,sys,json
from pathlib import Path
from dataclasses import replace
import pytest
from elevenbot.config import Config
from elevenbot.runtime_config import load_env_file
from elevenbot.setup_service import write_configuration
from elevenbot.providers import MockProvider,DisabledProvider,DefinitiveFailure
from elevenbot.supervisor import command
from elevenbot.telegram import TelegramApp
from test_ui import Bot,event,FakeService

@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.setattr(os,'environ',{})
    return os.environ

def test_saved_settings_reload_after_process_restart(tmp_path,clean_env):
    path=tmp_path/'.env';token='123456:'+('example_'*5)
    write_configuration(path,token,100,'postgresql://runtime:fixture@localhost/db')
    first=Config.env(path)
    clean_env.clear();second=Config.env(path)
    assert first==second and second.token==token and second.admin_ids==(100,)
    assert second.access_mode=='private' and second.mode=='catalogue'
    assert not second.generation_enabled and not second.payments_enabled
    if os.name!='nt':assert path.stat().st_mode&0o777==0o600
    with pytest.raises(FileExistsError):write_configuration(path,token,999,'postgresql://r:p@localhost/db')
    clean_env.clear();assert Config.env(path).admin_ids==(100,)

def test_paths_relative_to_config_not_current_directory(tmp_path,clean_env,monkeypatch):
    folder=tmp_path/'config';folder.mkdir();p=folder/'.env';p.write_text('CATALOGUE_PATH=data/модели.json\nAUDIO_STORAGE_DIR=data/audio\n',encoding='utf-8')
    monkeypatch.chdir(tmp_path);cfg=Config.env(p)
    assert cfg.catalogue_path==str(folder/'data/модели.json')
    assert cfg.storage==folder/'data/audio'

def test_environment_overrides_file_without_shell_expansion(tmp_path,clean_env):
    p=tmp_path/'.env';p.write_text('SUPPORT_CONTACT=$(do-not-run)\nTELEGRAM_BOT_TOKEN=file-value\n',encoding='utf-8')
    clean_env['TELEGRAM_BOT_TOKEN']='environment-value'
    cfg=Config.env(p)
    assert cfg.token=='environment-value' and cfg.support=='$(do-not-run)'

@pytest.mark.parametrize('text',['BAD LINE secret-value','A=x\nA=y','export A=x','A="unterminated-secret'])
def test_invalid_config_does_not_disclose_values(tmp_path,clean_env,text):
    p=tmp_path/'.env';p.write_text(text)
    with pytest.raises(ValueError) as e:load_env_file(p)
    assert 'secret' not in str(e.value) and not (set(clean_env)-{'PYTEST_CURRENT_TEST'})

@pytest.mark.parametrize('values',[{'PROVIDER_MODE':'catalogue','GENERATION_ENABLED':'true'},{'PROVIDER_MODE':'catalogue','PAYMENTS_ENABLED':'true'},{'ACCESS_MODE':'private'}])
def test_catalogue_and_owner_fail_closed(clean_env,values):
    clean_env.update(values)
    with pytest.raises(ValueError):Config.env()

async def test_non_admin_in_private_pilot_can_accept_terms_and_open_user_menu():
    bot=Bot();app=TelegramApp(None,Config(access_mode='private',admin_ids=(999,)),bot);app.svc=FakeService()
    await app.handle(event('/start'))
    assert bot.sent[-1][1].inline_keyboard[0][0].callback_data=='accept'
    await app.handle(event(callback='accept'))
    assert app.svc.accepted and bot.photos
    await app.handle(event('/price_report'))
    assert bot.sent[-1][0]=='Админ-доступ закрыт.'

async def test_no_os_specific_provider_required_and_assets_independent_of_cwd(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path);assert len(await MockProvider().synthesize('x','demo',1.0))>128
    with pytest.raises(DefinitiveFailure):await DisabledProvider().synthesize('x','x',1)

def test_supervisor_only_passes_config_path_not_token(tmp_path):
    result=command('bot',tmp_path/'.env')
    assert result==[sys.executable,'-m','elevenbot','--env-file',str(tmp_path/'.env'),'bot']

async def test_postgres_identity_consent_and_context_survive_reconnection(env):
    import asyncpg
    from elevenbot.core import Service
    pool,cfg,svc,u=env
    schema=await pool.fetchval('SELECT current_schema()')
    await svc.aggregate_context(u,{'version':'persistent','values':{'prompt':'test'}})
    second=await asyncpg.create_pool(os.environ['TEST_DATABASE_URL'],server_settings={'search_path':schema})
    try:
        restarted=Service(second,cfg)
        assert await restarted.identity(100)==u
        async with second.acquire() as c:await restarted.authorize(c,u)
        assert (await restarted.aggregate_context(u))['version']=='persistent'
        assert (await restarted.wallet(u))['available']==10000
    finally:await second.close()

def test_supervisor_shutdown_terminates_children(tmp_path,monkeypatch):
    from elevenbot import supervisor
    cfg=Config(token='fixture')
    monkeypatch.setattr(Config,'env',classmethod(lambda cls,path:cfg))
    monkeypatch.setattr(sys,'argv',['supervisor','--env-file',str(tmp_path/'.env')])
    children=[]
    class Child:
        stopped=False
        def poll(self):return 0 if self.stopped else None
        def terminate(self):self.stopped=True
        def wait(self,timeout):assert self.stopped
    def popen(args):
        child=Child();children.append(child);return child
    monkeypatch.setattr(supervisor.subprocess,'Popen',popen)
    def stop(*args):raise KeyboardInterrupt
    monkeypatch.setattr(supervisor.time,'sleep',stop)
    supervisor.main()
    assert len(children)==2 and all(c.stopped for c in children)

def test_supervisor_bounds_restarts(tmp_path,monkeypatch):
    from elevenbot import supervisor
    monkeypatch.setattr(Config,'env',classmethod(lambda cls,path:Config(token='fixture')))
    monkeypatch.setattr(sys,'argv',['supervisor','--env-file',str(tmp_path/'.env')])
    calls=[];clock=[0]
    class Dead:
        def poll(self):return 1
        def wait(self,timeout):pass
    monkeypatch.setattr(supervisor.subprocess,'Popen',lambda args:(calls.append(args) or Dead()))
    monkeypatch.setattr(supervisor.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(supervisor.time,'sleep',lambda n:clock.__setitem__(0,clock[0]+6))
    with pytest.raises(SystemExit) as e:supervisor.main()
    assert e.value.code==1 and len(calls)<=10
