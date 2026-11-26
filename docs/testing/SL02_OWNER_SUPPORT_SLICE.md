# SL-02 owner support slice

Historical identity: Burn2288 #24, MASTER #59, SL-02. This FUNCTIONAL_TEST
candidate layers an internal text ticket and immutable message store over
the existing verified transport identity. Admission and blocked-user checks
remain in force. It deliberately does not require purchase consent. The
existing Telegram contact and payment support commands remain available.

The service accepts only a verified transport subject from a trusted adapter.
The HTTP or Telegram transport must authenticate that subject before calling
it. No endpoint, operator role or operator action is exposed by this slice.
Separate AD-01 authority approval is required for operator actions. Attachment
handling, status transitions, notifications and retention/deletion need the
corresponding contract before real deployment. The candidate rejects every
attachment and uses only synthetic text in tests.

Run `python -m pytest -q tests/test_sl02_support_tickets.py` with an authorized
disposable PostgreSQL 16 profile. The suite covers owner-only read and append,
admission changes, idempotent concurrent requests, bounded text and pages,
immutable data and unchanged Wallet/Ledger. It makes no live support claim.
