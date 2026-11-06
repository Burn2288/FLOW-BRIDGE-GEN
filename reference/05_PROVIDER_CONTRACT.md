# Clodex и ElevenLabs

Состояние на 03.11.2026: в имеющемся аудите нет доказанного рабочего TTS-контракта Clodex. Каталог моделей не доказывает поддержку полного ElevenLabs API. Не подставлять ElevenLabs/OpenAI endpoints на Clodex без документации.

## Внутренний контракт адаптера (это НЕ HTTP API Clodex)
capabilities() → verified features, models, formats, limits.
list_voices() → id, display_name, languages, preview reference, ownership scope.
synthesize(request, operation_id) → completed artifact / accepted provider_job_id / definitive failure / unknown outcome.
get_job(provider_job_id) → status/result, если поддерживается.
get_usage(operation_id) → фактический расход, если поддерживается.

В запросе: internal job ID, text, voice_id, model_id, approved settings, format. В ответе: provider request ID, MIME, bytes либо проверяемая ссылка, usage и классификация результата. Отсутствующие функции возвращают unsupported и скрыты в UI.

## Что получить у Clodex
Официальные base URL, auth header, методы и body; точные model/voice IDs; поддержка приватных голосов; бинарный ответ/JSON/async; лимиты текста/загрузок/concurrency; цены и единицы; idempotency; timeout и возвраты; время хранения результатов; политика пользовательских данных; условия использования сервиса через платного бота.

## Проверка подключения
1. Получить документацию и отдельный ключ с минимальными правами.
2. Без генерации проверить auth и документированные справочные методы.
3. Зафиксировать capabilities и реальные model/voice IDs.
4. После разрешения владельца на расход выполнить один короткий TTS-запрос.
5. Проверить воспроизводимое аудио и реальное списание до/после.
6. Проверить обработку неверного ввода, 401, лимитов и неопределённого результата безопасной имитацией на нашей стороне.
7. Сохранить очищенные evidence: время, метод, путь, status, MIME, bytes, hash, request ID, расход. Секреты/приватные тексты исключить.

Прямой ElevenLabs — отдельный адаптер, со своими ключами, ценами и условиями. Автоматический переход на него при ошибке Clodex выключен: он может вызвать двойные расходы и передачу данных другому поставщику.

MOCK допускается для разработки UI/очереди/денег, но маркируется MOCK и не означает LIVE PASS. Не списывать реальные клиентские кредиты в mock-режиме.
