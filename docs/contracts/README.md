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
| C-011 | Referral Rewards | [Политика FUNCTIONAL_TEST](C-011-V1-FUNCTIONAL-TEST.md), [атрибуция и история](../../src/elevenbot/referrals.py), [начисление, сторно и долг](../../src/elevenbot/referral_rewards.py). Начисления на общем ledger доступны в одноразовом PostgreSQL для сохранённых результатов изображений, видео и озвучки. Музыкальный пилот использует тестовые гранты без PAID-финансирования. |
| C-012 | Generation Job | [task_launch.py](../../src/elevenbot/task_launch.py), [worker.py](../../src/elevenbot/worker.py); единый lifecycle всех типов не принят. |
| C-013 | Provider Adapter | [provider_execution.py](../../src/elevenbot/provider_execution.py), [fal.py](../../src/elevenbot/fal.py); live API и универсальность не доказаны. |
| C-014 | Provider Registry | [aggregate.py](../../src/elevenbot/aggregate.py), [provider_lifecycle.py](../../src/elevenbot/provider_lifecycle.py); lifecycle — метаданные, не универсальный runtime rollback. |
| C-015 | Model Pricing | [pricing.py](../../src/elevenbot/pricing.py), [tariff_admin.py](../../src/elevenbot/tariff_admin.py); Утверждён узкий [тестовый срез D-02](#решение-d-02-для-functional_test). Полная модель цен открыта. |
| C-016 | Media Storage | [storage.py](../../src/elevenbot/storage.py), [core.py](../../src/elevenbot/core.py); полная матрица медиа не доказана. |
| C-017 | Library | [library.py](../../src/elevenbot/library.py), [core.py](../../src/elevenbot/core.py); все типы и parity клиентов не приняты. |
| C-018 | Delivery Outbox | [worker.py](../../src/elevenbot/worker.py), [clodex_music.py](../../src/elevenbot/clodex_music.py); общего exactly-once контракта нет. |
| C-019 | Telegram Admin | [admin_access.py](../../src/elevenbot/admin_access.py), [telegram.py](../../src/elevenbot/telegram.py); исторические команды используют парольную сессию, общий обзор и видимость модели используют текущие PostgreSQL capabilities. |
| C-020 | Mini App Admin | [web.py](../../miniapp/backend/web.py); для обзора операций, очереди поддержки и видимости модели сервер проверяет текущие PostgreSQL capabilities. |
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

Внутренние токены, внешние RUB и XTR, а также единицы провайдеров учитываются раздельно. Владелец согласовал [PostgreSQL authority D-04](../planning/MEGA02_D04_DECISION.md) и изменение видимости модели для FUNCTIONAL_TEST.

| Артефакт | Что фиксировать |
| --- | --- |
| `provider-contracts/` | Версии схем и типизированные возможности текста, изображений, речи, распознавания и видео. Жизненный цикл вызова, результаты, статусы, ошибки, цены, идемпотентность. |
| `generation-api.yaml` | OpenAPI 3.1 для `/api/v1/`. Идентификация, каталог и параметры, расчёт цены, создание, статус и отмена задания, история, скачивание, баланс, платежи и профиль. |
| `billing.md` | Ledger, reservation, capture, release, refund и reconciliation. Аутентификация вебхуков, защита от повторов и правила неопределённого исхода. |
| `jobs.md` | Переходы статусов, атомарный захват, lease, fencing, повторы, отмена, восстановление и лимиты. |
| `media.md` | Проверка типа и размера, целостность, хранение, выдача и права доступа. |
| `events.md`, `error-codes.md` | Схемы событий, correlation ID, устойчивые коды ошибок и правила повторов. |

Публичные изменения сопровождаются оценкой совместимости и автоматическими контрактными проверками. Несовместимые изменения требуют плана перехода и отдельной версии контракта. Финансовые проверки должны исключить повторное зачисление, списание и возмещение, потерю записи и отрицательный баланс без разрешённого овердрафта. Неизвестный исход платной операции требует сверки.

## Решение D-02 для FUNCTIONAL_TEST

26 ноября 2026 года владелец утвердил один тарифный сценарий в одноразовом DEV PostgreSQL. [vankhu21 #23 · MASTER #35 · PC-02] публикация версионированного тарифа опирается на [vankhu21 #22 · MASTER #34 · PC-01] и действующий механизм pricing.

| Параметр | Утверждённое значение |
| --- | --- |
| Провайдер и модель | CLODEX FLUX Schnell (`flux-schnell`) |
| Операция и параметры | `images.generate`, `{"n":1}` |
| Основа расчёта | `request` |
| Единица цены | Целочисленные внутренние токены |
| Эффективная цена | 2 → 3 токена. Откат восстанавливает 2 токена новой ревизией |
| Полномочия | Действующая серверная роль `OWNER_ADMIN` в обоих клиентах |

Preview показывает модель, ревизию, прежнюю и предлагаемую базовую и итоговую суммы с учётом действующей наценки. Он оставляет тариф, оценки, кошелёк и проводки без изменений. Подтверждение под действующей блокировкой политики проверяет текущую роль, версию и точный payload. Целевой итог должен составить 3 токена.

Публикация фиксирует новую версию и append-only запись с актором, моделью, значениями до и после и ревизией в одной транзакции. Повтор безопасен. Откат фиксирует следующую версию и сохраняет историю. Telegram и Mini App получают новую цену для последующих оценок. Действующие оценки и принятые задания сохраняют исходную цену, а операции с тарифом не списывают средства.

D-03 остаётся открытым. Реальные цены, курсы, платные внешние операции, тарифы других моделей и корректирующие проводки требуют отдельных решений. Допуск в Telegram сам по себе не выдаёт серверную роль. D-02 разрешает реализацию в указанных границах. Результат реализации, глобальная приёмка и слияние фиксируются отдельно.

## Границы FUNCTIONAL_TEST для SE-01–SE-03

Проверено на `bf1a83d8bb1266aad25b92d32bae0914d7ffec6e`. 22 проверки PostgreSQL покрыли авторизацию обоих интерфейсов, отзыв ролей, права приложения на историю ролей, изоляцию обращений и файлов, неизменяемость ledger, идемпотентность операций и восстановление приватной копии. Отдельные 49 тестов покрыли синтетический экспорт с исключением секретов, безопасное журналирование lifecycle провайдера и защиту конфигурации тестовых транспортов. Профиль FT020 на этом же SHA прошёл 19 проверок HTTP и связанных сервисов. [FT020](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/45893600376/job/140161962507)

| Граница | Контроль и проверка |
| --- | --- |
| Вход и пользовательские данные | Mini App проверяет подпись и свежесть данных входа, затем использует серверную сессию. Выдача работ и HTTP API заданий проверяют владельца, Telegram сверяет отправителя с личным чатом, поддержка проверяет владельца обращения. [Mini App](../../miniapp/tests/test_miniapp.py) · [Задания](../../tests/test_ft020_http_image.py) · [Telegram](../../tests/test_chat_isolation.py) · [Поддержка](../../tests/test_sl02_support_tickets.py) |
| Действия администратора | Текущая роль выбирается из PostgreSQL при защищённом действии. Права приложения позволяют читать историю ролей и выполнять разрешённые операции. Делегирование использует отдельный доверенный principal. [Права PostgreSQL](../../tests/test_http_admin_runtime_acl.py) · [Отзыв роли](../../tests/test_http_admin_authority.py) |
| Финансы | Ledger защищён от изменения исторических движений. Повтор подтверждения, отмены и выдачи результата сохраняет однократную финансовую операцию. [Runtime role](../../tests/test_runtime_role.py) · [Границы транзакций](../../tests/test_ft014_boundaries.py) |
| Логи, экспорт и данные | Timeline и операционные отчёты используют ограниченные поля. Lifecycle отправляет в журнал идентификаторы событий без конфигурационных секретов. Экспорт доказательств ограничен перечисленными отчётами и проверяется на синтетический секрет. Приватный дамп предназначен для контролируемого резервного хранения. [Timeline](../../tests/test_job_timeline.py) · [Lifecycle](../../tests/test_provider_lifecycle.py) · [Экспорт доказательств](../../tests/test_au02_handoff.py) · [Восстановление](../../tests/test_ft024_backup_restore.py) |
| Тестовый профиль | Локальный Telegram transport требует явного разрешения, loopback, режима mock и отключённой оплаты. Изолированный Compose профиль использует внутреннюю сеть и тестовые учётные данные. [Защита конфигурации](../../tests/test_platega_unit.py) · [Compose](../../compose.dev.yaml) |

Для STANDARD/HIGH_PRODUCTION остаются формализованное хранение и legal hold D-08, сквозной аудит всех каналов журналирования и экспорта, проверка медиаполитик и бюджетов на production-конфигурации. SE-03 требует независимой проверки обоих клиентов на финальном SHA.
