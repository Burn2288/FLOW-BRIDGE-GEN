# DarkFlow Gen — взаимодействие с моделями

В режиме `mock` бот использует подставной ответ. Диалог хранит последние три
пары реплик в БД. Длинные ответы отправляются как `answer.txt`. Для промпта
можно отправить текст или UTF-8-файл `.txt` до 24 КБ. Команда `/menu` завершает сессию.

## Возможности адаптеров в FUNCTIONAL_TEST

Общий DEV-стенд запускает четыре маршрута CLODEX из Telegram и Mini App. Внешний HTTP провайдера заменён локальной заглушкой. AnyModel и Fal проверяются отдельными профильными наборами.

| Адаптер | Модель или операция | Доказательство | Live на текущем кандидате |
| --- | --- | --- | --- |
| CLODEX | FLUX Schnell (`flux-schnell`), изображение | [Матрица восьми маршрутов DEV](verification/studio_matrix.py), [HTTP image и изоляция владельца](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/45893600376) | Не проверен |
| CLODEX | Veo 3.1 (`clodex-video/veo-3.1`), видео | [Матрица DEV](verification/studio_matrix.py), [CLODEX video: quote, восстановление и библиотека](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/45893600189) | Не проверен |
| CLODEX | ElevenLabs v4 (`eleven_v4`), озвучка | [Матрица DEV](verification/studio_matrix.py), [общие голосовые capabilities и тарифные единицы](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/45893600146) | Не проверен |
| CLODEX | Music v1 (`clodex-video/music-v1`), один трек по тестовому гранту | [Матрица DEV](verification/studio_matrix.py), [обработка и история пилота](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/45893600236) | Не проверен |
| AnyModel | Каталог и маршрутизация чата, асинхронный FIBO, Grok Imagine Video 1.5, Fish Audio S2.1 и AnyVoice | [Маршрутизация чата и каталог](tests/test_anymodel.py), [FIBO и восстановление](tests/test_anymodel_fibo.py), [Grok и перезапуск](tests/test_anymodel_video.py), [Mock-озвучка и оплата](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/45893600146) | Не проверен |
| Fal | Lyria 3.5 (`google/lyria-3.5`), закрытый музыкальный пилот | [Метаданные маршрута и совместимость адаптеров](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/45893600322), [Mock-исполнение и история](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/45893600236) | Не проверен |

Для live-приёмки PR-03 (D-06) требуется отдельное разрешение и подтверждение конкретной модели, параметров, цены и сохранённого результата.

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
