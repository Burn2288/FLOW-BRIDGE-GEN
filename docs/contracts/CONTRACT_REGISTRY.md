# CONTRACT REGISTRY — реестр основополагающих контрактов

Статус: DESIGN_DRAFT. Следующие итерации должны довести каждый контракт до схем полей, команд, событий, ошибок, версий, migration, property/contract/integration/E2E тестов и acceptance evidence.

## Статусы и версия

Документальная зрелость: DRAFT → REVIEWED → APPROVED → IMPLEMENTED@SHA → VERIFIED@SHA. При DRAFT значения являются предложением. Результаты отдельных проверок: PASS / PARTIAL / FAIL / BLOCKED / NOT_PROVEN / NOT_TESTED. Любой PASS требует ссылки на evidence, среду и SHA. Для внешних API отдельно MOCK_PASS / PROVIDER_LIVE_PASS, никогда не смешивать.

## Доменные контракты

| ID | Контракт | Команды/события и обязательный инвариант | Тест-приёмка |
| --- | --- | --- | --- |
| C-001 | Identity | register/upsert; один Telegram ID → один user | повтор /start не обнуляет кошелёк |
| C-002 | Legal Consent | accept(version); без действующей версии gate | устаревшая кнопка отвергается |
| C-003 | Sessions/Auth | validate initData, issue session, revoke; server-authoritative | подмена user_id отклоняется |
| C-004 | Telegram Navigation | render(route, page, state); единое меню и Back | переходы и fallback edit |
| C-005 | Mini App Navigation | route/view model; те же команды API | parity Telegram/Mini App |
| C-006 | Capabilities/Models | list/filter; модель разрешена/активна | disabled model не выбирается |
| C-007 | Price Quote | calculate/version/expiry; неизменна для job | смена тарифа не меняет прошлый quote |
| C-008 | Wallet | reserve/capture/release/refund; нет двойных проводок | одновременная гонка не уводит баланс в минус |
| C-009 | Payment Intent | create/verify/reconcile; нет зачисления по redirect | duplicate webhook ровно одна запись |
| C-010 | Referral Attribution | bind-on-first-registration; immutable | self-referral/rebinding отвергаются |
| C-011 | Referral Rewards | grant/reverse/debt; уникальность по событию | refund и повтор не создают бонус дважды |
| C-012 | Generation Job | create/claim/transition; stable owner+id | crash recovery с fencing |
| C-013 | Provider Adapter | execute/poll/cancel; normalized result | второй adapter без правки UI |
| C-014 | Provider Registry | manifest/validate/activate/disable; secure credentials | неверная схема не активируется |
| C-015 | Model Pricing | cost vs sell price; effective dated | прошлые события не пересчитываются |
| C-016 | Media Storage | validate/store/checksum/retrieve; no orphan success | сбой диска не даёт SUCCEEDED |
| C-017 | Library | list/open/redeliver; только владелец | другой user получает 403/404 |
| C-018 | Delivery Outbox | dispatch/retry; не регенерировать | временный Telegram отказ восстанавливается |
| C-019 | Telegram Admin | legacy-compatible commands + RBAC | команда от чужого ID запрещена |
| C-020 | Mini App Admin | allowlist entry chooser + RBAC + audit | скрытие UI не является авторизацией |
| C-021 | Settings | typed validation/version/rollback; audit | ошибка не применяет половину настроек |
| C-022 | Support | create/reply/status; owner access | обращение и ответ сквозь оба клиента |
| C-023 | Reports | finance vs operations, observed vs estimated | reconciliation variance видна |
| C-024 | API v1 | schema + typed errors + access checks | contract tests на каждый endpoint |
| C-025 | Events/Outbox | dedup event IDs; at-least-once handling | повтор не меняет итог |
| C-026 | Security/Secrets | env, SSRF guard, redacted logs, least privilege | отказ на недоверенный URL |
| C-027 | Deployment/Backup | migrations/health/restore; recoverability | восстановление из бэкапа доказано |
| C-028 | Observability | correlation/job/provider/payment ID и явные стадии | оператор видит причину без SQL |
| C-029 | Feature Flags | разрешённые динамические изменения | выключение провайдера не рушит каталог |
| C-030 | User Data Retention | media/data retention, deletion/legal hold | истечение срока безопасно обработано |
| C-031 | Telegram Stars / payment channel | compliant XTR checkout, backend verified event, common ledger | no third-party digital checkout inside Telegram; refunds, race |

## Source-aware implementation gate (2026-11-15)

Ряд модулей существует в открытом PR #17: ProviderRegistry, TaskLaunch, Pricing, Ledger, Telegram Admin Edition, Platega, Stars и Mini App read-mostly. См. [инвентаризацию](../audit/VANKHU21_IMPLEMENTATION_BASELINE.md). Новые контракты задают TARGET, но не дают оснований повторно создавать эти модули. Состояние PR: UNMERGED, CI_PASS указанного SHA, LIVE_NOT_PROVEN.

Система внутренних средств на текущем кодовом срезе — токены DarkFlow; рубли фигурируют во внешней оплате с фиксацией курса, Stars — XTR. Не путать эти денежные единицы. Применимость Platega для продаж цифрового контента внутри Telegram ограничена C-031.

## Что детализировать во втором и последующих прогонах

**Слой 1:** JSON Schema для ProviderManifest, CapabilityInput, ModelParameters, Quote, Job, JobResult; OpenAPI 3.1 с auth, status codes, error taxonomy; миграционные DDL-ограничения.

**Слой 2:** state-transition tables, SQL transaction boundaries, idempotency keys, race matrices; webhook contract, refund/chargeback events, ledger double-entry projection and reconciliation.

**Слой 3:** каждый экран Telegram callback и Mini App route → command/query → endpoint → permission → audit event; административный CRUD settings с role matrix и dangerous-operation confirmation.

**Слой 4:** contract test fixtures для 4 AI типов, sync/async provider, timeout, delayed webhook, malformed output, non-idempotent unknown, corrupt media, rollback; нагрузка 10/50/100; live validation отдельно.

## Правило изменения

Новый контракт: ID, автор, зачем, связь с требованиями, вход, выход, владелец данных, инварианты, ошибки, retries, права, версия, expected telemetry, migration, rollback, security, acceptance. Переопределение без ADR и проверки совместимости запрещено. Реестр — главный указатель, а не подмена полных контрактов.
