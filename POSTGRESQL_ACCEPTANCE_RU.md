# PostgreSQL: настройка и полная приёмка DarkFlow | Gen

Дата: 04.11.2026. Основной движок - настоящий PostgreSQL 16. SQLite/RAM/PGlite не заменяют
его в финансовых тестах. Установка PostgreSQL server не выполняется этим архивом:
сервер должен быть установлен и запущен на машине владельца. Docker не нужен.

## Что проверено здесь

Полный локальный прогон: 148 PASS / 40 PostgreSQL SKIP / 0 FAIL. Проверка нативного
runner здесь дала BLOCKED, exit 78, Missing tool: pg_dump. Сам сервер отсутствует,
Docker отсутствует, UID 0 без capabilities и без возможности переключить пользователя.
runuser -u nobody -- id: cannot set groups, Operation not permitted. Защитные ограничения
не обходились, initdb/postgres не патчились. Полная работоспособность БД не подтверждена.

Миграции 001-006 и потребители core/worker/bot изучены. Добавленные SQL-команды создания
базы/ролей требуют исполнения на реальном сервере; статическая проверка и stubs этого
не заменяют. Ошибки реального прогона должны быть исправлены после получения его evidence.

## Изученные первичные источники

- https://www.postgresql.org/docs/16/app-initdb.html - кластер принадлежит непривилегированному OS-пользователю; сервер не запускается от root.
- https://www.postgresql.org/docs/16/sql-createdatabase.html - CREATE DATABASE вне transaction block; template0 для чистой базы.
- https://www.postgresql.org/docs/16/sql-createrole.html - NOSUPERUSER/NOCREATEDB/NOCREATEROLE и область ролей на уровне cluster.
- https://www.postgresql.org/docs/16/sql-alterdefaultprivileges.html - default privileges действуют только на будущие объекты текущего создателя.
- https://www.postgresql.org/docs/16/auth-pg-hba-conf.html - порядок HBA, SCRAM и CONNECT; скрипт не переписывает существующий pg_hba.conf.
- https://www.postgresql.org/docs/16/app-pgdump.html и app-pgrestore.html - согласованный dump, совместимость версий, --exit-on-error при restore.
- https://www.postgresql.org/download/windows/ - официальная страница Windows installer, ведущая к EDB.

## Шаг 1. Установить зависимости на целевой машине

Windows: PostgreSQL 16 x64 с сервером и Command Line Tools. Сохранить пароль администратора
postgres локально. Порт 5432, loopback; не открывать БД в интернет. StackBuilder не нужен
для этого проекта. Установить FFmpeg, чтобы команда ffprobe была доступна в PATH.
В стандартной установке pg_dump/pg_restore находятся в Program Files/PostgreSQL/16/bin:
runner добавляет этот каталог в свой PATH, не меняя системные настройки.

Ubuntu: PostgreSQL 16, pg_dump/pg_restore 16, ffprobe; сервер работает под штатным
непривилегированным OS-пользователем. Парольный TCP-доступ через loopback нужен runner;
настройку доверенной local socket authentication не ослаблять ради тестов.

Приёмку выполнять только на выделенном локальном dev-instance. Runner откажется от
кластера с посторонними базами (разрешены postgres, darkflow_* и restore_test_*).
Администратор для тестов имеет полномочия создавать тестовые роли/базы: не использовать
чужой/общий production cluster. Обычный bot/worker никогда не получает этот пароль.

## Шаг 2. Полная проверка ДО настройки рабочего сервиса

Windows: распаковать архив в отдельную папку и открыть CHECK_POSTGRESQL.cmd. Он установит
requirements-acceptance.txt в .venv, спросит пароль администратора скрытым вводом и
запустит полный pytest на новой darkflow_accept_<uuid>. Токен Telegram/ключ Clodex не нужны.

