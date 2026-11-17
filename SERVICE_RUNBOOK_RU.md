# DarkFlow | Gen - постоянный сервис Ubuntu / Windows

Основной runtime теперь `python -m elevenbot`, а не `elevenbot.demo`.
Токен/настройки вводятся один раз в конфигурацию. Пользователи, согласия, контекст,
история, задания, деньги и polling offset хранятся в PostgreSQL. Новая личная ссылка
при каждом старте не создаётся. Вход владельца: обычный /start в том же Telegram-боте.

Текущая включаемая возможность: каталог Clodex и preview запросов. Рабочее постоянное
хранение не означает, что исполнение новых генераций уже реализовано. По умолчанию
PROVIDER_MODE=catalogue, GENERATION_ENABLED=false, PAYMENTS_ENABLED=false.

## 1. Зависимости

На обеих ОС нужны Python 3.12 и работающий PostgreSQL 16. Для аудио worker с генерацией
нужен ffmpeg/ffprobe в PATH. В режиме catalogue новые генерации не создаются.
PostgreSQL можно установить нативно, без Docker/WSL/виртуализации. Ubuntu systemd
предполагает отдельную службу PostgreSQL; данные нельзя хранить во временном каталоге.

Linux, из распакованного проекта:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-service.txt
export PYTHONPATH="$PWD/src"
```

На Windows `SETUP_SERVICE.cmd` создаёт .venv, устанавливает те же зафиксированные
пакеты и запускает настройку. Это уже не старый RUN_DARKFLOW_TEST.cmd.

## 2. База и роли (новая изолированная установка)

Не выполнять этот раздел на действующей БД без отдельного плана. Пользователь БД для
bot/worker должен отличаться от владельца миграций. Пример для интерактивного psql
с административным подключением; реальные пароли вводятся через \password, не в код:

```sql
CREATE ROLE darkflow_owner LOGIN;
\password darkflow_owner
CREATE ROLE darkflow_app LOGIN;
\password darkflow_app
CREATE DATABASE darkflow OWNER darkflow_owner;
\connect darkflow
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO darkflow_app;
ALTER DEFAULT PRIVILEGES FOR ROLE darkflow_owner IN SCHEMA public
 GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO darkflow_app;
ALTER DEFAULT PRIVILEGES FOR ROLE darkflow_owner IN SCHEMA public
 GRANT USAGE,SELECT ON SEQUENCES TO darkflow_app;
