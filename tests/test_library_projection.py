from datetime import datetime, timezone
from uuid import UUID

import pytest
from elevenbot.library import LibraryItem


@pytest.mark.parametrize('kind', ['image', 'audio', 'video', 'chat', 'music'])
def test_saved_results_have_shared_projection(kind):
    row = {'id': UUID('00000000-0000-0000-0000-000000000001'), 'kind': kind,
           'model_id': 'fixture-model', 'status': 'succeeded', 'file_available': True,
           'price': None, 'created_at': datetime(2026, 1, 1, tzinfo=timezone.utc)}
    item = LibraryItem.from_history(row).as_dict()
    assert item == {'id': str(row['id']), 'kind': kind, 'model': 'fixture-model',
                    'status': 'succeeded', 'available': True,
                    'created_at': '2026-01-01T00:00:00+00:00', 'price': None,
                    'result_url': f"/api/v1/works/{kind}/{row['id']}"}


def test_unavailable_item_cannot_be_presented_as_available():
    row = {'id': UUID(int=2), 'kind': 'audio', 'model_id': None, 'status': 'failed',
           'file_available': None, 'price': 17, 'created_at': datetime(2026, 1, 1, tzinfo=timezone.utc)}
    item = LibraryItem.from_history(row).as_dict()
    assert not item['available'] and item['price'] == '17'


async def test_http_lists_all_types_from_existing_history(monkeypatch):
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock
    from aiohttp.test_utils import TestClient, TestServer
    from elevenbot.config import Config
    from elevenbot.core import Service
    from miniapp.backend.web import create_app

    owner = UUID(int=23)
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            class Connection:
                fetchval = AsyncMock(side_effect=[owner, 100])
            yield Connection()
    rows = [{'id': UUID(int=i), 'kind': kind, 'model_id': 'mock', 'status': 'succeeded',
             'file_available': True, 'price': None, 'created_at': datetime(2026, 1, 1, tzinfo=timezone.utc)}
            for i, kind in enumerate(('image', 'audio', 'video', 'chat'), 1)]
    monkeypatch.setattr(Service, 'authorize', AsyncMock())
    history = AsyncMock(return_value=rows)
    monkeypatch.setattr(Service, 'history', history)
    async with TestClient(TestServer(create_app(Pool(), Config(token='fixture')))) as client:
        response = await client.get('/api/v1/works', headers={'Authorization': 'Bearer ' + 'x' * 43})
        assert response.status == 200
        result = (await response.json())['works']
        assert [item['kind'] for item in result] == ['image', 'audio', 'video', 'chat']
        assert all(item['available'] and item['status'] == 'succeeded' for item in result)
        history.assert_awaited_once_with(owner, 0, include_pending_tasks=True, include_music=False)
