# C-024/C-025 — HTTP API v1 and event contracts
Status: DESIGN_DRAFT; next run must produce executable OpenAPI 3.1 and JSON schemas. Mini App requires genuine backend API; Telegram presentation may call the same application services directly in monolith, with identical permissions and output semantics.

## API baseline
Base path /api/v1; JSON request/response; authenticated identity from validated Telegram initData plus short-lived session; never accept user_id as authoritative in body/query. Mutations require idempotency-key with stable semantic payload, conflict response for changed payload using reused key. Cursor pagination supported. Consistent UTC timestamps, stable IDs, integer minor currency units and versioned model schemas.
Standard error envelope: {code, message, request_id, retryable, details?}; details never contain credentials or raw provider payload. Map to 400 validation, 401 auth, 403 access/consent, 404 owner-scoped not found, 409 conflict/stale quote, 422 unsupported parameters, 429 limits, 502 provider protocol failure, 503 unavailable, 504 timeout. Unknown paid operation returns stable job status UNCERTAIN, not an arbitrary 500 that triggers auto-repeat.

## Initial endpoints (proposed)
POST /auth/telegram/exchange; POST /auth/logout; GET /me; GET /legal/current; POST /legal/accept
GET /catalog/providers; GET /catalog/models?kind=; GET /catalog/models/{id}; POST /quotes
POST /jobs; GET /jobs/{id}; GET /jobs?cursor=; POST /jobs/{id}/cancel
GET /library?kind=&cursor=; GET /library/{id}; POST /library/{id}/resend; POST /library/{id}/download-link
GET /wallet; GET /wallet/transactions; GET /payments/topups; POST /payments/topups; GET /payments/topups/{id}; POST /payments/topups/{id}/verify
GET /referrals; GET /referrals/invitees; GET /referrals/rewards
GET /support/tickets; POST /support/tickets; GET /support/tickets/{id}; POST /support/tickets/{id}/messages
GET /admin/overview; GET /admin/jobs; GET /admin/payments; GET /admin/providers; POST /admin/providers/drafts; POST /admin/providers/{id}/activate
GET /admin/settings; PATCH /admin/settings/{key}; GET /admin/audit
Webhook endpoints isolated: POST /webhooks/platega (provider auth; not user session); POST /webhooks/providers/{adapter_id} (adapter-specific signatures).

## Events and transactional outbox
UserRegistered, LegalConsentAccepted, QuoteCreated, FundsReserved, JobQueued, JobClaimed, ProviderSubmitted, ProviderCompleted, MediaSaved, LibraryItemCreated, FundsCaptured, FundsReleased, DeliveryRequested, DeliverySucceeded/Failed, PaymentVerified, PaymentCredited, ReferralRewardGranted, ReferralRewardReversed, SettingsPublished. Every envelope: event_id, type, schema_version, aggregate_id/version, occurred_at, causation_id, correlation_id, actor, redacted payload, dedup_key.
Persistent outbox is committed within source transaction and dispatched at least once; listeners must deduplicate, never rely on exactly-once transport. Ordering guaranteed only per aggregate when implemented using version checks. No ledger mutation from unverified external callbacks.

## Security
CORS allowlisted Mini App origin, no wildcard with credentials; CSRF protection for cookies; rate limits, content-size limits and strict schema; structured secure logging; OpenAPI docs restricted as appropriate. Short-lived signed media URLs, owner checks, authz at command boundaries. Audit role and consent on server on every protected action.

## E2E parity acceptance
For each API mutation: Telegram handler and Mini App button invoke same application command and produce same persisted state. Verify double clicks, race, changed quote, revoked role, malformed schema, high-cost generation and delayed outbox event. Physical Telegram Mini App use and provider live verification remain separate evidence levels.
