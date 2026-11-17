# DarkFlow | Gen - Ubuntu 24.04 LTS

Отдельная Linux-поставка: Python 3.12, PostgreSQL 16, systemd, приватные файлы.
Рабочая область сейчас: постоянные пользователи/согласия/история в БД, автоматический
каталог Clodex и подготовка запросов. Генерация через новый каталог и оплаты выключены.
Полная PostgreSQL/systemd приёмка в среде сборки BLOCKED; см. актуальный отчёт AUDIT_FOLLOWUP_RU.md и исходный UBUNTU_RELEASE_REPORT.md.

## Модели Clodex из API

При новой настройке `configure.sh` предлагает ввести ключ Clodex скрытым вводом.
Для установленного сервиса внеси `CLODEX_API_KEY` через `sudoedit /etc/darkflow/runtime.env`
и перезапусти `darkflow-bot`. Ключ хранится в приватном файле окружения.

С ключом бот берёт ID моделей из авторизованного `GET /v1/models`. Без ключа он
показывает публичный список из `/api/pricing` с соответствующей отметкой.
Модели открываются через `/models` или «Агрегаторы → Clodex → Модели».
Бот обновляет снимок при запуске и каждые пять минут. Успешная загрузка даёт событие
`aggregate_refresh_ok` с количеством моделей и источником в журнале.
Сбой цен или документации не блокирует список, полученный для ключа.
Список моделей и подтверждённые возможности конкретной модели проверяются отдельно.

Чтобы проверить источники и число моделей без запуска бота:

```sh
sudo env PYTHONPATH=/opt/darkflow/src /opt/darkflow/.venv/bin/python -m elevenbot --env-file /etc/darkflow/runtime.env catalog-refresh
```

После миграции 007 отправка с неизвестным исходом помечается в «Моих работах».
Кнопка «Получить файл» позволяет запросить тот же файл повторно без новой генерации.
Задания с неизвестным исходом генерации требуют сверки оператором. После проверки
оператор может освободить резерв командой `release-uncertain --job UUID --reason ПРИЧИНА`.
Эта команда фиксирует событие в журнале БД. Текст причины ведётся в журнале оператора.

## 0. Только новая выделенная установка

Не запускать установщик поверх существующих сервисов. Он отказывается при наличии
/opt/darkflow, /etc/darkflow, /var/lib/darkflow, OS-пользователя/группы darkflow или
собственных units. При частичном сбое он не удаляет созданные файлы автоматически:
проверить состояние и исправить причину, не удалять каталоги с данными наугад.

Поддерживаемая автоматическая установка: Ubuntu 24.04 LTS. Ubuntu 22.04/26.04 и другие
дистрибутивы не заявляются проверенными. В контейнере без работающего systemd installer
не выполняется; для Docker сохранён отдельный Compose путь в исходниках.

## 1. Проверить пакет и установить OS-зависимости

Проверить SHA-256 ZIP по внешнему sidecar, распаковать как обычный пользователь.
На отдельной целевой машине оператор выполняет:

```sh
sudo apt-get update
sudo apt-get install python3.12 python3.12-venv postgresql-16 postgresql-client-16 ffmpeg
```

Пакеты ставятся из штатных доверенных Ubuntu repositories. Установщик приложения сам
не запускает apt, не меняет firewall, postgresql.conf или pg_hba.conf. PostgreSQL должен
уже работать как штатная служба, не от root. Не открывать его порт в интернет.

Для локальной TCP-проверки задать пароль postgres интерактивно, не в shell history:

```sh
sudo -u postgres psql -X
```

В psql: `\password postgres`, ввести пароль дважды, затем `\q`. Не заменять peer/SCRAM
на trust. Этот пароль вводится в локальные инструменты настройки/приёмки, не в Telegram.

## 2. Полный тест до установки сервиса

Из распакованного проекта, без sudo:

```sh
bash deploy/ubuntu/check.sh
```

Это создаёт отдельное .acceptance-venv, ставит зафиксированные dev-зависимости,
запрашивает local postgres пароль и запускает все тесты на darkflow_accept_<uuid>.
Никаких live ключей, оплат и внешнего Telegram не требуется. Тесты используют настоящий
PostgreSQL, настоящие процессы bot/worker и локальный Telegram HTTP stub с MOCK MP3.
Native runner требует выделенный dev cluster, отказывается от посторонних баз.

PASS требует все ожидаемые case IDs и НОЛЬ SKIP/FAIL/ERROR. Результаты сохраняются в
reports/native_runs. Не выдавать пропуск PostgreSQL за успешную приёмку.

## 3. Установить код и неактивные systemd units

```sh
sudo bash deploy/ubuntu/install.sh --check
sudo bash deploy/ubuntu/install.sh
```

--check не меняет систему. install.sh создаёт непривилегированного darkflow с nologin,
копирует только исходники/модули/миграции/assets/тесты/документы по allowlist, создаёт
.venv в /opt/darkflow, ставит runtime dependencies и проверяет импорты. Секреты, аудио,
локальные venv и Git directory из исходной папки не копируются. Сервисы НЕ запускаются.
Нужен доступ к package index для pip; offline колёса в архив не включены.

Код: /opt/darkflow, root:root, читается runtime, не записывается им.
Секреты: /etc/darkflow, root-only; EnvironmentFile читает systemd manager.
Данные: /var/lib/darkflow, darkflow:darkflow 0700; data/log не смешиваются с кодом.

## 4. Настроить базу и токен один раз

```sh
sudo bash /opt/darkflow/deploy/ubuntu/configure.sh
```

