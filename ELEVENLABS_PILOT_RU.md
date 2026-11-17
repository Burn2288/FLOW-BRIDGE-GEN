# Закрытый тест ElevenLabs v4 в DarkFlow

Распакуйте обновление поверх рабочего проекта. Сохраните свой .env. Выполните из
папки проекта:

```cmd
docker compose up -d --build bot worker
docker compose exec bot python -m elevenbot voice-candidates
```

Вторая команда необязательна. Она проверяет чтение каталога голосов CLODEX.
В пилоте бот загружает этот список сам при нажатии «Выбрать голос».
Ручное создание JSON и VOICES_FILE для пилота больше не нужны.

Проверьте в кабинете CLODEX цену и доступный лимит расходов. В локальном .env
оставьте приватный доступ и отключённые платежи. Используйте рабочий ключ
CLODEX и действующий токен Telegram. Укажите параметры:

```dotenv
ACCESS_MODE=private
PAYMENTS_ENABLED=false
PROVIDER_MODE=clodex
CATALOGUE_ENABLED=true
CLODEX_SPEECH_PILOT=true
CLODEX_TTS_MODEL=eleven_v4
GENERATION_ENABLED=true
ECONOMY_VERIFIED=true
```

ECONOMY_VERIFIED=true используйте только после проверки тарифа. Обязательные
положительные целые настройки PROVIDER_COST_BOUND_PER_CHAR и
DAILY_PROVIDER_BUDGET_UNITS задайте в одной внутренней расчётной единице.
Первое значение — консервативная оценка затрат на символ, второе —
дневной предел в той же единице. Баланс CLODEX и внутренние кредиты DarkFlow
учитываются раздельно. Если на другом TTS-провайдере уже есть незавершённые
работы, дождитесь их окончания перед переключением модели и worker.

```cmd
docker compose up -d bot worker
docker compose exec bot python -m elevenbot catalog-refresh
docker compose exec bot python -m elevenbot speech-pilot-credit --telegram-id ВАШ_ID --credits 300
```

Перед начислением примите условия бота через /start. Начисление однократное
для каждого администратора, максимум 3000 внутренних кредитов. Оно не
пополняет CLODEX. В Telegram откройте «Открыть каталог → Озвучить текст →
eleven_v4», нажмите «Выбрать голос», выберите вариант, введите короткую фразу и подтвердите запуск.
Именно подтверждение запускает очередь. После MP3 сравните расход в кабинете
CLODEX с лимитом и журналом. Публикация пользователям отдельная, через
PUBLIC_CATALOGUE_MODELS после успешного сквозного теста.
