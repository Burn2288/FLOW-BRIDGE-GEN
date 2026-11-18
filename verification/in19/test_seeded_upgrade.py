"""Disposable PostgreSQL regression; never run against an existing database."""
import hashlib
import os
import shutil
import socket
import subprocess
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg
import pytest

from elevenbot import db

ROOT = Path(__file__).resolve().parents[2]
USER = uuid.UUID(int=1001)
PAYMENT = uuid.UUID(int=1002)
IMAGE = uuid.UUID(int=1003)
VIDEO = uuid.UUID(int=1004)
SPEECH = uuid.UUID(int=1005)
QUOTES = [uuid.UUID(int=1010), uuid.UUID(int=1011)]
JOBS = [uuid.UUID(int=1020), uuid.UUID(int=1021)]
PNG = b'fixture-png-bytes-not-real-media'
MP3 = b'fixture-mp3-bytes-not-real-media'
MP4 = b'fixture-mp4-bytes-not-real-media'
SPEECH_BYTES = b'fixture-speech-bytes-not-real-media'


def digest(value):
    return hashlib.sha256(value).hexdigest()


def safe_config():
    raw = os.environ.get('IN19_TEST_DATABASE_URL', '')
    url = urlsplit(raw)
    if (os.environ.get('IN19_DISPOSABLE_POSTGRES') != 'YES'
            or url.scheme != 'postgresql' or url.hostname != '127.0.0.1'
            or url.port != 55432 or url.path != '/in19_admin'
            or url.username != 'postgres' or url.query or url.fragment):
        raise RuntimeError('requires explicitly disposable local IN19 PostgreSQL service')
    return raw, url


async def migrate_to(pool, stage, tmp_path, monkeypatch):
    root = tmp_path / ('migration-stage-%03d' % stage)
    migrations = root / 'migrations'
    migrations.mkdir(parents=True, exist_ok=True)
    (root / 'src' / 'elevenbot').mkdir(parents=True, exist_ok=True)
    for source in sorted((ROOT / 'migrations').glob('*.sql')):
        if int(source.name[:3]) <= stage:
            shutil.copyfile(source, migrations / source.name)
    monkeypatch.setattr(db, '__file__', str(root / 'src' / 'elevenbot' / 'db.py'))
    await db.migrate(pool)


async def registry(conn, stage):
    rows = await conn.fetch('SELECT version,sha256 FROM schema_migrations ORDER BY version')
    expected = sorted((ROOT / 'migrations').glob('*.sql'))[:stage]
    assert len(rows) == len(expected) == stage
    for row, path in zip(rows, expected):
        assert row['version'] == path.name
        assert row['sha256'] == digest(path.read_text(encoding='utf-8').encode())
    return [tuple(row) for row in rows]


async def seed_013(conn, audio_dir):
    audio_dir.mkdir()
    (audio_dir / 'historical.mp3').write_bytes(MP3)
    async with conn.transaction():
        await conn.execute('INSERT INTO users(id) VALUES($1)', USER)
        await conn.execute("INSERT INTO identities(platform,external_id,user_id,terms_version,accepted_at) VALUES('telegram',90001,$1,'fixture-v1',now())", USER)
        await conn.execute("INSERT INTO wallets(user_id,mode) VALUES($1,'demo'),($1,'live')", USER)
        await conn.execute("INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr) VALUES($1,$2,'demo','grant-fixture','demo_grant',1000,0)", uuid.UUID(int=1030), USER)
        await conn.execute("INSERT INTO payments(id,user_id,amount,credits,currency,tariff,charge_id,status) VALUES($1,$2,100,500,'XTR','fixture','fixture-charge','succeeded')", PAYMENT, USER)
        await conn.execute("INSERT INTO payment_callback_events(provider,remote_id,status) VALUES('platega',$1,'fixture-pending')", uuid.UUID(int=1006))
        await conn.execute("INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,payment_id) VALUES($1,$2,'live','payment-fixture','payment',500,0,$3)", uuid.UUID(int=1031), USER, PAYMENT)
        await conn.execute("INSERT INTO budgets(day) VALUES('2026-01-01')")
        for i in range(2):
            await conn.execute("INSERT INTO quotes(id,user_id,mode,voice,speed,price,cost_bound,tariff) VALUES($1,$2,'demo','fixture',1,100,100,'fixture')", QUOTES[i], USER)
            await conn.execute("INSERT INTO jobs(id,user_id,quote_id,mode,price,cost_bound,budget_day,status) VALUES($1,$2,$3,'demo',100,100,'2026-01-01','queued')", JOBS[i], USER, QUOTES[i])
            await conn.execute("INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,job_id) VALUES($1,$2,'demo',$3,'reserve',-100,100,$4)", uuid.UUID(int=1040+i), USER, 'reserve-fixture-'+str(i), JOBS[i])
            if i == 0:
                await conn.execute("INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,job_id) VALUES($1,$2,'demo','capture-fixture','capture',0,-100,$3)", uuid.UUID(int=1050), USER, JOBS[0])
                await conn.execute("UPDATE jobs SET status='succeeded',settlement='capture',completed_at=now() WHERE id=$1", JOBS[0])
        await conn.execute("INSERT INTO files(job_id,storage_key,sha256,size,expires_at) VALUES($1,'historical.mp3',$2,$3,now()+interval '7 days')", JOBS[0], digest(MP3), len(MP3))
        await conn.execute("INSERT INTO image_works(id,update_id,user_id,model_id,prompt,image,filename) VALUES($1,90002,$2,'fixture','fixture',$3,'test.png')", IMAGE, USER, PNG)
        await conn.execute("INSERT INTO video_jobs(id,user_id,model_id,prompt,cost_usd,status,provider_id,video) VALUES($1,$2,'fixture','fixture',0,'succeeded','fixture-video',$3)", VIDEO, USER, MP4)


