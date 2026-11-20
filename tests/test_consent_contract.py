import pytest
from elevenbot import consent
from elevenbot.core import ConsentRequired


def test_documents_are_versioned_and_marked_as_test():
    docs = consent.documents()
    assert docs['version'] == consent.CURRENT_VERSION == '1'
    assert docs['test_only'] is True
    assert 'тестовый текст' in docs['terms'] and 'тестовый текст' in docs['privacy']


async def test_accept_presented_version_and_check_updates(env, monkeypatch):
    pool, _, service, user = env
    docs = service.get_consent_documents()
    assert docs == consent.documents()
    async with pool.acquire() as conn:
        assert await service.has_current_consent(conn, user)
    await service.accept(user, docs['version'])
    assert await pool.fetchval('SELECT terms_version FROM identities WHERE user_id=$1', user) == docs['version']
    monkeypatch.setattr(consent, 'CURRENT_VERSION', 'test-next')
    async with pool.acquire() as conn:
        assert not await service.has_current_consent(conn, user)
        with pytest.raises(ConsentRequired):
            await service.authorize(conn, user)
    with pytest.raises(ConsentRequired):
        await service.accept(user, docs['version'])
    with pytest.raises(ConsentRequired):
        await service.accept(user)
    await service.accept(user, 'test-next')
    async with pool.acquire() as conn:
        assert await service.has_current_consent(conn, user)
        await service.authorize(conn, user)
