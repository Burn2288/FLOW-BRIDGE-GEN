# C-031 — Telegram Stars as compliant digital-services checkout

Status: DESIGN_DRAFT + PLATFORM_REQUIREMENT verified against official Telegram documentation on 2026-11-15. This is a product/compliance gate, not legal advice, and no real payments or new code have been executed.

## Verified platform requirement
Official [Telegram Bot Payments for Digital Goods](https://core.telegram.org/bots/payments-stars) and [Developer Terms §6.2](https://telegram.org/tos/bot-developers) state digital goods/services sold inside Telegram bots and Mini Apps must be paid exclusively through Telegram Stars (XTR), including when a provider offers an external web payment page. Media generation is a digital service. External Platega checkout should therefore **NOT** be enabled as a substitute for Stars in the in-Telegram digital-product flow. Independent outside-Telegram legal channels would require separate formal product/sales/legal analysis and must not be an evasion route.

## Existing SOURCE_PRESENT before new work
At work/vankhu21/miniapp-read SHA d691d54..., `src/elevenbot/telegram.py` already has `send_invoice(... currency='XTR')`, `pre_checkout_query`, `successful_payment`, `refunded_payment`, `refund_star_payment`; `src/elevenbot/core.py` has `order`, `precheckout`, `payment`, `prepare_refund`, `complete_refund`; CLI `python -m elevenbot reconcile-stars` exists. `src/elevenbot/config.py` accepts `PAYMENT_BACKEND=stars`; payments are feature-gated. These are code paths, not proven production deployment. Reuse and harden, do not blindly recreate Stars processing.
Existing separate Platega files `src/elevenbot/topups.py`, `platega.py`, `topup_ui.py` handle external methods and share wallet/ledger; preserve their tests and logic without exposing prohibited checkout inside Telegram for digital goods.

## Unified PaymentGateway contract
A checkout adapter must implement CreateOrder, VerifyPaid, Reconcile, Refund/Review. One canonical user wallet in internal tokens; external settlement denominated in Stars (XTR) or in a separately approved external channel. Every order snapshots conversion policy and amount; no float, no silent re-pricing, one credit per confirmed event; provider-specific tokens are not internal bot-token units. All creation/verification/refund events are traceable in ledger. Telegram payments require pre_checkout and successful_payment validation; no credit from the invoice send/press alone. Guard duplicate update, delivery timeout, refund idempotency and partial/unknown states.
Mini App displays the same Stars-compliant payment mechanism for in-Telegram product; do not render direct Platega for digital service unless compliance is positively established and documented.

## Security and acceptance
Enforce ownership, current consent, immutable merchant and price snapshot, XTR currency and amount, stable Telegram charge ID, replay protection, authorized refund and `/paysupport` handling. Tests: duplicate successful_payment, precheckout mismatch, forged update, delayed confirmation, refund after spent balance with debt policy, race with generation hold, restart, Stars test environment, real Telegram client proof; no real funds without owner consent. Link to original official guidance in any production checklist. `PASS` for Stars only after proper test and independent evidence.

## Decision gate
Before commercial release, choose and document (with owner confirmation) Stars package prices, credit conversion, refund policy, tax/fee implications, administrative controls, customer disclosure and media licensing. If choice unresolved: payments for digital generation remain disabled, while read-only catalogue and demo tests may operate.
