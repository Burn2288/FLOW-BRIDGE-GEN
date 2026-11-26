# Подготовка эксплуатации

Целевая среда приёмки — Ubuntu 24.04 и PostgreSQL. DEV-стенд запускает Telegram gateway, worker и Mini App с общим PostgreSQL. Доступные маршруты Mini App описаны в [HTTP API](../../miniapp/openapi.json). Установка на Ubuntu и сервисные операции описаны в [руководстве Ubuntu](../../README_UBUNTU_RU.md) и [сервисном runbook](../../SERVICE_RUNBOOK_RU.md).

## Проверки без реальных запросов

Из корня репозитория, в окружении Python 3.12, установите зафиксированные зависимости:

```sh
python -m pip install -r requirements-acceptance.txt
python -m pytest -q -ra
```

Для проверки аудио нужен `ffprobe`. Для проверок с БД используйте только одноразовый PostgreSQL-профиль с предусмотренными `TEST_DATABASE_URL`, `DISPOSABLE_POSTGRES_PROFILE` и `DISPOSABLE_POSTGRES_CONFIRM`; точные допустимые значения проверяет [guard](../../scripts/disposable_test_db.py). Также нужны `pg_dump` и `pg_restore`. Тесты создают временные схемы и базы. GitHub Actions поднимает отдельный экземпляр PostgreSQL и использует заглушки внешних сервисов.

## Локальный Docker-стенд flowbridge-dev

Из корня рабочей копии запустите PostgreSQL, Telegram gateway с локальной заглушкой,
worker и Mini App. Mini App обслуживает frontend и API на одном порту. Внутренние
сервисы используют `flowbridge_dev` и общий том аудио. PostgreSQL и Telegram
transport доступны внутри проекта. Порт Mini App опубликован на loopback хоста
Docker. Для второго независимого проекта задайте другой порт через
`FLOWBRIDGE_DEV_MINIAPP_PORT`.

```sh
docker compose -f compose.dev.yaml up -d --build --wait
docker compose -f compose.dev.yaml ps
curl --fail http://127.0.0.1:8091/healthz
docker compose -f compose.dev.yaml logs bot worker miniapp
docker compose -f compose.dev.yaml exec -T bot python -m elevenbot metrics
```

Откройте `http://127.0.0.1:8091/` на хосте Docker для проверки загрузки интерфейса.
Авторизованные сценарии требуют подписанных Telegram Web App init data. Для
закрытой браузерной проверки с тестовым сертификатом и fixture-пользователями
используйте существующий [OP-01](../../verification/op01/test_https.py).
Для запуска через Telegram укажите в настройках тестового бота HTTPS-адрес
закрытого стенда. Loopback HTTP предназначен для локального просмотра и health-check.

На новом томе ожидаются `migrations applied`, `telegram_stub_smoke=ok` и
`telegram_stub_delivery=audio` в логах. Добавьте `-f compose.dev.override.yaml`
после основного файла, если нужен read-only bind mount исходников. Исходники
должны быть доступны для чтения UID 10001 в контейнере. После изменения
Python-кода перезапустите соответствующий сервис. После изменения зависимостей
соберите образ заново. Остановка и запуск сохраняют PostgreSQL и аудио в томах.

```sh
docker compose -f compose.dev.yaml stop
docker compose -f compose.dev.yaml up -d --wait
```

Проект `compose.test.yaml` использует отдельный экземпляр PostgreSQL и
одноразовую БД `elevenbot_test`. Для проверки восстановления и process journey:

```sh
docker compose -p flowbridge-runtime-check -f compose.test.yaml run --build --rm tests python -m pytest -q tests/test_dev_fixture.py tests/test_process_e2e.py tests/test_ft024_backup_restore.py
```

### Сборка через корпоративный CA

