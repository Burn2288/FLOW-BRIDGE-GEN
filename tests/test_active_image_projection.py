from dataclasses import replace
from types import SimpleNamespace

import pytest
from aiohttp.test_utils import TestClient, TestServer
from elevenbot.core import Rejected
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.job_timeline import get_timeline
from miniapp.backend.web import create_app
from miniapp.tests.test_miniapp import signed


async def test_active_image_is_owned_and_transitions_to_saved_work(env):
    pool, cfg, service, owner = env
    other = await service.identity(101)
    await service.accept(other)
    for update, user, status in ((93311, owner, 'pending'), (93312, other, 'pending')):
        await pool.execute('INSERT INTO interaction_attempts(update_id,user_id) VALUES($1,$2)', update, user)
        await pool.execute("""INSERT INTO anymodel_image_jobs(update_id,user_id,prompt,model_id,status,provider_id,next_at)
                              VALUES($1,$2,'fixture','fixture-model',$3,'fixture-'||$1::bigint::text,now())""", update, user, status)
    owner_items = await service.history(owner, include_pending_tasks=True)
    found = [item for item in owner_items if item['id'] == 'image-job:93311']
    assert len(found) == 1 and found[0]['status'] == 'queued' and not found[0]['file_available']
    assert 'image-job:93312' not in [item['id'] for item in owner_items]
    assert all(item['id'] != 'image-job:93311' for item in await service.history(owner))
    assert (await get_timeline(pool, service, owner, 'image', 'image-job:93311'))['status'] == 'queued'
    with pytest.raises(Rejected):
        await get_timeline(pool, service, other, 'image', 'image-job:93311')
    async with TestClient(TestServer(create_app(pool, replace(cfg, token='fixture')))) as client:
        login = await client.post('/api/v1/session', json={'initData': signed('fixture', 100)})
        foreign = await client.post('/api/v1/session', json={'initData': signed('fixture', 101)})
        assert login.status == foreign.status == 200
        owner_header = {'Authorization': 'Bearer ' + (await login.json())['token']}
        foreign_header = {'Authorization': 'Bearer ' + (await foreign.json())['token']}
        response = await client.get('/api/v1/works', headers=owner_header)
        works = (await response.json())['works']
        assert any(w['id'] == 'image-job:93311' and w['status'] == 'queued' and not w['available'] for w in works)
        assert all(w['id'] != 'image-job:93312' for w in works)
        path = '/api/v1/works/image/image-job:93311/timeline'
        assert (await client.get(path, headers=owner_header)).status == 200
        assert (await client.get(path, headers=foreign_header)).status == 404
    await pool.execute("UPDATE anymodel_image_jobs SET status='submitting' WHERE update_id=93311")
    saved = await service.save_image_work(owner, 93311, 'fixture-model', 'fixture',
                                         SimpleNamespace(image=MOCK_IMAGE, filename='test.png'))
    await pool.execute("UPDATE anymodel_image_jobs SET status='ready' WHERE update_id=93311")
    items = await service.history(owner, include_pending_tasks=True)
    assert not any(item['id'] == 'image-job:93311' for item in items)
    assert sum(item['id'] == saved for item in items) == 1
    assert (await get_timeline(pool, service, owner, 'image', 'image-job:93311'))['status'] == 'succeeded'
    assert await pool.fetchval('SELECT update_id FROM image_works WHERE id=$1', saved) == 93311


@pytest.mark.parametrize('status,expected', [('submitting','dispatching'),('pending','queued'),
                                              ('failed','failed'),('unknown','uncertain')])
async def test_status_maps_without_other_users(env, status, expected):
    pool, _, service, owner = env
    await pool.execute('INSERT INTO interaction_attempts(update_id,user_id) VALUES(93313,$1)', owner)
    await pool.execute("""INSERT INTO anymodel_image_jobs(update_id,user_id,prompt,model_id,status,provider_id,next_at)
                          VALUES(93313,$1,'fixture','fixture-model',$2,'fixture-93313',now())""", owner,status)
    rows = await service.history(owner, include_pending_tasks=True)
    item = next(x for x in rows if x['id'] == 'image-job:93313')
    assert item['status'] == expected and not item['file_available']
    assert (await get_timeline(pool, service, owner, 'image', 'image-job:93313'))['status'] == expected