async def snapshot(conn, audio_dir, speech):
    queries = [
        ('users', 'SELECT id,blocked FROM users ORDER BY id'),
        ('identities', 'SELECT platform,external_id,user_id,terms_version,accepted_at FROM identities ORDER BY external_id'),
        ('wallets', 'SELECT user_id,mode,available,reserved FROM wallets ORDER BY mode'),
        ('ledger', 'SELECT id,user_id,mode,event_key,kind,da,dr,job_id,payment_id FROM ledger ORDER BY event_key'),
        ('jobs', 'SELECT id,user_id,quote_id,mode,price,cost_bound,budget_day,status,settlement FROM jobs ORDER BY id'),
        ('payments', 'SELECT id,user_id,amount,credits,currency,tariff,charge_id,status FROM payments ORDER BY id'),
        ('payment_events', 'SELECT id,provider,remote_id,status,received_at FROM payment_callback_events ORDER BY id'),
        ('files', 'SELECT job_id,storage_key,sha256,size FROM files ORDER BY job_id'),
        ('images', 'SELECT id,user_id,image FROM image_works ORDER BY id'),
        ('videos', 'SELECT id,user_id,status,provider_id,video FROM video_jobs ORDER BY id'),
    ]
    result = {name: [tuple(row) for row in await conn.fetch(sql)] for name, sql in queries}
    assert result['wallets'] == [(USER, 'demo', 800, 100), (USER, 'live', 500, 0)]
    assert await conn.fetchval("SELECT count(*) FROM wallets w WHERE available<>(SELECT coalesce(sum(da),0) FROM ledger l WHERE l.user_id=w.user_id AND l.mode=w.mode) OR reserved<>(SELECT coalesce(sum(dr),0) FROM ledger l WHERE l.user_id=w.user_id AND l.mode=w.mode)") == 0
    assert digest(result['images'][0][2]) == digest(PNG)
    assert digest(result['videos'][0][4]) == digest(MP4)
    assert digest((audio_dir / 'historical.mp3').read_bytes()) == digest(MP3)
    if speech:
        result['speech'] = [tuple(x) for x in await conn.fetch('SELECT id,user_id,audio FROM anymodel_speech ORDER BY id')]
        assert result['speech'] == [(SPEECH, USER, SPEECH_BYTES)]
    return result


