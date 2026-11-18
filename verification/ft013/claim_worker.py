"""Subprocess fixture using only the validated disposable PostgreSQL profile."""
import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import asyncpg
from elevenbot.config import Config
from elevenbot.providers import MockProvider
from elevenbot.worker import Worker
from scripts.disposable_test_db import require_disposable_dsn


async def main():
    dsn = require_disposable_dsn(os.environ)
    schema = os.environ.get('FT013_SCHEMA', '')
    if not re.fullmatch(r'test_[0-9a-f]{32}', schema):
        raise ValueError('Invalid isolated fixture schema')
    with tempfile.TemporaryDirectory(prefix='ft013-worker-') as storage_dir:
        async with asyncpg.create_pool(dsn, min_size=1, max_size=2, server_settings={'search_path': schema}) as pool:
            worker = Worker(pool, Config(generation_enabled=True, storage=Path(storage_dir)), MockProvider())
            print('READY', flush=True)
            await asyncio.to_thread(sys.stdin.readline)
            row = await worker.claim()
            print(json.dumps({'id': str(row['id']), 'fence': str(row['fence'])} if row else None), flush=True)
            if row and os.environ.get('FT013_HOLD') == '1':
                await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(main())
