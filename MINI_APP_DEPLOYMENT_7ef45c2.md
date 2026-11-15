# DarkFlow | Gen Mini App — flowbridge-live-smoke

[PR №17](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/17). Развёрнут актуальный SHA `7ef45c2dc8fb6cc79ceedd46e270297b4bb78c3a`. До обновления бот был на `5601faa`. Образ bot, miniapp и migrate — `sha256:0634723bf8dbf12bd912a1d863d297d3446eafb9ba76f395658fb02ae5766db4`.

- Перед миграциями создан PostgreSQL custom dump, оглавление проверено через pg_restore --list. Резервная копия хранится локально вне Git. Миграции 037 и 038 подтверждены в schema_migrations.
- Сервисы используют `compose.yaml` и `compose.miniapp.yaml` в существующем проекте. Бот и Mini App используют одну БД и тестовый токен. Тома audio и catalogue сохранены. Бот и PostgreSQL healthy. `halted=true`, `GENERATION_ENABLED=false`, `PAYMENTS_ENABLED=false`, `TOPUP_MODE=off`.
- Локальный HTTP `127.0.0.1:8091`. Страница, JS, CSS и PNG вернули 200. Корень выдачи — `/app/miniapp/frontend`. API каталога, кошелька, работ и настроек без сессии вернул 401.
- Bot API подтвердил команды start, menu, cancel. Штатные сценарии команд, настройки темы и права доступа — 34 теста на отдельной PostgreSQL. Четыре вкладки, обе темы и восстановление проверены локально в предыдущей браузерной приёмке на этом SHA.
- Доверенный HTTPS и `MINIAPP_URL` отсутствуют. Bot API возвращает тип меню `commands`. Ссылка запуска Mini App, кнопка «Приложение», клиентская проверка Android и Desktop и ручной ввод команд пока не приняты. Для завершения нужен HTTPS reverse proxy к `127.0.0.1:8091`, URL в локальном окружении и пересоздание бота. Затем нужно открыть «Каталог» из чата и проверить команды и тему в Telegram. [Инструкция](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/7ef45c2dc8fb6cc79ceedd46e270297b4bb78c3a/miniapp/README.md).
