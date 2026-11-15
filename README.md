# FLOW-BRIDGE-GEN — DarkFlow Gen

Коммерческая модульная AI-платформа для Telegram: бот с навигацией через редактируемое меню, Mini App с отдельным качественным UI, общие студии изображений/видео/озвучки/песен, единые кошелёк, Platega-пополнение, медиатека, рефералы, поддержка и администрирование. Один бизнес-backend и подключаемые агрегаторы AI. **На данный момент это проектное намерение; работоспособность не доказана.**

## С чего начинать чтение

1. **[Фундаментальная карта проекта и статусы документов](docs/FOUNDATION_INDEX.md)** — единый индекс, источники требований и реестр.
2. [Продуктовая модель и сценарии](docs/product/PRODUCT_BLUEPRINT.md).
3. [Модульная система служб и процессов](docs/architecture/MODULAR_SYSTEM.md).
4. [Реестр базовых контрактов C-001—C-030](docs/contracts/CONTRACT_REGISTRY.md).
5. [Telegram-меню](docs/contracts/TELEGRAM_UX.md) и [Mini App](docs/contracts/MINI_APP_UX.md).
6. [Донорская база AI-SHOP-BOT](docs/reference/AI_SHOP_REUSE.md) для Platega и реферальной системы.
7. [Матрица требований и приёмки](docs/acceptance/FOUNDATION_TEST_MATRIX.md).
8. [Состояние документации](docs/PROJECT_STATE.md) и [решения](docs/DECISION_LOG.md).

## Совместная разработка

[Правила работы двоих и синхронизация](CONTRIBUTING.md), [инструкции Codex](AGENTS.md), [карта файлов](docs/README.md), [дорожная карта S0–S8](docs/ROADMAP.md). Индивидуальные планы живут в личных ветках [dev/burn2288](https://github.com/Burn2288/FLOW-BRIDGE-GEN/tree/dev/burn2288) и [dev/vankhu21](https://github.com/Burn2288/FLOW-BRIDGE-GEN/tree/dev/vankhu21). **Личные планы и уже написанный код в рамках текущего документарного этапа не анализировались и не менялись.**

## Реализация и доказательства

Основной инженерный метод: FACT → EVIDENCE → ROOT CAUSE → CHANGE → PHYSICAL PROOF → REGRESSION → ACCEPTANCE. Первым продуктовым доказательством остаётся реальная E2E генерация изображения с сохранением, библиотекой, доставкой и контролем списания. Новые контракты имеют статус DESIGN_DRAFT до решения владельца и независимой проверки реализации. Детали старого стартового пакета: [план AS-IS аудита](docs/audit/AS_IS_ARCHITECTURE.md), [базовая матрица проверок](docs/acceptance/TEST_MATRIX.md).

## Повторное использование реального кода коллеги

См. [инвентаризацию vankhu21 на точном SHA](docs/audit/VANKHU21_IMPLEMENTATION_BASELINE.md), [регламент PR и локальной синхронизации](docs/coordination/BRANCH_INTEGRATION_PROTOCOL.md), [конструктор задания Codex](docs/codex/PROMPT_FACTORY.md) и [готовые промпты срезов](docs/codex/NEXT_TASK_PROMPTS.md). Эти документы отражают **кандидатную рабочую ветку PR #17, а не принятый main**. Платёжная совместимость с правилами Telegram: [Stars для цифровых услуг](docs/contracts/TELEGRAM_STARS_CHANNEL.md).