Если `uv sync` на хосте с HTTPS-прокси сообщает `UnknownIssuer`, передайте
полный доверенный PEM-bundle хоста с CA прокси. Храните файл вне рабочей копии.
Дополнительные Compose-файлы передают его в `uv sync` как BuildKit secret.
Проверка TLS остаётся включённой. Сертификаты не копируются в образ и не
монтируются в запущенные сервисы. При обычном доступе используйте базовые команды.

```sh
export FLOWBRIDGE_BUILD_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
docker compose -f compose.dev.yaml -f deploy/compose.dev.build-ca.yaml up -d --build --wait
docker compose -f compose.test.yaml -f deploy/compose.test.build-ca.yaml run --build --rm tests
```

Выберите путь к bundle для вашего хоста. Если после смены bundle требуется
повторная загрузка зависимостей, выполните `build --no-cache` с теми же
Compose-файлами перед запуском.

## Конфигурация стенда

[Config.env](../../src/elevenbot/config.py) читает `ADMIN_TELEGRAM_IDS`, `TELEGRAM_BOT_TOKEN` и `MINIAPP_URL`; имя `ADMIN_TELEGRAM_USER_IDS` не является установленным alias. Telegram Admin Edition использует отдельный вход администратора. Обычная HTTP-сессия Mini App не наследует эту административную сессию. Для защищённых административных HTTP-маршрутов источник полномочий — PostgreSQL RBAC (D-04, OPTION_B); актуальная роль проверяется на каждом запросе, а при недоступности источника доступ запрещён.

В disposable окружении оператор с `settings.visibility` может открыть
«Администрирование → Видимость моделей» в Mini App или вызвать
`/model_visibility` в Telegram. Для предпросмотра в Telegram передайте
`/model_visibility clodex flux-schnell images.generate HIDDEN` и подтвердите
изменение кнопкой. Для предпросмотра отката передайте `rollback` вместо `HIDDEN`.
Модель должна присутствовать в разрешённом каталоге. Устаревшее подтверждение
требует нового предпросмотра. Скрытие модели не отменяет уже принятые задания
и не удаляет сохранённые результаты.

В Telegram обращения открываются через «Помощь», в Mini App через «Поддержка».
Для выбора обращения из административной очереди и ответа требуется
`support.operate`. Поддерживаются текстовые обращения.

Для диагностики без изменения БД: `python -m elevenbot reconcile-report --env-file <env-файл> --limit 100`. JSON содержит `wallet_mismatches` — число нарушений двух проверок (один кошелёк может учитываться дважды), ограниченный список причин и `truncated`. Отчёт не переключает `halted` и не исправляет проводки; обычный `reconcile` сохраняет прежнюю остановку при расхождении. Вывод содержит UUID и финансовые значения и предназначен оператору.

Локальная копия оригинальной конфигурации находится в игнорируемом каталоге `.local/archive/`. При переносе в новый клон возьмите значения из своего тестового окружения, начиная с `.env.example`. Проверьте, что конфигурация указывает на тестовую БД и тестовый бот, `PAYMENTS_ENABLED=false`, а относительные пути каталога и хранилища считаются от расположения файла, переданного в `--env-file`. Для безрасходного прогона используйте `CLODEX_INTERACTION_MODE=mock`. Живой вызов CLODEX проверяется отдельно на согласованных условиях расхода. Реальные ID пользователей остаются в локальной конфигурации и базе.

- Хранить реальные значения конфигурации вне Git. Разделять тестовые и production-среды. Использовать только обезличенные логи, correlation IDs, health и readiness probes.
- Проверить контролируемое завершение, восстановление worker после падения, резервное копирование и восстановление БД и медиа. В runbook указать диагностику по job ID и действия при недоступности провайдера, БД или диска.
- Модель угроз охватывает Telegram, HTTP API, Mini App, платежи, вебхуки, PostgreSQL, credentials, админку, медиа и деплой. Проверки включают SSRF и redirects, path traversal, SQL injection, IDOR, подделку вебхуков, гонки, вложения, исчерпание ресурсов, повторы и повышение привилегий.
- Для релиза зафиксировать SHA, шаги миграции, проверку восстановления и результаты матрицы. Эксплуатационные изменения выполнять по [правилам команды](../../CONTRIBUTING.md).

