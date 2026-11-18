"""Functional smoke of the existing speech queue; no real providers or payments."""
from elevenbot.providers import MockProvider
from elevenbot.telegram import STATUS
from elevenbot.worker import Worker


async def test_queue_cancel_and_mock_completion(env):
    pool, cfg, service, user = env
    provider = MockProvider()
    worker = Worker(pool, cfg, provider)
    before = await service.wallet(user)
    quote, _ = await service.quote(user, 'Cancel this', 'demo')
    cancelled = await service.confirm(user, quote)
    assert (await service.owned(user, cancelled))['status'] == 'queued'
    assert STATUS['queued'] == 'В очереди'
    assert await service.cancel(user, cancelled)
    assert (await service.owned(user, cancelled))['status'] == 'cancelled'
    assert STATUS['cancelled'] == 'Отменено'
    after_cancel = await service.wallet(user)
    assert (after_cancel['available'], after_cancel['reserved']) == (before['available'], before['reserved'])
    assert not await worker.run_one()
    assert provider.calls == 0

    quote, _ = await service.quote(user, 'Complete this', 'demo')
    completed = await service.confirm(user, quote)
    assert (await service.owned(user, completed))['status'] == 'queued'
    assert await worker.run_one()
    result = await service.owned(user, completed)
    assert result['status'] == 'succeeded' and STATUS['succeeded'] == 'Готово'
    assert worker.storage.path(result['storage_key']).is_file()
    assert provider.calls == 1
    assert (await service.wallet(user))['reserved'] == 0
    print('QUEUE=queued; CANCEL=cancelled; MOCK_RESULT=succeeded; PROVIDER_CALLS=1')