Ubuntu из корня проекта:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-acceptance.txt
.venv/bin/python scripts/run_native_acceptance.py
```

Runner не читает service .env и удаляет inherited production API/оплатные настройки.
Каждый DB test использует отдельную schema. Проверяются конкурентные резервы/дубли,
capture/release, бюджет, fault boundaries, uncertain/fencing, доставка, изоляция,
Platega DB checks, runtime role, реальные pg_dump/pg_restore, DB reconnection.
Process E2E запускает настоящие bot/worker с PostgreSQL в двух вариантах: административный
тестовый DSN и ограниченная runtime роль. Затем оба процесса перезапускаются: проверяются
heartbeat, polling offset, одно задание, один capture и одна отправка MP3 на localhost.
Это MOCK-engineering E2E, не live Telegram/Clodex/Platega.

PASS возможен только при exit=0, отсутствии FAIL/ERROR/SKIP и наличии всех ожидаемых
case IDs из tests/required_s2_cases.json. Пропуск инфраструктуры - FAIL, не PASS.
Лимит прогона 900 сек; падение не удаляет evidence. Собственная scratch DB удаляется
после проверки; обычная darkflow_service не удаляется. Если тест прерван, могут остаться
созданные им restore_test_* базы/тестовые роли: проверить их вручную, не удалять по широкому
шаблону. Чужие базы и роли runner не должен очищать.

Результаты: reports/native_runs/<id>/result.json, tests.log, test-results.xml.
Журналы очищаются от известных паролей/DSN и Telegram token patterns. Это ограниченный
sanitizer; перед отправкой всё равно не прикладывать .env или private-db.

## Шаг 3. Создать отдельную рабочую БД

После успешной приёмки: Windows SETUP_POSTGRESQL.cmd. Ubuntu:

```sh
export PYTHONPATH="$PWD/src"
.venv/bin/python -m elevenbot.database_setup
```

Это создание НОВОЙ darkflow_service, не установка PostgreSQL. Уже существующая база
не изменяется и не пересоздаётся. Создаются две отдельные роли с случайными hex-паролями:
owner для миграций и app для runtime, обе без superuser/createdb/createrole/replication/bypassrls.
Создаётся UTF-8 database из template0, отзываются PUBLIC права БД и CREATE схемы,
задаются runtime CONNECT/USAGE и права таблиц/sequence через default privileges.
Owner выполняет все миграции, затем runtime выполняет обратимый heartbeat probe и
проверку отказа DDL. Только после успешных операций возвращается READY.

В private-db сохраняются:

- database.env - только runtime DATABASE_URL;
- migration.env - только owner DATABASE_URL;
- database.credentials.json - приватные сгенерированные DSN для восстановления после частичной ошибки;
- database-result.json - отчёт без паролей, единственный файл из этой папки, который можно передавать проверяющему.

Файлы не перезаписываются. При частичной ошибке - PARTIAL_REVIEW, не повторять настройку
в новой папке наугад: изучить status и созданные ресурсы. Автоматического DROP рабочей
БД нет. Admin пароль не сохраняется. POSIX private files 0600, каталог 0700; Windows
использует унаследованные ACL приватной учётной записи. private-db исключена из Git/Docker.
Владелец может указать иной новый darkflow_* database через --database; допускается только
localhost/127.0.0.1/::1. Скрипт не перенастраивает службы, firewall или pg_hba.conf.

## Шаг 4. Настроить и запустить тот же рабочий bot/worker

Windows: SETUP_SERVICE.cmd. Он автоматически прочитает private-db/database.env и попросит
только BotFather token и Telegram ID владельца. Если .env уже существует, не перезапишет его.
Для старой сохранённой .env адрес БД обновляется явно, а не скрытно. Далее:

```sh
.venv/bin/python -m elevenbot --env-file .env doctor
```

В Windows команда выполняется через .venv\Scripts\python.exe и PYTHONPATH=src; готовый
START_DARKFLOW.cmd уже задаёт PYTHONPATH. Запуск: START_DARKFLOW.cmd. На Ubuntu:
START_DARKFLOW.sh либо подготовленные systemd units (SERVICE_RUNBOOK_RU.md).
Runtime token вводится один раз, постоянные identities/согласия/история сохраняются.
Генерации из нового каталога и оплаты всё ещё выключены. READY базы не означает
PROVIDER_VERIFIED или PAYMENT_VERIFIED.

## Уровни доказательства

1. Локальные unit/static PASS - уже приложены, но не доказывают сервер.
2. Полный CHECK_POSTGRESQL PASS без SKIP - доказательство PostgreSQL + исполняемых
   процессов с локальным Telegram stub и MOCK provider на указанной машине.
3. doctor READY и рабочий /start в реальном Telegram - дополнительная проверка настоящего
   подключения, только с локально введённым владельцем токеном.
4. Реальная генерация, экономика, платежи/возвраты и production/pilot требуют собственных
   разрешений и evidence. Ни один нижний уровень не подтверждает их автоматически.
