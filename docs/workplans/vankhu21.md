# vankhu21. Telegram, сквозная проверка и интеграция

Общая последовательность — [S0–S7](../ROADMAP.md). До импорта S0 имеет статус `BLOCKED`.

| Срез | Рабочая задача | Передача результата |
| --- | --- | --- |
| S0 | После получения SHA исходников проследить Telegram update → обработчик → job и обратный путь результата в Telegram и библиотеку. | Согласовать точки соединения с Burn2288 и дополнить [карту аудита](../audit/AS_IS_ARCHITECTURE.md). |
| S0 | Подготовить безопасное воспроизведение по correlation ID. Проверить дубликаты update, параметры модели и выбор `sendPhoto` или `sendDocument`. | Передать этап отказа, SHA и обезличенные сведения, нужные для диагностики провайдера. |
| S1 | Подтвердить получение изображения и доступ после перезапуска. Собрать три живых успеха и один временный отказ, если доступна разрешённая среда. | Записать результаты в [реестр](../acceptance/EVIDENCE.md). В отсутствие живого доступа зафиксировать `BLOCKED_LIVE`. |
| S2 | Собрать нагрузочные сценарии 10/50/100 запросов с контрактным эмулятором, проверкой восстановления и метриками из [матрицы](../acceptance/TEST_MATRIX.md). | Сверить с Burn2288 поведение при потере ответа и падении worker. |
| S4/S5 | Вести минимальные срезы Mini App, API, админки и отчётности по [объёму продукта](../product/PRODUCT_SCOPE.md). | Согласовать контракты, права доступа и ревью с Burn2288. |

Первый шаг — получить от Burn2288 ссылку и SHA исходного снимка, затем подготовить сценарий воспроизведения. После принятия среза обновить общую локальную копию по [инструкции](../../CONTRIBUTING.md).

## Интеграция изображений · S1

- [PR №8](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/8) в `main`, коммит `eaadb892227e6b731e4cebccb071b23c1b209b3b`. Включает PR №7 и проверенные правки smoke-стенда.
- [GitHub Actions на коммите PR](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42309353362). Локально прошли 238 тестов с отдельной PostgreSQL и заглушками Telegram/CLODEX.
- Для принятия нужны ревью Burn2288 и успешные проверки актуального коммита. `gpt-image-2` ожидает повторной проверки генерации в тестовой ветке.

## Veo 3.1 · S1–S2

- [PR №9](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/9), коммит `b5c1368cf9663bd0be43a1e9c0b65816c51fe61d`. Владелец задачи vankhu21. База — ветка PR №8 до его слияния.
- На изолированной PostgreSQL прошли 243 теста. Оба варианта Veo, повторное подтверждение, восстановление по ID и выдача проверены заглушками. Платных запусков нет. [GitHub Actions](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42311728186).
- Перед живой приёмкой подтвердить успешные форматы ответов создания, статуса и скачивания CLODEX. Пилот выключен по умолчанию.

## AnyModel · S3

- [PR №10](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/10) поверх PR №9. SHA стенда `0e9d538aaa7c5674273adbfb4ba283bee2c8fee5`, SHA PR `eaa1a6fdc6eb19ed61a231ad05c9eb412c0d2496`. Владелец задачи vankhu21.
- Прошли 247 тестов с отдельной PostgreSQL. Публичный снимок AnyModel содержит 65 моделей. Приёмка каталога по ключу и меню в Telegram Desktop ожидает тестового ключа и доступа к клиенту.
- Платный чат выключен. Контракт тестовой модели `ds/deepseek-v4-flash-vision` проверен на заглушке.

## FIBO 2 через AnyModel · S3

- [PR №11](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/11) поверх PR №10, SHA `a9768dcf60eb0bb8bc04fe97ea7b3eac56196d7e`. На стенде проверены меню и авторизованный каталог из 109 моделей. Точный ID пилота — `anymedia/fibo-2`.
- Прошли 252 теста с отдельной PostgreSQL. Выдача и повторное открытие PNG проверены на заглушке. Живая выдача и формат успешного ответа ожидают отдельной приёмки. Платный запуск выключен.

- Обновление [PR №11](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/11) на `99c091476de23d998a3101bb0e39d199552f8838`. FIBO 2 использует фоновый POST, сохраняет ID и продолжает GET по `Retry-After` после перезапуска. Прошли 254 теста с отдельной PostgreSQL. Живая генерация ждёт отдельной приёмки.

## AnyModel · Grok Imagine Video 1.5

- [PR №12](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/12) поверх PR №11, SHA `de4e5f1183ec9ee7b079977fda68f99e02d00dd7`. Владелец vankhu21. Закрытый пилот текста в видео, 4 с, 480p, 16:9, оценка 3 200 000 токенов баланса.
- 258 тестов на отдельной PostgreSQL. Подтверждены один POST, продолжение опроса после перезапуска, выдача и библиотека на заглушках. Платный запуск выключен.

