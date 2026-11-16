# Карта документации FLOW-BRIDGE-GEN

**Главный индекс**: [FOUNDATION_INDEX.md](FOUNDATION_INDEX.md). Действует на документационном этапе, до интеграции проверенного исходного приложения.

| Область | Источник |
| --- | --- |
| Продукт, цель, user flows и функциональный паритет | [PRODUCT_BLUEPRINT.md](product/PRODUCT_BLUEPRINT.md) |
| Модульная архитектура и ответственность за данные | [MODULAR_SYSTEM.md](architecture/MODULAR_SYSTEM.md) |
| Реестр C-001—C-030 и планы глубоких схем | [CONTRACT_REGISTRY.md](contracts/CONTRACT_REGISTRY.md) |
| Пользовательские интерфейсы DM и Mini App | [TELEGRAM_UX.md](contracts/TELEGRAM_UX.md), [MINI_APP_UX.md](contracts/MINI_APP_UX.md) |
| Провайдеры, модели, задачи | [PROVIDER_PLUGINS.md](contracts/PROVIDER_PLUGINS.md), [CATALOG_PRICING.md](contracts/CATALOG_PRICING.md), [GENERATION_JOBS.md](contracts/GENERATION_JOBS.md) |
| Библиотека, медиа и доставка | [MEDIA_LIBRARY.md](contracts/MEDIA_LIBRARY.md) |
| Баланс и платежи | [WALLET_LEDGER.md](contracts/WALLET_LEDGER.md), [PLATEGA_ADAPTATION.md](contracts/PLATEGA_ADAPTATION.md) |
| Рефералы | [REFERRALS.md](contracts/REFERRALS.md) |
| Административная система | [ADMIN_CONTROL.md](contracts/ADMIN_CONTROL.md) |
| Public API и события | [API_FOUNDATION.md](contracts/API_FOUNDATION.md) |
| Донорские исходники AI-SHOP-BOT | [AI_SHOP_REUSE.md](reference/AI_SHOP_REUSE.md) |
| .env/секреты и allowlist администраторов | [ENV_CONTRACT.md](operations/ENV_CONTRACT.md) |
| Проверки, доказательства, ограничения | [FOUNDATION_TEST_MATRIX.md](acceptance/FOUNDATION_TEST_MATRIX.md), [EVIDENCE.md](acceptance/EVIDENCE.md), [KNOWN_LIMITATIONS.md](acceptance/KNOWN_LIMITATIONS.md) |
| Фиксация статуса, решения | [PROJECT_STATE.md](PROJECT_STATE.md), [DECISION_LOG.md](DECISION_LOG.md) |
| Историческая первичная архитектура / аудит | [SYSTEM_OVERVIEW.md](architecture/SYSTEM_OVERVIEW.md), [AS_IS_ARCHITECTURE.md](audit/AS_IS_ARCHITECTURE.md) |
| Deployment | [DEPLOYMENT.md](operations/DEPLOYMENT.md) |
| Общая дорожная карта | [ROADMAP.md](ROADMAP.md) |

В дальнейшем при импорте приложения сохранять исходные пути/миграции и сравнивать с целевой моделью, а не объявлять все подготовленные документы реализацией. Для следующей итерации запланированы машинно-проверяемые OpenAPI 3.1, JSON Schema, модель SQL/PostgreSQL, подробная таблица переходов, ADR и runbooks. Личные планы находятся только в личных ветках и не являются предметом этой работы.

## Актуализация после анализа кода vankhu21 (2026-11-15)

- [Исходники кандидата и степень доказанности](audit/VANKHU21_IMPLEMENTATION_BASELINE.md).
- [Правила приёмки стэка PR и синхронизации](coordination/BRANCH_INTEGRATION_PROTOCOL.md).
- [Шаблон постановки задачи Codex](codex/PROMPT_FACTORY.md), [готовые промпты](codex/NEXT_TASK_PROMPTS.md).
- [Платёжная политика Stars для цифровых услуг](contracts/TELEGRAM_STARS_CHANNEL.md).

Эти документы не означают merge PR #8–#17, не меняют личные dev-планы и не доказывают полный live E2E. Начинать расширение только после выбора интеграционной базы.

## Team planning proposal

[TASK-PLAN-001 — план, worklists и протокол аудита](planning/README.md). Не заменяет принятую main до review/merge.
