# План контрактов

## Действующий срез и происхождение

Карта ниже относится к непринятому кандидату [PR #75 на `856a6b4407dc91e0f25e016d5f18d12aa2dcd0d4`](https://github.com/Burn2288/FLOW-BRIDGE-GEN/tree/856a6b4407dc91e0f25e016d5f18d12aa2dcd0d4). Имена и ID C-001–C-031 взяты из [реестра PR #31 на `16e12968dbebaeb2a859de09decf52520ac1bc5d`](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/16e12968dbebaeb2a859de09decf52520ac1bc5d/docs/contracts/CONTRACT_REGISTRY.md); [сверка PR #29 на `6697bfa5ce1a4f5c20c29cd628b2151db1fe306d`](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/6697bfa5ce1a4f5c20c29cd628b2151db1fe306d/docs/planning/FOUNDATION_CONTRACT_AS_IS.md) описывает более ранний источник. Оба — исторические кандидаты, IN-18 полностью не принят. Определения контрактов остаются `DESIGN_DRAFT`: перечисленные файлы показывают наличие компонентов, а не доказательство полной реализации или приёмки контракта.

Фактическая схема существующих HTTP-маршрутов — [miniapp/openapi.json](../../miniapp/openapi.json), обработчики — [web.py](../../miniapp/backend/web.py). Quote и image jobs доступны в предусмотренном ими срезе; универсальный generation API для всех типов ниже остаётся целевым. Ссылка на исходник не заменяет проверки поведения. Подтверждённые тесты с точными SHA перечислены в [матрице приёмки](../acceptance/TEST_MATRIX.md).

| ID | Историческое название | Наличие в кандидате и открытая граница |
| --- | --- | --- |
| C-001 | Identity | [core.py](../../src/elevenbot/core.py), [admission.py](../../src/elevenbot/admission.py); полный контракт и эксплуатационная модель допуска требуют приёмки. |
| C-002 | Legal Consent | [core.py](../../src/elevenbot/core.py), [legal](../../src/elevenbot/legal); юридические тексты тестовые до утверждения. |
| C-003 | Sessions/Auth | [web.py](../../miniapp/backend/web.py), [admission.py](../../src/elevenbot/admission.py); все режимы и live-клиенты отдельно проверяются. |
| C-004 | Telegram Navigation | [telegram.py](../../src/elevenbot/telegram.py); ручная Telegram-приёмка отложена. |
| C-005 | Mini App Navigation | [Mini App](../../miniapp); полное равенство клиентских сценариев не установлено. |
| C-006 | Capabilities/Models | [model_capabilities.py](../../src/elevenbot/model_capabilities.py), [model_policy.py](../../src/elevenbot/model_policy.py); схема параметров ограничена. |
| C-007 | Price Quote | [pricing.py](../../src/elevenbot/pricing.py); не все типы и внешние цены подтверждены live. |
| C-008 | Wallet | [task_wallet.py](../../src/elevenbot/task_wallet.py), [core.py](../../src/elevenbot/core.py); общий финансовый контракт требует приёмки. |
| C-009 | Payment Intent | [topups.py](../../src/elevenbot/topups.py), [platega.py](../../src/elevenbot/platega.py); реальные платежи и каналы не проверены этим срезом. |
| C-010 | Referral Attribution | [referrals.py](../../src/elevenbot/referrals.py), [миграция 044](../../migrations/044_referral_attribution.sql); реализованная привязка не означает начисление наград. |
| C-011 | Referral Rewards | [referrals.py](../../src/elevenbot/referrals.py); версионированная тестовая политика и операции начисления, reversal и погашения долга описаны в [C-011 v1](C-011-V1-FUNCTIONAL-TEST.md). Доступность начислений зависит от профиля, маршрута генерации и подтверждённого PAID funding. |
| C-012 | Generation Job | [task_launch.py](../../src/elevenbot/task_launch.py), [worker.py](../../src/elevenbot/worker.py); единый lifecycle всех типов не принят. |
| C-013 | Provider Adapter | [provider_execution.py](../../src/elevenbot/provider_execution.py), [fal.py](../../src/elevenbot/fal.py); live API и универсальность не доказаны. |
| C-014 | Provider Registry | [aggregate.py](../../src/elevenbot/aggregate.py), [provider_lifecycle.py](../../src/elevenbot/provider_lifecycle.py); lifecycle — метаданные, не универсальный runtime rollback. |
| C-015 | Model Pricing | [pricing.py](../../src/elevenbot/pricing.py), [tariff_admin.py](../../src/elevenbot/tariff_admin.py); D-02 и полная модель цен открыты. |
| C-016 | Media Storage | [storage.py](../../src/elevenbot/storage.py), [core.py](../../src/elevenbot/core.py); полная матрица медиа не доказана. |
| C-017 | Library | [library.py](../../src/elevenbot/library.py), [core.py](../../src/elevenbot/core.py); все типы и parity клиентов не приняты. |
| C-018 | Delivery Outbox | [worker.py](../../src/elevenbot/worker.py), [clodex_music.py](../../src/elevenbot/clodex_music.py); общего exactly-once контракта нет. |
| C-019 | Telegram Admin | [admin_access.py](../../src/elevenbot/admin_access.py), [telegram.py](../../src/elevenbot/telegram.py); целевая RBAC-модель не утверждена. |
| C-020 | Mini App Admin | [web.py](../../miniapp/backend/web.py); для обзора операций и очереди поддержки сервер проверяет текущие независимые PostgreSQL capabilities. |
| C-021 | Settings | [runtime_config.py](../../src/elevenbot/runtime_config.py), [config.py](../../src/elevenbot/config.py); универсальная версия и rollback настроек не доказаны. |
| C-022 | Support | [support_tickets.py](../../src/elevenbot/support_tickets.py), [web.py](../../miniapp/backend/web.py); текстовые обращения, история владельца и ответы оператора хранятся в PostgreSQL. |
| C-023 | Reports | [task_receipts.py](../../src/elevenbot/task_receipts.py), [topups.py](../../src/elevenbot/topups.py); полный набор отчётов и сверка не приняты. |
| C-024 | API v1 | [openapi.json](../../miniapp/openapi.json), [web.py](../../miniapp/backend/web.py); универсальный API и все коды ошибок требуют развития. |
| C-025 | Events/Outbox | [worker.py](../../src/elevenbot/worker.py), [task_launch.py](../../src/elevenbot/task_launch.py); общий event outbox не установлен. |
| C-026 | Security/Secrets | [config.py](../../src/elevenbot/config.py), [provider_manifest.py](../../src/elevenbot/provider_manifest.py); полный security-аудит отложен. |
| C-027 | Deployment/Backup | [snapshot.py](../../src/elevenbot/snapshot.py), [db.py](../../src/elevenbot/db.py); production recovery и D-09 открыты. |
| C-028 | Observability | [worker.py](../../src/elevenbot/worker.py), [telegram.py](../../src/elevenbot/telegram.py); полная операторская диагностика не доказана. |
| C-029 | Feature Flags | [config.py](../../src/elevenbot/config.py), [model_policy.py](../../src/elevenbot/model_policy.py); универсальное динамическое управление не доказано. |
| C-030 | User Data Retention | [core.py](../../src/elevenbot/core.py), [storage.py](../../src/elevenbot/storage.py); полный deletion/legal hold контракт не доказан. |
| C-031 | Telegram Stars / payment channel | [telegram.py](../../src/elevenbot/telegram.py), [topups.py](../../src/elevenbot/topups.py); live-приёмка платёжного канала остаётся открытой. |

Внутренние токены, внешние RUB и XTR, а также единицы провайдеров — разные единицы; карта не вводит курсы или формулы. D-02 и D-04 остаются открытыми.

| Артефакт | Что фиксировать |
| --- | --- |
| `provider-contracts/` | Версии схем и типизированные возможности текста, изображений, речи, распознавания и видео. Жизненный цикл вызова, результаты, статусы, ошибки, цены, идемпотентность. |
| `generation-api.yaml` | OpenAPI 3.1 для `/api/v1/`. Идентификация, каталог и параметры, расчёт цены, создание, статус и отмена задания, история, скачивание, баланс, платежи и профиль. |
| `billing.md` | Ledger, reservation, capture, release, refund и reconciliation. Аутентификация вебхуков, защита от повторов и правила неопределённого исхода. |
| `jobs.md` | Переходы статусов, атомарный захват, lease, fencing, повторы, отмена, восстановление и лимиты. |
| `media.md` | Проверка типа и размера, целостность, хранение, выдача и права доступа. |
| `events.md`, `error-codes.md` | Схемы событий, correlation ID, устойчивые коды ошибок и правила повторов. |

Публичные изменения сопровождаются оценкой совместимости и автоматическими контрактными проверками. Несовместимые изменения требуют плана перехода и отдельной версии контракта. Финансовые проверки должны исключить повторное зачисление, списание и возмещение, потерю записи и отрицательный баланс без разрешённого овердрафта. Неизвестный исход платной операции требует сверки.
