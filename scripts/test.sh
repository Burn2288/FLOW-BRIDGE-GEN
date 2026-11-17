#!/bin/sh
set -eu
: "${TEST_DATABASE_URL:?genuine ISOLATED PostgreSQL required; no SQLite substitution}"
uv run --locked pytest -q --junitxml=reports/test-results.xml
