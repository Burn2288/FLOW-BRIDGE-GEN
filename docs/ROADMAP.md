# Общая инженерная дорожная карта S0–S8

Статус: DESIGN_DRAFT. Восстанавливает последовательность главной инженерной директивы и учитывает продуктовые потребности двух клиентов и провайдерских плагинов. Не является персональным распределением задач.

| Этап | Основной результат | Условия доказательства |
| --- | --- | --- |
| S0 — Baseline Audit | Точная исходная версия, архитектура, миграции, тесты, старые админ-функции | SHA, AS-IS карта, воспроизводимый запуск или конкретный блокер |
| S1 — Image E2E | Telegram → реальный провайдер → файл → хранилище → библиотека → пользователь | 3 живых успешных запроса, временный отказ, рестарт, нет двойного списания |
| S2 — Concurrency | Надёжная очередь и независимые воркеры | atomic claim, lease, fencing, controlled retry и тесты 10/50/100 |
| S3 — Unified Job Contracts | Общая модель заданий для image/video/voice/music | schema, transitions, устойчивое завершение/доставка |
| S4 — Provider Independence | Подключение разных агрегаторов без изменения ядра | 2 разнородных адаптера, validation/dry-run, contract tests и admin staging |
| S5 — Public API | Версионированный backend для Mini App | проверенный initData, API OpenAPI 3.1, единый кошелёк/задачи/библиотека; базовый UI |
| S6 — Admin & Reporting | Telegram admin совместим и доступна отдельная Mini App admin панель | env allowlist + RBAC, аудит настроек, диагностика job ID и отчёты |
| S7 — Financial & Security Hardening | Platega, Ledger, referrals и security проверены в авариях | double-charge prevention, reconciliation, возвраты, threat model, recovery |
| S8 — Commercial Pilot Acceptance | Подтверждённая Ubuntu поставка с ограниченными возможностями | live E2E, backup/restore, ограничения/риски и утверждённая приёмка |

Правила: нельзя закрыть этап mock-тестом вместо живого доказательства, нельзя делать платный автоматический retry при UNCERTAIN, нельзя выдавать дизайн-контракт за код. Смена этапности — только через Decision Log. Списки конкретных контрактов — [реестр](contracts/CONTRACT_REGISTRY.md); результаты и доказательства — [матрица](acceptance/FOUNDATION_TEST_MATRIX.md).