Штатный Ubuntu snapshot содержит дамп БД, внешние MP3 и, если настроенный `CATALOGUE_PATH` существует, конкретный файл каталога; их SHA-256 перечислены в `manifest.json`. Относительные пути разрешаются от каталога env-файла. Отсутствие каталога указывается явно и не подтверждает его восстановление; старые manifest без этого поля остаются совместимыми. Runtime env и credentials в архив не входят. Для изолированного drill: `python -m elevenbot.snapshot restore-drill --backup <папка> --migration-config <env-файл>`; пароль локального администратора вводится скрыто. Drill создаёт и удаляет отдельную БД и оставляет восстановленную копию остановленной. Тест FT-024 проверяет один DB image и один внешний MP3, но не устанавливает production RPO/RTO или политику хранения (D-09).

## DEV для разработки и закрытый STAGING

На чистом DEV-томе `scripts/dev_bot.py` подаёт синтетический диалог в настоящий
Telegram gateway. Пользователь принимает условия, выбирает тестовый голос и
подтверждает цену. Отдельный штатный worker сохраняет mock-аудио. Локальный
транспорт отмечает получение строкой `telegram_stub_delivery=audio`.
Offset хранится в PostgreSQL. Завершённый сценарий при рестарте не запускается снова.
Для повторяемых независимых запусков и проверки изображений используйте тестовую БД.

```sh
docker compose -f compose.dev.yaml up -d --build --wait
docker compose -f compose.dev.yaml logs bot worker
docker compose -f compose.dev.yaml exec -T bot python -m elevenbot metrics
docker compose -f compose.dev.yaml restart worker
docker compose -f compose.test.yaml run --build --rm tests python -m pytest -q tests/test_dev_fixture.py tests/test_process_e2e.py tests/test_public_image_topup.py tests/test_image_recovery.py tests/test_worker.py::test_A10_timeout
docker compose -f compose.dev.yaml stop
```

Закрытая приёмка на отдельных проектных томах, во внутренней сети без публикации порта и без монтирования исходников:

```sh
docker compose -p flowbridge-staging -f compose.dev.yaml -f compose.staging.yaml up -d --build --wait
docker compose -f compose.test.yaml run --build --rm tests python -m pytest -q tests/test_process_e2e.py tests/test_public_image_topup.py
docker compose -p flowbridge-staging -f compose.dev.yaml -f compose.staging.yaml stop
```

В обоих профилях PostgreSQL доступна только внутри проекта. Шлюз и worker используют
loopback в сетевом пространстве контейнера БД. Скрипт принимает только fixture-БД и
передаёт приложению явный набор переменных. Production compose загружает свой .env
и отдельные роли. Для реального интеграционного вызова требуется отдельно настроенный
закрытый стенд с тестовым ключом, списком допущенных пользователей, моделью и лимитом
конкретной операции. В этих двух профилях внешних разрешений нет.

В Telegram команда `/referral` показывает код и команду приглашения, число
приглашённых, доступные начисления, долг, условия и историю. В Mini App эти
данные доступны в разделе рефералов. Для ссылки приглашения задайте
`TELEGRAM_BOT_USERNAME` без `@` для бота, которому принадлежит
`TELEGRAM_BOT_TOKEN`. Изменение username требует обновления конфигурации.

Тестовые начисления C-011 используют ставку 5% из профильной fixture и подтверждённое
PAID-финансирование после сохранения результата и capture. Общий DEV smoke
запускает демо-озвучку без такого PAID funding. Для синтетической
оплаты, начислений, reversal и погашения долга используйте
`docker compose -f compose.test.yaml run --build --rm tests python -m pytest -q tests/test_ft022_referrals.py`.
Музыкальный пилот использует отдельные бесплатные гранты.