Скрипт создаёт новую darkflow_service с owner/runtime ролями, выполняет миграции и
runtime probe. Существующая БД не пересоздаётся. Пароли генерируются случайно и
сохраняются только локально в /etc/darkflow/db-private. После READY запросит токен
BotFather и numeric Telegram ID владельца. Токен и данные вводятся только в локальной
консоли. Закрытый режим PRIVATE сохраняется, генерации/оплаты выключены.

/etc/darkflow/runtime.env содержит только runtime DB DSN, токен/настройки и абсолютные
пути /var/lib/darkflow/audio и /var/lib/darkflow/catalogue/models.json.
/etc/darkflow/migration.env содержит отдельный owner DSN. Owner DSN не передаётся bot/worker.
Файлы 0600, существующая конфигурация не перезаписывается. Частичная установка требует
review; не повторять создание в новой папке вслепую. Администраторский пароль postgres
не сохраняется. Приватный database.credentials.json не включать в отчёты/архивы исходников.

## 5. Запустить после успешной приёмки

```sh
sudo systemctl enable --now darkflow-bot.service darkflow-worker.service
sudo systemctl status darkflow-migrate darkflow-bot darkflow-worker
sudo journalctl -u darkflow-bot -u darkflow-worker --since today
```

Зависимость от PostgreSQL и oneshot migrations включена в units. При reboot менеджер
запускает enabled units. В runtime используются PYTHONPATH=/opt/darkflow/src,
ProtectSystem=strict, NoNewPrivileges, private tmp и запись только в state directory.
Доступ к EnvironmentFile ограничен; это не обещание защиты от root/компрометации ОС.
Токены не передаются как аргументы команд. Не публиковать env-файлы или process environment.

Открыть прежнего Telegram-бота и отправить /start. Повторной pairing-ссылки нет.
Данные согласия/identity привязаны к PostgreSQL. Только ADMIN_TELEGRAM_IDS допускаются
в PRIVATE режиме. Не запускать одновременно старого poller, supervisor и systemd.

## 6. Проверка здоровья

```sh
sudo env PYTHONPATH=/opt/darkflow/src /opt/darkflow/.venv/bin/python -m elevenbot --env-file /etc/darkflow/runtime.env doctor
sudo env PYTHONPATH=/opt/darkflow/src /opt/darkflow/.venv/bin/python -m elevenbot --env-file /etc/darkflow/runtime.env health --component bot
sudo env PYTHONPATH=/opt/darkflow/src /opt/darkflow/.venv/bin/python -m elevenbot --env-file /etc/darkflow/runtime.env health --component worker
```

doctor: соединение/version/checksums всех миграций и безопасная сводка настроек.
health: свежесть heartbeat, не доказательство live генерации. После первого запуска
дать компонентам завершить цикл. Telegram network retry не повторяет генерацию.

## 7. Нативный backup и изолированный restore drill

Использовать только собственные доверенные backups. Полный DB dump содержит приватные
тексты/финансовые записи: не загружать его вместе с обычным отчётом.

```sh
sudo bash /opt/darkflow/deploy/ubuntu/backup.sh /var/backups/darkflow/snapshot-001
```

Обёртка останавливает оба известных systemd компонента, проверяет остановку, делает
pg_dump -Fc, копирует MP3, проверяет существование/хеш активных DB-файлов, пишет manifest
и возвращает ранее активные компоненты. Destination должен быть новым. Не запускать
параллельные вручную поднятые workers или другие writers во время backup. Перед будущим
включением webhook/payments потребуется quiesce всех их writers: текущая процедура
рассчитана на закрытый catalogue deployment. Конфигурация и пароли в backup не копируются.

Проверить восстановление без изменения действующей базы:

```sh
sudo env PYTHONPATH=/opt/darkflow/src /opt/darkflow/.venv/bin/python -m elevenbot.snapshot restore-drill --backup /var/backups/darkflow/snapshot-001 --migration-config /etc/darkflow/migration.env
```

Запросит postgres пароль скрытым вводом. Создаёт только новый darkflow_restore_<uuid>,
восстанавливает под owner ролью, ставит halted=true, переводит queued/dispatching в
uncertain/RESTORE_REVIEW, pending payments в review, проверяет ledger reconciliation
и активные audio hashes. После проверки удаляет только эту временную копию. Runtime.env
не переключается, реальные генерации не запускаются. Ошибка cleanup считается ошибкой.

Для настоящего disaster recovery на другом сервере сначала восстановить роли/приватную
конфигурацию безопасным каналом; обычный pg_dump не содержит cluster roles. Затем
восстанавливать в отдельную БД и отдельный audio directory, проводить те же review
состояния и проверки. Переключение live DSN/audio - ручная операция после сверки;
автоматического отката или повторения неизвестного платного запроса нет.

## 8. Обновление и откат

install.sh только для fresh install. При обновлении: сделать и проверить backup,
остановить bot/worker, сохранить старый код/lockfiles, развернуть совместимый новый src,
migrations/assets/deploy и dependencies в том же /opt/darkflow. Не переносить .venv в
иной префикс: её скрипты могут содержать абсолютные пути. /etc и /var/lib не заменять.
Перезапустить darkflow-migrate, проверить doctor, затем bot/worker. Проверить свежие
heartbeat и журнал. Обновлённые units устанавливать явно с daemon-reload.

Откат кода допустим только при совместимой схеме. Иначе использовать отдельную restore
копию и операторскую сверку. Не делать DROP рабочей БД и не применять миграции назад
наугад. Новая версия пакета сама не выполняет deployment на существующий VPS.

## 9. Что отправлять проверяющему

Только result.json, test-results.xml и очищенный tests.log из native_runs, версию пакета,
команды/exit codes. Не присылать runtime.env, migration.env, database.credentials.json,
DB dumps, личную pairing ссылку или токены. Если все DB tests прошли, это engineering
MOCK-уровень; live Telegram, Clodex и Platega имеют отдельные gates.
