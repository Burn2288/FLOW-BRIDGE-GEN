# C-009 — Platega payment adapter adaptation from AI-SHOP-BOT
Status: DESIGN_DRAFT. SOURCE_AI_SHOP confirmed repository contents at Burn2288/AI-SHOP-BOT main SHA 494ab81f5552be836a37ec3aa685e6be8308076c. No port into FLOW-BRIDGE-GEN claimed. Provider API details must be revalidated against current official terms and sandbox before execution.

## User experience
Account → My balance → Top up → select configured amount preset (or custom amount only if enabled and validated) → server creates PaymentIntent and Platega payment → open validated payment URL → manual «Check payment» or verified callback/reconciliation → atomic credit → visible history. Add pending/unknown/manual-review state and support link; choosing Cancel stops UI flow, not necessarily an external payment already created. Transfer and credits never happen from redirect URL or client click alone.

## Payment intent canonical schema
intent_id UUID, owner_id, amount_minor, currency, provider=platega, verified_payload (opaque correlation), external_transaction_id unique nullable, external_payment_url (sensitive/short-lived, do not log), payment_method, status, created/updated/expires/confirmed/credited_at, idempotency_key unique, reconciliation_attempts, last_reconciled_at, next_retry_at, blocked_reason, provider_verified_snapshot, fee fields, source_contract_version.
Proposed states DRAFT → CREATING → REDIRECTED/PENDING → PROVIDER_CONFIRMED → CREDITED; alternate CREATE_UNKNOWN, EXPIRED, FAILED, CANCELED, DISPUTED, CHARGEBACKED, MANUAL_REVIEW. Provider statuses are not our states; translate through explicit tested map. In particular CREATE_UNKNOWN cannot be safely set FAILED after timer alone.

## Source donor implementation facts (not FLOW implementation)
AI-SHOP-BOT code has app/integrations/platega.py, app/services/topup.py, app/services/platega_webhook.py, app/services/topup_reconciliation.py, app/repositories/topup.py, app/repositories/platega_callback.py, app/repositories/platega_alert.py, app/handlers/balance.py and tests. The old design uses SQLite and users.balance_minor / balance_transactions; adapt to PostgreSQL and shared Ledger rather than copy DB writes.
The donor documentation describes POST /v2/transaction/process for creation, GET /transaction/{id} for independent verification, callback header authentication, durable webhook queue and strict CONFIRMED status. Its documentation includes historical statements of not-yet-implemented webhook/worker while code contains related classes: verify effective runtime configuration and test evidence separately before claiming an operational source feature.

## Security & settlement contract
- Platega credentials only from secret references/env, not user inputs. Restrict base URL to trusted HTTPS hosts and validate redirects; ensure no secret leakage.
- Create: bounded amount, currency, unique opaque correlation, return only allowlisted external payment link. If external response times out after submission and id is unknown → CREATE_UNKNOWN, suppress unsafe retries, reconcile.
- Verify: receive external id and independently query Platega by server credentials. Match exact external transaction ID (or verified opaque creation payload when external ID was not yet saved), currency and amount; merely matching user+amount is insufficient. Only documented confirmed payment status may credit.
- Webhook: validate request authentication/signature and max body, persist unique event transactionally before 2xx acknowledgement. Async processing independently verifies actual transaction state. Untrusted callback never writes balance.
- Callback delivery may duplicate and arrive out of order; idempotent event log with unique provider/event ID and unique wallet credit source key. Commit intent status, ledger credit and wallet projection atomically; crash before/after commit tested.
- Fee gross/net scheme is payment-method-specific; never infer from amount. Reject mismatched commission, negative/subkopeck issues and unspecified conversion to MANUAL_REVIEW. Correct handling of CANCELED→CONFIRMED, expiration, disputes requires documented reconciliation decision.
- Chargeback/refund events: flag, alert and reconcile with finance; no silent automatic debit of money already spent. Distinguish pending external refund from internal wallet compensation.

## Presets and settings
Administrators manage sorted, distinct allowed amounts, bounds, enable/disable and cooldown. Donor described /preset_replenishment and preset tables. Current donor handler additionally includes custom amount flow; do not assume old documents are fully current. In FLOW use one Settings service and role-checked UI both for Telegram admin and Mini App.
PAYMENT_ENABLED and PLATEGA_* env/secret configuration control availability. Without credentials the bot remains usable except topup; never create a fake successful invoice.

## Migration plan
(1) Freeze donor SHA and inspect relevant tests/docs, (2) map source method and DB schema to new PaymentIntent/Wallet, (3) implement PlategaGateway interface, (4) wire outbox/callback workers, (5) preserve user-friendly UX with new navigation, (6) DB migration and reconciliation playbook, (7) test exact financial invariants and authorize sandbox/live operations separately. No unreviewed transplant of secrets, SQLite migration numbers or hardcoded admin chat IDs.

## Evidence / acceptance
Create/verify success and pending, duplicate webhook, mismatch external ID/payload/amount/currency/fee, manual status, delayed confirmation, transient 5xx, unknown create, restart mid-credit, concurrent payment attempts, exact one credit, audited admin preset change, cancellation then external confirmation, chargeback without silent debit, full user history. Donor mock PASS does not equal FLOW LIVE PASS.
