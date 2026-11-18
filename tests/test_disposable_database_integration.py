"""Real disposable PG: repeat the guarded fixture and preserve a neighbour."""
import asyncio
import os
import sys
import uuid
from pathlib import Path
import asyncpg

ROOT = Path(__file__).resolve().parents[1]


async def test_guarded_fixture_repeated_preserves_neighbour(env):
    pool, _, _, _ = env
    schema = 'neighbour_' + uuid.uuid4().hex
    admin = await asyncpg.connect(os.environ['TEST_DATABASE_URL'])
    created = False
    try:
        await admin.execute('CREATE SCHEMA ' + schema)
        created = True
        await admin.execute('CREATE TABLE ' + schema + '.marker (value integer NOT NULL)')
        await admin.execute('INSERT INTO ' + schema + '.marker VALUES (41)')
        before = {r['nspname'] for r in await admin.fetch("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'test\\_%' ESCAPE '\\'")}
        for _ in range(2):
            process = await asyncio.create_subprocess_exec(
                sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                'tests/test_task_wallet.py::test_confirmation_uses_live_wallet_and_server_quote',
                cwd=ROOT, env=os.environ.copy(), stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT)
            output, _ = await asyncio.wait_for(process.communicate(), 180)
            assert process.returncode == 0, 'nested fixture test failed (output redacted)'
            assert b'1 passed' in output
            after = {r['nspname'] for r in await admin.fetch("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'test\\_%' ESCAPE '\\'")}
            assert before == after
            assert await admin.fetchval('SELECT value FROM ' + schema + '.marker') == 41
        assert not pool._closed
    finally:
        try:
            if created:
                await admin.execute('DROP SCHEMA ' + schema + ' CASCADE')
        finally:
            await admin.close()
