# FUNCTIONAL_TEST build sprint 02

`BATCH_ID = CLOUD-PRODUCT-COMPLETION-MEGA-02`. Общий [Draft #115](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/115) продолжен от HEAD `09375aae1ca1838c4f1eca6e5a458f467a0fbe3b`, TREE `ee8832d6579fec86bdeca267e585b66b7f9c28e1`. Историческая база принятой main — `a889d8306c743c0046b710b950608052eabfdc78`. GitHub Actions TQ-01 на исходном кандидате зафиксировал 692 общих и 18 профильных проверок. [Исходный прогон](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/45887330992).

## Стенд и демонстрация

```sh
docker compose -f compose.dev.yaml up -d --build --wait
docker compose -f compose.dev.yaml ps
curl --fail http://127.0.0.1:8091/healthz
docker compose -f compose.dev.yaml logs bot worker miniapp
docker compose -f compose.dev.yaml stop
docker compose -f compose.dev.yaml up -d --wait
```

PostgreSQL, bot с локальной Telegram-заглушкой, worker и Mini App используют одну disposable БД. На хосте Docker Mini App доступен на loopback HTTP, а проверка авторизованного браузерного пути OP-01 использует Caddy HTTPS и подписанные синтетические Telegram init data. Настройка доступа, остановка и отдельный профиль регрессии приведены в [руководстве запуска](../operations/DEPLOYMENT.md).

В облачной среде Debian 13 при скачивании зафиксированных зависимостей понадобился доверенный CA этой среды. Для фактического запуска локальный BuildKit передал CA как секрет `SSL_CERT_FILE=/run/secrets/cloud_ca` на шаг `uv sync --locked`. Полученный образ подключён через временный Compose override с `--no-build`. TLS-проверка действует. Обычный репозиторный запуск рассчитан на доступ к registry и PyPI через доверенную цепочку.

## Продукт и профильные сценарии

| Функция | Telegram | Mini App | Запуск и доказательство | Остаток |
| --- | --- | --- | --- | --- |
| Вход, документы, профиль, баланс | Stub-gateway, обычные команды | Signed init data, согласие, отдельный профиль | DEV smoke, Telegram tests, Chromium OP-01 | Настоящий Telegram WebView и внешняя машина |
| Синтетическая оплата, ledger, история | Stars fixture | HTTP invoice/history | PostgreSQL Stars и Platega, повтор события сохраняет один credit | Реальный checkout требует разрешения |
| Изображение | Offline FLUX | Offline FLUX | Приватный disposable fixture, общий тариф, durable PNG и capture в обоих клиентах | Добавить профиль к общему smoke, live отдельно |
| Видео | Veo/Grok fixtures | Veo browser fixture | Quote, create/poll и сохранение на PostgreSQL с инъекцией провайдера | Штатный Compose mock route |
| Речь | Штатный worker доставил mock-аудио | История и скачивание того же MP3 | Один PostgreSQL и общий том; отдельный OP-01 проверяет priced speech | Общий Compose путь запуска priced speech из Mini App |
| Музыка | Mock CLODEX/Fal | Browser pilot | Отдельные fixtures и бесплатный музыкальный ledger | Общий ordinary-user runtime и PAID-контракт |
| Поддержка | Создание, список, история и ответ | Создание, очередь оператора, ответ, история | HTTP/PostgreSQL и Chromium, isolation и revoke | Вложения и retention требуют контракта |
| Администрирование | Legacy Edition, /operations и PostgreSQL visibility | Агрегированный обзор и очередь | Capability gate, preview, CAS, rollback; ранее оплаченный результат сохраняется | Детальные операторские представления и внешние alerts |
| Рефералы | Атрибуция и история | Реферальная вкладка и история | Тестовые 500 bps, PAID → capture → reward, повтор, reversal, debt и repayment на PostgreSQL | Музыкальные гранты не дают eligible PAID |
| Перезапуск и restore | Gateway/worker перезапускаются | Повторная загрузка истории | Сравнение identity, ledger, job и MP3 до и после; отдельный FT-024 restore | Ubuntu 24.04, production D-09 |

Подсистемы используют несколько изолированных профилей. Восемь сквозных маршрутов четырёх студий из двух клиентов на одном Compose-профиле остаются открыты.

## Прогоны и происхождение

- На опубликованном срезе `ff75efdfa6e2012c56d3ea7cf27ba520744ac9da`, TREE `e1a32dd1cd63cd07f01c75ab024d767c18a7af0c`, локально прошло 42 PostgreSQL-проверки, 3 проверки OP-01 и 4 Node-проверки. Успешные профильные Actions указаны у затронутых TASK_ID. Два последующих изменения сохраняют совместимость старых HTTP/upgrade fixtures и уточняют права runtime-роли. Результаты итогового SHA доступны в [Draft #115](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/115).
- На том же срезе после stop/start все четыре сервиса снова healthy, коды выхода равны 0. PostgreSQL сохранил identity, баланс `9989/0`, одно завершённое задание со списанием и хэш MP3. В Chromium Mini App скачал совпадающий файл размером 4935 байт.
- На исходной базе локальная общая регрессия с PostgreSQL 16.15 прошла 692 теста. Изолированный срез S15 прошёл 18 проверок запуска, process E2E, сохранности, backup/restore и отчётности. Наборы пересекаются.
- Debian 13, Docker 29.9.2, Compose 2.40.3. Интегратор и шесть дочерних агентов. На итоговом локальном повторе одновременно работали два независимых тестовых процесса с разными PostgreSQL и один общий стенд.
- Подготовлено 54/81 (66,67%) функциональных кандидата. Ещё 13 в работе, 1 заблокирован и 13 без статуса оценки в каноническом реестре. Техническая интеграция фиксированной исторической когорты — 23/37 (62,16%), из них 18 в main и 5 только в историческом глобальном кандидате, 14 остаются открытыми. [Сверка исторических PR](../audit/MEGA-02-HISTORICAL-PR-COHORT.md).

## Результаты потоков

| Поток | Результат | Остаток |
| --- | --- | --- |
| S01 | Единый Draft, карта контрактов, 81 строка с исходными владельцами | Две независимые оценки |
| S02 | Telegram Back, consent, профиль и список обращений | Ручной Telegram-клиент |
| S03 | Mini App профиль, согласие и HTTPS пользовательский проход | Настоящий WebView и полная матрица маршрутов |
| S04 | Общий отчёт `/operations`, актуальные DB-роли и legacy Admin Edition | Полный ручной обход legacy меню |
| S05 | Visibility в двух клиентах, CAS, аудит и обратное событие | Детальные представления и внешние alerts |
| S06 | Manifest, registry, каталоги и модельные ограничения | Live capabilities |
| S07 | Общий job list/status, worker regression и безопасная отмена HTTP image | Доставка незавершённой речи после рестарта бота, отмена всех типов |
| S08 | Offline FLUX в двух клиентах, сохранение PNG и capture | Автоматический запуск через общий DEV |
| S09 | Veo/Grok fixtures и видимость Telegram-видео в Mini App | Полноценный общий Compose mock для видео |
| S10 | Mock речь в штатном worker, priced speech и music в профильных fixtures | Единый runtime; музыкальный PAID-контракт |
| S11 | Синтетические Stars/Platega, ledger, replay и сверка | D-02/D-03 для новых тарифных операций |
| S12 | Реферальные начисления на PAID capture трёх типов, reversal/debt | Music grant исключён из PAID |
| S13 | Цикл поддержки с ответом и owner history в двух клиентах | Вложения и retention |
| S14 | Ownership, revoke, защита visibility/profile и runtime ACL | Полный аудит логов, экспорта и retention |
| S15 | Четыре сервиса, повторный запуск и disposable restore | Ubuntu 24.04 release-host |
| S16 | OP-01, профильные journeys и Actions для Draft | Восемь маршрутов на одном Compose-профиле |

## Матрица 81 задачи

Статусы зафиксированы в [каноническом реестре](../planning/completion-level-register.json). Для каждой строки приведён проверяемый путь или источник текущего среза и конкретный остаток. Часть доказательств относится к профильным fixtures. Колонка статусов учитывает формальные требования реестра к GitHub Actions. Все `completed_level` равны `null`.

| Историческая задача | IMPLEMENTATION_STATUS | Результат и сценарий | Источник | Остаток |
| --- | --- | --- | --- | --- |
| [Burn2288 #1 · MASTER #1 · IN-01] Утвердить порядок интеграции и freeze SHA | `NOT_ASSESSED` → `NOT_ASSESSED` | Правила совместной работы и freeze кандидата сверены с актуальным PR | CONTRIBUTING.md, PR #115 | Отдельная приёмка исторического порядка и исключений из стэка |
| [Burn2288 #2 · MASTER #2 · IN-02] Принять документационную базу PR #1 | `NOT_ASSESSED` → `NOT_ASSESSED` | Документационная база сохранена в общей истории | MEGA-02-HISTORICAL-PR-COHORT.md, PR #1 | Независимая приёмка документационного среза |
| [vankhu21 #1 · MASTER #3 · IN-08] Интегрировать PR #8 и доказать supersession ранних пилотов | `NOT_ASSESSED` → `NOT_ASSESSED` | Image lifecycle и текущая приёмка проверяются в профильном наборе | tests/test_public_image_topup.py | Эквивалентность всех ранних пилотов требует отдельного сравнения |
| [vankhu21 #2 · MASTER #4 · IN-09] Провести отдельную приёмку и интеграцию PR #9: Veo video | `NOT_ASSESSED` → `NOT_ASSESSED` | Veo create/poll присутствует в общей сборке | tests/test_anymodel_video.py | Путь ordinary user на общем стенде для Veo |
| [vankhu21 #3 · MASTER #5 · IN-10] Провести отдельную приёмку и интеграцию PR #10: AnyModel registry | `NOT_ASSESSED` → `NOT_ASSESSED` | AnyModel registry и provider manifest сохранены | tests/test_provider_extensibility.py | Отдельная приёмка исторического PR |
| [vankhu21 #4 · MASTER #6 · IN-11] Провести отдельную приёмку и интеграцию PR #11: FIBO async image | `NOT_ASSESSED` → `NOT_ASSESSED` | Асинхронный FIBO проверяется на локальном адаптере | tests/test_anymodel_fibo.py | Контрольные live-вызовы с отдельным разрешением |
| [vankhu21 #5 · MASTER #7 · IN-12] Провести отдельную приёмку и интеграцию PR #12: Grok video | `NOT_ASSESSED` → `NOT_ASSESSED` | Grok create/poll присутствует в общей сборке | tests/test_anymodel_video.py | Путь ordinary user на общем стенде для Grok |
| [vankhu21 #6 · MASTER #8 · IN-13] Провести отдельную приёмку и интеграцию PR #13: AnyModel speech | `NOT_ASSESSED` → `NOT_ASSESSED` | AnyModel speech и legacy речь доступны в профильных тестах | tests/test_ft021_speech_capabilities.py, tests/test_process_e2e.py | AnyModel speech на общем Compose профиле |
| [vankhu21 #7 · MASTER #9 · IN-14] Провести отдельную приёмку и интеграцию PR #14: Welcome/navigation | `NOT_ASSESSED` → `NOT_ASSESSED` | Welcome и Back покрыты Telegram-тестами | tests/test_navigation.py, tests/test_telegram_consent.py | Приёмка исторического PR и ручной Telegram-клиент |
| [vankhu21 #8 · MASTER #10 · IN-15] Провести отдельную приёмку и интеграцию PR #15: Task progress | `NOT_ASSESSED` → `NOT_ASSESSED` | Общие проекции job progress и статусов доступны | tests/test_job_timeline.py | Полная матрица изменений статуса в двух клиентах |
| [vankhu21 #9 · MASTER #11 · IN-16] Принять PR #16: финансы, каталог и Telegram Admin | `NOT_ASSESSED` → `NOT_ASSESSED` | Сохранены Telegram Admin Edition и финансовые сервисы | tests/test_admin_edition.py, tests/test_http_admin_authority.py | Полный интерактивный обход legacy меню |
| [vankhu21 #10 · MASTER #12 · IN-17] Принять PR #17: Mini App и новый inbox | `NOT_ASSESSED` → `NOT_ASSESSED` | Mini App и очередь доступны в интеграционном наборе | miniapp/tests/test_miniapp.py, tests/test_process_e2e.py | Независимая приёмка исторического PR |
| [Burn2288 #3 · MASTER #13 · IN-18] Согласовать фундамент и план как отдельные docs PR | `NOT_ASSESSED` → `NOT_ASSESSED` | Сверены действующие документы и карта контрактов | docs/contracts/README.md, docs/ROADMAP.md | Согласование всех исторических проектов контрактов |
| [Burn2288 #4 · MASTER #14 · IN-19] Синхронизировать и запустить целую принятую сборку | `NOT_ASSESSED` → `IN_PROGRESS` | Сверен удалённый кандидат и выполнен локальный запуск | Раздел стенда в этом отчёте | Сверка второй машины и глобальная приёмка |
| [Burn2288 #5 · MASTER #15 · AR-01] Зафиксировать реальные границы модулей и транзакций | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Сохранены границы composition, API и финансовых транзакций | core.py, task_launch.py, web.py | Глобальная сверка контрактов |
| [Burn2288 #6 · MASTER #16 · AR-02] Изолировать транспортные команды от финансовых деталей | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Команды продолжают использовать общие Wallet, quote и job сервисы | tests/test_task_wallet.py, miniapp/tests/test_miniapp.py | Единый lifecycle всех типов в общем Compose |
| [vankhu21 #11 · MASTER #17 · TG-01] Перевести главное меню и Back без потери старых маршрутов | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Навигация и Back проходят сценарии Telegram | tests/test_navigation.py | Ручной Telegram-клиент |
| [vankhu21 #12 · MASTER #18 · TG-02] Подключить документы и текущий consent к Telegram UX | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Документы и согласие проходят через Telegram stub | tests/test_telegram_consent.py, tests/test_process_e2e.py | Ручной Telegram-клиент |
| [vankhu21 #13 · MASTER #19 · TG-03] Личный кабинет и история общего кошелька | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Баланс и история остаются связаны с общей identity | tests/test_navigation.py, tests/test_stars_wallet_flux.py | Сквозной restart и история обоих клиентов в одном сеансе |
| [vankhu21 #14 · MASTER #20 · MA-01] Принять существующую Mini App в Telegram по HTTPS | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Проверен Mini App через Caddy HTTPS и Chromium | verification/op01/miniapp_journey.py | Настоящий Telegram WebView |
| [vankhu21 #15 · MASTER #21 · MA-02] Форма image quote и явное подтверждение | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Форма quote и подтверждение покрыты HTTP и браузером | miniapp/tests/test_miniapp.py, OP01 | Образ общего DEV smoke использует речь, offline FLUX отдельно на профильных fixtures |
| [vankhu21 #16 · MASTER #22 · MA-03] Карточка job и безопасная отмена | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Есть просмотр статуса и безопасная отмена по владельцу | tests/test_job_timeline.py, miniapp/tests/test_miniapp.py | Четыре типа на общем пользовательском маршруте |
| [vankhu21 #17 · MASTER #23 · MA-04] Довести пользовательский parity и доступность | `NOT_ASSESSED` → `IN_PROGRESS` | Проверены пользовательские экраны и изоляция истории | OP01, miniapp/tests | Полный паритет двух клиентов и доступность |
| [Burn2288 #7 · MASTER #24 · AD-01] Серверные admin roles, chooser и read-only обзор | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Текущие capability, default deny и revoke проверяются на PostgreSQL | tests/test_http_admin_authority.py | Доверенный bootstrap вне disposable среды и независимая приёмка |
| [Burn2288 #8 · MASTER #25 · AD-02] Одна typed settings-мутация с аудитом и rollback | `BLOCKED` → `CANDIDATE_PREPARED` | Реализованы VISIBLE/HIDDEN, preview, подтверждение по версии, аудит и rollback в Telegram и Mini App | tests/test_model_visibility.py, tests/test_telegram_model_visibility.py, OP01 | Независимая приёмка и provisioning вне disposable среды |
| [vankhu21 #18 · MASTER #26 · AD-03] Графические admin экраны по общему API | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Сгруппированный обзор пользователей, очереди, заданий, моделей, платежей и себестоимости | miniapp/backend/web.py, OP01 | Полный проход всех admin разделов и детальные представления в рамках D-04 |
| [vankhu21 #19 · MASTER #27 · TA-01] Зафиксировать compatibility inventory Admin Edition | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Сохранён существующий Telegram Admin Edition | tests/test_admin_edition.py | Сверка всех legacy маршрутов вручную |
| [vankhu21 #20 · MASTER #28 · TA-02] Сохранить Telegram admin при общих admin services | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | HTTP authority отделена от Telegram Admin Edition, тарифные сценарии сохранены | tests/test_http_admin_authority.py, tests/test_admin_edition.py | Сквозной Telegram admin проход |
| [Burn2288 #9 · MASTER #29 · PR-01] Расширить existing registry нормализованным manifest | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Нормализованные provider manifests и registry покрыты профильными тестами | tests/test_provider_manifest.py, tests/test_provider_extensibility.py | Live capability отдельно по провайдерам |
| [Burn2288 #10 · MASTER #30 · PR-02] Версии, health, staging и rollback провайдера | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Версии и rollback метаданных проверяются контрактным набором | tests/test_provider_lifecycle.py | Полный runtime provider rollback |
| [Burn2288 #11 · MASTER #31 · PR-03] Сверить live capability каждого включаемого адаптера | `NOT_ASSESSED` → `IN_PROGRESS` | Доступны контрактные mock проверки адаптеров | Тесты AnyModel, Fal и OP01 | Live вызовы требуют разрешения |
| [Burn2288 #12 · MASTER #32 · MC-01] Версионировать модель и capabilities без второго каталога | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Model policy и версии сохраняются в общей базе | tests/test_ft019_model_capabilities.py | Сверка каталога обоих клиентов после изменения настройки |
| [vankhu21 #21 · MASTER #33 · MC-02] Общие карточки и schema-driven параметры каталога | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Схемы параметров поддержаны для профильных маршрутов | tests/test_ft019_model_capabilities.py, tests/test_ft021_speech_capabilities.py | Полный проход форм и каталога двух клиентов |
| [vankhu21 #22 · MASTER #34 · PC-01] Уточнить токены, XTR, RUB и immutable quote | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Immutable quote и разделение единиц покрыты финансовым набором | tests/test_task_wallet.py, tests/test_ft023_combined.py | Реальные цены и production D-02 |
| [vankhu21 #23 · MASTER #35 · PC-02] Preview и publish versioned тарифов | `NOT_ASSESSED` → `BLOCKED` | Сохранены существующие тарифные операции и проверки | src/elevenbot/tariff_admin.py, tests/test_admin_edition.py | Расширение pricing mutation требует решения по D-02/D-03 |
| [Burn2288 #13 · MASTER #36 · JO-01] Доказать topology и закрыть missing lease/fencing | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Lease, heartbeat и worker покрыты профильным набором | tests/test_worker.py, tests/test_ft013_worker_process.py | Production topology и нагрузка |
| [Burn2288 #14 · MASTER #37 · JO-02] Bounded queue, fairness, cancellation и shutdown | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Очередь, безопасная отмена и shutdown покрыты тестами | tests/test_process_e2e.py, tests/test_worker.py | Нагрузочный уровень и все типы в общем Compose |
| [Burn2288 #15 · MASTER #38 · JO-03] Единый job projection и состояния четырёх типов | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Общий job status читает данные per-kind backend | miniapp/backend/image_commands.py, tests/test_job_timeline.py | Восемь сквозных маршрутов на одном стенде |
| [vankhu21 #24 · MASTER #39 · IM-01] Повторить штатный image путь с ordinary user | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Оба клиента проходят offline FLUX с обычным допущенным пользователем, общим тарифом и ledger | tests/test_ft020_http_image.py | Проверка на общем DEV-профиле без специального fixture |
| [vankhu21 #25 · MASTER #40 · IM-02] Три live изображения и временный отказ | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | FIBO и временный отказ имеют mock coverage | tests/test_anymodel_fibo.py, tests/test_image_recovery.py | Три живых изображения и отказ требуют разрешения |
| [vankhu21 #26 · MASTER #41 · VI-01] Согласовать video create/poll и финальный расчёт | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Состояния create/poll и финальный расчёт покрыты mock | tests/test_anymodel_video.py | Provider live и общий Compose mock worker для video |
| [vankhu21 #27 · MASTER #42 · VI-02] Video формы двух клиентов и разрешённая приёмка | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Видео доступно в профильных формах и OP01 | verification/op01/miniapp_journey.py | Delivery на штатном общем mock worker и настоящий Telegram |
| [Burn2288 #16 · MASTER #43 · VO-01] Нормализовать существующие TTS голоса и units | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Голоса и units покрыты профильным набором | tests/test_ft021_speech_capabilities.py | Live паритет движков и голосов |
| [vankhu21 #28 · MASTER #44 · VO-02] Voice UI и E2E двух клиентов | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Legacy mock речь проходит Telegram standalone bot/worker | tests/test_process_e2e.py | Тот же тип speech в обоих клиентах на одном runtime |
| [Burn2288 #17 · MASTER #45 · MU-01] Свести CLODEX/Fal music в общий lifecycle | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | CLODEX/Fal music lifecycle покрыт заглушками | tests/test_clodex_music.py | Общая конфигурация Music mock для Compose |
| [vankhu21 #29 · MASTER #46 · MU-02] Music UI, library и разрешённый live proof | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Формы music и playback проверяются в профильном окружении | OP01, tests/test_clodex_music.py | Общий mock worker и live proof с разрешением |
| [Burn2288 #18 · MASTER #47 · ML-01] Доказать сохранность image и восстановление доставки | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Повторная доставка сохранённого image и recovery покрыты | tests/test_ml01_delivery_recovery.py, tests/test_image_recovery.py | Общий restart путь image |
| [Burn2288 #19 · MASTER #48 · ML-02] Общий LibraryItem для всех сохранённых типов | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Owner-scoped библиотека использует общий backend | miniapp/tests/test_miniapp.py, tests/test_job_timeline.py | Матрица доставки всех типов с одного стенда |
| [vankhu21 #30 · MASTER #49 · ML-03] Пять строк Telegram и карточки Mini App | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Telegram список и Mini App карточки используют сохранённые данные | tests/test_navigation.py, miniapp/tests/works_ui.test.cjs | Паритет отображения всех типов и обеих identity |
| [vankhu21 #31 · MASTER #50 · WL-01] Проверить атомарный reserve/capture/release/refund | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Атомарные reserve, capture, release, refund покрыты PostgreSQL | tests/test_task_wallet.py | Приёмка и промышленная нагрузка отдельно |
| [Burn2288 #20 · MASTER #51 · WL-02] Сверка ledger и контролируемые корректировки | `IN_PROGRESS` → `IN_PROGRESS` | Использованы существующие сверка и отчётность | tests/test_task_wallet.py, operations_read_model.py | Дополнительная операция корректировки только по согласованному контракту |
| [vankhu21 #32 · MASTER #52 · PY-01] Проверить existing Stars checkout на одном конфиге | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Синтетический Telegram Stars и replay покрыты PostgreSQL | tests/test_stars_wallet_flux.py | Реальный checkout с разрешением |
| [vankhu21 #33 · MASTER #53 · PY-02] Проверить Platega callback/reconcile без Telegram checkout | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Platega reconciliation и restart покрыты тестами | tests/test_platega_db.py, tests/test_platega_restart.py | Внешнее подтверждение провайдера |
| [vankhu21 #34 · MASTER #54 · PY-03] Mini App Stars и payment history | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Mini App Stars invoice/history работают в тестовом профиле | miniapp/tests и профильный финансовый набор | Настоящий Telegram checkout |
| [Burn2288 #21 · MASTER #55 · RF-01] Адаптировать immutable attribution из донора | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Attribution выполняется до начисления и сохраняется при повторе | tests/test_ft022_referrals.py | Проход с реальным Telegram deep link |
| [Burn2288 #22 · MASTER #56 · RF-02] Rewards на capture и reversal/debt | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Проверены PAID capture для изображения, видео и речи, reversal и погашение долга | tests/test_ft022_referrals.py | Музыкальные гранты не относятся к PAID, live провайдеры требуют отдельной проверки |
| [vankhu21 #35 · MASTER #57 · RF-03] Реферальные экраны и API обоих клиентов | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Оба клиента показывают реферальную атрибуцию и историю | tests/test_ft022_referrals.py, тесты Mini App | Сквозная активация тестовой политики на общем стенде |
| [Burn2288 #23 · MASTER #58 · SL-01] Общее versioned consent и юридические MD | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Versioned consent и документы покрыты общим тестовым набором | tests/test_consent_contract.py, tests/test_telegram_consent.py | Принятие юридических документов отдельно |
| [Burn2288 #24 · MASTER #59 · SL-02] Общий support ticket и operator workflow | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | В двух клиентах проверены ticket, очередь, ответ, изоляция и revoke | tests/test_sl02_support_tickets.py, OP01 | Вложения и их retention требуют отдельного контракта |
| [vankhu21 #36 · MASTER #60 · SL-03] Support/legal/profile в двух клиентах | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Поддержка, история, профиль и общий consent доступны в Telegram и Mini App | tests/test_sl02_support_tickets.py, OP01 | Настоящий Telegram WebView |
| [Burn2288 #25 · MASTER #61 · SE-01] Threat model и security boundary suite | `NOT_ASSESSED` → `IN_PROGRESS` | Проверены защищённый HTTP, ownership, отзыв полномочий и ACL истории ролей | tests/test_http_admin_authority.py, tests/test_sl02_support_tickets.py | Полная threat model и независимая приёмка |
| [Burn2288 #26 · MASTER #62 · SE-02] Безопасные экспорт, логи и retention | `NOT_ASSESSED` → `IN_PROGRESS` | Timeline и operations используют безопасные DTO | tests/test_job_timeline.py, operations_read_model.py | Полный аудит экспорта, логов и retention |
| [vankhu21 #37 · MASTER #63 · SE-03] Независимая regression security двух клиентов | `NOT_ASSESSED` → `IN_PROGRESS` | Регрессия проверяет изоляцию и revoke на общих сервисах | tests/test_sl02_support_tickets.py, OP01 | Независимая проверка обоих клиентов |
| [Burn2288 #27 · MASTER #64 · TQ-01] Закрепить CI profile и fixtures для интегрированной базы | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Существующий composite workflow и fixtures используются повторно | .github/workflows/tq01-composite.yml | Финальные результаты на опубликованном HEAD |
| [vankhu21 #38 · MASTER #65 · TQ-02] Сквозная parity/regression matrix четырёх студий | `NOT_ASSESSED` → `IN_PROGRESS` | Профильные suites и браузер проверяют части паритета | OP01 и раздел регрессии | Восемь маршрутов и restart на едином общем процессе |
| [Burn2288 #28 · MASTER #66 · OP-01] Подготовить закрытый HTTPS test endpoint Mini App | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | HTTPS browser journey через Caddy и синтетические Telegram сессии | verification/op01/miniapp_journey.py | Telegram WebView и интерактивная удалённая демонстрация отдельно |
| [Burn2288 #29 · MASTER #67 · OP-02] Проверить миграции и полный backup/restore | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Проверка PostgreSQL 16 backup/restore выполняется в disposable окружении | tests/test_admission_privilege_boundary.py, раздел стенда | Полный production restore и D-09 |
| [Burn2288 #30 · MASTER #68 · OP-03] Принять Ubuntu release candidate и shutdown | `NOT_ASSESSED` → `IN_PROGRESS` | Compose shutdown/restart фиксируется в облачной среде | Раздел стенда в этом отчёте | Вторая машина и Ubuntu 24.04 release acceptance |
| [Burn2288 #31 · MASTER #69 · OB-01] Единая safe timeline job и provider request | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Owner-scoped timeline и безопасные ошибки покрыты | tests/test_job_timeline.py | Расширенный provider live trace |
| [Burn2288 #32 · MASTER #70 · OB-02] Операционный и финансовый read API | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Capability-gated отчёт строится из PostgreSQL aggregate queries | src/elevenbot/operations_read_model.py, tests/test_http_admin_authority.py | Отдельная эксплуатационная сверка с live данными |
| [vankhu21 #39 · MASTER #71 · OB-03] Dashboard отчётов и управляемые incident alerts | `NOT_ASSESSED` → `IN_PROGRESS` | Dashboard использует отчёт и состояние очереди сверки из БД | Mini App, OP01 | Внешний канал alerts требует отдельного решения |
| [Burn2288 #33 · MASTER #72 · DC-01] Устранить расхождения фундаментальных контрактов | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Уточнены работающие C-011, C-020 и C-022 | docs/contracts/README.md | Финальная сверка остальных контрактов |
| [Burn2288 #34 · MASTER #73 · DC-02] Сверить финальные runbooks с реализацией | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Документированы запуск и ограничения общей disposable среды | docs/operations/DEPLOYMENT.md | Отдельное подтверждение на машине второго разработчика |
| [Burn2288 #35 · MASTER #74 · RL-01] Согласовать scope, цены и критерии пилота | `NOT_ASSESSED` → `IN_PROGRESS` | Тестовый scope ограничен synthetic payments, quote fixtures и mock providers | Этот отчёт и C-011 v1 | Решение по коммерческой цене и условиям |
| [vankhu21 #40 · MASTER #75 · RL-02] Провести ограниченный коммерческий user journey | `NOT_ASSESSED` → `IN_PROGRESS` | По частям проверены synthetic payment, durable result и capture | Наборы Stars, process E2E, RF-02 | Сквозная оплата до результата на том же общем runtime и коммерческий пилот |
| [Burn2288 #36 · MASTER #76 · RL-03] Release decision и синхронизация двух полных сборок | `NOT_ASSESSED` → `IN_PROGRESS` | Итоговый checkout и Draft PR сверяются по SHA | Раздел refs в этом отчёте | Две независимые оценки и вторая машина |
| [Burn2288 #37 · MASTER #77 · AP-01] Описать существующий API OpenAPI 3.1 и auth errors | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | OpenAPI описывает действующие маршруты | miniapp/openapi.json, tests/test_openapi_viewer.py | Все типы и полный error contract |
| [Burn2288 #38 · MASTER #78 · AP-02] Transport-neutral quote и image job command | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Quote/image commands используют общий job backend | miniapp/backend/image_commands.py, miniapp/tests/test_miniapp.py | Универсальный transport-neutral маршрут всех типов |
| [Burn2288 #39 · MASTER #79 · AP-03] Owned job status, list и cancel API | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Owned list, status и cancel покрыты HTTP тестами | miniapp/tests/test_miniapp.py, tests/test_job_timeline.py | Полная матрица кросс-клиентных статусов |
| [Burn2288 #40 · MASTER #80 · AU-01] Согласовать audit-artifacts lifecycle и schema gate | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Сохранены прежние доказательства и gate реестра | .github/check_completion_register.py, AGENTS.md | Два независимых заключения на итоговом SHA |
| [vankhu21 #41 · MASTER #81 · AU-02] Доказать передачу и повторный аудит без потери истории | `CANDIDATE_PREPARED` → `CANDIDATE_PREPARED` | Пакет сохраняет происхождение задач, точный SHA и общий Draft | Реестр, этот отчёт и PR #115 | Независимый повторный аудит до merge |
## CLOUD-FINALIZATION-MEGA-03

Изолированный Compose `sprint03-product` использовал PostgreSQL, Telegram gateway, worker и Mini App. На одном PostgreSQL подтверждены 8/8 маршрутов image, video, speech и music. Каждая работа открылась из обоих клиентов с одинаковыми байтами. Шесть заданий оставили по одному Wallet/Ledger capture. Две музыкальные работы использовали отдельные пилотные grants. У Telegram music возник явный отказ по лимиту частоты, после окончания окна то же ожидающее подтверждение завершилось одним grant settlement.

Проверенный runtime-прогон матрицы использовал исходники `0f29ef260e3180a9b06da76a86ed797cf623f7a0`, дерево `79e80d674ed4f5ce30de7dcabc8261a727da4b6a`. Последующие исправления восстанавливают совместимость исторического upgrade-фикстура и запуск gateway из read-only checkout. Проверки итогового SHA и связь с синтетическим merge приведены в [Draft #115](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/115).

Штатное размещение исполнения сохранено. Image и priced speech стартуют в gateway или backend, video/music используют существующие poller-циклы gateway. Worker выполняет legacy speech, settlement и обслуживание очереди. Отдельный process E2E доказал получение сохранённой legacy-озвучки после остановки gateway, одно списание, скачивание владельцем в Mini App и отказ чужому аккаунту. Миграция 063 включает автодоставку для новых подтверждений Telegram. Исторические строки, для которых отправка не была отмечена, при обновлении повторно не доставляются.

Сквозной DEV finance использовал настоящие обработчики с синтетическим Stars-платежом. Повтор сохранил одно зачисление. Списание 100 PAID начислило 5 токенов, подтверждённый refund привёл к долгу 5, следующее начисление погасило его до нуля. Результат виден в обоих клиентах, сверка кошельков вернула 0 расхождений. Отдельный Chromium-прогон прошёл историю оплаты, сохранённый результат, рефералов и обращение с ответом оператора.

На хосте Docker тестовый transport и Mini App публикуются на loopback. Fixture transport доступен внутри сети проекта. Подписанный вход вне допущенного списка отклонён без создания identity. Производственный образ не содержит fixture-скриптов. Полная независимая проверка SE-03 остаётся на глобальной приёмке.

Воспроизведение запуска, безопасного CA, восьми маршрутов и демонстрации приведено в [руководстве эксплуатации](../operations/DEPLOYMENT.md). Возможности провайдеров и ссылки на профильные проверки перечислены в [карте адаптеров](../../INTERACTION_PILOT_RU.md). Отдельный [Ubuntu 24.04 workflow job](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/45896992473/job/140173224769) проверил чистый запуск, миграции и повторный запуск на Actions runner. Отдельный release-host ожидает проверки.

### Пакеты и задачи Sprint 03

| Пакет | Продуктовый результат | Задачи в существующем реестре |
| --- | --- | --- |
| P01 | Четыре студии и управляющий ввод в локальный Telegram transport | JO-03, IM-01, VI-01, VI-02, MU-01, MU-02 |
| P02 | Durable legacy-озвучка после перезапуска и сохранность библиотек | JO-03, VO-02, ML-02 |
| P03 | Mobile preview, фильтр студий, статус музыки и ссылки на результаты | MA-04, VO-02, RF-03 |
| P04 | 8/8 маршрутов с media и settlement в одной базе | TQ-02, MA-04, ML-02 |
| P05 | Карточки объектов, очередь поддержки и инциденты в двух клиентах | AD-03, OB-03, AD-02 |
| P06 | Read-only сверка, Stars replay, PAID reward, refund, debt, repayment | WL-02, PC-02, RF-02, RF-03 |
| P07 | Адаптеры offline и доказательства сохранения исторических реализаций | PR-03, IN-08, IN-09, IN-10, IN-11, IN-12, IN-13 |
| P08 | Сохранены исторические маршруты и проверена их применимость | IN-14, IN-15, IN-16, IN-17 |
| P09 | Утверждённый порядок, ancestry и действующий интеграционный фундамент | IN-01, IN-02, IN-18, IN-19 |
| P10 | Defensive проверки роли, ownership, журналирования и fixture guard | SE-01, SE-02, SE-03 |
| P11 | Документированный старт, безопасный CA, Ubuntu Actions и повторный запуск | OP-03, IN-19, RL-03 |
| P12 | Синтетический коммерческий сценарий и браузерная демонстрация | RL-01, RL-02, RL-03 |

| Историческая задача | Пакет | Статус до → после | Выполненный объём | Доказательство | Остаток и решение |
| --- | --- | --- | --- | --- | --- |
| [Burn2288 #1 · MASTER #1 · IN-01] Утвердить порядок интеграции и freeze SHA | P09 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Проверены утверждённый порядок интеграции и исходные remote refs. | Documentation и сверка исторических PR | Уникальная дельта и ретаргет исходного #18 |
| [Burn2288 #2 · MASTER #2 · IN-02] Принять документационную базу PR #1 | P09 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Подтверждено включение документационного фундамента PR #1 в принятую main. | Documentation и ancestry #1 | Глобальная приёмка последующих изменений |
| [vankhu21 #1 · MASTER #3 · IN-08] Интегрировать PR #8 и доказать supersession ранних пилотов | P07 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Сохранены image-пилоты и миграции 001–012, повторены 55 image-проверок. | ML01, FT020 и сверка ancestry #8 | Платные live-возможности по разрешению владельца |
| [vankhu21 #2 · MASTER #4 · IN-09] Провести отдельную приёмку и интеграцию PR #9: Veo video | P07 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Сохранён Veo create/poll. Заглушка выдаёт сохранённый MP4 из общего профиля. | TQ01 и матрица студий | Live Veo вне выполненного прогона |
| [vankhu21 #3 · MASTER #5 · IN-10] Провести отдельную приёмку и интеграцию PR #10: AnyModel registry | P07 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Реестр AnyModel, discovery и манифесты сохранены в принятой ancestry. | FT016 и FT017 | Коммерчески разрешённый набор live-моделей |
| [vankhu21 #4 · MASTER #6 · IN-11] Провести отдельную приёмку и интеграцию PR #11: FIBO async image | P07 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Async FIBO удерживает результаты и путь recovery/refund. | FT017 и FT022 | Live FIBO |
| [vankhu21 #5 · MASTER #7 · IN-12] Провести отдельную приёмку и интеграцию PR #12: Grok video | P07 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Grok video и его process restart проверены на fixtures. | TQ01 и FT017 | Live Grok |
| [vankhu21 #6 · MASTER #8 · IN-13] Провести отдельную приёмку и интеграцию PR #13: AnyModel speech | P07 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | AnyModel speech, UTF-16 и выдача аудио подтверждены. | FT021 | Live AnyModel speech |
| [vankhu21 #7 · MASTER #9 · IN-14] Провести отдельную приёмку и интеграцию PR #14: Welcome/navigation | P08 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Сохранены Welcome, обязательное согласие, навигация и Back. | FT031 | Настоящий Telegram-клиент и глобальная приёмка |
| [vankhu21 #8 · MASTER #10 · IN-15] Провести отдельную приёмку и интеграцию PR #15: Task progress | P08 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Сохранены проекция статусов и timeline. Закрыта потеря legacy-доставки речи. | JO03, process E2E | Долгосрочная обработка неоднозначных внешних ответов |
| [vankhu21 #9 · MASTER #11 · IN-16] Принять PR #16: финансы, каталог и Telegram Admin | P08 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Проверены тарифы, синтетические платежи, каталог и Telegram Admin. | FT028 и TQ01 | D-02/D-03 для новых мутаций |
| [vankhu21 #10 · MASTER #12 · IN-17] Принять PR #17: Mini App и новый inbox | P08 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | Mini App, inbox и idempotent повторы сохранены. | TQ01 и OP01 | Live Telegram WebView |
| [Burn2288 #3 · MASTER #13 · IN-18] Согласовать фундамент и план как отдельные docs PR | P09 | `NOT_ASSESSED` → `CANDIDATE_PREPARED` | План, канонический реестр и карта контрактов покрывают текущий процесс. | Documentation и сверка исторических PR | Полное замещение исходного #18 ещё не установлено |
| [Burn2288 #4 · MASTER #14 · IN-19] Синхронизировать и запустить целую принятую сборку | P09/P11 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Общий DEV запустился. Seeded upgrade проверил identity, ledger и media. | TQ01, FT024, Compose | Машины обоих разработчиков и отдельный release-host |
| [vankhu21 #17 · MASTER #23 · MA-04] Довести пользовательский parity и доступность | P03/P04 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Добавлены фильтр студий, мобильный preview, скачивание и статус музыки. | OP01 и матрица студий | Настоящий WebView и отдельное тестирование accessibility для STANDARD |
| [Burn2288 #11 · MASTER #31 · PR-03] Сверить live capability каждого включаемого адаптера | P07 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Составлена таблица четырёх DEV-маршрутов, AnyModel и Fal. | INTERACTION_PILOT_RU.md, FT016, FT017 и FT021 | Живые вызовы требуют отдельного разрешения |
| [vankhu21 #23 · MASTER #35 · PC-02] Preview и publish versioned тарифов | P06 | `BLOCKED` → `BLOCKED` | Legacy preview сохраняет тарифы, оценки, баланс и ledger. Общая публикация заблокирована. | Профильный PostgreSQL и тест операторских объектов | D-02: цены, единицы, приоритеты, audit и rollback |
| [Burn2288 #20 · MASTER #51 · WL-02] Сверка ledger и контролируемые корректировки | P06 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Добавлены детализация расхождений и чтение payment/referral cases. Пройден разрешённый учёт возврата. | FT029, операторские объекты и DEV finance journey | D-02/D-03 для расширенных корректирующих проводок |
| [Burn2288 #25 · MASTER #61 · SE-01] Threat model и security boundary suite | P10 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Проверены deny, актуальные PostgreSQL-роли, изоляция и отсутствие реальных вызовов в DEV. | OP01, тесты ACL, анализ рабочего профиля | Независимая проверка в глобальном аудите |
| [Burn2288 #26 · MASTER #62 · SE-02] Безопасные экспорт, логи и retention | P10 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Проверены безопасные экспорты, журналы и сохранность данных. Fixture отсутствует в производственном образе. | AU02 и проверка Compose | Долгосрочное хранение и legal hold для STANDARD |
| [vankhu21 #37 · MASTER #63 · SE-03] Независимая regression security двух клиентов | P10 | `IN_PROGRESS` → `IN_PROGRESS` | Выполнена внутренняя регрессия изоляции и отказов. | OP01, PostgreSQL и контроль DEV | Два независимых аудитора; внутренняя проверка не заменяет приёмку |
| [vankhu21 #38 · MASTER #65 · TQ-02] Сквозная parity/regression matrix четырёх студий | P04 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Единый сценарий связывает восемь входов, один PostgreSQL, результат и списание либо grant. | verification/studio_matrix.py и matrix.json | Настоящий Telegram WebView и дополнительное покрытие неоднозначной внешней доставки для STANDARD |
| [Burn2288 #30 · MASTER #68 · OP-03] Принять Ubuntu release candidate и shutdown | P11 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Проверены чистый запуск и сохранность после restart. CA передаётся через BuildKit secret. | FT024 и Compose | Отдельный Ubuntu release-host |
| [vankhu21 #39 · MASTER #71 · OB-03] Dashboard отчётов и управляемые incident alerts | P05 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Добавлены инциденты, очереди и карточки объектов в Telegram и Mini App. | Операторские проверки и Chromium OP01 | Внешний канал требует отдельного разрешения |
| [Burn2288 #35 · MASTER #74 · RL-01] Согласовать scope, цены и критерии пилота | P12 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Тестовый коммерческий сценарий использует действующие synthetic Stars и пилотные цены. | DEV finance journey | Коммерческие цены и условия утверждает владелец |
| [vankhu21 #40 · MASTER #75 · RL-02] Провести ограниченный коммерческий user journey | P12 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Проверен путь от синтетического пополнения до результата, библиотеки, награды и поддержки. | P06/P12 Chromium и synthetic Stars | Реальный коммерческий пилот требует разрешения |
| [Burn2288 #36 · MASTER #76 · RL-03] Release decision и синхронизация двух полных сборок | P11/P12 | `IN_PROGRESS` → `CANDIDATE_PREPARED` | Собран единый Draft и повторяемые демонстрационные сценарии. | Compose, FT024, PR #115 | Независимые аудиты и решение владельца о выпуске |

Итог — 79/81 `CANDIDATE_PREPARED`, 1 `IN_PROGRESS` (SE-03), 1 `BLOCKED` (PC-02), 0 `NOT_ASSESSED`, 0 завершённых. Техническая интеграция исторической когорты 23/37. Для 14 оставшихся PR подтверждения полного supersession пока нет.

## FINAL-IMPLEMENTATION-FREEZE-06

D-02 утверждено владельцем 26 ноября 2026 года. [vankhu21 #23 · MASTER #35 · PC-02] реализует один disposable-тариф CLODEX FLUX Schnell, images.generate, n=1, request, целые внутренние токены 2 → 3. Право OWNER_ADMIN проверяется сервером в каждом действии. Preview учитывает существующую наценку. Confirm использует POLICY_LOCK, текущую ревизию и фиксированный payload, сохраняет новую версию с append-only audit атомарно. Rollback восстанавливает 2 как следующую версию. D-03 остаётся открытым для дополнительных корректировок.

[vankhu21 #22 · MASTER #34 · PC-01] и [Burn2288 #20 · MASTER #51 · WL-02] проверены общим PostgreSQL-сценарием: старые quotes обоих клиентов подтвердились по 2 после публикации 3, новые задания списали по 3, rollback вернул следующие quotes к 2. Preview и публикация не меняют Wallet/Ledger. Одновременный повтор создаёт одну запись, устаревшая версия и отозванная роль отклоняются. Аудит неизменяем.

[vankhu21 #37 · MASTER #63 · SE-03], [Burn2288 #25 · MASTER #61 · SE-01] и PC-01 получили прямое негативное покрытие клиентских полей price/total на /api/v1/quotes и /api/v1/jobs. Отказы сохраняют кошельки, Ledger и отсутствие dispatch. Чужой quote отклоняется. Штатный запрос рассчитывается сервером. SE-03 ожидает два независимых заключения.

[vankhu21 #38 · MASTER #65 · TQ-02], [vankhu21 #17 · MASTER #23 · MA-04] и [Burn2288 #30 · MASTER #68 · OP-03] проверены на одном новом Compose-профиле с PostgreSQL, gateway, worker и Mini App. Матрица 8/8 завершилась перед публикацией цены. Браузер владельца опубликовал 3, Telegram владельца вернул 2. После stop/start четыре сервиса healthy, финансовые данные и тарифный аудит сохранились, восемь файлов скачались с прежними SHA-256. Упражнение исходно выполнено на 919c7f8, последующие изменения добавили тесты, CI и запись результатов. Итоговые SHA/TREE и точные повторные доказательства опубликованы в Draft #115 и следующей ревизии приватного GLOBAL_PR_REGISTER.

Профиль FT020 теперь включает tests/test_fixture_tariff_roundtrip.py. Исходная замороженная ревизия 190a46c и приватный пакет 15731aa сохранены в истории. Итоговый реестр после доказанного PC-02 содержит 80 CANDIDATE_PREPARED, 1 IN_PROGRESS (SE-03), 0 BLOCKED, 0 NOT_ASSESSED, 0 завершённых. Номера и completed_level сохраняются.
