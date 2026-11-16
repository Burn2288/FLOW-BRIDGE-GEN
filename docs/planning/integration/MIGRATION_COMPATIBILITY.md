# MIGRATION COMPATIBILITY

На candidate `d691d54e0266c3d519d66575555fa45895ef40ac` найдено 39 SQL migration paths, [blob и SHA256](migration-blobs.json). Сверка порядка, immutable checksums, DDL и tested upgrade обязательны на независимой PostgreSQL до каждого интеграционного merge; source mapping не является доказательством применимости к реальной БД. Исторический стенд 5601faa имел по документации миграции 001–036; #17 добавляет 037–039, но реальное состояние стенда сейчас NOT_PROVEN.

Сначала сравнить предыдущий и новый `schema_migrations`, номера и hashes, запретить изменение ранее применённых файлов. При конфликте номер резервирует один writer, согласует новую миграцию с владельцем, сохраняет обе версии и проверяет upgrade/restore на копии. Никаких destructive downgrade, production миграций или automatic conflict resolution. Проверить backup+restore пользователей, wallet/ledger и media bytes; rehearsal и реальные проверки NOT_TESTED.

Механическая source-проверка: 39 номеров, все уникальны и идут подряд 001–039. Из этого не следует совместимость DDL или фактически применённой базы.
