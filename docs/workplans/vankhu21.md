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

## AnyVoice и новые модели · S3/S5

- [PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16), SHA `743ab5c13d8781bedc958bd3723cbe9cfa2e5b04`. Выбор и массовая настройка голосов AnyVoice, новые единицы ручного тарифа, динамический каталог видео и озвучки.
- На стенде подтверждены 54 русских и 10 английских голосов на обоих экранах. Заглушки подтвердили появление нового пресета и по одному запуску нового ID для изображения, видео и озвучки. Миграция 021 применена. Платных запусков нет, подтверждённых ручных ставок в БД нет.
- 290 тестов на отдельной PostgreSQL. Проверки этого SHA: [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42494548897) · [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42494548780). PR ожидает ревью.

## Каталог и срок тарифа · S3/S5

- [PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16), SHA `a2525859d7a1d79e20c3c268389bfbc3ae8ed4a5`. Админ-каталог, бессрочная подтверждённая ставка, обязательный срок тестовой ставки, приоритет API при повторном подтверждении.
- На стенде миграция 022 и 64 голоса AnyVoice, подтверждены свежие цены FIBO 2, Fish Audio, Grok и Veo Fast. Ручные ставки проверены на заглушках. Платных запусков и списаний нет.
- 293 теста на отдельной PostgreSQL. [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42495605709) · [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42495605643). PR ожидает ревью.

## Расширяемость и отказоустойчивость · S2/S3/S5

- [PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16), SHA `0c7152e9127e228a126a3e81448f553f45c17b3d`. Третий адаптер на заглушке проходит каталог, цену и исполнение через реестр. Индивидуальные и массовые ставки сохраняются после предпросмотра.
- Изолированная PostgreSQL, 297 локальных тестов. Первая волна 32 задач и 20 повторов дала 32 GET цены при подтверждении и 29 POST, один повторный расчёт и два отказа цены. После трёх явных подтверждений всего 67 GET с исходными оценками и 32 POST.
- Два перезапуска до POST сохранили согласованную цену и дали терминальный статус. Платных вызовов нет. [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42497319024) · [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42497319021). PR ожидает ревью.

## Допуски и наценки Admin Edition · S3/S5

- [PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16), SHA `3fb74636bc11691afed54e4a97185438125b80a7`. Разделены API-каталог и рабочие допуски. «Наши модели» показывает цены и режимы наценки из общего источника.
- На стенде сверены 4 допуска AnyModel и 5 CLODEX, переключение режимов, совпадение цены FIBO 2 и перезапуск. Миграция 024, 298 тестов. Снимки клиента ожидают доступа. Платных запусков нет.
- [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42508887923) · [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42508887919). PR ожидает ревью.

### Допуск видео CLODEX в обоих разделах

- [PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16), SHA `bb81345bcda71f73d1b3092f302bdfc00769696f`. Видеодопуск проверяет подключённый маршрут. Карточка Veo 3.1 сохраняет оба режима.
- Заглушка и отдельная PostgreSQL: проверены допуск и отзыв ID вне Veo, один запуск по подтверждению, повторная выдача сохранённого MP4 и отказ без записи при отсутствии маршрута. 299 тестов, платных запусков нет. [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42510043576) · [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42510043547). PR ожидает ревью.

- Стенд `flowbridge-live-smoke` обновлён на `bb81345bcda71f73d1b3092f302bdfc00769696f`. Штатные Telegram-обработчики с тестовым транспортом показали одну карточку Veo с двумя доступными режимами. Оба ID совпали с «Нашими моделями», где показаны оценки с общей наценкой 0%. `halted=true`, генераций 0. [Приёмка и команды в PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6725454506).

### Исходные единицы и курс Admin Edition

- [Приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6725969327), SHA `4669f3fe35fa7f5ad26be00872263d2e86d75b7b`, стенд `flowbridge-live-smoke`, миграция 025. Исходные суммы, курсы и итоговые цены показаны отдельно. Курсы AnyModel и CLODEX USD перенесены. Ручная себестоимость в токенах бота, рублёвый эквивалент и повторное подтверждение проверены на заглушках.
- Локально 302 теста, [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42514398735) и [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42514398564) зелёные. `halted=true`, генераций и списаний 0. PR ожидает ревью.

