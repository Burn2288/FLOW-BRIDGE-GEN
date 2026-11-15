# C-019/C-020/C-021 — Unified administration

> **Новая сверка с фактическим кодом (PR #17, SHA d691d54e…; 2026-11-15):** Telegram Admin Edition реально существует в `admin_access.py`, `telegram.py`, `model_policy.py`, `tariff_admin.py`, `topup_ui.py`. Сессия пароля process-local, конфигурация `ADMIN_TELEGRAM_IDS`; не переносить в Mini App как веб-роль. Ниже — согласуемая архитектура HTTP admin и UX выбора. Состояние этого кода — SOURCE_PRESENT_UNMERGED + CI_PASS, не принятая main. [Полная инвентаризация](../audit/VANKHU21_IMPLEMENTATION_BASELINE.md).
Status: DESIGN_DRAFT. Source: OWNER_REQUIREMENT + BASE_DIRECTIVE. Existing Telegram admin implementations must be inventoried and preserved in later AS-IS audit, not assumed here.

## Two administrative clients
A. Telegram DM admin: existing commands/menus shall be preserved as compatibility routes and supplemented with new management functions after inventory; inline-message editing paradigm retained. Do not discard previous commands or financial behavior without tested migration/rollback.
B. Mini App /admin: secure graphical console on the same Admin API, reachable via entry chooser only for Telegram IDs in ADMIN_TELEGRAM_USER_IDS env allowlist after verified initData. User/admin chooser may display «Войти в админ-панель» and «Войти как пользователь». User context is normal user, not elevated simulation. The chooser is a UX feature, not an authorization mechanism.

## Authorization
Default deny. Every administrative action needs authenticated Telegram identity and server-checked policy (allowlist, active admin role, resource permission, elevated verification for sensitive actions). Proposed roles: OWNER, ADMIN, OPERATOR, SUPPORT, AUDITOR_READONLY; least privilege and explicit separation of dangerous financial mutations. Env allowlist can bootstrap eligibility, but role grants must be governed by controlled server-side assignments; never trust client role, query parameters, or static menus.
Owner-only high risk: add provider credentials, payment settings, financial adjustments, irreversible removal, consent document publish, production switches. Each high-risk command requires explicit confirmation preview with expected old/new values, request idempotency key, actor and immutable AuditEvent; optionally second approval for critical actions.

## Modules of admin screen
Overview: generation counts, error rates, provider availability, queue, last reconciliation.
Users: ID, status, wallet read-only and audited administrative actions, consent version.
Jobs: locate job by ID, execution timeline, safe retry eligibility and manual uncertain review, worker and delivery status.
Providers: installed adapter families, credentials reference, health, add/stage/activate/pause.
Models: editable capability schema, model visibility, limits, version, stage/publish.
Pricing: rules, cost vs sale separation, quotes snapshot, preview/rollback, role-limited publish.
Payments: topup intents, pending/unknown, verified transactions, reconciliation, disputes.
Wallet/Ledger: ledger, holds and correction commands with immutable traces (no direct balance edit).
Referrals: program percent, rule version, earned/credited/reversed rewards and debt ledger.
Support: tickets, replies, attachments and escalation.
Reports: operational metrics, financial metrics, exports, provenance of estimated/actual costs.
Settings: feature flags, UI catalog ordering, rate limits, menu copy, retention policies.
Audit: who changed what, before/after redacted values, timestamp, SHA/config version, cause and approval.
Security: read-only credential health and last rotation time; no plaintext secrets in UI.

## Typed settings transaction
Each setting declares key, type, units, allowed range/enumeration, secret flag, required admin permission, default, environment override policy, version, rollback strategy, service owner, dynamic/restart-required flag. Changes are validated against full candidate config and committed atomically; publish a settings-version event. Invalid edit must leave prior valid config intact. Persist history and allow rollback without deleting audit.
Do not allow arbitrary SQL/Python or unrestricted provider URL from admin. For new protocol use reviewed adapter deployment.

## Telegram admin preservation plan
Future S0 must inventory original admin bot menu, commands, screen states, roles, edit-message flows, features and DB fields from permitted baseline source — retain exact command names and compatibility tests. Current documentation alone cannot claim they already work in FLOW.
Add navigation to same Admin API/service (not separate finance/catalog logic). Legacy endpoints remain until tested transition.

## Admin acceptance
Nonallowlisted user never sees chooser and cannot access /admin directly. Allowlisted user with no role may see chooser but is denied admin route. Expired/tampered initData cannot grant role. Changing env allowlist requires restart/reload policy, documented. Role removal revokes session privileges. Every settings edit and financial action audited, with double-click idempotency and optional step-up. New AI provider staged in admin and exposed in both user clients only after approved publish.
