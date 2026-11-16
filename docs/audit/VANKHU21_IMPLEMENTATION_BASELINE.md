# Инвентаризация наработок vankhu21 — read-only, 2026-11-15

**Статус аудита:** SOURCE_PRESENT + CI_REPORTED, не MERGED и не LIVE_ACCEPTED. Эта инвентаризация не меняет исходники, ветки разработчиков или принятые PR. Для новых инженерных задач нужен fresh fetch и проверка SHA: всё ниже привязано к снимку.

## Фиксированные источники

- Общая принятая `main`: `98d05504446458252ede2df35e8870b2e1bc63e2` (первоначальные README и .gitignore).
- Правила сотрудничества: `docs/bootstrap` SHA `008951279802ee0761da998e71c5a6e78c21a6d5`, PR [#1](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/1) открыт.
- Наиболее поздний исходный срез vankhu21: `work/vankhu21/miniapp-read` SHA `d691d54e0266c3d519d66575555fa45895ef40ac`, PR [#17](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/17) открыт, draft; база PR #16 — `work/vankhu21/anymodel-pricing`.
- На этом SHA GitHub Actions [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/43759469582) и [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/43759469627) завершились `success`. PR сообщает 392 passed, 0 skipped; отдельно не утверждаем live-сценарии.
- Контрольная точка стенда в [DARKFLOW_STAND_AUDIT](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/docs/audit/DARKFLOW_STAND_AUDIT.md): `5601faa0481a52a67e0ada43a8a48f07bd3d1968` с 36 миграциями; это НЕ текущий код PR #17. Новые миграции до 039 находятся в PR #17, их развёртывание на production здесь не доказано.

**Критично:** ни PR #1, ни PR #8–#17, ни документационный PR #18 не слиты в `main` на момент исследования. Работающий в feature-ветке код не равен принятой общей версии. PR #9–#17 устроены как стэк: каждый базируется на предыдущей рабочей ветке. Прямой merge такого стэка без порядка, регрессионной проверки и согласования нарушает ожидаемый процесс.

## Что уже существует в коде (все пути относительно корня, ref=d691d54...)

| Область | Доказательство SOURCE_PRESENT | Повторно использовать | Не утверждать / добавить |
| --- | --- | --- | --- |
| PostgreSQL + миграции | `migrations/001_initial.sql` … `039_inbox_unprocessed.sql`, `src/elevenbot/db.py` | Схему пользователей, `identities`, `wallets`, `ledger`, jobs, media, admin | Совпадение конкретной локальной/production-БД с веткой не проверено |
| Telegram onboarding | `src/elevenbot/telegram.py`, `core.py` | /start, consent gate, сохранение Telegram ID, существующие команды | Сейчас согласие и документы выводятся текстом из config, требуемая отправка двух .md и versioned consent — отдельный gap |
| Telegram навигация | `src/elevenbot/navigation.py`, `telegram.py`, `progress.py` | Отдельные панели, редакции клавиатур, независимое сообщение прогресса, восстановление | Желаемое главное меню «Открыть студию / Личный кабинет», нужная вложенность и ≤5 библиотечных строк не тождественны текущему меню агрегаторов и «Мои работы» |
| Каталоги/реестр провайдеров | `src/elevenbot/aggregate.py:ProviderRegistry`, `discovery.py`, `provider_execution.py` | register/collect, цена и launch адаптеры, изоляция провайдеров; fixture 3-го агрегатора в `tests/test_provider_extensibility.py` | Универсальный безопасный админ-мастер подключения неизвестных API ещё не доказан |
| AI-модели | `src/elevenbot/anymodel.py`, `anymodel_image_jobs.py`, `anymodel_video.py`, `anymodel_speech.py`, `video.py`, `clodex_music.py`, `fal.py` | Имеющиеся пути изображений, видео, озвучки, музыки; исходные тесты | Нельзя повторно реализовывать такие ветви без подтверждённого дефекта; большинство live-путей требуют независимого proof |
| Каталог и админ-тарифы | `src/elevenbot/model_policy.py`, `tariff_admin.py`, `pricing.py`; `migrations/024_approved_models.sql` | `approved_models` допуски, версии тарифов, наценки, расчёты | Публикация произвольных моделей из Mini App admin не реализована; UI сохранения конфигурации отдельный этап |
| Создание заданий | `src/elevenbot/task_launch.py` и `task_wallet.py` | `ExecutionAdapter`, `TaskLaunch`, `task_dispatch`, один резерв, capture/release, статус UNCERTAIN без автоповтора | Контракт HTTP-запуска, независимый от Telegram update ID, отсутствует; проверить sync/async и recovery по типам |
| Внутренний баланс | `src/elevenbot/core.py`, `pricing.py`, `task_wallet.py`, миграции 026/034 | Кошелёк содержит **внутренние токены**, modes demo/live, ledger. RUB — сумма внешнего платежа и курс к токенам, а не единица внутреннего кошелька | Первичный документ C-008 предполагал RUB-кошелёк; нельзя менять единицы/конвертацию без ADR и миграции |
| Пополнение Platega | `src/elevenbot/platega.py`, `topups.py`, `topup_ui.py`, `platega_web.py`, `migrations/034_topups.sql` | намерение/заказ, создание один POST, сверка, chargeback и долг, пресеты, admin UI; тесты `tests/test_topups.py` | Платёжный канал для цифрового товара внутри Telegram требует Stars; реальная Platega-приёмка и юридическая допустимость не доказаны |
| Telegram Stars | `telegram.py` (sendInvoice с XTR, pre_checkout, successful_payment, refund), `core.py`, CLI `reconcile-stars` | Уже существует основной Stars flow; не проектировать его с нуля | Совместимость с новыми AI-заказами, idempotency/refunds, Telegram test/live должны быть проверены |
| Telegram Admin Edition | `src/elevenbot/admin_access.py`, `telegram.py`, `model_policy.py`, `tariff_admin.py`, `topup_ui.py`, `broadcasts.py` | Логин с паролем, allowlist `ADMIN_TELEGRAM_IDS`, курсы/допуски/рассылки/пополнения | Сессии Admin Edition process-local; нельзя бездумно использовать их для HTTP admin. Реестр команд и parity проверять отдельно |
| Mini App user MVP | `miniapp/backend/web.py`, `miniapp/frontend/*`, `miniapp/tests/test_miniapp.py`, миграции 037/038 | Проверка подписи initData, защита свежести (300 с), одноразовый exchange на Bearer session 600 с, каталог, кошелёк, библиотека/файл, тема | HTTP `/api/v1` содержит только session, catalogue, wallet, settings theme, works. Генерации, новые платежи, referrals, support, web-admin не предоставлены |
| Доставка/медиатека | `src/elevenbot/core.py`, `telegram.py`, `anymodel_image_jobs.py`, `progress.py` | Получение работ по user ID, media, retry/recovery в нескольких пилотах | Общий контракт хранения/retention и единый outbox доставки требуют подробной сверки |
| Тесты CI | `.github/workflows/test.yml`, `miniapp/tests/test_miniapp.py`, `tests/test_topups.py`, `tests/test_provider_extensibility.py` | PostgreSQL integration + mock provider + source test fixtures | Green CI не равно LIVE_PROVEN, а количество тестов не равно продуктовой приёмке |

## Важные факты о Mini App из кода
`miniapp/backend/web.py`: `POST /api/v1/session`, `DELETE /api/v1/session`, `GET /api/v1/catalogue`, `GET /api/v1/wallet`, `GET/PUT /api/v1/settings` (тема), `GET /api/v1/works`, `GET /api/v1/works/{kind}/{id}`. Нет `POST /api/v1/jobs`, `POST /api/v1/payments`, `/api/v1/admin`. Хотя маршрут settings использует PUT, эта версия Mini App — **read-mostly**, а не полнофункциональный двойник бота.

## Отдельная граница доказанности
- SOURCE_PRESENT: наблюдались файлы и отдельные SQL/интерфейсы на указанном SHA.
- CI_PASS: два GitHub Actions successful на указанном SHA. По PR указано 392 passed; полную live-приёмку это не подтверждает.
- LIVE_NOT_PROVEN: производство платежей, реальные генерации и физический показ новых Mini App экранов в Telegram не проверены в рамках этой работы.
- MERGE_PENDING: все перечисленные изменения вне `main`. Не объявлять принятой/синхронизированной сборку на основании PR.
- Ранее отмеченный в аудите `5601faa` публичный отказ после пополнения мог быть адресован изменениями PR #17 (`PUBLIC_IMAGE_MODELS`); повторная проверка на неизменном конфиге и на точном новом SHA обязательна. Не выдавать старую находку за неустранённую без воспроизведения.

## Приоритетный порядок следующей инженерной проверки
1. Правильный интеграционный базовый SHA и стэк PR, review/CI каждой ступени; запрет потери кода.
2. Платёжный канал Telegram Stars и публичный E2E пользователь с одним Wallet; регрессия существующего Platega как отдельно разрешённого адаптера.
3. HTTP create quote/job на существующих Pricing/TaskLaunch, независимый от Telegram update ID; проверка двух каналов.
4. Mini App admin chooser + server authz поверх существующей Telegram Admin Edition модели без переноса process-local сессии.
5. Telegram IA/легальные .md и полнофункциональный Mini App UI, одна библиотека и цена.
6. Referrals: адаптация донора AI-SHOP-BOT к подтверждённому списанию генерации.
7. Дополнительные провайдерские manifests, rollback, нагрузка и восстановление.

Не назначать исполнителей и не вносить изменения в личные планы: следующий этап — выбор задач владельцем и уточнение фактического интеграционного HEAD.
