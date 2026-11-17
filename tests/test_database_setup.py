import importlib.util,json,os,sys
from pathlib import Path
from urllib.parse import urlsplit,unquote
import pytest
from elevenbot.database_setup import identifier,connection_url,private_json,ProvisionError,provision

spec=importlib.util.spec_from_file_location('native_acceptance',Path(__file__).resolve().parents[1]/'scripts/run_native_acceptance.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

@pytest.mark.parametrize('bad',['postgres','darkflow_x;DROP DATABASE x','darkflow_','darkflow_A','../darkflow_x'])
def test_identifier_new_database_boundary(bad):
    with pytest.raises(ProvisionError):identifier(bad)

def test_local_url_escaping_and_remote_refusal():
    u=connection_url('127.0.0.1',5432,'postgres','a@b:c#d','darkflow_service')
    assert unquote(urlsplit(u).password)=='a@b:c#d'
    assert urlsplit(connection_url('::1',5432,'u','p','darkflow_x')).hostname=='::1'
    with pytest.raises(ProvisionError):connection_url('remote.invalid',5432,'u','p','darkflow_x')

def test_private_credentials_no_overwrite(tmp_path):
    path=tmp_path/'private'/'credentials.json';private_json(path,{'value':'fixture'})
    with pytest.raises(FileExistsError):private_json(path,{'value':'replacement'})
    assert json.loads(path.read_text())['value']=='fixture'
    if os.name!='nt':assert path.stat().st_mode&0o777==0o600

@pytest.mark.parametrize('skip,fail,exit_code,expected',[(False,False,0,'PASS'),(True,False,0,'FAIL'),(False,True,1,'FAIL'),(False,False,1,'FAIL')])
def test_acceptance_never_counts_skip_or_failed_exit_as_pass(tmp_path,skip,fail,exit_code,expected):
    xml=tmp_path/'r.xml';xml.write_text('<testsuite><testcase classname="tests.x" name="case">'+('<skipped/>' if skip else '')+('<failure/>' if fail else '')+'</testcase></testsuite>')
    assert runner.assess(xml,['tests.x#case'],exit_code)['status']==expected
    assert runner.assess(xml,['tests.x#missing'],exit_code)['status']=='FAIL'

def test_sanitize_database_and_token_values():
    text='postgresql://u:private@127.0.0.1/db password=private '+('123456789:'+('fixture_'*5))
    result=runner.sanitize(text,['private'])
    assert 'private' not in result and 'postgresql://' not in result and '123456789:' not in result

async def test_database_provision_existing_files_prevents_network(tmp_path,monkeypatch):
    private_json(tmp_path/'database.credentials.json',{'existing':True})
    async def forbidden(*args,**kw):raise AssertionError('No network expected')
    import elevenbot.database_setup as module
    monkeypatch.setattr(module.asyncpg,'connect',forbidden)
    with pytest.raises(ProvisionError):await provision('127.0.0.1',5432,'postgres','fixture','darkflow_service',tmp_path)

async def test_genuine_database_provision_roles_migrations_and_preservation(env,tmp_path):
    pool,cfg,svc,u=env;parsed=urlsplit(os.environ['TEST_DATABASE_URL'])
    import uuid,asyncpg
    name='darkflow_provision_'+uuid.uuid4().hex[:12];roles=[];admin=await asyncpg.connect(os.environ['TEST_DATABASE_URL'])
    try:
        result=await provision(parsed.hostname,parsed.port or 5432,unquote(parsed.username),unquote(parsed.password or ''),name,tmp_path)
        assert result['status']=='READY' and result['runtime_probe']=='PASS'
        credentials=json.loads((tmp_path/'database.credentials.json').read_text())
        roles=[urlsplit(credentials[k]).username for k in ('DATABASE_URL','DATABASE_MIGRATION_URL')]
        connection=await asyncpg.connect(credentials['DATABASE_URL'])
        try:
            assert await connection.fetchval('SELECT count(*) FROM schema_migrations')==len(list(Path('migrations').glob('*.sql')))
            assert not await connection.fetchval('SELECT rolsuper FROM pg_roles WHERE rolname=current_user')
            with pytest.raises(asyncpg.InsufficientPrivilegeError):await connection.execute('ALTER TABLE ledger DISABLE TRIGGER ALL')
        finally:await connection.close()
        with pytest.raises(ProvisionError):await provision(parsed.hostname,parsed.port or 5432,unquote(parsed.username),unquote(parsed.password or ''),name,tmp_path/'another')
        assert await admin.fetchval('SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=$1)',name)
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS {identifier(name)} WITH (FORCE)')
        for role in roles:await admin.execute(f'DROP ROLE {identifier(role)}')
        await admin.close()
