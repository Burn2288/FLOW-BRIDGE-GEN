# Media delivery compatibility candidate

PREPARATION_ONLY. Base: PR #32 `46ffc9b7f7682ca069f670262480a2ab6e16fb51`.
This candidate merges PR #25 `9bd04dce0b4f16afca76f496a13e604a3e04d31e`
without rewriting Burn2288's commits, then adds explicit delivery metadata and
the corresponding Veo stop-before-I/O boundary. PR #35 at
`769dbf3e501fdada4bcea60dee775388228397f8` is diagnostic evidence, not a fix.

The claim transaction writes the worker's automatic-send stop marker and an
`unknown` record in `task_media_delivery` before invoking Telegram. An acknowledged
response records `sent` and its message ID. A definite BadRequest or RetryAfter
records `rejected` and permits at most three attempts, respecting Retry-After.
Timeout, transport error, decode error, cancellation and process loss leave
`unknown`; another worker or process must not automatically send again.
The claim UUID fences receipt updates. This is conservative at-most-once automatic
attempt after ambiguity, **not** exactly-once Telegram delivery. A crash before the
network request may leave an undelivered file for manual retrieval.

Provider task status, bytes, ownership, quota, wallet and ledger are independent
of this receipt. The owner can explicitly reopen the saved result in My Works;
this is a new requested delivery, not a generation or financial operation.
There is no administrative force-retry or reconciliation UI in this candidate.

Migration `041_media_delivery.sql` is additive. Number 040 is already used by
Burn2288's independent PR #38; coordinate final numbering/order with Burn2288
before integration. Historical unacknowledged attempts are conservatively marked
unknown and stopped, while prior confirmed sends are imported as sent. Receipt
message IDs for historical records remain unavailable. Existing SQL checksums
must remain unchanged. Applying 041 does not adopt PR #38 or its policy.

Shared-file boundary: the PR #25 implementation and routing are reused intact
as ancestry. Compatibility additions to its image notify transaction and new
delivery metadata are isolated here; Burn2288's source branch is unchanged.
vankhu21 writes this candidate's `video.py` slice; review of the shared image
worker, receipt contract and new migration by Burn2288 remains required. This
does not supersede the broader job lifecycle or admission work.

Tests (disposable PostgreSQL, HTTP/Telegram mocks only):

```sh
python -m pytest -q -s -p no:cacheprovider tests/test_delivery_ambiguity.py tests/test_ml01_delivery_recovery.py
python -m pytest -q -ra -p no:cacheprovider
```

The dedicated tests exercise provider create/poll, accepted-but-lost acknowledgement,
actual fresh worker processes, cancellation, definite rejection, 429, competing
workers, preserved media/ledger and owner-only reopening, plus seeded 039-to-041
upgrade and a second migration pass. Real clients, real provider contracts and
real financial operations remain outside this acceptance.
