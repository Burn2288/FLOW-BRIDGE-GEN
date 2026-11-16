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

## Новые решения / риски после сверки кандидатного кода

| ID | Решение / риск | Основание | Статус |
| --- | --- | --- | --- |
| D-011 | Применять существующую реализацию vankhu21 (ProviderRegistry, Ledger, TaskLaunch, Mini App) как исходный кандидат, не переписывать | PR #17 d691d54e; inventory | PENDING_OWNER_INTEGRATION |
| D-012 | Соблюсти порядок исторического стэка PR #8–#17, сначала ревью, CI, затем merge и sync | CONTRIBUTING.md / BRANCH_INTEGRATION_PROTOCOL | PENDING_OWNER |
| D-013 | Telegram digital-service checkout через Stars; Platega не включать внутри Telegram для продажи цифровых услуг | Telegram developer TOS §6.2; C-031 | PLATFORM_REQUIREMENT / IMPLEMENTATION_PENDING |
| D-014 | Внутренние токены DarkFlow, RUB и XTR различаются; курс фиксируется в платёжном заказе | code pricing.py, topups.py, wallet | PENDING_OWNER_FINAL_ACCOUNTING |
| D-015 | Для Mini App admin beta использовать уже существующий `ADMIN_TELEGRAM_IDS` как eligibility и отдельный server role | Config source and ADMIN_CONTROL | PENDING_OWNER |
| D-016 | Сохранять Mini App read-mostly как основу, наращивать узкие endpoints вместо второго API | web.py + miniapp tests | PENDING_OWNER |

Следующие документы: [инвентаризация](audit/VANKHU21_IMPLEMENTATION_BASELINE.md), [протокол веток](coordination/BRANCH_INTEGRATION_PROTOCOL.md), [конструктор Codex](codex/PROMPT_FACTORY.md). Ни одна запись PENDING не является разрешением менять рабочий код или проводить реальные платежи.

## TASK-PLAN-001 — proposals, 2026-11-16

- P-001: source-aware task registry и два worklist вместо повторной реализации существующих модулей; owner approval pending. Автор сложных financial компонентов vankhu21 сохраняет их развитие, Burn2288 reviewer/contract owner.
- P-002: рабочий package docs/audit/handoffs, долгосрочное отображение в audit-artifacts/audit/handoffs; auditor read-only для разработчиков; schema 2020-12 + docs checks; bootstrap archive branch отдельным PR после approval.
- P-003: immutable tested content SHA отличается от artifact/publication SHA, чтобы manifest не требовал невозможной самоссылки; final PR HEAD checks отдельно.
- P-004: TASK-PLAN-001 разрешает planning branch от foundation; повторяющиеся branch exceptions только после review. Ни один новый процесс не молча отменяет CONTRIBUTING.

Решения D-01…D-10 плана — открытые owner gates, не approvals старого D-001…D-016. Таблицы исторических решений не удаляются.
