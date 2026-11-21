# DarkFlow | Gen Telegram Mini App

Основная папка Telegram Mini App — `miniapp/` в корне репозитория.

- `frontend/` — HTML, JavaScript, CSS и фирменная графика, вкладки «Каталог», «Мои работы», «Баланс», «Настройки» и «Приглашения».
- `backend/` — HTTP API, проверка Telegram initData, сессия и серверные настройки темы.
- `tests/` — проверки HTTP, входа и изоляции аккаунтов. Общие сервисы и интеграция меню Telegram находятся в `src/elevenbot/`, миграции — в `migrations/`.

## Быстрый локальный запуск с тестовыми данными

Из корня репозитория выполните проверку с отдельной PostgreSQL. Тест сам создаёт два аккаунта, тестовый баланс и PNG, подписывает синтетические Telegram initData и проверяет их через HTTP. Токен Telegram и доступ к рабочему стенду для этого сценария не нужны.

```powershell
docker compose -f compose.test.yaml -p flowbridge-miniapp-test run --rm --build tests python -m pytest -q miniapp/tests
docker compose -f compose.test.yaml -p flowbridge-miniapp-test down
```

Для просмотра страницы в браузере используйте отдельную рабочую копию, скопируйте `.env.example` в `.env`, задайте разные локальные пароли PostgreSQL и тестовый токен. Оставьте оплату и живую генерацию выключенными.

```powershell
docker compose -f compose.yaml -f compose.miniapp.yaml -p flowbridge-miniapp-local up -d --build miniapp
curl.exe -f http://127.0.0.1:8091/
curl.exe -f http://127.0.0.1:8091/assets/app.js
curl.exe -f http://127.0.0.1:8091/assets/style.css
curl.exe -f -o NUL http://127.0.0.1:8091/assets/darkflow-banner.png
```

Этот профиль использует порт 8091. Если его уже занимает стенд, выберите другой локальный порт через отдельный override. В браузере без initData доступна оболочка. Авторизованный сценарий с синтетическими аккаунтами выполняется первой командой.

## HTTPS-стенд и Telegram

1. Подключите доверенный HTTPS reverse proxy к `127.0.0.1:8091` отдельного стенда. Проверьте страницу и статические ресурсы по HTTPS.
2. Установите `MINIAPP_URL=https://<закрытый-домен>/` в локальном `.env`. Бот и Mini App используют один тестовый токен, один Compose-проект и одну PostgreSQL.
3. Запустите `docker compose -f compose.yaml -f compose.miniapp.yaml -p flowbridge-miniapp-local up -d --build bot miniapp`. Бот оставляет синюю кнопку «Меню» в режиме команд. После /start в первой строке нижней клавиатуры появится «Приложение». При пустом MINIAPP_URL эта строка скрыта.
4. Под двумя отдельными тестовыми аккаунтами примите условия в боте и откройте «Приложение» в Telegram Android и Desktop. Стартовая вкладка — «Каталог». Telegram не передаёт подписанный initData при открытии из нижней клавиатуры. Для входа закройте окно, отправьте /miniapp и нажмите inline-кнопку «Открыть каталог». Проверьте четыре вкладки, обе темы и сохранение после второго входа на другом устройстве. Сверьте баланс и работы с чатом и проверьте ручные команды /start и /menu.
5. Подготовьте одну работу для первого аккаунта. Скачайте её из Mini App владельца и проверьте через HTTP, что запрос того же ID со второй сессией получает 404.

Тема по умолчанию тёмная. Сервер хранит выбор в профиле, а подлинность запроса проверяет по краткоживущей сессии.

Вкладка «Приглашения» показывает персональный код и фиксированный при регистрации статус приглашения. Начисления наград или средств рефералам не предусмотрены.


## Обновление стенда по тому же HTTPS-адресу

Выполняйте из каталога стенда после перехода на проверенный SHA. Сохраните существующий `.env`, проект `flowbridge-live-smoke`, тома, установленный `MINIAPP_URL` и проксирование на `127.0.0.1:8091`. Правила DNS и сертификат остаются у того же HTTPS-прокси.

```powershell
$dc = @('-p','flowbridge-live-smoke','-f','compose.yaml','-f','compose.miniapp.yaml')
docker compose @dc ps -a
docker compose @dc build bot miniapp migrate
docker compose @dc stop bot miniapp
docker compose @dc exec -T db pg_dump -U elevenbot -d elevenbot -Fc -f /tmp/before-miniapp.dump
docker compose @dc exec -T db pg_restore --list /tmp/before-miniapp.dump
$db = docker compose @dc ps -q db
docker cp "${db}:/tmp/before-miniapp.dump" "<локальный-закрытый-каталог>/before-miniapp.dump"
docker compose @dc up --no-deps --no-build --force-recreate --exit-code-from migrate migrate
docker compose @dc up -d --no-deps --no-build --force-recreate --wait bot miniapp
docker compose @dc ps -a
docker compose @dc exec -T db psql -U elevenbot -d elevenbot -Atc "SELECT max(version) FROM schema_migrations; SELECT halted FROM settings WHERE id=1;"
```

Останавливайтесь при ошибке любой команды. После обновления проверьте страницу, CSS, JS и PNG по прежнему HTTPS-адресу. На телефоне отключите Wi‑Fi, откройте чат тестового бота и нажмите «Приложение». Затем вручную отправьте /start, /menu и /miniapp. Повторите в Telegram Desktop. Сохраните SHA запущенных контейнеров и результаты по обоим аккаунтам. Для проверки чужой работы используйте только заранее подготовленную тестовую запись.