```

Если таблицы уже созданы, default privileges недостаточно: владелец отдельно выдаёт
runtime роли SELECT/INSERT/UPDATE/DELETE ON ALL TABLES IN SCHEMA public и
USAGE/SELECT ON ALL SEQUENCES IN SCHEMA public. Триггеры ledger сохраняются.
PostgreSQL слушает loopback/приватную сеть; не открывать его публично.

## 3. Настройка один раз

Linux:

```sh
.venv/bin/python -m elevenbot.setup_service --env-file .env
```

Для установки из requirements без editable package нужно перед этим `export PYTHONPATH="$PWD/src"`.
На Windows это делает SETUP_SERVICE.cmd.
Настройка спрашивает токен (скрытый ввод), числовой Telegram ID владельца и runtime
PostgreSQL URL (скрытый ввод). Файл создаётся только при отсутствии, повторный запуск
его не перезаписывает. В него не вводится владелец БД: runtime DSN использует darkflow_app.
Пароль в URL должен быть URL-encoded. Не присылать .env в чат или архив аудита.

Параметры доступа: ACCESS_MODE=private, ADMIN_TELEGRAM_IDS=числовой_ID. Чужие пользователи
не регистрируются через пользовательские действия. Финансовые уведомления продолжают
обрабатываться, чтобы ограничение доступа не теряло подтверждённые оплаты. Публичный
доступ здесь не включается. Смена владельца - явное редактирование конфигурации и restart.

.env - UTF-8 KEY=value, одна строка на значение. Поддерживаются пустые строки, строки
комментариев и парные кавычки. Shell expansion, export и многострочные значения не
поддерживаются. Экспортированные переменные имеют приоритет. Не исполнять файл через shell.
Относительные пути данных при --env-file привязаны к каталогу этого файла, а не к CWD.

Файл содержит секреты открытым текстом: на POSIX создаётся с правами 0600. На Windows
применяются унаследованные ACL: хранить проект в приватном каталоге учётной записи,
не в общей папке. DPAPI, реестр Windows и Credential Manager не требуются. На сервере
можно вместо .env использовать защищённые EnvironmentFile/секреты оркестратора.

## 4. Миграции и диагностика

Миграции выполняются отдельно от runtime. Создать отдельный приватный migration.env
с DATABASE_URL владельца darkflow_owner; не передавать его bot/worker. Опциональный
DATABASE_MIGRATION_URL поддерживается, но для разделения секретов предпочтительны
раздельные файлы. Не добавлять owner DSN в общий runtime EnvironmentFile.

```sh
.venv/bin/python -m elevenbot --env-file migration.env migrate
.venv/bin/python -m elevenbot --env-file .env doctor
```

Doctor проверяет соединение, версию PostgreSQL, checksum всех миграций и наличие токена;
печатает только безопасные сводные поля. Наличие ffprobe выводится отдельно. Проверка
успешного Telegram подключения или генерации этим не подменяется.

## 5. Запуск с сохранёнными настройками

Windows: START_DARKFLOW.cmd. Linux для локального foreground запуска: ./START_DARKFLOW.sh.
Supervisor запускает отдельные bot/worker, перезапускает упавший процесс с паузой 5 сек
и останавливается после пяти сбоев одного компонента. Ctrl+C завершает оба процесса;
.env и PostgreSQL остаются. Это foreground запуск: автозапуск после reboot на Ubuntu
организуется через systemd, а на Windows потребует отдельно настроенной задачи/службы.

Ручной запуск компонентов в двух окнах:

```sh
.venv/bin/python -m elevenbot --env-file .env bot
.venv/bin/python -m elevenbot --env-file .env worker
```

Не запускать supervisor и systemd одновременно для одной установки. В bot сохранён
DB advisory lock от двух pollers. Нет одноразовой pairing-ссылки: аккаунты определяются
по Telegram ID и сопоставляются с постоянной записью identities.

## 6. Ubuntu systemd (подготовлено, здесь не развёрнуто)

Код и .venv расположить в /opt/darkflow, создать непривилегированного пользователя и
группу darkflow. Конфигурация runtime: /etc/darkflow/runtime.env, миграции:
/etc/darkflow/migration.env. Файлы root:root 0600 читает менеджер systemd через
EnvironmentFile; bot/worker получают только runtime файл. В runtime обязательно:

```text
AUDIO_STORAGE_DIR=/var/lib/darkflow/audio
CATALOGUE_PATH=/var/lib/darkflow/catalogue/models.json
```

Абсолютные пути важны: systemd создаёт /var/lib/darkflow через StateDirectory и разрешает
запись только туда. Код /opt/darkflow доступен на чтение, зависимости должны быть
установлены заранее. Единицы лежат в deploy/systemd/. Миграции - отдельный oneshot,
bot/worker требуют его успешного завершения. PostgreSQL должен уже принимать подключения.

После проверки конфигурации владелец сервера может установить подготовленные units:

```sh
sudo install -m 0644 deploy/systemd/darkflow-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now darkflow-bot.service darkflow-worker.service
sudo systemctl status darkflow-bot darkflow-worker
sudo journalctl -u darkflow-bot -u darkflow-worker --since today
```

При обновлении остановить bot/worker, сохранить backup, установить совместимый код,
`sudo systemctl restart darkflow-migrate`, проверить doctor/логи и запустить компоненты.
Не выполнять миграции автоматически при каждом падении рабочего процесса. Смена
runtime.env требует restart bot/worker, а не новой привязки аккаунта.

## 7. Docker Compose

Сохранён как альтернативный путь. Использовать .env.example, заполнить разные пароли
POSTGRES_PASSWORD и APP_DB_PASSWORD, TELEGRAM_BOT_TOKEN и ADMIN_TELEGRAM_IDS. Runtime DSN
в Compose задаётся через environment и имеет приоритет над шаблонным DATABASE_URL.
Тома pgdata/audio/catalogue постоянные. Не применять down -v для остановки: это удаление
данных. Уникальное имя проекта задавать явно, например `docker compose -p darkflow ...`.
Команды Docker в текущей среде не исполнялись.

## 8. Backup/restore и перенос

Для нативного сервера нужны pg_dump/pg_restore подходящей версии и backup приватного
AUDIO_STORAGE_DIR вместе с БД. .env передавать отдельно безопасным каналом; никогда не
включать в исходный ZIP. Для Compose сохранены scripts/backup.sh и restore.sh.
Восстановление проводить в отдельную БД, с остановленными bot/worker и settings.halted=true.
Задания queued/dispatching переводить в uncertain/RESTORE_REVIEW, pending payments -
review; неизвестные оплаченные запросы не повторять. Следовать исходной процедуре
restore.sh, не запускать восстановленную копию как активный сервис без сверки.

Переход Windows → Ubuntu: совместимый код, PostgreSQL backup/restore, приватные аудио,
новая серверная конфигурация с тем же TELEGRAM_BOT_TOKEN/ADMIN_TELEGRAM_IDS. Одновременно
старый и новый bot не запускать. Telegram ID/согласия не требуют повторной pairing.
Неизвестные генерации после restore требуют ручной сверки по исходным инвариантам.

## 9. Что ещё не доказано

Новый runtime подготовлен на уровне кода/локальных проверок. Настоящий PostgreSQL,
DB reconnection test, full bot/worker E2E, Windows execution и systemd boot в этой среде
не проверены. Unit verification systemd использует изолированный фиктивный filesystem:
это проверка units, не рабочий сервер. Коммерческие LIVE gates не повышены.
Реальная генерация из агрегированного каталога по-прежнему не реализована.