@pytest.mark.asyncio
async def test_in19_seeded_upgrade_and_restore(tmp_path, monkeypatch):
    raw, url = safe_config()
    outbound_attempts = []
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def allow_loopback(address):
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1'):
            outbound_attempts.append(address[0])
            raise RuntimeError('external network blocked in fixture')

    def guarded_connect(sock, address):
        allow_loopback(address)
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        allow_loopback(address)
        return original_connect_ex(sock, address)

    monkeypatch.setattr(socket.socket, 'connect', guarded_connect)
    monkeypatch.setattr(socket.socket, 'connect_ex', guarded_connect_ex)
    name = 'in19_seed_' + uuid.uuid4().hex
    restored_name = 'in19_restore_' + uuid.uuid4().hex
    admin = await asyncpg.connect(raw)
    pool = restored = None
    created = []
    try:
        for database in (name, restored_name):
            await admin.execute('CREATE DATABASE "' + database + '"')
            created.append(database)
        pool = await asyncpg.create_pool(raw.rsplit('/', 1)[0] + '/' + name, min_size=1, max_size=2)
        await migrate_to(pool, 13, tmp_path, monkeypatch)
        audio = tmp_path / 'audio-original'
        async with pool.acquire() as conn:
            await seed_013(conn, audio)
            baseline = await snapshot(conn, audio, False)
            assert len(await registry(conn, 13)) == 13
        print('STAGE 013 seeded: identity, consent, wallets, ledger, completed/queued jobs, payment, image/audio/video')
        baseline_speech = None
        for stage in (14, 15, 16, 17, 18, 36, 39, 40, 41):
            await migrate_to(pool, stage, tmp_path, monkeypatch)
            async with pool.acquire() as conn:
                if stage == 16:
                    await conn.execute("INSERT INTO anymodel_speech(id,user_id,model_id,title,input,cost_tokens,claimed,audio) VALUES($1,$2,'fixture','fixture','fixture',0,true,$3)", SPEECH, USER, SPEECH_BYTES)
                current = await snapshot(conn, audio, stage >= 16)
                if stage >= 16:
                    speech = current.pop('speech')
                    if baseline_speech is None:
                        baseline_speech = speech
                    assert speech == baseline_speech
                assert current == baseline
                before = await registry(conn, stage)
                if stage == 39:
                    await conn.execute("INSERT INTO miniapp_sessions(token_hash,init_hash,user_id,expires_at) VALUES($1,$2,$3,now()+interval '1 hour')", b'fixture-token', b'fixture-init', USER)
                    session = await conn.fetch("SELECT * FROM miniapp_sessions")
                if stage >= 39:
                    assert await conn.fetch("SELECT * FROM miniapp_sessions") == session
            await db.migrate(pool)
            async with pool.acquire() as conn:
                assert await registry(conn, stage) == before
                if stage >= 39:
                    assert await conn.fetch("SELECT * FROM miniapp_sessions") == session
                check = await snapshot(conn, audio, stage >= 16)
                if stage >= 16:
                    assert check.pop('speech') == baseline_speech
                assert check == baseline
            assert not outbound_attempts
            print(f'STAGE {stage:03d} PASS registry={stage} rerun=stable data=stable ledger=balanced')

        async with pool.acquire() as conn:
            first = await conn.fetchrow('SELECT version,sha256 FROM schema_migrations ORDER BY version LIMIT 1')
            await conn.execute('UPDATE schema_migrations SET sha256=$1 WHERE version=$2', '0'*64, first['version'])
        with pytest.raises(RuntimeError, match='Migration checksum mismatch'):
            await db.migrate(pool)
        async with pool.acquire() as conn:
            assert await conn.fetchval('SELECT sha256 FROM schema_migrations WHERE version=$1', first['version']) == '0'*64
            await conn.execute('UPDATE schema_migrations SET sha256=$1 WHERE version=$2', first['sha256'], first['version'])
            assert len(await registry(conn, 41)) == 41
        print('CHECKSUM_MISMATCH PASS rejected without rewriting SQL')

        env = {k: os.environ[k] for k in ('PATH', 'SYSTEMROOT') if k in os.environ}
        env.update(PGHOST='127.0.0.1', PGPORT='55432', PGUSER='postgres', PGPASSWORD=url.password or '')
        dump = tmp_path / 'fixture.dump'
        subprocess.run(['pg_dump', '-Fc', '-f', str(dump), '-d', name], env=env, check=True)
        media_backup = tmp_path / 'fixture-media.zip'
        with zipfile.ZipFile(media_backup, 'w') as archive:
            archive.write(audio / 'historical.mp3', arcname='historical.mp3')
        subprocess.run(['pg_restore', '--exit-on-error', '-d', restored_name, str(dump)], env=env, check=True)
        restored_audio = tmp_path / 'audio-restored'
        restored_audio.mkdir()
        with zipfile.ZipFile(media_backup) as archive:
            (restored_audio / 'historical.mp3').write_bytes(archive.read('historical.mp3'))
        restored = await asyncpg.create_pool(raw.rsplit('/', 1)[0] + '/' + restored_name, min_size=1, max_size=2)
        async with restored.acquire() as conn:
            after = await snapshot(conn, restored_audio, True)
            speech = after.pop('speech')
            assert after == baseline and speech == baseline_speech
            assert len(await registry(conn, 41)) == 41
            assert await conn.fetch("SELECT * FROM miniapp_sessions") == session
            assert await conn.fetchval("SELECT count(*) FROM pg_constraint WHERE conrelid IN ('ledger'::regclass,'jobs'::regclass,'identities'::regclass) AND contype IN ('f','c','p','u')") > 10
            with pytest.raises(asyncpg.UniqueViolationError):
                await conn.execute("INSERT INTO identities(platform,external_id,user_id) VALUES('telegram',90001,$1)", USER)
        print('RESTORE PASS new database rows/ledger/jobs/results/registry/constraints; audio restored from separate archive')
        print('MEDIA_SHA256 png='+digest(PNG)+' mp3='+digest(MP3)+' mp4='+digest(MP4)+' speech='+digest(SPEECH_BYTES))
        assert not outbound_attempts
        print('PROVIDER_POSTS=0; no provider client invoked; Python non-loopback connections blocked')
    finally:
        if restored:
            await restored.close()
        if pool:
            await pool.close()
        for database in created:
            await admin.execute('DROP DATABASE "' + database + '" WITH (FORCE)')
        await admin.close()
