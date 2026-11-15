# Donor mapping — AI-SHOP-BOT → FLOW-BRIDGE-GEN
Status: SOURCE_AI_SHOP inspected by auditor on 2026-11-15. Private source repository: https://github.com/Burn2288/AI-SHOP-BOT ; frozen SOURCE SHA: 494ab81f5552be836a37ec3aa685e6be8308076c (main, 2026-11-08). Access requires the developer's permitted GitHub credential. No donor code has been copied into FLOW.

## Source inventory: referrals
- app/handlers/referrals.py — referral page, link, pagination, edit-media/caption fallback.
- app/handlers/start.py — /start deep links, referral binding and consent gate.
- app/repositories/referrals.py — stable code generation, lookup, inviter counts and confirmed purchase turnover.
- app/repositories/referral_settings.py — dynamic percent (default 10, range 0..100).
- app/repositories/referral_rewards.py — credit/reversal/debt offset, unique purchase-based accounting.
- app/services/referrals.py — readable referral page text and escaping.
- app/repositories/users.py — immutable referral binding through upsert.
- app/database/schema.sql and app/database/migrations.py — exact source schema and constraints.
- app/keyboards/inline.py — referral keyboard and pagination.
- tests/test_referrals.py, tests/test_task16_referrals_and_markup.py, tests/test_migrations.py — donor test ideas and fixtures.
- docs/USER_FLOWS.md and docs/DATA_MODEL.md — original business flows.

## Source inventory: Platega
- app/integrations/platega.py — authenticated HTTP client, errors, bounded requests.
- app/services/topup.py — amount parsing, quote validation, payment create/verify and safety rules.
- app/services/platega_webhook.py — callback validation, queue worker, alerts and callback web application.
- app/services/topup_reconciliation.py — reconciliation worker.
- app/repositories/topup.py — PaymentIntent DB lifecycle, atomic credit and presets.
- app/repositories/platega_callback.py — durable callback records and work queue.
- app/repositories/platega_alert.py — delivery of administrator notifications.
- app/repositories/transactions.py — balance transaction querying.
- app/handlers/balance.py — topup presets, optional custom amount, payment check and history UI.
- app/config.py, .env.example — credential and runtime toggles.
- tests/test_platega_client.py, tests/test_platega_webhook.py, tests/test_topup_end_to_end.py, tests/test_topup_service.py, tests/test_topup_reconciliation.py, tests/test_topup_repository.py, tests/test_topup_history_lifecycle.py and tests/test_topup_custom_amount.py — verification sources.
- docs/modules/BALANCE_TOPUP_PLATEGA.md, docs/integrations/PLATEGA.md, docs/adr/002-platega-balance-topup.md, docs/SECURITY.md, docs/OPERATIONS_RUNBOOK.md — source design/restrictions.

## Exact retrieval guide for Codex
Using an account authorized for private donor:
  git clone https://github.com/Burn2288/AI-SHOP-BOT.git
  cd AI-SHOP-BOT
  git fetch origin
  git checkout --detach 494ab81f5552be836a37ec3aa685e6be8308076c
  git rev-parse HEAD
  git show HEAD:app/repositories/referral_rewards.py
  git show HEAD:app/services/topup.py
Prefer a separate read-only donor clone, not a git remote that is automatically merged. Work inside isolated FLOW task branch after approved task breakdown (not in this documentation-only run). Do not commit secrets or vendor caches. Preserve original copyright/licensing obligations as applicable; repository access does not by itself establish rights to relicense third-party code.

## Adaptation rules
1. Inventory source handler/service/repository and tests at frozen SHA, map commands, state transitions, unique indexes and failure paths.
2. Generalize donor purchase → captured paid generation job only after policy approval. Change referral base, refund policies, reward semantics, UI and transactional guarantees deliberately; do not merely rename tables.
3. Generalize SQLite BEGIN IMMEDIATE and users.balance_minor → PostgreSQL transaction/row lock and shared Ledger. Keep idempotency/business keys, verified status and payload binding; rewrite DB-specific SQL and migrations.
4. Adapt Platega provider client to Gateway interface isolated from wallet; ensure provider status is not direct trusted settlement. Document provider API version change.
5. Replace hardcoded support group IDs, bot file IDs, brand labels and env defaults with FLOW-controlled settings.
6. Reuse source regression scenarios as donor-specific examples but require new FLOW contract, integration and live checks.
7. Explicitly distinguish SOURCE_PRESENT, PORTED, TESTED, LIVE_PROVEN. No direct code transplant is claimed in this phase.

## Potential discrepancy and verification
Donor written module describes a webhook and background daemon as not implemented in one historical section; current inspected source has classes create_platega_webhook_app, PlategaCallbackQueueWorker, PlategaReconciliationWorker. This demonstrates why code inventory and startup wiring/runtime evidence must supersede outdated prose. No claim was made about successful donor production webhook usage.
