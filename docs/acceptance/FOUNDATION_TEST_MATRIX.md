# Foundation acceptance matrix — requirement to contract to evidence
Status: PLANNED / NOT_TESTED for FLOW-BRIDGE-GEN. Only read-only documentation analysis and source mapping conducted.

| Requirement | Contract(s) | Planned proof |
| --- | --- | --- |
| /start identity & legal gate | C-001/002/003 | first/repeat /start; both .md; stale agreement |
| DM editing-menu navigation | C-004 | Back, replacement edit fallback, ≤5/page |
| Four studio types and real model prices | C-006/007/012 | model capability forms, quotes, checkout |
| Library saved paid content | C-016/017/018 | restart, cross-user denial, resend no charge |
| Mini App parity with bot | C-005/024 | same user, wallet, library, jobs, action outcomes |
| Admin launch chooser by env ID | C-003/020/026 | allowlist + signed initData, server role check |
| Retain Telegram admin functions | C-019 | inventory baseline commands, parity tests before migration |
| Add any AI aggregator without core rewriting | C-013/014/015 | second adapter type and staged model, UI unchanged |
| Reusable donor referral module | C-010/011 | deep link, binding, reward, reversal, debt |
| Reusable donor Platega topup | C-008/009 | verified credit once, webhook/recovery/manual review |
| Safe global finances and jobs | C-008/012/025 | concurrent reserve, unknown paid job, crash |
| Operational safety | C-026/027/028 | secrets, SSRF, logs, incident runbook and restore |

## E2E milestones, detailed criteria
F0 Documentation: all required contract links resolve, documents mark provenance and maturity, no secrets, no changes to developers' plans or implementation.
S0 Evidence baseline: exact FLOW source SHA and database migrations; map existing Telegram admin features; separate previous findings from confirmed defects.
S1 Image vertical slice: three real successful executions; provider returned bytes; image validated+stored; user library survives restart; Telegram API receipt and if possible user-visible verification; no duplicate charges; one transient outage.
S2 Concurrency: simulated 10/50/100 jobs, no double claim, fair and bounded queue, recovery, latency metrics, failover blocked on unknown paid outcome.
S3 Common Job contracts: sync/async job transitions, no blind paid retry and recovery.
S4 Provider adapters: schema validation, second adapter and provider test suite; API/consumers unchanged.
S5 Mini App/public API: authenticated data equality and complete core user flow; admin chooser security.
S6 Admin and reports: editable settings with version rollback, RBAC, job diagnosis, payment and financial reconciliation.
S7 Financial/security hardening: PostgreSQL transaction races, verified credit, reversal, abuse probes, restore.
S8 Pilot criteria: Ubuntu deployment, backup recovery, limited pilot with explicit exclusions; do not silently declare commercial ready.

## Evidence requirement per test
contract_id, test_id, scenario, environment, repository+commit_sha, configuration redacted, command/method, timestamps, expected and actual results, evidence artifact link, reviewer, status. PASS requires independently inspectable artifact; MOCK_PASS is not LIVE_PASS; if no access use BLOCKED_EXTERNAL; software success without physical proof → SOFTWARE_PASS/LIVE_NOT_PROVEN. Test omitted → NOT_TESTED.

## Source-aware acceptance gates after vankhu21 code inspection

| Source-backed scenario | Current evidence | Remaining acceptance |
| --- | --- | --- |
| Mini App initData/session/catalogue/wallet/library/theme | CODE_PRESENT in PR #17, two success Actions at exact SHA | HTTPS Telegram client physical E2E and production auth/session review |
| Mini App paid generation, referral, payment, web-admin | No endpoints in checked `miniapp/backend/web.py` | Transport-neutral API, RBAC, client UI and regression tests |
| Provider registry, third adapter | Code/test fixture exists; CI success | Approved manifest/onboarding and provider-live proof |
| Telegram Stars XTR and refunds | Source paths exist | Contract C-031; one-config synthetic and authorized Stars test payment |
| Platega topups/ledger | Source paths and mock test suite exist | No Platega checkout for digital in-Telegram product; authorized separate integration proof |
| Shared accepted build and local machine sync | PR #8–#17 all open; origin/main README-only | Peer review/merge gates, CI current SHA, then full clone FF and regression |
