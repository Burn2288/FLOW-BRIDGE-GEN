# Runtime configuration — CURRENT keys vs TARGET additions

Статус: DESIGN_DRAFT и SOURCE-AWARE из PR #17 SHA d691d54e; фактические ключи брать из `src/elevenbot/config.py` и `.env.example` на интегрируемом SHA. Ранее предложенные имена (BOT_TOKEN, ADMIN_TELEGRAM_USER_IDS, MINI_APP_PUBLIC_URL) **не** присутствуют в проверенном Config как рабочие ключи — не задавать их как единственный способ запуска и не создавать двойной allowlist без ADR.

## Реально встречающиеся в коде кандидата ключи (секреты — placeholders)

```env
DATABASE_URL=postgresql://local_user:CHANGE_ME@localhost:55432/elevenbot
TELEGRAM_BOT_TOKEN=CHANGE_ME
ACCESS_MODE=private
ADMIN_TELEGRAM_IDS=111111111
ADMIN_PASSWORD=CHANGE_ME
MINIAPP_URL=https://example.invalid/
GENERATION_ENABLED=false
PUBLIC_IMAGE_MODELS=
PAYMENTS_ENABLED=false
PAYMENT_BACKEND=stars
TOPUP_MODE=off
PLATEGA_ENABLED=false
PLATEGA_MERCHANT_ID=
PLATEGA_SECRET=
CLODEX_API_KEY=
FAL_KEY=
```

Все значения примерные, не реальные! Полный фактический список флагов и валидацию изучать по `Config.env`; в коде существуют конфликтные ограничения private/public, live payment и pilot modes. Не включать генерацию или платные операции только ради теста UI. `ADMIN_TELEGRAM_IDS` контролирует Telegram Admin Edition и в проектной Mini App может быть единственным источником eligibility для выбора режима, но **сама роль и право должны проверяться сервером**. `ADMIN_PASSWORD` относится к отдельной Telegram process-local сессии, не готовый HTTP admin-token.

## Предлагаемые изменения (пока не реализованы)

```env
MINIAPP_ADMIN_CHOOSER_ENABLED=false
# Optional only if owner approves distinct whitelist and no ambiguity with ADMIN_TELEGRAM_IDS:
# MINIAPP_ADMIN_ENTRY_IDS=
STARS_CHECKOUT_ENABLED=false
```

Рекомендация: для beta использовать уже существующий `ADMIN_TELEGRAM_IDS` как allowlist *входного выбора*, плюс независимые roles/permissions для Admin API. Не добавлять одновременно `ADMIN_TELEGRAM_USER_IDS` без миграции и alias contract. Если требуются отдельные веб-администраторы — оформить ADR и нормализовать оба списка.

## Config ownership
- Immutable bootstrap secrets (token, Platega credentials, provider keys, DB) — только env/secret manager; не из UI или БД.
- Business settings (модели, допуск, тарифы, пресеты, видимость, UI) — версия в БД и Admin API с RBAC/audit/rollback, env kill-switch имеет приоритет.
- Изменения флагов, влияющих на pricing/платежи/режим кошелька, разрешаются только после проверки текущих ограничений и одного неизменного E2E-конфига.
- Раздельно `demo`/ `live` Wallet и provider credit; нельзя конвертировать рубли или Stars в токены без зафиксированной политики/курса.
- Для продажи цифрового контента в Telegram применяется Stars C-031, не прямой Platega checkout. Platega сохраняется как отдельный adapter для допустимых каналов/операций по согласованной политике.

## Fail-closed и критерии проверки
Неправильные ADMIN_TELEGRAM_IDS/miniapp initData/role → admin access denied. Нет действительного token/DB → startup failure. Нет API агрегатора → модель выключена, не вся платформа. Нет платёжных ключей → соответствующий channel unavailable. Конфигурация должна печататься только redacted. Интеграционные тесты: readonly /miniapp, один signed auth, user/admin switch, revoke, permission, смешанные флаги, no external spending, missing secret, unchanged wallet.
