# Архитектура

Один репозиторий, Python, aiogram, PostgreSQL, HTTP-клиент. Два процесса: bot и worker. Без обязательного Redis, публичного Backend API и микросервисов. Telegram long polling: один активный polling-процесс на токен. При будущем webhook применять официальный secret token и HTTPS.

## Направление зависимостей
transport Telegram/MAX → application services → domain/repositories/provider interface.
Worker → application services → provider adapter → Clodex.
Ядро не импортирует aiogram и не принимает Telegram callback объекты.

## Предлагаемое дерево
src/domain/ — деньги, статусы, ошибки, правила доступа.
src/application/ — quote, confirm, list_jobs, deliver, credit_payment, refund.
src/adapters/telegram/ — handlers, keyboards, payment events, polling.
src/adapters/max/ — отдельное будущее подключение.
src/providers/ — interface, clodex, direct_elevenlabs (не включён по умолчанию).
src/db/ — repositories, migrations, transactions.
src/worker/ — lease, dispatch, reconcile, delivery, cleanup.
src/storage/ — приватные файлы.
src/admin/ — команды по allowlist, без веб-панели.
tests/ — приёмочные и интеграционные проверки.

## Основные прикладные операции
quote(user_id, text, voice, settings) → quote_id, price, expires_at.
confirm(user_id, quote_id) → job_id; идемпотентно по quote_id.
list_jobs(user_id, cursor); get_result(user_id, job_id).
apply_payment(verified_event) → receipt; идемпотентно по provider charge ID.
Все входы транспорта нормализуются; ядро само проверяет владельца и ограничения.

## Операционная простота
Очередь — таблица jobs; worker выбирает готовую запись с FOR UPDATE SKIP LOCKED. Сетевой вызов выполняется после коммита короткой транзакции. Отдельные длительные транзакции вокруг HTTP запрещены. Для первого релиза достаточно одного worker с ограниченным concurrency.
