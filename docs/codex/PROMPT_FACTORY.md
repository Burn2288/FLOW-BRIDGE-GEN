# Codex Prompt Factory — генератор задач с учётом реального кода коллеги

**Статус:** DOCUMENTATION_DRAFT / NOT_ASSIGNED. Данный файл предназначен для подготовки следующих заданий. **Не** является командой немедленно модифицировать код/репозиторий, менять личные планы или сливать PR.

**Читать до каждой задачи:** `CONTRIBUTING.md`, `AGENTS.md`, `docs/FOUNDATION_INDEX.md`, `docs/coordination/BRANCH_INTEGRATION_PROTOCOL.md`, `docs/audit/VANKHU21_IMPLEMENTATION_BASELINE.md`, `docs/contracts/CONTRACT_REGISTRY.md`, и только нужные контракты. Выполнение по FACT → EVIDENCE → ROOT CAUSE → CHANGE → PHYSICAL PROOF → REGRESSION → ACCEPTANCE.

## Приоритет источника правды

1. Фактически принятый `origin/main` HEAD/коммиты/миграции и работающие тесты.
2. Ревьюируемые PR при точном SHA — кандидаты (существующий код для reuse), не признанная main.
3. Доказательства CI по конкретному SHA, отдельно mock и live.
4. Контракты `APPROVED` владельцем, а `DRAFT` — предложение.
5. История аудитов, архивов и текстовые отчёты — гипотезы до новой проверки.

Нельзя присваивать статус `DONE` только по совпадающему имени файла. Запрещено уничтожать код/историю коллеги из-за расхождения веток. Отчёт другого Codex не является сам по себе кодовым или live-доказательством.

## Как составлять один запрос Codex

Заполните переменные:

- `TASK_ID`: одна наблюдаемая проблема и один проверяемый результат.
- `OWNER`: назначается владельцем (не подразумевается автором прошлого PR).
- `BASE_SHA`: актуальный `origin/main` на старте после разрешения зависимости.
- `CANDIDATE_REF`: PR и точный SHA нужного кода коллеги; не вставлять просто ссылку на последний branch.
- `CONTRACTS`: C-... / документация в PR #18; указать, что её approval ещё pending.
- `IN_SCOPE`: конкретный вертикальный путь, файлы и тесты.
- `OUT_OF_SCOPE`: что не переписывать.
- `EVIDENCE_GATE`: точные mock/DB/live способы проверки.
- `MERGE_GATE`: review второго человека + обязательные зелёные Actions на финальном SHA + одобрение.
- `SYNC_GATE`: после merge общая локальная `main` и user env соответствуют origin SHA.

## Универсальный шаблон задания (копировать как единый промпт)

> Ты Codex — исполнитель одного инженерного среза FLOW-BRIDGE-GEN. Владелец задачи: `{OWNER}`, номер `{TASK_ID}`. Соблюдай `CONTRIBUTING.md`, `AGENTS.md`, `docs/coordination/BRANCH_INTEGRATION_PROTOCOL.md`, метод FACT→EVIDENCE→ROOT CAUSE→CHANGE→PHYSICAL PROOF→REGRESSION→ACCEPTANCE. Не изменяй production, не выполняй платные запросы и слияния без отдельного разрешения.
>
> До правок проверь `git status --short`, `git branch --show-current`, `git fetch --prune origin`, `git rev-parse origin/main`; укажи фактический main SHA. Проверь открытые PR и связанные SHA кандидата `{CANDIDATE_REF}`. Сначала прочитай существующие `{FILES_TO_REUSE}`, их тесты и связанные контракты `{CONTRACTS}`. Пометь каждый необходимый элемент: IN_MAIN / PR_OPEN / SOURCE_PRESENT / TESTED_CI / LIVE_PROVEN / NOT_PROVEN. Не создавай дубль уже реализованного сервиса, кошелька, адаптера, UI или миграции.
>
> Выполни `{IN_SCOPE}` минимальными совместимыми изменениями. Не затрагивай `{OUT_OF_SCOPE}`. Сохрани безопасные инварианты: единственный Ledger, один paid POST при двойном нажатии, UNCERTAIN без автоповтора, owner checks, неизменный quote, результат в библиотеке независимо от Telegram. Для изменения контракта приложи ADR и migration/rollback; при зависимости от чужого PR не переписывай пересекающийся код, сначала подготовь точный dependency report.
>
> Проверь `{EVIDENCE_GATE}`. Проведи unit + PostgreSQL integration + targeted regressions + Docs CI; live разрешён только после согласования. Если внешний доступ недоступен — BLOCKED_EXTERNAL, не PASS. Создай один небольшой PR по правилам команды, укажи base/head SHA, все результаты и риски. Не merge автоматически. После подтверждённого merge синхронизируй **всю** локальную сборку по CONTRIBUTING.md, включая код коллеги, и проверь SHA и повторяемость тестов.

## Условия предотвращения пустой работы

**NO-REDO GATE:** перед постановкой задачи Codex ищет аналогичный модуль и тест на принятой main и открытых PR #8–#17. Если найдено, задание должно иметь вид «проверить, адаптировать и закрыть конкретный GAP», а не «написать с нуля». Если gap не воспроизведён, ограничить работу аудитом и вернуть NOT_PROVEN.

**BRANCH GATE:** если base — всё ещё README-only main, а код присутствует только на work-ветке, разработчик не может начинать надстройку по новому main как над уже готовым продуктом; сначала требуется согласованный интеграционный порядок и проверенная база. Запрещена скрытая кросс-веточная зависимость.

**PROMPT SIZE RULE:** одному Codex — один контрактный срез, а не общая миссия «сделать весь Mini App». Для каждого PROMPT ссылка на существующий код, функциональный критерий, запреты, тесты и handoff.

## Матрица экономии

| Не писать заново | Использовать | Реальная надстройка |
| --- | --- | --- |
| User/wallet/ledger | `core.py`, `task_wallet.py`, миграции | разница реального paid checkout, compliance и recovery |
| Provider Registry | `aggregate.py`, `provider_execution.py` | manifest/adapter capability, admin staging |
| Quotes + acceptance | `pricing.py`, `task_launch.py` | transport-neutral job API |
| Telegram UI state | `navigation.py`, `progress.py`, `telegram.py` | требуемая информационная архитектура и consent .md |
| Mini App auth/catalog/library | `miniapp/backend/web.py`, frontend | jobs/payments/admin/referrals, а не новый backend |
| Telegram Admin | `admin_access.py`, `tariff_admin.py`, `model_policy.py`, `topup_ui.py` | совместимый Admin API и web RBAC |
| Platega | `platega.py`, `topups.py`, `topup_ui.py` | соблюдение правил продажи digital + adapter boundary |
| Stars | `telegram.py`, `core.py` | подтверждённый user checkout + Mini App + reconciliation |
| Referrals | AI-SHOP-BOT donor SHA 494ab81f... | полный перенос только referral logic в GenerationJob ledger |

## Следующие готовые промпты

[Модульные срезы PROMPT-00…PROMPT-09](NEXT_TASK_PROMPTS.md). Их нужно выбирать после разрешения зависимостей, а не выполнять все параллельно. Исполнитель определяется владельцем при реальной выдаче задания.
