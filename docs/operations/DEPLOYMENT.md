# Подготовка эксплуатации

Целевая среда приёмки — Ubuntu 24.04 и PostgreSQL. Исходный стенд предоставляет Telegram gateway, worker и миграции. HTTP API запланирован на S4. Точки запуска приведены в [руководстве Ubuntu](../../README_UBUNTU_RU.md) и [сервисном runbook](../../SERVICE_RUNBOOK_RU.md). Эти инструкции описывают импортированный стенд, включая исторические результаты.

## Проверки без реальных запросов

Из корня репозитория, в окружении Python 3.12, установите зафиксированные зависимости:

```sh
python -m pip install -r requirements-acceptance.txt
python -m pytest -q -ra
```

Для проверки аудио нужен `ffprobe`. Для проверок с БД установите `TEST_DATABASE_URL` на отдельную тестовую PostgreSQL и предоставьте `pg_dump` и `pg_restore`. Тесты создают временные схемы и базы. GitHub Actions поднимает отдельный экземпляр PostgreSQL и использует заглушки внешних сервисов.

## Локальный Docker-стенд flowbridge-dev

Запускайте из корня рабочей копии. Проект использует внутреннюю сеть без опубликованных портов, собственные тома `flowbridge-dev_postgres` и `flowbridge-dev_runtime` и локальную Telegram-заглушку. Сервис бота использует БД `flowbridge_dev`, а тесты — `flowbridge_acceptance` в том же изолированном экземпляре PostgreSQL. Разные базы позволяют одновременно запускать smoke-бота и тестовые процессы с PostgreSQL advisory lock.

```sh
docker compose -f compose.dev.yaml -f compose.dev.override.yaml up -d --build
docker compose -f compose.dev.yaml -f compose.dev.override.yaml ps
docker compose -f compose.dev.yaml -f compose.dev.override.yaml logs bot
docker compose -f compose.dev.yaml -f compose.dev.override.yaml exec -T bot python -m elevenbot health --component bot
docker compose -f compose.dev.yaml -f compose.dev.override.yaml exec -T bot python -m pytest -p no:cacheprovider -q -s tests/test_image_recovery.py
```

У первого запуска на новом томе ожидаются `migrations applied` и `telegram_stub_smoke=ok` в логах. Dev override монтирует `src/`, `scripts/` и `tests/` из рабочей копии в режиме чтения. После изменения Python-кода для бота перезапустите только `bot`. При изменении зависимостей соберите образ заново. Для остановки используйте `stop`, чтобы сохранить контейнеры и данные.

```sh
docker compose -f compose.dev.yaml -f compose.dev.override.yaml restart bot
docker compose -f compose.dev.yaml -f compose.dev.override.yaml stop
```

## Конфигурация стенда

Локальная копия оригинальной конфигурации находится в игнорируемом каталоге `.local/archive/`. При переносе в новый клон возьмите значения из своего тестового окружения, начиная с `.env.example`. Проверьте, что конфигурация указывает на тестовую БД и тестовый бот, `PAYMENTS_ENABLED=false`, а относительные пути каталога и хранилища считаются от расположения файла, переданного в `--env-file`. Для безрасходного прогона используйте `CLODEX_INTERACTION_MODE=mock`. Живой вызов CLODEX проверяется отдельно на согласованных условиях расхода. Реальные ID пользователей остаются в локальной конфигурации и базе.

- Хранить реальные значения конфигурации вне Git. Разделять тестовые и production-среды. Использовать только обезличенные логи, correlation IDs, health и readiness probes.
- Проверить контролируемое завершение, восстановление worker после падения, резервное копирование и восстановление БД и медиа. В runbook указать диагностику по job ID и действия при недоступности провайдера, БД или диска.
- Модель угроз охватывает Telegram, HTTP API, Mini App, платежи, вебхуки, PostgreSQL, credentials, админку, медиа и деплой. Проверки включают SSRF и redirects, path traversal, SQL injection, IDOR, подделку вебхуков, гонки, вложения, исчерпание ресурсов, повторы и повышение привилегий.
- Для релиза зафиксировать SHA, шаги миграции, проверку восстановления и результаты матрицы. Эксплуатационные изменения выполнять по [правилам команды](../../CONTRIBUTING.md).
