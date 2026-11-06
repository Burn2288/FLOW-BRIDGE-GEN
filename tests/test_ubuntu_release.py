import hashlib,json,os,subprocess,uuid
from pathlib import Path
import pytest
from elevenbot.runtime_config import parse_env_file
from elevenbot.setup_service import write_configuration
from elevenbot.snapshot import verify,verify_database_audio,backup,restore_drill

ROOT=Path(__file__).resolve().parents[1]

def test_ubuntu_shell_scripts_parse():
    for p in (ROOT/'deploy/ubuntu').glob('*.sh'):
        assert subprocess.run(['bash','-n',str(p)],capture_output=True).returncode==0,p.name

def test_systemd_imports_source_and_separates_secrets():
    for p in (ROOT/'deploy/systemd').glob('*.service'):
        s=p.read_text()
        assert 'Environment=PYTHONPATH=/opt/darkflow/src' in s
        assert 'User=darkflow' in s and 'ProtectSystem=strict' in s
        assert 'After=postgresql.service' in s
        assert ('EnvironmentFile=/etc/darkflow/migration.env' in s)==('migrate' in p.name)
        assert 'TELEGRAM_BOT_TOKEN=' not in s

def test_setup_absolute_state_directory(tmp_path):
    p=tmp_path/'runtime.env';state=tmp_path/'state'
    write_configuration(p,'123456:'+('fixture_'*5),100,'postgresql://u:p@localhost/db',state)
    parsed=parse_env_file(p)
    assert parsed['AUDIO_STORAGE_DIR']==str(state/'audio')
    assert parsed['CATALOGUE_PATH']==str(state/'catalogue/models.json')

def test_env_parser_can_read_multiple_files_without_mutating_environment(tmp_path,monkeypatch):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    a=tmp_path/'a';b=tmp_path/'b';a.write_text('DATABASE_URL=one');b.write_text('DATABASE_URL=two')
    assert parse_env_file(a)['DATABASE_URL']=='one' and parse_env_file(b)['DATABASE_URL']=='two'
    assert 'DATABASE_URL' not in os.environ

async def test_missing_migrations_never_marks_empty_install_as_pass(monkeypatch,tmp_path):
    import elevenbot.db as db
    fake=tmp_path/'src/elevenbot/db.py';fake.parent.mkdir(parents=True)
    monkeypatch.setattr(db,'__file__',str(fake))
    class Pool:
        def acquire(self):raise AssertionError('DB must not be mutated without migrations')
    with pytest.raises(RuntimeError,match='Migration files unavailable'):await db.migrate(Pool())

def test_backup_manifest_detects_corruption_and_path_escape(tmp_path):
    (tmp_path/'database.dump').write_bytes(b'fixture')
    m={'schema':1,'files':{'database.dump':hashlib.sha256(b'fixture').hexdigest()}}
    (tmp_path/'manifest.json').write_text(json.dumps(m))
    assert verify(tmp_path)==m
    (tmp_path/'database.dump').write_bytes(b'corrupt')
    with pytest.raises(ValueError):verify(tmp_path)
    m['files']['../outside']='bad';(tmp_path/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(ValueError):verify(tmp_path)

def test_referenced_audio_must_exist_and_match_digest(tmp_path):
    rows=[{'storage_key':'example.mp3','sha256':hashlib.sha256(b'tone').hexdigest()}]
    with pytest.raises(ValueError):verify_database_audio(rows,tmp_path)
    (tmp_path/'example.mp3').write_bytes(b'tone');verify_database_audio(rows,tmp_path)
    rows[0]['storage_key']='../example.mp3'
    with pytest.raises(ValueError):verify_database_audio(rows,tmp_path)

async def test_ubuntu_backup_restore_drill_with_real_postgres(env,tmp_path):
    import asyncpg
    from urllib.parse import urlsplit,unquote
    from elevenbot.database_setup import provision,identifier
    pool,cfg,svc,u=env;url=urlsplit(os.environ['TEST_DATABASE_URL'])
    name='darkflow_backup_'+uuid.uuid4().hex[:12];folder=tmp_path/'private'
    admin=await asyncpg.connect(os.environ['TEST_DATABASE_URL']);roles=[]
    try:
        await provision(url.hostname,url.port or 5432,unquote(url.username),unquote(url.password or ''),name,folder)
        creds=json.loads((folder/'database.credentials.json').read_text())
        roles=[urlsplit(creds[k]).username for k in ('DATABASE_URL','DATABASE_MIGRATION_URL')]
        runtime=tmp_path/'runtime.env';runtime.write_text('DATABASE_URL='+creds['DATABASE_URL']+'\nAUDIO_STORAGE_DIR='+str(tmp_path/'audio')+'\n')
        from elevenbot.core import Service
        from elevenbot.config import Config
        from elevenbot.worker import Worker
        from elevenbot.providers import MockProvider
        app_pool=await asyncpg.create_pool(creds['DATABASE_URL'],min_size=1,max_size=2)
        try:
            cfg=Config(mode='mock',generation_enabled=True,storage=tmp_path/'audio')
            service=Service(app_pool,cfg);user=await service.identity(991);await service.accept(user)
            quote,_=await service.quote(user,'Ubuntu snapshot','demo');job=await service.confirm(user,quote)
            await Worker(app_pool,cfg,MockProvider()).run_one()
            assert (await service.owned(user,job))['status']=='succeeded'
        finally:await app_pool.close()
        target=tmp_path/'backup';result=await backup(runtime,target)
        assert result['status']=='BACKUP_CREATED'
        result=await restore_drill(target,folder/'migration.env',unquote(url.password or ''),unquote(url.username))
        assert result['status']=='RESTORE_DRILL_PASS' and not result['live_database_changed']
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS {identifier(name)} WITH (FORCE)')
        for role in roles:await admin.execute(f'DROP ROLE {identifier(role)}')
        await admin.close()