### Меню агрегаторов Admin Edition

- [Приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6726531861), SHA `e147db36a4fefb531e30016407bb4616dfa315d0` на `flowbridge-live-smoke`. Общий порядок рабочих разделов и отдельный экран управления. На стенде проверены CLODEX и AnyModel, обратная навигация и отказы гостю. Третий провайдер из реестра покрыт заглушкой.
- Локально 303 теста, [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42518727407) и [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42518727392) зелёные. `halted=true`, генераций 0. PR ожидает ревью.

### Баланс на нижней клавиатуре Admin Edition

- [Приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6726815222), SHA `e3cc8ee639103b72d2a84f885449a84286d21c22`. Третья кнопка показывает актуальный остаток и, если задан курс, рублёвый эквивалент. Старые числовые подписи и «Баланс» открывают действующий экран.
- На отдельной PostgreSQL с тестовым транспортом проверены порядок кнопок, нулевой и ненулевой остаток, отсутствие курса, обновление после начисления и перезапуска. Локально 304 теста. [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42521048883) · [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42521048898). PR ожидает ревью.

- На `flowbridge-live-smoke` развёрнут `e3cc8ee639103b72d2a84f885449a84286d21c22`. Через штатный обработчик и тестовый транспорт подтверждены третья широкая кнопка, курс стенда и открытие актуального баланса по старой подписи. Контейнеры здоровы, `halted=true`, генераций 0. [Вывод клавиатуры и SHA в PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6726890969).

### Возврат из карточек и порядок клавиатуры

- [Приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6727060177), SHA `eff7bdce9a03246be244d10040c17f97d221213d` на `flowbridge-live-smoke`. FIBO 2 и Veo 3.1 возвращаются в исходные списки одной кнопкой, действия сохранены. Настройка стоимости токенов стоит перед «Помощью» при старте и автообновлении баланса.
- Локально 304 теста, [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42522795792) и [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42522795763) зелёные. `halted=true`, генераций 0. PR ожидает ревью.

### Подсказки команд Telegram Admin Edition

- [Приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6727218079), SHA `dd94f9dcfa83eabb78eb01b7a43899542ef6984a` на `flowbridge-live-smoke`. На старте зарегистрированы три общие команды и отдельный `/price_report` в двух чатах администраторов. `getMyCommands` подтвердил списки, тест проверил отказ гостю. `halted=true`.
- Локально 306 тестов. [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42524100636) · [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42524100705). PR ожидает ревью.

### Команда /menu открывает выбор агрегатора

- [Приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6727313874), SHA `c3bc7b8a2eada6bddb1697b0c29ea4123f88f3e1` на `flowbridge-live-smoke`. Кнопка «Агрегаторы», `/menu` и `/menu@имя_бота` из карточки FIBO 2 открыли одинаковый экран с GIF. Приветствие сохранено, в подсказках «Главное меню». `halted=true`, генераций 0.
- Локально 306 тестов. [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42524859479) · [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42524859473). PR ожидает ревью.

### Пароль и сессии Admin Edition

- [Приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6727500236), SHA `0b1ac9a8b1d2e9f22d511eced71ac2210ed199db` на `flowbridge-live-smoke`. Вход по разрешённому Telegram ID и паролю, 8-часовые сессии, выход, защита старых кнопок, ограничение попыток. Секрет перехватывается до записи в inbox.
- 309 локальных тестов. На стенде `ADMIN_PASSWORD` передан пустым и админ-доступ закрыт, `halted=true`. [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42526244516) · [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42526244474). PR ожидает ревью.

### Пользовательский режим и Admin Edition

- [Приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6727786126), SHA `77385db69f9b14c57998a01e47284b4b75657de0` на `flowbridge-live-smoke`. Один бот. По умолчанию «Агрегатор 1» и «Агрегатор 2», управление и детализация цен открываются по активной админ-сессии. Проверены неверный пароль, вход, выход, отказ старой кнопке и обычному аккаунту. Настройки БД сохранились.
- 310 тестов на изолированной PostgreSQL. [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42528338359) · [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42528338319). Стенд `halted=true`, живых генераций 0. PR ожидает ревью.

