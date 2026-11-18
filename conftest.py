"""Apply the disposable DSN guard before tests that consume TEST_DATABASE_URL."""
import os
import pytest
from scripts.disposable_test_db import require_disposable_dsn


@pytest.fixture(autouse=True)
def _guard_supplied_test_database():
    # Non-database unit tests remain runnable without a DSN. Any supplied DSN
    # must be validated before fixture setup, even for direct-connection tests.
    if 'TEST_DATABASE_URL' in os.environ:
        require_disposable_dsn(os.environ)
