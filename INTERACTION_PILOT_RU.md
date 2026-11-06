# DarkFlow Gen — взаимодействие с моделями

В режиме `mock` бот использует подставной ответ. Диалог хранит последние три
пары реплик в БД. Длинные ответы отправляются как `answer.txt`. Для промпта
можно отправить текст или UTF-8-файл `.txt` до 24 КБ. Команда `/menu` завершает сессию.

## Пилот генерации изображений

Добавьте эти записи в локальный `.env` отдельного стенда. Сохраните настройки
других используемых моделей и выберите положительный лимит для стенда.

```dotenv
ACCESS_MODE=private
CATALOGUE_ENABLED=true
PAYMENTS_ENABLED=false
CLODEX_INTERACTION_MODE=live
CLODEX_INTERACTION_LIMIT=2
PUBLIC_CATALOGUE_MODELS=image:flux-schnell,image:gpt-image-2.5-sunburst
CLODEX_INTERACTION_PAIRS=images.generate:flux-schnell,images.generate:gpt-image-2.5-sunburst
```

Проверьте точные ID через авторизованный `GET /v1/models` и протокол
`image-generation` через свежий `/api/pricing`. У Sunburst кнопка
«Качество: high» отправляет `quality=high`. FLUX Schnell использует параметры
провайдера по умолчанию. Счётчик попыток хранится в PostgreSQL и действует
после перезапуска. Фактическую стоимость определяет CLODEX.

```sh
docker compose -p flowbridge-live-smoke -f compose.yaml exec -T bot python -m elevenbot catalog-refresh
docker compose -p flowbridge-live-smoke -f compose.yaml up -d --build --no-deps --force-recreate bot
```

Откройте «Открыть каталог → Генерировать изображение» и проверьте карточки
и экран промпта. Для проверки без платного запроса используйте режим `mock`
или изолированный набор тестов `compose.test.yaml`. Держите токены, ключи,
данные пользователей и подписанные URL локально.

## Доставка и восстановление

Бот проверяет целостность и размеры PNG/JPEG из `b64_json` или защищённой
HTTPS-загрузки. После проверки исходные байты сохраняются в PostgreSQL
перед отправкой в Telegram. При сбое отправки откройте ту же картинку через
«Мои работы». Повторное открытие использует сохранённый файл, а дубликат
Telegram-обновления не запускает новый запрос. Изображение и промпт
доступны семь дней.

В журнале этапы связаны идентификатором запроса. Событие `image_download_failed`
содержит короткий код причины отказа. Подписанные URL и ключи в журнал
не попадают.

Nano Banana 2 снята с витрины. Старые кнопки запуска заблокированы, а
сохранённые работы доступны в «Моих работах» до истечения срока хранения.
