# Источники и достоверность

Проверка публичных источников: 03.11.2026. Страницы изменяемые; перепроверять перед реализацией.

1. Telegram Stars и цифровые услуги: https://core.telegram.org/bots/payments-stars
2. Telegram Bot API (getUpdates, setWebhook, payments, refundStarPayment): https://core.telegram.org/bots/api
3. ElevenLabs возможности: https://elevenlabs.io/api
4. ElevenLabs авторизация: https://elevenlabs.io/docs/api-reference/authentication
5. ElevenLabs документация: https://elevenlabs.io/docs/overview/intro
6. MAX upload: https://dev.max.ru/docs-api/methods/POST/uploads/
7. MAX messages: https://dev.max.ru/docs-api/methods/POST/messages
8. MAX API setup: https://dev.max.ru/docs/chatbots/bots-coding/prepare/

Материалы предыдущего аудита: CLODEX_API_AUDIT_2026-11-03.zip, включены в original_clodex_audit/. Они не содержат LIVE PASS.

Подтверждено публичной документацией: Telegram Stars для цифровых продаж; наличие средств оплаты/возврата; необходимость защиты ElevenLabs ключей; возможности прямого ElevenLabs; наличие загрузки и отправки аудио в MAX.
Не подтверждено: реальный TTS Clodex, голосовые методы и стоимость; доступность всех ElevenLabs функций через Clodex; платежи MAX и допуск конкретного владельца к созданию бота; production работоспособность разрабатываемого продукта.
Проектные решения: Python/aiogram/PostgreSQL, 4 кнопки, queue в БД, лимиты, retention, тарифные правила. Это рекомендации для реализации, не утверждения о внутреннем устройстве чужих ботов.
