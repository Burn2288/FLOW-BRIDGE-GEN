# MODULAR SYSTEM — границы служб и процессов

Статус: DESIGN_DRAFT, не AS_IMPLEMENTED. Архитектурный ориентир: Modular Monolith + Independent Workers + Unified HTTP API. Не запускать микросервисы без эксплуатационного основания.

## Процессы

1. Telegram Gateway: long polling/webhook updates, ack callbacks, FSM/menu state, презентация. Не вызывает долгие AI API и не меняет баланс напрямую.
2. Public HTTP API: Mini App аутентификация, чтение каталога/библиотеки, команды создания генераций и оплат через application services.
3. Job Worker(s): атомарный захват и исполнение durable jobs, heartbeat, fencing, controlled retry, финализация результатов.
4. Provider Runners: ограниченный слой I/O с внешними API, возможные sync/async задачи, декодирование нормализованных результатов.
5. Payment Gateway Endpoint + Reconciliation Worker: приём валидированных webhook и независимая проверка по API, восстановление неизвестных платежей.
6. Delivery Worker: уведомления Telegram, outbox и повторная доставка готовых результатов.
7. Maintenance/Reporting: cleanup по retention policy, reconciliation ledger, отчёты и алерты.

На первом этапе допустимы разные процессы одного Python-пакета и общей PostgreSQL. Нужны health/readiness и корректное graceful shutdown.

## Модули и право владения данными

| Модуль | Отвечает | Только его запись в |
| --- | --- | --- |
| Identity & Consent | Telegram identity, статус соглашений, серверная сессия | users, consents, sessions |
| Navigation/Presentation | Экранные модели без SQL | navigation_sessions (если нужно) |
| Catalog | Видимые модели/версии/возможности | providers, model_catalog, capability_catalog |
| Pricing | Котировки, правила наценки, версии тарифов | price_rules, quotes |
| Generation Orchestrator | Создание job, переходы, политика отказов | jobs, attempts, job_events |
| Provider Registry | Контракты адаптеров, credentials references, health | provider_config, adapter_versions |
| Billing & Ledger | Резервы, списания, возвраты, balance projection | ledger_entries, wallet_reservations |
| Payments | PaymentIntent, provider transactions, reconciliation | payment_intents, payment_events |
| Referrals | Атрибуция, награды, долги | referrals, referral_rewards |
| Media Storage | Валидация, объектное хранение, checksum | media_assets |
| User Library | Доступность и метаданные результата пользователю | library_items |
| Support | Обращения и сообщения | tickets, ticket_messages |
| Administration | RBAC, изменения настроек, аудит | admin_roles, setting_versions, audit_events |
| Reporting | Read models/агрегаты | report_snapshots |

Модули не обращаются напрямую к чужой таблице для изменения данных. Межмодульное взаимодействие: типизированные команды, query ports, события после коммита (transactional outbox). Объединённые финансовые транзакции выполняются внутри одной ACID границы в сервисе приложения с документированным порядком операций.

## Общий путь генерации

Telegram DM или Mini App → Auth/Consent → Catalog/Capability → Pricing quote → Job command → атомарный Reserve в Ledger + создание durable job → Job Worker atomic claim → Provider Adapter → validate media → Media Storage → Library Item → Capture или Release по политике → Outbox Delivery → Telegram/Mini App status. Источник истина о результате — БД и объектное хранилище, не сообщение Telegram.

## Базовые инварианты

- Пользователь и администратор не получают данные другого пользователя по подменённому ID.
- Каждый job имеет стабильный id, owner_id, product type, capability, catalog model version, quoted pricing version, status и correlation ID.
- ProviderRequest.idempotency_key передаётся только если провайдер реально поддерживает семантику; unknown outcome фиксируется без auto-replay.
- Reserve/Capture/Release/Refund — только через Ledger и уникальные бизнес-ключи; любые события обратимы компенсирующей проводкой.
- Библиотечная запись появляется после проверки файла и устойчивого сохранения; отсутствие Telegram-доставки не уничтожает результат.
- Существующие Telegram admin-функции нельзя удалять или переписывать до отдельной инвентаризации и доказанной совместимости.

## Очереди / аварии

Durable job: QUEUED → CLAIMED/EXECUTING → WAITING_PROVIDER / VALIDATING / STORING → SUCCEEDED или FAILED / CANCELED / UNCERTAIN. Atomic claim, lease_until, heartbeat_at, fencing_version, worker_id, attempt_count, next_retry_at; чтение и запись требуют compare-and-set версии. Уменьшать concurrency при перегрузке, иметь лимиты на пользователя/модель/провайдера и максимум ожидания. Fair scheduling; idempotent delivery outbox; graceful shutdown. Создание мультимедиа может возвращать provider_job_id с polling/webhook — это не завершённая генерация.

## Эволюция и совместимость

Добавлять capability через адаптер + manifest + контрактные тесты; UI получает каталог по API, а не жёстко зашитый перечень. Контракты версионируются; несовместимое изменение требует ADR, migration и rollback. Примитивы платформы (идентичность, кошельки, журналы, библиотека) общие всем типам контента; новые типы имеют schema-driven input forms, валидаторы и media handlers.

## Граница правды

Текущая документация описывает цель. Реальный порт/пакет/ORM/миграции и топологию процессов определять после S0 на проверенной кодовой базе. Если фактический код отличается, фиксировать AS-IS отдельно от TARGET и не объявлять проект реализованным по схеме.
