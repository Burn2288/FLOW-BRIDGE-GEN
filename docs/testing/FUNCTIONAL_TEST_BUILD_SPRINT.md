# FUNCTIONAL_TEST build sprint

Use a clean checkout of this Draft PR. Follow [deployment](../operations/DEPLOYMENT.md) for prerequisites. Use the repository's disposable test profile rather than a production configuration.

```sh
docker compose -p ftl1-build -f compose.test.yaml run --build --rm tests \
  python -m pytest -q -ra tests/test_ft022_referrals.py tests/test_anymodel_fibo.py \
  tests/test_http_admin_authority.py tests/test_sl02_support_tickets.py
docker compose -p ftl1-build -f compose.test.yaml down --remove-orphans
```

This command exercises PostgreSQL, the application backend, and synthetic Telegram flows. Use the OP01 and OB02 workflows for the repository's headless Chromium proofs. A full integrated smoke result must be recorded for the exact candidate SHA before acceptance.

In Mini App, sign in through the existing Telegram launch flow. Open Administration and refresh. The application requests current capabilities, then loads the operations report only when operations.read is present. A role must be seeded solely for a synthetic account in the disposable test environment. Revocation is checked server-side on the next request. The visibility mutation remains disabled pending a concrete approved setting.
