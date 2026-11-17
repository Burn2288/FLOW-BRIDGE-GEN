# Video delivery safety — proposed acceptance contract

Scope: one already saved video job; these tests use synthetic MP4 bytes, a disposable PostgreSQL schema and a fake Telegram adapter. No Telegram, provider or payment network request occurs. Source is PR #34 at `904aa95e7cc6c42b93c8567bbb86c88832021449`. This document is a proposal for the owner of `video.py`, vankhu21, and is not an implemented contract or evidence of exactly-once Telegram delivery.

Before sending, persist a durable claim for one job. Confirmed Telegram receipt may be recorded as sent. Any outcome that could have reached Telegram — response lost after acceptance, timeout, ambiguous Telegram API error, process crash after claim or while sending — must be recorded as uncertain and must not automatically initiate another send after restart. A timeout alone is not proof that Telegram rejected the send. A separate authorized and auditable reconciliation/manual action may be designed and tested; it is NOT_IMPLEMENTED/NOT_TESTED by this package. Do not solve ambiguity merely by changing the attempt count.

The saved video and its original bytes remain retrievable by the owner, while another identity is denied. Reopening it must not create a provider job, reserve or debit again. Two competing workers cannot send the same claimed job. Record enough non-secret state to investigate, without signed URLs, credentials, raw initData or secrets. The mechanism must distinguish confirmed from uncertain outcomes; exact state names and schema require owner review.

## Reproducible checks

- Existing regression: `python -m pytest -q -p no:cacheprovider tests/test_video.py tests/test_video_delivery_contract_baseline.py`. This includes existing provider-create, ledger and library paths plus three targeted baseline cases.
- Diagnostic acceptance: `python -m pytest -q -s -p no:cacheprovider tests/video_delivery_diagnostic_cases.py`. The filename is outside ordinary pytest discovery and the separate GitHub Actions job runs it explicitly. It has normal assertions: no xfail, skip or conversion to success. On the current implementation this job is expected to fail, reporting the defect; after the owning developer fixes delivery, the unchanged expectations must pass.
- Both commands require the documented disposable PostgreSQL test profile and synthetic credentials. They do not authorize a live Veo run or real Telegram calls. The diagnostic advances `notify_at` to simulate an elapsed retry interval; it does not sleep two minutes or modify application source.

The selected notify-only mock tests verify that these calls do not create provider requests or mutate the ledger; they do not start a paid provider request. End-to-end quote/reserve/capture is covered separately by the existing video tests, not by the synthetic pre-saved job. Concurrency proves the tested overlapping claim, not arbitrary distributed exactly-once guarantees. Authorization and manual recovery require separate design and tests.