## AnyModel · озвучка текста · S3

- [PR №13](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/13) поверх PR №12, SHA `6c82761c5e4c42e1129934884c5b23030df4e090`. Владелец vankhu21. Fish Audio и русские пресеты AnyVoice, оценка по UTF-16, однократный POST и повторная выдача MP3.
- На отдельной PostgreSQL прошли 266 тестов. [CI приложения](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42407956970) и [CI документации](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42407956974). На стенде применена миграция 016, живая озвучка выключена.
- Fish Audio доступна по ключу по ставке 50 токенов баланса за единицу UTF-16. Для 54 русских голосов AnyVoice тариф не подтверждён, запуск закрыт. PR ожидает ревью.

## Приветствие DarkFlow | Gen · S1

- [PR №14](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/14) поверх PR №13, SHA стенда `08c2ac88cb4a8c2981625a135ca83f495f0cf5d6`. Владелец vankhu21.
- PNG и приветствие в Telegram после согласия или повторного `/start`, рабочее меню при недоступном баннере. 269 тестов на отдельной PostgreSQL. [CI приложения](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42415168316) и [CI документации](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42415168177). PR ожидает ревью.
- Исправление хранения приветствия в [PR №14](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/14), SHA `cf694df73c1e6ac08e28a30b7c7400cbd6c4c405`. Миграция 017 применена на стенде, ID сохранился после перезапуска. 270 тестов, [CI приложения](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42416136806) и [CI документации](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42416136903) зелёные. Полный живой проход по кнопкам ожидает подтверждения.
- Анимация экрана «Агрегаторы» в [PR №14](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/14), SHA `2169c46c80294bd2dbf702d5fb40ec7879155ca7`. На стенде Telegram принял GIF с подписью и кнопками. 272 теста прошли на отдельной PostgreSQL. [CI приложения](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42417172795) и [CI документации](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42417172713). Запись живого прохода ожидается.
- Клавиатура и каталоги агрегаторов в [PR №14](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/14), SHA `a0e30c57a26e495f1a5193e579c56eaabf4df909`. На стенде Bot API принял нижнюю клавиатуру без общей кнопки каталога и открыл отдельные каталоги CLODEX и AnyModel. 272 теста прошли локально. [CI приложения](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42418488353) и [CI документации](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42418488358).
- Первый экран CLODEX в [PR №14](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/14), SHA `92bca79a288db167146f59fea946a257d602a1a2`. На стенде проверены прямые переходы в видео и изображения и те же списки через прежний каталог. 272 теста прошли локально. [CI приложения](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42419611278) и [CI документации](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42419611295).
- Убран повторный вход в каталог с первого экрана CLODEX в [PR №14](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/14), SHA `742db84eb8663d5a4b7a7e50b2c10825e7b18a87`. В Telegram проверены прямые разделы видео, изображений и озвучки, «🧩 Модели» и каталог AnyModel. [CI приложения](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42420216580) и [CI документации](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42420216674).

## Статус выполнения в Telegram · S2–S3

- [PR №15](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/15) поверх PR №14, SHA `5162e8e58ba91564c7989617567e24a18aa5f3da`. Владелец vankhu21. Отдельный индикатор для видео, изображений, озвучки и чата. Привязка фонового статуса хранится в PostgreSQL.
- 277 тестов на изолированной PostgreSQL. [CI приложения](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42488799411) и [CI документации](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42488799397) зелёные. PR ожидает ревью и запись живой приёмки Grok.

## Оценка и наценки AnyModel · S3/S5

- [PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16) поверх PR №15, SHA `7c3337ad37582bc71412030b643f4c37a53d75db`. Владелец vankhu21. Единая карточка оценки и подтверждения, приоритет наценок по модели и отчёт по подтверждённым суммам.
- 280 тестов на отдельной PostgreSQL. [CI приложения](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42491119773) и [CI документации](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42491119788) зелёные.
- На стенде сверены Grok, FIBO 2 и Fish Audio, отмена, истечение, изменение тарифа и отчёт на тестовых данных. Платных запусков и списаний нет. PR ожидает ревью и принятия зависимого PR №15.

## Admin Edition · S3/S5

- В [PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16) добавлены ручные тарифы с истечением, подтверждение CLODEX и сохранение ответов чата в «Моих работах». SHA `d8d36350a7e09e21878f29bb4b6416c1a6a036c8`.
- 282 теста на изолированной PostgreSQL. Проверки обновлённого SHA: [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42493271708) · [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42493271162).
- На `flowbridge-live-smoke` один бот, миграция 020 применена. Подтверждены расчёты AnyModel и Veo Fast, блокировка отсутствующего или истёкшего тарифа. Платных запусков нет. PR ожидает ревью.
