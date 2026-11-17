"""All denial cases must fail before asyncpg can open a connection."""
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock
import asyncpg
import pytest
from scripts.disposable_test_db import require_disposable_dsn

ROOT = Path(__file__).resolve().parents[1]
URL = 'postgresql://postgres:fixture-only-disposable@127.0.0.1:55432/elevenbot_test'
VALID = {'TEST_DATABASE_URL': URL, 'DISPOSABLE_POSTGRES_PROFILE': 'github-service',
         'DISPOSABLE_POSTGRES_CONFIRM': 'YES'}


@pytest.mark.parametrize('changes', [
    {'TEST_DATABASE_URL': ''}, {'DISPOSABLE_POSTGRES_CONFIRM': ''},
    {'TEST_DATABASE_URL': 'postgresql://postgres:secret@production.example:55432/elevenbot_test'},
    {'TEST_DATABASE_URL': 'postgresql://postgres:fixture-only-disposable@127.0.0.1:55432/production'},
    {'TEST_DATABASE_URL': 'not a DSN'},
    {'TEST_DATABASE_URL': URL.replace('elevenbot_test', 'wrong_test')},
    {'TEST_DATABASE_URL': URL.replace('127.0.0.1', '192.0.2.10')},
    {'TEST_DATABASE_URL': URL + '?host=production.example'},
    {'TEST_DATABASE_URL': URL + '#fragment'},
    {'DATABASE_URL': 'postgresql://secret@production.example/production'},
    {'DATABASE_MIGRATION_URL': 'postgresql://secret@production.example/production'},
    {'PGOPTIONS': '-c search_path=production'},
    {'DISPOSABLE_POSTGRES_PROFILE': ''},
])
@pytest.mark.parametrize('target', ['tests/conftest.py', 'miniapp/tests/test_miniapp.py'])
async def test_refuses_before_fixture_connect(monkeypatch, tmp_path, changes, target):
    for key in (*VALID, 'DATABASE_URL', 'DATABASE_MIGRATION_URL', 'PGOPTIONS'):
        monkeypatch.delenv(key, raising=False)
    for key, value in (VALID | changes).items():
        monkeypatch.setenv(key, value)
    connect = AsyncMock()
    monkeypatch.setattr(asyncpg, 'connect', connect)
    spec = importlib.util.spec_from_file_location('_fixture_under_test', ROOT / target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fixture = module.env if target.startswith('tests/') else module.account_db
    generator = fixture.__wrapped__(tmp_path)
    with pytest.raises(ValueError, match='rejected before connection') as error:
        await generator.__anext__()
    assert 'secret' not in str(error.value)
    connect.assert_not_awaited()


def test_only_explicit_profiles_accepted():
    assert require_disposable_dsn(VALID) == URL
    compose = {'TEST_DATABASE_URL': 'postgresql://postgres:isolated-test-only@127.0.0.1:5432/elevenbot_test',
               'DISPOSABLE_POSTGRES_PROFILE': 'compose-service', 'DISPOSABLE_POSTGRES_CONFIRM': 'YES'}
    assert require_disposable_dsn(compose) == compose['TEST_DATABASE_URL']
