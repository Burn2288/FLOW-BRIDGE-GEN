# IN-19 integration readiness 02 — candidate, not acceptance

Starting accepted main: `60254e9ba24acb71d5694a230eebdb547f0e092e`. PR #9 and #10 are merged; PR #11 remains open at `0826afe61d41e9abc8a1d8d0337a158418ddeac9`. No source PR is retargeted or merged to main. The candidate starts at main and merges the existing test composite `abed11649750fe250efcd7065cbf30fe6bb31ad4` (#33), then PR #11, in its own branch only.

## Sources and deduplication

The #33 source includes #28 `6b7c3b14110ddd0a464e115ef654e8f158200906` (HTTPS), #26 `3d8f70863f308d6e17aae55b79c92cd911e6881a` (composite) and its PR #17 `d691d54e0266c3d519d66575555fa45895ef40ac` ancestor. #26 combines the unique test/implementation work from #23 `541b9f73fdcf9a5cc6bb836f43148a4e59c9dab8`, #24 `90f7eccfd3d5ff293d606499d6bd96e425839b8a` and #25 `9bd04dce0b4f16afca76f496a13e604a3e04d31e` as snapshots, not their Git ancestry. Do not replay these PRs on top. Main’s merged #9–#10 are preserved by the first parent. PR #12–#16 are ancestors of #17; #11 includes subsequent unique fixes and is merged separately.

## Conflict and semantic log

Main + #33 merged without textual conflicts. Merging #11 required two resolutions: `src/elevenbot/anymodel.py` preserves both `endpoint` (catalogue diagnosis) and `terminal` (retry prohibition), including when wrapping an error; `tests/test_anymodel_fibo.py` combines funded-wallet and multi-endpoint catalogue fixtures with both restart cases for 503 and timeout. `anymodel_image_jobs.py` auto-merged the 503 retry/terminal logic; its interaction with saved-image delivery remains subject to the regression and peer review. No applied SQL migrations were edited; migrations 014–039 are additions relative to main.

Each common file still requires a single assigned writer and the other developer as reviewer before acceptance. Semantics requiring review include paid POST uncertainty, delivery ambiguity for media other than images, process restart, RBAC/admission revocation and transaction boundaries. FIBO terminal poll failure notification is not evidence of a universal delivery outbox. The individual fixes are candidate code, not owner approval or production readiness.

**VIDEO-DELIVERY-AMBIGUITY / FIX_REQUIRED:** `src/elevenbot/video.py::notify_one` increments `notify_attempts` and defers the next attempt before `send_video`; a Telegram timeout leaves `notify_at` in place and later retries up to three times. If Telegram accepted the first request but its response was lost, duplicate delivery is possible. The image-specific guard does not cover video. Existing stack owner vankhu21 should review and be assigned a writer for a separate fix; Burn2288 reviews shared delivery contracts. Runtime reproduction of this exact ambiguity is NOT_TESTED here; this source-level control-flow finding is an integration blocker, not a claim of an observed duplicate. No universal outbox is claimed.

Ruff flagged a possibly unbound `remaining` in `_verify_png_streams`; initialize it to zero before stream processing. Existing stream initialization overwrites it before use when a stream exists. PNG/APNG/Adam7 regression tests must run against the candidate; no image bytes or size limits are changed.

## Documentation and gates

Documentation PR #22 `f4bb350bd6a82b7f43c2aa8769ed14b5025d5e46` has four merge-tree conflicts against main: `.gitattributes`, `README.md`, `docs/README.md`, `docs/ROADMAP.md`; its adoption remains separate. PR #27 `151c3b7914248662bdf1704830285d8474ed150e`, #29 `6697bfa5ce1a4f5c20c29cd628b2151db1fe306d` and #31 `16e12968dbebaeb2a859de09decf52520ac1bc5d` are not integrated here. IN-18, DC-01 and AU-01 are not accepted. D-02 and D-04 remain open. Historical audit outcomes are not rewritten.

Exact-head GitHub workflows run the disposable PostgreSQL full regression, S2, seeded migration/restore, private-pilot tests, image recovery, isolated HTTPS and lint; see the PR and audit package for actual outcomes and limitations. Local HTTPS is not public Mini App evidence. No live paid calls or production connections are permitted. `IN-19_ACCEPTANCE=PARTIAL` pending integrated evidence, peer review, owner decisions and authorized integration.
