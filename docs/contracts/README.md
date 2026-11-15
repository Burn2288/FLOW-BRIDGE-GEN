# Архитектурные контракты — централизованный индекс

См. [реестр C-001—C-030](CONTRACT_REGISTRY.md). Этот документ — навигатор, не дублирует полный текст контрактов. Все новые контракты имеют статус DESIGN_DRAFT, без заявления о внедрении.

- [Identity/Consent](IDENTITY_CONSENT.md) — Telegram identity, согласие, Mini App initData, auth.
- [Telegram UX](TELEGRAM_UX.md) — обязательные меню и подменю, пагинация, обработка callbacks, edit-message.
- [Mini App UX](MINI_APP_UX.md) — все клиентские маршруты, parity, выбор администратора/пользователя.
- [Generation Jobs](GENERATION_JOBS.md) — жизненный цикл, очередь, повторы, отказ, доставка.
- [Provider Plugins](PROVIDER_PLUGINS.md) — адаптеры любых агрегаторов и безопасное расширение.
- [Catalog/Pricing](CATALOG_PRICING.md) — capabilities, динамические модели и котировки.
- [Media/Library](MEDIA_LIBRARY.md) — сохранение оплаченного результата, доступ и повторная отправка.
- [Wallet/Ledger](WALLET_LEDGER.md) — резервирование, списание, возврат и атомарность.
- [Platega](PLATEGA_ADAPTATION.md) — полноценная схема адаптации наработок AI-SHOP-BOT.
- [Referrals](REFERRALS.md) — атрибуция, вознаграждения, возвраты и долги.
- [Admin](ADMIN_CONTROL.md) — наследуемый Telegram admin + Mini App admin, RBAC, настройки.
- [API Foundation](API_FOUNDATION.md) — HTTP API v1, событийный outbox и ошибка/разрешение.

## Последующие углубления

Нужны формальные схемы OpenAPI 3.1 и JSON Schema, DDL и индексы, спецификация статусов по каждому переходу, CBAC/permission matrix, контракт тестовые фикстуры, версии провайдерских адаптеров, observability events, подробные threat models, deployment и backup/restore. См. программу в CONTRACT_REGISTRY. Любое изменение проходит ADR/compatibility review, тестирование конкретного SHA и evidence.

## Источник правды

OWNER_REQUIREMENT и эталонная инженерная директива задают цели; SOURCE_AI_SHOP описывает только подтверждённое присутствие кода в доноре; DESIGN_PROPOSAL не обозначает реализацию FLOW. При реальном импорте код проверяется заново и фиксируется в отдельном AS-IS аудите.
