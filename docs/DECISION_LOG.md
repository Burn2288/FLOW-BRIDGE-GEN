# DECISION LOG — pending architecture decisions
Status: proposal register; no owner approvals implied. Keep append-only ADR entries with date, participants, alternatives, consequences and exact source.

| ID | Proposed decision | Alternatives / tradeoff | Approval |
| --- | --- | --- | --- |
| D-001 | Single backend core for DM + Mini App | Separate backends rejected due to wallet/job divergence | PENDING_OWNER |
| D-002 | Modular monolith with independent workers on PostgreSQL | Microservices and in-process long jobs not default | PENDING_OWNER |
| D-003 | Env Telegram user ID allowlist for Mini App chooser + server RBAC | Visibility alone must not grant privileges | PENDING_OWNER |
| D-004 | Installed reviewed provider adapter packages + dynamic model manifests | Arbitrary user-supplied HTTP scripts unsafe | PENDING_OWNER |
| D-005 | Generation refund/capture only via Ledger, never handler SQL | Simpler direct balance mutation fails race/audit | PENDING_OWNER |
| D-006 | Refer to AI-SHOP-BOT as donor, adapt not blindly copy | SQLite purchase code is not AI-job schema | PENDING_OWNER |
| D-007 | Consent versioned with persistent acceptance history | Simple boolean can't prove current document consent | PENDING_OWNER |
| D-008 | Persistent paid-media library, separate Telegram delivery | Telegram-only storage cannot guarantee access | PENDING_OWNER |
| D-009 | Quoted generation price immutable with explicit expiry | Current admin tariff cannot rewrite past charges | PENDING_OWNER |
| D-010 | Payment webhook verified by backend independent API read | Browser redirect or callback body alone unsafe | PENDING_OWNER |

## ADR template
Decision ID, date, reason, affected contracts, current proven state, alternatives considered, selected choice, security/cost/performance effects, migration impact, rollout/rollback steps, required test evidence and owner approval.

## No implicit code tasks
These are architectural choices pending approval, not assigned to either developer. Personal plans and work branches remain untouched.
