from datetime import datetime, timezone
from uuid import uuid4

from elevenbot.library import LibraryItem


def test_failed_result_is_not_available_even_if_file_metadata_exists():
    row = dict(id=uuid4(), kind='audio', model_id='fixture', status='failed',
               file_available=True, price=None, created_at=datetime.now(timezone.utc))
    item = LibraryItem.from_history(row).as_dict()
    assert item['available'] is False
    assert item['result_url'] is None

async def test_postgres_library_integrity_and_owner(env):
    from dataclasses import replace
    from aiohttp.test_utils import TestClient, TestServer
    from elevenbot.core import Service
    from elevenbot.providers import MockProvider
    from elevenbot.worker import Worker
    from miniapp.backend.web import create_app
    from miniapp.tests.test_miniapp import signed

    pool, cfg, service, owner = env
    cfg = replace(cfg, token='fixture', mode='mock', payments_enabled=False)
    service = Service(pool, cfg)
    other = await service.identity(101)
    await service.accept(other)
    quote, _ = await service.quote(owner, 'fixture', 'demo')
    job = await service.confirm(owner, quote)
    provider = MockProvider()
    await Worker(pool, cfg, provider).run_one()
    file_row = await pool.fetchrow('SELECT storage_key FROM files WHERE job_id=$1', job)
    assert file_row is not None
    path = cfg.storage / file_row['storage_key']
    original = path.read_bytes()
    empty, valid = uuid4(), uuid4()
    video = b'fixture-video-bytes'
    await pool.execute("""INSERT INTO video_jobs(id,user_id,model_id,prompt,cost_usd,status,video,expires_at)
                          VALUES($1,$3,'fixture','fixture',0,'succeeded',NULL,now()+interval '1 day'),
                                ($2,$3,'fixture','fixture',0,'succeeded',$4,now()+interval '1 day')""", empty, valid, owner, video)
    ledger = [tuple(x) for x in await pool.fetch('SELECT * FROM ledger ORDER BY id')]
    calls = provider.calls
    headers = []
    async def check_app():
        async with TestClient(TestServer(create_app(pool, cfg))) as client:
            if not headers:
                for external in (100, 101):
                    response = await client.post('/api/v1/session', json={'initData': signed('fixture', external)})
                    assert response.status == 200
                    headers.append({'Authorization': 'Bearer ' + (await response.json())['token']})
            own, foreign = headers
            response = await client.get('/api/v1/works', headers=own)
            works = {x['id']: x for x in (await response.json())['works']}
            assert not works[str(empty)]['available'] and works[str(empty)]['result_url'] is None
            assert works[str(valid)]['available']
            for kind, work in [('video',empty), ('video',valid), ('audio',job)]:
                assert (await client.get(f'/api/v1/works/{kind}/{work}', headers=foreign)).status == 404
            assert (await client.get(f'/api/v1/works/video/{empty}', headers=own)).status == 404
            assert await (await client.get(f'/api/v1/works/video/{valid}', headers=own)).read() == video
            assert await (await client.get(f'/api/v1/works/audio/{job}', headers=own)).read() == original
            path.write_bytes(b'corrupted' + original[9:])
            assert (await client.get(f'/api/v1/works/audio/{job}', headers=own)).status == 404
            path.unlink()
            response = await client.get(f'/api/v1/works/audio/{job}', headers=own)
            assert response.status == 404 and str(cfg.storage) not in await response.text()
            path.write_bytes(original)
    await check_app()
    # A fresh application instance must still serve intact bytes to its owner.
    await check_app()
    assert provider.calls == calls
    assert [tuple(x) for x in await pool.fetch('SELECT * FROM ledger ORDER BY id')] == ledger
