# FLOW-BRIDGE-GEN — фундаментальная документация v0.1

Статус: DESIGN_DRAFT / DOCUMENTATION_ONLY. Составлено 2026-11-15 для дальнейшего согласования владельцем. Ни один документ этой серии не является доказательством реализованного функционала, завершённого переноса или успешных тестов.

## Цель

Единая коммерческая AI-платформа с двумя равноправными клиентами: Telegram-бот в личном чате и Telegram Mini App. Оба используют общие identity, consent, catalog, generation, payments, wallet, library, referrals, support, administration. Функции не дублируются в бизнес-слое; различаются исключительно каналы представления. Подключаемые агрегаторы (CLODEX, AnyModel, Fal и будущие) не определяют формат основной бизнес-логики.

## Правила источников

1. OWNER_REQUIREMENT — прямое требование владельца из постановки 2026-11-15. Определяет пользовательское намерение.
2. BASE_DIRECTIVE — DARKFLOW GEN MASTER ENGINEERING DIRECTIVE (база 5601faa), предоставленная владельцем: проверочный метод, инварианты безопасности, S0–S8.
3. SOURCE_AI_SHOP — извлечённые повторно используемые решения из приватного Burn2288/AI-SHOP-BOT, main SHA 494ab81f5552be836a37ec3aa685e6be8308076c. Это референс переноса, не состояние FLOW-BRIDGE-GEN.
4. DESIGN_PROPOSAL — предложенная архитектура и значения по умолчанию; до утверждения владельцем не выдавать за согласованную функцию.
5. SOURCE_PRESENT_UNMERGED — наблюдаемый исходный код в PR #17 SHA d691d54e..., не являющийся принятой main; CI этого SHA успешен. AS_IMPLEMENTED_IN_MAIN подтверждается только после merge и повторной проверки HEAD.

Работы, выполненные vankhu21 в FLOW-BRIDGE-GEN, и личные рабочие планы двух разработчиков намеренно не оцениваются и не используются как доказательства в этом пакете. Документы не заменяют прежнюю историю или код.

## Навигация

| Уровень | Документ | Назначение |
| --- | --- | --- |
| Продукт | [PRODUCT_BLUEPRINT](product/PRODUCT_BLUEPRINT.md) | Сущности, каналы, сценарии, MVP, права |
| Архитектура | [MODULAR_SYSTEM](architecture/MODULAR_SYSTEM.md) | Службы, потоки, границы и отказоустойчивость |
| Контроль контрактов | [CONTRACT_REGISTRY](contracts/CONTRACT_REGISTRY.md) | Идентификаторы, владельцы данных, тесты и версия |
| Общие правила | [IDENTITY_CONSENT](contracts/IDENTITY_CONSENT.md) | /start, соглашение, идентичность |
| Telegram | [TELEGRAM_UX](contracts/TELEGRAM_UX.md) | Дерево меню и edit-message UX |
| Mini App | [MINI_APP_UX](contracts/MINI_APP_UX.md) | Экранная карта и административный выбор режима |
| Генерации | [GENERATION_JOBS](contracts/GENERATION_JOBS.md) | Задания, цена, сохранение, доставка |
| Каталог | [CATALOG_PRICING](contracts/CATALOG_PRICING.md) | Провайдеры, модели, тарифы, видимость |
| Провайдеры | [PROVIDER_PLUGINS](contracts/PROVIDER_PLUGINS.md) | Расширяемые адаптеры и безопасное подключение |
| Медиа | [MEDIA_LIBRARY](contracts/MEDIA_LIBRARY.md) | Библиотека, права, сроки хранения |
| Бухгалтерия | [WALLET_LEDGER](contracts/WALLET_LEDGER.md) | Баланс, резервы, списания, возвраты |
| Платежи | [PLATEGA_ADAPTATION](contracts/PLATEGA_ADAPTATION.md) | Перенос механики AI-SHOP-BOT |
| Рефералы | [REFERRALS](contracts/REFERRALS.md) | Глубокие ссылки, бонусы, возвраты |
| Администраторы | [ADMIN_CONTROL](contracts/ADMIN_CONTROL.md) | Telegram admin, Mini App admin, RBAC |
| Backend | [API_FOUNDATION](contracts/API_FOUNDATION.md) | Общий API, auth, версии и ошибки |
| Наследование | [AI_SHOP_REUSE](reference/AI_SHOP_REUSE.md) | Точные пути кодовой базы-донора |
| Существующий код | [VANKHU21_IMPLEMENTATION_BASELINE](audit/VANKHU21_IMPLEMENTATION_BASELINE.md) | Реально присутствующие модули, тесты и ограничения по SHA PR #17 |
| Ветки | [BRANCH_INTEGRATION_PROTOCOL](coordination/BRANCH_INTEGRATION_PROTOCOL.md) | Ревью, зависимости PR, синхронизация и запрет автослияния |
| Промпты Codex | [PROMPT_FACTORY](codex/PROMPT_FACTORY.md), [NEXT_TASK_PROMPTS](codex/NEXT_TASK_PROMPTS.md) | Антидублирование существующего кода и последовательные задачи |
| Stars / compliance | [TELEGRAM_STARS_CHANNEL](contracts/TELEGRAM_STARS_CHANNEL.md) | Правило цифровых услуг и существующие Stars-механизмы |
| Настройки | [ENV_CONTRACT](operations/ENV_CONTRACT.md) | Секреты, allowlist админов, флаги |
| Приёмка | [FOUNDATION_TEST_MATRIX](acceptance/FOUNDATION_TEST_MATRIX.md) | Требование → контракт → проверка |
| Состояние | [PROJECT_STATE](PROJECT_STATE.md) | Срез реальной доказанности |
| Решения | [DECISION_LOG](DECISION_LOG.md) | Неутверждённые и утверждённые ADR |

## Неподвижные инварианты проекта

- Без принятия актуальной версии пользовательского соглашения недоступны платные и продуктовые действия в обоих клиентах.
- Единственное ядро пользователей, кошельков, генераций, медиатеки и рефералов; Telegram и Mini App не ведут отдельные таблицы денег и заказов.
- Подтверждение платёжного шлюза само по себе не начисляет средства: серверная независимая проверка + атомарная идемпотентная проводка.
- Повтор доставки уже созданного результата никогда не инициирует повторную платную генерацию.
- Новая AI-интеграция не правит Telegram UI, Mini App UI и Ledger; расширяет Provider Registry / Adapter Contract.
- Административная видимость в Mini App не даёт права на административные операции без повторной серверной проверки.
- Неизвестный исход платной операции запрещает слепой retry/failover.
- Одни и те же правила безопасности, цены и прав действуют независимо от клиента.

## Управление версиями

Контракты сначала DRAFT, затем REVIEWED (командой), APPROVED (владельцем), IMPLEMENTED (код+SHA), VERIFIED (отдельные тесты и evidence). Не путать эти статусы с результатами тестов PASS/PARTIAL/FAIL/BLOCKED/NOT_PROVEN/NOT_TESTED.

Каждая следующая итерация сверяет изменение с контрактным реестром, добавляет migration/compatibility plan, ADR, матрицу тестов и конкретные evidence. Удаление прежнего механизма допускается только после подтверждения замены и регрессии.

## Ближайший документарный milestone

Утвердить жизненные циклы кошелька, оплаты, генерации и реферала; утвердить значения по умолчанию и ограничения тарифов; зафиксировать эталонный UX Mini App. Далее — AS-IS аудит кода и вертикальный E2E image slice; без преждевременной переписи архитектуры.
