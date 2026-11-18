from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from elevenbot.core import Rejected
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.job_timeline import get_timeline, summarize


def test_error_projection_has_only_safe_text():
    now = datetime.now(timezone.utc)
    row = {'id': uuid4(), 'kind': 'audio', 'model_id': 'fixture', 'status': 'failed',
           'created_at': now, 'completed_at': now, 'saved_only': False,
           'error_code': 'secret-provider-token-123'}
    result = summarize(row)
    assert result['status'] == 'failed'
    assert result['error'] == 'Не удалось выполнить задачу.'
    assert 'secret-provider-token-123' not in str(result)
    assert [event['label'] for event in result['events']] == ['Задание создано', 'Не удалось выполнить задачу.']


def test_completed_saved_result_does_not_invent_execution_time():
    row = {'id': uuid4(), 'kind': 'image', 'model_id': 'fixture', 'status': 'succeeded',
           'created_at': datetime.now(timezone.utc), 'completed_at': None, 'saved_only': True}
    events = summarize(row)['events']
    assert [event['label'] for event in events] == ['Результат сохранён', 'Готово']
    assert events[1]['at'] is None


async def test_owned_success_and_failed_mock_timelines(env):
    pool, cfg, service, owner = env
    other = await service.identity(101)
    await service.accept(other)
    quote, _ = await service.quote(owner, 'fixture', 'demo')
    job = await service.confirm(owner, quote)
    queued = await get_timeline(pool, service, owner, 'audio', job)
    assert queued['status'] == 'queued'
    await service.settle(job, 'release')
    await pool.execute("UPDATE jobs SET error_code='secret-provider-token-123' WHERE id=$1", job)
    failed = await get_timeline(pool, service, owner, 'audio', job)
    assert failed['status'] == 'failed' and 'secret-provider-token-123' not in str(failed)
    image = await service.save_image_work(owner, 83311, 'mock', 'fixture',
                                         SimpleNamespace(image=MOCK_IMAGE, filename='test.png'))
    success = await get_timeline(pool, service, owner, 'image', image)
    assert success['status'] == 'succeeded'
    for kind, job_id in [('audio', job), ('image', image)]:
        with pytest.raises(Rejected):
            await get_timeline(pool, service, other, kind, job_id)


async def test_timeline_http_respects_ownership(env):
    from dataclasses import replace
    from aiohttp.test_utils import TestClient, TestServer
    from miniapp.backend.web import create_app
    from miniapp.tests.test_miniapp import signed

    pool, cfg, service, owner = env
    other = await service.identity(101)
    await service.accept(other)
    image = await service.save_image_work(owner, 83312, 'mock', 'fixture',
                                         SimpleNamespace(image=MOCK_IMAGE, filename='test.png'))
    async with TestClient(TestServer(create_app(pool, replace(cfg, token='fixture')))) as client:
        owner_response = await client.post('/api/v1/session', json={'initData': signed('fixture', 100)})
        other_response = await client.post('/api/v1/session', json={'initData': signed('fixture', 101)})
        assert owner_response.status == other_response.status == 200
        owner_header = {'Authorization': 'Bearer ' + (await owner_response.json())['token']}
        other_header = {'Authorization': 'Bearer ' + (await other_response.json())['token']}
        route = f'/api/v1/works/image/{image}/timeline'
        assert (await (await client.get(route, headers=owner_header)).json())['status'] == 'succeeded'
        assert (await client.get(route, headers=other_header)).status == 404
        assert (await client.get(route)).status == 401
