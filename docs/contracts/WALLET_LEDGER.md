# C-008 — Wallet, Ledger and internal accounting
Status: DESIGN_DRAFT for TARGET; partial SOURCE_PRESENT in unmerged PR #17 SHA d691d54e. Fundamental paid generation and referral invariant.

## Units and ownership
CURRENT UNMERGED SOURCE: PostgreSQL `wallets` with `available`/`reserved`, modes `demo`/`live`, internal DarkFlow tokens, ledger movements in `src/elevenbot/core.py`, `task_wallet.py`, `pricing.py`, migrations 026/034. A Platega payment is RUB in kopecks with a pinned RUB→tokens conversion; existing Telegram Stars charges use XTR. TARGET: one canonical Wallet per user/account/mode and explicit token semantics; do not treat internal tokens, RUB and XTR as interchangeable currencies. Any change to wallet unit requires ADR, migration, pricing/reconciliation tests and owner approval. Never use float for monetary amounts. Snapshot account balances are derived or transactionally maintained projections, not uncontrolled source of truth. Only Billing service may mutate wallet/ledger.

Ledger events include TOPUP_CREDIT, RESERVE, CAPTURE, RELEASE, REFUND, REFERRAL_CREDIT, REFERRAL_REVERSAL, ADMIN_ADJUSTMENT, CHARGEBACK_REVIEW. Each has unique event ID, user/account ID, source entity ID, amount_minor, currency, idempotency_key, created_at, actor/source, status and audit correlation. Ledger entries immutable; corrections are compensating operations with explicit reason and actor. For stronger accounting, use balanced postings / double-entry across user liability, reserved funds, payment clearing and expenses, with sum-zero per currency.

## Invariants
available >= 0 unless an explicitly approved debt mechanism; reserved >= 0; no duplicate effect for one business source; source amount/currency strictly matches; all balance-changing events transactional; concurrency-safe compare-and-swap/row lock in PostgreSQL. Transaction references allow exact reconciliation.
Reserve(job_id,quote_id) → capture(job_id,settlement) when success proven; release(job_id,reason) for verified no-charge failure; refund(job_id,reason) separate from release and requires policy; uncertain paid job retains tracked reservation until resolution or controlled policy. Payment intent success creates single topup credit, never direct SQL from webhook. Admin adjustments require reason, explicit confirmation, RBAC and immutable audit; forbid silently editing amount directly.

## UI
Balance shown as available funds with separately visible reserved (proposed). History combines topups, spending on generation, refunds, bonuses and admin adjustments with clear type, date, amount, status, job/payment IDs and pagination. Pending topup is NOT shown as available credit. Provide user-friendly separate «История пополнений» and «Все операции».

## Referral coupling
Referral reward event is derived from confirmed completed paid generation order (recommended; source AI-SHOP-BOT used delivered purchase instead). No rewards from merely topping up or inviting, unless owner explicitly chooses a different basis. Same reward unique by source event and referral program version; refund reverses reward, with any shortfall tracked as controlled referral debt; never subtract other users' funds without defined policy.

## Operational control
Reconciliation: wallet projection vs ledger, ledger vs payment intents, reservations vs jobs, provider cost vs estimated expense. Daily reporting distinguishes actual revenue/payment, calculated provider expense, unknown/outstanding liabilities; do not label approximate cost as settled paid expense.

## Test matrix
Concurrent 20 reserve requests for same wallet, duplicate payment webhook, duplicate job finish, refund after referral bonus spent, unknown provider outcome, crash between capture and commit, negative amounts, currency mismatch, refund more than captured, admin adjustment without reason, consistency after DB backup/restore.
