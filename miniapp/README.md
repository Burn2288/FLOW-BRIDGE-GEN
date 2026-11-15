# DarkFlow | Gen Telegram Mini App

Основная папка Telegram Mini App — `miniapp/` в корне репозитория.

- `frontend/` — HTML, JavaScript, CSS и фирменная графика, вкладки «Каталог», «Мои работы», «Баланс» и «Настройки».
- `backend/` — HTTP API, проверка Telegram initData, сессия и серверные настройки темы.
- `tests/` — проверки HTTP, входа и изоляции аккаунтов. Общие сервисы и интеграция меню Telegram находятся в `src/elevenbot/`, миграции — в `migrations/`.

## Локальный запуск

В отдельной рабочей копии скопируйте `.env.example` в `.env`. Задайте разные локальные пароли PostgreSQL, токен отдельного тестового бота и его администраторов. Оставьте оплату и живые генерации выключенными. У сервиса Mini App порт 8091 опубликован на loopback.

```powershell
docker compose -f compose.yaml -f compose.miniapp.yaml -p flowbridge-miniapp-local up -d --build miniapp
curl.exe -f http://127.0.0.1:8091/
curl.exe -f http://127.0.0.1:8091/assets/app.js
curl.exe -f http://127.0.0.1:8091/assets/style.css
curl.exe -f -o NUL http://127.0.0.1:8091/assets/darkflow-banner.png
docker compose -f compose.test.yaml -p flowbridge-miniapp-test run --rm --build tests python -m pytest -q miniapp/tests
```

Через обычный браузер без initData доступна оболочка. Сервисы кошелька, каталога и работ требуют сессию Telegram.

## HTTPS-стенд и Telegram

1. Подключите доверенный HTTPS reverse proxy к `127.0.0.1:8091` отдельного стенда. Проверьте страницу и статические ресурсы по HTTPS.
2. Установите `MINIAPP_URL=https://<закрытый-домен>/` в локальном `.env`. Бот и Mini App используют один тестовый токен, один Compose-проект и одну PostgreSQL.
3. Запустите `docker compose -f compose.yaml -f compose.miniapp.yaml -p flowbridge-miniapp-local up -d --build bot miniapp`. Бот регистрирует общую кнопку «Приложение» через MenuButtonWebApp при получении блокировки polling. Для сброса ранее зарегистрированной кнопки можно выбрать стандартное меню через BotFather.
4. Под двумя отдельными тестовыми аккаунтами примите условия в боте и откройте «Приложение» в Telegram Android и Desktop. Стартовая вкладка — «Каталог». Проверьте четыре вкладки, обе темы и сохранение после второго входа на другом устройстве. Сверьте баланс и работы с чатом и проверьте ручные команды /start и /menu.
5. Подготовьте одну работу для первого аккаунта. Скачайте её из Mini App владельца и проверьте через HTTP, что запрос того же ID со второй сессией получает 404.

Тема по умолчанию тёмная. Сервер хранит выбор в профиле, а подлинность запроса проверяет по краткоживущей сессии.