### Рабочие вкладки пользовательского каталога

- [Приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6727904221), SHA `a84526303e7613d953f814ad2af7eeea813a7bfb` на `flowbridge-live-smoke`. В обоих агрегаторах порядок видео → изображение → озвучка → чат → «Мои работы». Проверены рабочие списки и возврат из пустых разделов без админ-сессии. Допуски и настройки пилотов сохранены, `halted=true`.
- 310 тестов на отдельной PostgreSQL. [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42529344578) · [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42529344568). PR ожидает ревью.

### Резерв кошелька перед запуском

- [PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16), SHA `e2a2a0754af91a6b474f5ce15e57321e651781d8`. Владелец оценки, итоговая цена и доступный остаток проверяются на сервере. Резерв и принятие задачи фиксируются одной транзакцией перед POST. Подтверждённое пополнение учитывается один раз.
- 311 тестов на отдельной PostgreSQL, включая нулевой и поддельный баланс, чужую оценку, повтор, два одновременных подтверждения и восстановление после перезапуска. Для отклонённых задач POST не было. [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42531054936) · [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42531055074). Миграция 026 проверена локально и в CI. Стенд остался на прежней сборке, PR ожидает ревью.

### Выпуск резерва кошелька на тестовый стенд

- [Приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6728256601). До обновления сохранена локальная копия PostgreSQL. На `flowbridge-live-smoke` запущен `e2a2a0754af91a6b474f5ce15e57321e651781d8`, миграция `026_task_wallet.sql` применена, бот и БД healthy, `halted=true`.
- Публичный вход и просмотр проверены. Генерация обычного аккаунта закрыта пилотом. На заглушках выявлено удержание резерва при подтверждённом HTTP 400 чата, озвучки и создания видео. Реальных списаний и платных вызовов 0. CI зелёный, PR ожидает ревью.

### Возврат резерва при отказе провайдера

- [Проводки и приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6728368392), SHA `4735591f75024fd127f082fd53a860e8286378df`. Чат, озвучка и создание видео возвращают резерв один раз при документированном отклонении. При неизвестном исходе резерв сохраняется после перезапуска, повторного POST нет.
- Изолированный прогон обычного ID с тестовым балансом: один POST только в адаптер заглушки, одна проводка списания. 22 целевых и 333 теста в полном локальном прогоне. [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42532976676) · [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/42532976669). На живом стенде `halted=true`, миграция 027 на нём не применялась. PR ожидает ревью.

### Выпуск возврата резерва на flowbridge-live-smoke

- [Выпуск и проводки PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6728451307). Работает `4735591f75024fd127f082fd53a860e8286378df`, применена `027_task_refusal.sql`, бот и БД healthy. До обновления сохранён локальный архив БД. `halted=true`.
- 14 тестов через штатный обработчик на отдельной PostgreSQL. Подтверждённый отказ вернул резерв один раз, таймаут сохранил резерв, повторных POST после перезапуска нет. CI зелёный. Платных запросов и реальных списаний 0. PR ожидает ревью.

### Восстановление каталога AnyModel после сетевого сбоя

- [Приёмка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6728600507), SHA стенда `3b1421d0362cbcd64712b4d843f9abe93cb4e24c`. Воспроизведён TLS EOF на `GET /v1/models`. Фоновая задача процесса bot после временной ошибки повторяет чтение через 30 секунд и сохраняет код и маршрут сбоя.
- Подтверждён свежий снимок по ключу и все четыре рабочие вкладки без админ-сессии. Временный сбой отображается отдельно от пустого списка. 335 локальных тестов, `halted=true`, платных запросов 0. PR ожидает ревью.

### Публичный пользовательский вход на тестовом стенде

- [Проверка PR №16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16#issuecomment-6739905251), SHA `3b1421d0362cbcd64712b4d843f9abe93cb4e24c`, [@DarkFlowGen_Bot](https://t.me/DarkFlowGen_Bot). `halted=true`, платёжные функции и живые флаги выключены.
- Штатные обработчики с тестовым транспортом подтвердили две карточки, отказ админ-команде, нулевой кошелёк и отсутствие резерва и POST. Живой вход с нового обычного аккаунта не подтверждён, владелец взял эту часть проверки на себя.
