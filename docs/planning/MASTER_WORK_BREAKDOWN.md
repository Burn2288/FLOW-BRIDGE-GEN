# MASTER WORK BREAKDOWN — TASK-PLAN-001

Предложение 2026-11-16, не приказ выполнять приложение. 27 направлений, 81 постоянных TASK_ID. Принятая main: `98d05504446458252ede2df35e8870b2e1bc63e2`; код-кандидат #17: `d691d54e0266c3d519d66575555fa45895ef40ac`; документационная база #18: `37337cc1538e26f91696be366908420d9dbb08d2`. [Источник GitHub](evidence/github-snapshot.json), [coverage](FEATURE_COVERAGE_MATRIX.md), [зависимости](IMPLEMENTATION_DEPENDENCIES.md), [интеграция](BRANCH_INTEGRATION_SEQUENCE.md), [параллелизм](PARALLEL_WORK_MATRIX.md), [вехи](RELEASE_MILESTONES.md), [аудит](AUDIT_GATES.md), [решения](DECISIONS_REQUIRED.md), [первые шаги](NEXT_ACTIONS.md).

Планы [Burn2288](../workplans/burn2288.md) и [vankhu21](../workplans/vankhu21.md) — связанные представления этого реестра. Машинный реестр [tasks.json](tasks.json). Данные исторических dev-планов сохранены отдельно в [history](history/README.md).

Статус исходников многомерный: NOT_STARTED, SOURCE_PRESENT, PR_OPEN, CI_PASS@SHA, PARTIAL, LIVE_NOT_PROVEN, BLOCKED; ACCEPTED только после согласованной приёмки и интеграции. Все исходные PR открыты: ни одному компоненту не присваивается ACCEPTED. Статус задачи: Планируется → выполняется → READY_FOR_AUDIT/ожидает аудита → принято, либо заблокировано. READY — заявление исполнителя о пакете, не независимый PASS.

Этапы строго по ROADMAP S0–S8. Подготовка документации/тестовых fixtures допустима параллельно; начало широкой реконструкции после IM-02 либо точной внешней блокировки. Integration tasks означают review/предложение merge; фактический merge только после решения команды. Новые endpoints и миграции — планы, не текущая реализация.

Общий DoD: FACT→EVIDENCE→ROOT CAUSE→CHANGE→PHYSICAL PROOF→REGRESSION→ACCEPTANCE; при отсутствии дефекта ROOT_CAUSE_UNCONFIRMED или N/A для новой возможности, не выдумывать причину. Один изменяемый модуль/контракт/миграция — один writer. [Протокол доказательств](EVIDENCE_PUBLICATION_PROTOCOL.md) обязателен для каждой строки. Если live доступа нет, соответствующая часть BLOCKED_EXTERNAL/LIVE_NOT_PROVEN и задача не принята полностью.

Effort 1/3/5 — относительная сложность, не дни и не обещание срока. Рецензент — второй разработчик; integration owner отвечает за связку с main, аудитор ChatGPT — независимое решение.

| TASK_ID | Результат | Владелец / reviewer | Приоритет / этап | Effort | Зависимости |
| --- | --- | --- | --- | --- | --- |
| [IN-01](#in-01) | Утвердить порядок интеграции и freeze SHA | Burn2288 / vankhu21 | P0 / S0 | 3 | нет |
| [IN-02](#in-02) | Принять документационную базу PR #1 | Burn2288 / vankhu21 | P0 / S0 | 1 | IN-01 |
| [IN-08](#in-08) | Интегрировать PR #8 и доказать supersession ранних пилотов | vankhu21 / Burn2288 | P0 / S0 | 3 | IN-02 |
| [IN-09](#in-09) | Провести отдельную приёмку и интеграцию PR #9: Veo video | vankhu21 / Burn2288 | P0 / S0 | 1 | IN-08 |
| [IN-10](#in-10) | Провести отдельную приёмку и интеграцию PR #10: AnyModel registry | vankhu21 / Burn2288 | P0 / S0 | 1 | IN-09 |
| [IN-11](#in-11) | Провести отдельную приёмку и интеграцию PR #11: FIBO async image | vankhu21 / Burn2288 | P0 / S0 | 1 | IN-10 |
| [IN-12](#in-12) | Провести отдельную приёмку и интеграцию PR #12: Grok video | vankhu21 / Burn2288 | P0 / S0 | 1 | IN-11 |
| [IN-13](#in-13) | Провести отдельную приёмку и интеграцию PR #13: AnyModel speech | vankhu21 / Burn2288 | P0 / S0 | 1 | IN-12 |
| [IN-14](#in-14) | Провести отдельную приёмку и интеграцию PR #14: Welcome/navigation | vankhu21 / Burn2288 | P0 / S0 | 1 | IN-13 |
| [IN-15](#in-15) | Провести отдельную приёмку и интеграцию PR #15: Task progress | vankhu21 / Burn2288 | P0 / S0 | 1 | IN-14 |
| [IN-16](#in-16) | Принять PR #16: финансы, каталог и Telegram Admin | vankhu21 / Burn2288 | P0 / S0 | 5 | IN-15 |
| [IN-17](#in-17) | Принять PR #17: Mini App и новый inbox | vankhu21 / Burn2288 | P0 / S0 | 3 | IN-16 |
| [IN-18](#in-18) | Согласовать фундамент и план как отдельные docs PR | Burn2288 / vankhu21 | P0 / S0 | 3 | IN-02 |
| [IN-19](#in-19) | Синхронизировать и запустить целую принятую сборку | Burn2288 / vankhu21 | P0 / S0 | 3 | IN-17, IN-18 |
| [AR-01](#ar-01) | Зафиксировать реальные границы модулей и транзакций | Burn2288 / vankhu21 | P1 / S3 | 3 | JO-03 |
| [AR-02](#ar-02) | Изолировать транспортные команды от финансовых деталей | Burn2288 / vankhu21 | P1 / S3 | 5 | AR-01 |
| [TG-01](#tg-01) | Перевести главное меню и Back без потери старых маршрутов | vankhu21 / Burn2288 | P1 / S5 | 3 | IN-19 |
| [TG-02](#tg-02) | Подключить документы и текущий consent к Telegram UX | vankhu21 / Burn2288 | P1 / S5 | 3 | SL-01, TG-01 |
| [TG-03](#tg-03) | Личный кабинет и история общего кошелька | vankhu21 / Burn2288 | P1 / S5 | 3 | PY-01, TG-01 |
| [MA-01](#ma-01) | Принять существующую Mini App в Telegram по HTTPS | vankhu21 / Burn2288 | P1 / S5 | 3 | IN-19, OP-01 |
| [MA-02](#ma-02) | Форма image quote и явное подтверждение | vankhu21 / Burn2288 | P1 / S5 | 3 | AP-02, MA-01 |
| [MA-03](#ma-03) | Карточка job и безопасная отмена | vankhu21 / Burn2288 | P1 / S5 | 3 | MA-02, AP-03, JO-02 |
| [MA-04](#ma-04) | Довести пользовательский parity и доступность | vankhu21 / Burn2288 | P1 / S8 | 5 | MA-03, VI-02, VO-02, MU-02, ML-03, RF-03, SL-03, PY-03 |
| [AD-01](#ad-01) | Серверные admin roles, chooser и read-only обзор | Burn2288 / vankhu21 | P1 / S6 | 5 | AP-01, TA-01 |
| [AD-02](#ad-02) | Одна typed settings-мутация с аудитом и rollback | Burn2288 / vankhu21 | P1 / S6 | 3 | AD-01, MC-01 |
| [AD-03](#ad-03) | Графические admin экраны по общему API | vankhu21 / Burn2288 | P1 / S6 | 5 | AD-02, OB-02 |
| [TA-01](#ta-01) | Зафиксировать compatibility inventory Admin Edition | vankhu21 / Burn2288 | P1 / S0 | 3 | IN-01 |
| [TA-02](#ta-02) | Сохранить Telegram admin при общих admin services | vankhu21 / Burn2288 | P1 / S6 | 3 | AD-02, TA-01 |
| [PR-01](#pr-01) | Расширить existing registry нормализованным manifest | Burn2288 / vankhu21 | P1 / S4 | 5 | AR-01 |
| [PR-02](#pr-02) | Версии, health, staging и rollback провайдера | Burn2288 / vankhu21 | P1 / S4 | 3 | PR-01 |
| [PR-03](#pr-03) | Сверить live capability каждого включаемого адаптера | Burn2288 / vankhu21 | P1 / S4 | 3 | PR-02, IM-02 |
| [MC-01](#mc-01) | Версионировать модель и capabilities без второго каталога | Burn2288 / vankhu21 | P1 / S4 | 3 | PR-01 |
| [MC-02](#mc-02) | Общие карточки и schema-driven параметры каталога | vankhu21 / Burn2288 | P1 / S5 | 3 | MC-01, MA-01 |
| [PC-01](#pc-01) | Уточнить токены, XTR, RUB и immutable quote | vankhu21 / Burn2288 | P0 / S1 | 3 | IN-19 |
| [PC-02](#pc-02) | Preview и publish versioned тарифов | vankhu21 / Burn2288 | P1 / S6 | 3 | PC-01, AD-02 |
| [JO-01](#jo-01) | Доказать topology и закрыть missing lease/fencing | Burn2288 / vankhu21 | P0 / S2 | 5 | IM-02 |
| [JO-02](#jo-02) | Bounded queue, fairness, cancellation и shutdown | Burn2288 / vankhu21 | P0 / S2 | 5 | JO-01 |
| [JO-03](#jo-03) | Единый job projection и состояния четырёх типов | Burn2288 / vankhu21 | P1 / S3 | 5 | JO-02 |
| [IM-01](#im-01) | Повторить штатный image путь с ordinary user | vankhu21 / Burn2288 | P0 / S1 | 3 | IN-19, PC-01 |
| [IM-02](#im-02) | Три live изображения и временный отказ | vankhu21 / Burn2288 | P0 / S1 | 3 | IM-01, ML-01 |
| [VI-01](#vi-01) | Согласовать video create/poll и финальный расчёт | vankhu21 / Burn2288 | P1 / S3 | 3 | JO-03, PC-01 |
| [VI-02](#vi-02) | Video формы двух клиентов и разрешённая приёмка | vankhu21 / Burn2288 | P1 / S5 | 3 | VI-01, AP-03, MC-02 |
| [VO-01](#vo-01) | Нормализовать существующие TTS голоса и units | Burn2288 / vankhu21 | P1 / S3 | 3 | JO-03, PC-01 |
| [VO-02](#vo-02) | Voice UI и E2E двух клиентов | vankhu21 / Burn2288 | P1 / S5 | 3 | VO-01, AP-03, MC-02 |
| [MU-01](#mu-01) | Свести CLODEX/Fal music в общий lifecycle | Burn2288 / vankhu21 | P1 / S4 | 3 | JO-03, PR-01 |
| [MU-02](#mu-02) | Music UI, library и разрешённый live proof | vankhu21 / Burn2288 | P1 / S5 | 3 | MU-01, AP-03, MC-02 |
| [ML-01](#ml-01) | Доказать сохранность image и восстановление доставки | Burn2288 / vankhu21 | P0 / S1 | 3 | IN-19 |
| [ML-02](#ml-02) | Общий LibraryItem для всех сохранённых типов | Burn2288 / vankhu21 | P1 / S3 | 3 | JO-03, ML-01 |
| [ML-03](#ml-03) | Пять строк Telegram и карточки Mini App | vankhu21 / Burn2288 | P1 / S5 | 3 | ML-02, MA-01 |
| [WL-01](#wl-01) | Проверить атомарный reserve/capture/release/refund | vankhu21 / Burn2288 | P0 / S7 | 5 | JO-03, PC-01 |
| [WL-02](#wl-02) | Сверка ledger и контролируемые корректировки | Burn2288 / vankhu21 | P1 / S7 | 5 | WL-01, PY-02 |
| [PY-01](#py-01) | Проверить existing Stars checkout на одном конфиге | vankhu21 / Burn2288 | P0 / S1 | 3 | IN-19, PC-01 |
| [PY-02](#py-02) | Проверить Platega callback/reconcile без Telegram checkout | vankhu21 / Burn2288 | P1 / S7 | 3 | IN-19 |
| [PY-03](#py-03) | Mini App Stars и payment history | vankhu21 / Burn2288 | P1 / S5 | 3 | AP-01, PY-01, MA-01 |
| [RF-01](#rf-01) | Адаптировать immutable attribution из донора | Burn2288 / vankhu21 | P1 / S7 | 3 | AR-01, SL-01 |
| [RF-02](#rf-02) | Rewards на capture и reversal/debt | Burn2288 / vankhu21 | P1 / S7 | 5 | RF-01, WL-01 |
| [RF-03](#rf-03) | Реферальные экраны и API обоих клиентов | vankhu21 / Burn2288 | P1 / S7 | 3 | RF-02, AP-01 |
| [SL-01](#sl-01) | Общее versioned consent и юридические MD | Burn2288 / vankhu21 | P1 / S5 | 3 | AR-01 |
| [SL-02](#sl-02) | Общий support ticket и operator workflow | Burn2288 / vankhu21 | P1 / S6 | 3 | AD-01 |
| [SL-03](#sl-03) | Support/legal/profile в двух клиентах | vankhu21 / Burn2288 | P1 / S6 | 3 | SL-01, SL-02, MA-01 |
| [SE-01](#se-01) | Threat model и security boundary suite | Burn2288 / vankhu21 | P1 / S7 | 5 | AR-01, AD-01 |
| [SE-02](#se-02) | Безопасные экспорт, логи и retention | Burn2288 / vankhu21 | P1 / S7 | 3 | SE-01, ML-02 |
| [SE-03](#se-03) | Независимая regression security двух клиентов | vankhu21 / Burn2288 | P1 / S7 | 3 | SE-02, AD-03, MA-03 |
| [TQ-01](#tq-01) | Закрепить CI profile и fixtures для интегрированной базы | Burn2288 / vankhu21 | P1 / S0 | 3 | IN-19 |
| [TQ-02](#tq-02) | Сквозная parity/regression matrix четырёх студий | vankhu21 / Burn2288 | P1 / S8 | 5 | MA-04, TA-02, WL-02, SE-03 |
| [OP-01](#op-01) | Подготовить закрытый HTTPS test endpoint Mini App | Burn2288 / vankhu21 | P1 / S5 | 3 | IN-19 |
| [OP-02](#op-02) | Проверить миграции и полный backup/restore | Burn2288 / vankhu21 | P1 / S7 | 5 | ML-02, WL-01 |
| [OP-03](#op-03) | Принять Ubuntu release candidate и shutdown | Burn2288 / vankhu21 | P1 / S8 | 5 | OP-02, JO-02, SE-02 |
| [OB-01](#ob-01) | Единая safe timeline job и provider request | Burn2288 / vankhu21 | P1 / S3 | 3 | JO-03 |
| [OB-02](#ob-02) | Операционный и финансовый read API | Burn2288 / vankhu21 | P1 / S6 | 3 | OB-01, AD-01 |
| [OB-03](#ob-03) | Dashboard отчётов и управляемые incident alerts | vankhu21 / Burn2288 | P1 / S6 | 3 | OB-02, AD-03 |
| [DC-01](#dc-01) | Устранить расхождения фундаментальных контрактов | Burn2288 / vankhu21 | P1 / S0 | 3 | IN-18 |
| [DC-02](#dc-02) | Сверить финальные runbooks с реализацией | Burn2288 / vankhu21 | P1 / S8 | 3 | OP-03, TQ-02 |
| [RL-01](#rl-01) | Согласовать scope, цены и критерии пилота | Burn2288 / vankhu21 | P1 / S8 | 3 | PR-03, WL-02, PY-03, SE-03 |
| [RL-02](#rl-02) | Провести ограниченный коммерческий user journey | vankhu21 / Burn2288 | P1 / S8 | 5 | RL-01, TQ-02, OP-03, OB-03 |
| [RL-03](#rl-03) | Release decision и синхронизация двух полных сборок | Burn2288 / vankhu21 | P1 / S8 | 3 | RL-02, DC-02 |
| [AP-01](#ap-01) | Описать существующий API OpenAPI 3.1 и auth errors | Burn2288 / vankhu21 | P1 / S5 | 3 | AR-01 |
| [AP-02](#ap-02) | Transport-neutral quote и image job command | Burn2288 / vankhu21 | P1 / S5 | 5 | AP-01, AR-02, PC-01 |
| [AP-03](#ap-03) | Owned job status, list и cancel API | Burn2288 / vankhu21 | P1 / S5 | 3 | AP-02, JO-02 |
| [AU-01](#au-01) | Согласовать audit-artifacts lifecycle и schema gate | Burn2288 / vankhu21 | P1 / S0 | 3 | IN-18 |
| [AU-02](#au-02) | Доказать передачу и повторный аудит без потери истории | vankhu21 / Burn2288 | P1 / S0 | 3 | AU-01 |

## IN — Интеграция существующего кода

### IN-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-01 |
| EPIC_ID | IN |
| Название | Утвердить порядок интеграции и freeze SHA |
| Описание | Согласовать #1, #8–#18, supersession #2/#4/#6/#7 и исключение для стэка; проверить diff и checksum миграций, ничего не сливать автоматически |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #18, `37337cc1538e26f91696be366908420d9dbb08d2`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/37337cc1538e26f91696be366908420d9dbb08d2/CONTRIBUTING.md); [.github/workflows/docs.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/37337cc1538e26f91696be366908420d9dbb08d2/.github/workflows/docs.yml) |
| Требуемые изменения | Согласовать #1, #8–#18, supersession #2/#4/#6/#7 и исключение для стэка; проверить diff и checksum миграций, ничего не сливать автоматически |
| Зависимости | нет; начинается read-only |
| Owner decisions | D-01 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | merge-base, range-diff, diff --check для каждой ступени |
| Физическое доказательство | Подписанное решение двух разработчиков, неизменные base/head refs |
| Критерий приёмки | Согласованы владельцы ретаргета и точные SHA; нет потерянных уникальных изменений; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/docs.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-02 |
| EPIC_ID | IN |
| Название | Принять документационную базу PR #1 |
| Описание | Ревью существующих правил и включение только после согласованного merge |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | DOCUMENTATION_ACCEPTED; PR #1 merged 01ef3ea; IN-01 remains PARTIAL; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #1, `008951279802ee0761da998e71c5a6e78c21a6d5`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/008951279802ee0761da998e71c5a6e78c21a6d5/CONTRIBUTING.md); [.github/workflows/docs.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/008951279802ee0761da998e71c5a6e78c21a6d5/.github/workflows/docs.yml) |
| Требуемые изменения | Ревью существующих правил и включение только после согласованного merge |
| Зависимости | IN-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Документационный CI текущего SHA; правила local sync |
| Физическое доказательство | GitHub review и merge commit после разрешения |
| Критерий приёмки | Правила вошли в main; SHA и CI опубликованы; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/docs.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 1 |
| Статус | Принято: документационная база PR #1; IN-01 остаётся PARTIAL |

### IN-08

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-08 |
| EPIC_ID | IN |
| Название | Интегрировать PR #8 и доказать supersession ранних пилотов |
| Описание | Сохранить исходники/историю #2/#4/#6/#7; убрать только доказанное дублирование интеграции |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #8, `eaadb892227e6b731e4cebccb071b23c1b209b3b`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/eaadb892227e6b731e4cebccb071b23c1b209b3b/CONTRIBUTING.md); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/eaadb892227e6b731e4cebccb071b23c1b209b3b/.github/workflows/test.yml) |
| Требуемые изменения | Сохранить исходники/историю #2/#4/#6/#7; убрать только доказанное дублирование интеграции |
| Зависимости | IN-02 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Полный PostgreSQL CI; image validation/recovery; 001–012 |
| Физическое доказательство | Одобренный diff, дерево миграций, review и merge SHA |
| Критерий приёмки | В принятой main есть исходный image slice, уникальные тесты сохранены; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-09

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-09 |
| EPIC_ID | IN |
| Название | Провести отдельную приёмку и интеграцию PR #9: Veo video |
| Описание | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta video.py |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #9, `b5c1368cf9663bd0be43a1e9c0b65816c51fe61d`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/b5c1368cf9663bd0be43a1e9c0b65816c51fe61d/CONTRIBUTING.md); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/b5c1368cf9663bd0be43a1e9c0b65816c51fe61d/.github/workflows/test.yml) |
| Требуемые изменения | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta video.py |
| Зависимости | IN-08 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Полный CI на новом SHA + профильные тесты video.py; миграционные checksum |
| Физическое доказательство | Review, новый base/head diff, checks и merge SHA |
| Критерий приёмки | Предшественник принят; текущий PR прошёл ревью и CI после ретаргета; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 1 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-10

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-10 |
| EPIC_ID | IN |
| Название | Провести отдельную приёмку и интеграцию PR #10: AnyModel registry |
| Описание | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel.py |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #10, `eaa1a6fdc6eb19ed61a231ad05c9eb412c0d2496`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/eaa1a6fdc6eb19ed61a231ad05c9eb412c0d2496/CONTRIBUTING.md); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/eaa1a6fdc6eb19ed61a231ad05c9eb412c0d2496/.github/workflows/test.yml) |
| Требуемые изменения | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel.py |
| Зависимости | IN-09 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Полный CI на новом SHA + профильные тесты anymodel.py; миграционные checksum |
| Физическое доказательство | Review, новый base/head diff, checks и merge SHA |
| Критерий приёмки | Предшественник принят; текущий PR прошёл ревью и CI после ретаргета; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 1 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-11

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-11 |
| EPIC_ID | IN |
| Название | Провести отдельную приёмку и интеграцию PR #11: FIBO async image |
| Описание | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel_image_jobs.py |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #11, `99c091476de23d998a3101bb0e39d199552f8838`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/99c091476de23d998a3101bb0e39d199552f8838/CONTRIBUTING.md); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/99c091476de23d998a3101bb0e39d199552f8838/.github/workflows/test.yml) |
| Требуемые изменения | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel_image_jobs.py |
| Зависимости | IN-10 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Полный CI на новом SHA + профильные тесты anymodel_image_jobs.py; миграционные checksum |
| Физическое доказательство | Review, новый base/head diff, checks и merge SHA |
| Критерий приёмки | Предшественник принят; текущий PR прошёл ревью и CI после ретаргета; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 1 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-12

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-12 |
| EPIC_ID | IN |
| Название | Провести отдельную приёмку и интеграцию PR #12: Grok video |
| Описание | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel_video.py |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #12, `de4e5f1183ec9ee7b079977fda68f99e02d00dd7`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/de4e5f1183ec9ee7b079977fda68f99e02d00dd7/CONTRIBUTING.md); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/de4e5f1183ec9ee7b079977fda68f99e02d00dd7/.github/workflows/test.yml) |
| Требуемые изменения | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel_video.py |
| Зависимости | IN-11 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Полный CI на новом SHA + профильные тесты anymodel_video.py; миграционные checksum |
| Физическое доказательство | Review, новый base/head diff, checks и merge SHA |
| Критерий приёмки | Предшественник принят; текущий PR прошёл ревью и CI после ретаргета; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 1 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-13

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-13 |
| EPIC_ID | IN |
| Название | Провести отдельную приёмку и интеграцию PR #13: AnyModel speech |
| Описание | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel_speech.py |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #13, `6c82761c5e4c42e1129934884c5b23030df4e090`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/6c82761c5e4c42e1129934884c5b23030df4e090/CONTRIBUTING.md); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/6c82761c5e4c42e1129934884c5b23030df4e090/.github/workflows/test.yml) |
| Требуемые изменения | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel_speech.py |
| Зависимости | IN-12 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Полный CI на новом SHA + профильные тесты anymodel_speech.py; миграционные checksum |
| Физическое доказательство | Review, новый base/head diff, checks и merge SHA |
| Критерий приёмки | Предшественник принят; текущий PR прошёл ревью и CI после ретаргета; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 1 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-14

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-14 |
| EPIC_ID | IN |
| Название | Провести отдельную приёмку и интеграцию PR #14: Welcome/navigation |
| Описание | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta telegram.py |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #14, `742db84eb8663d5a4b7a7e50b2c10825e7b18a87`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/742db84eb8663d5a4b7a7e50b2c10825e7b18a87/CONTRIBUTING.md); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/742db84eb8663d5a4b7a7e50b2c10825e7b18a87/.github/workflows/test.yml) |
| Требуемые изменения | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta telegram.py |
| Зависимости | IN-13 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Полный CI на новом SHA + профильные тесты telegram.py; миграционные checksum |
| Физическое доказательство | Review, новый base/head diff, checks и merge SHA |
| Критерий приёмки | Предшественник принят; текущий PR прошёл ревью и CI после ретаргета; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 1 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-15

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-15 |
| EPIC_ID | IN |
| Название | Провести отдельную приёмку и интеграцию PR #15: Task progress |
| Описание | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta progress.py |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #15, `5162e8e58ba91564c7989617567e24a18aa5f3da`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/5162e8e58ba91564c7989617567e24a18aa5f3da/CONTRIBUTING.md); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/5162e8e58ba91564c7989617567e24a18aa5f3da/.github/workflows/test.yml) |
| Требуемые изменения | Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta progress.py |
| Зависимости | IN-14 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Полный CI на новом SHA + профильные тесты progress.py; миграционные checksum |
| Физическое доказательство | Review, новый base/head diff, checks и merge SHA |
| Критерий приёмки | Предшественник принят; текущий PR прошёл ревью и CI после ретаргета; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 1 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-16

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-16 |
| EPIC_ID | IN |
| Название | Принять PR #16: финансы, каталог и Telegram Admin |
| Описание | Разобрать большой накопленный PR по тестовым областям, сохранить авторство; не переписывать Pricing/Wallet/Platega |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #16, `76a030a5dc32ccf79b9c9a8393f1807d7df9d791`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/76a030a5dc32ccf79b9c9a8393f1807d7df9d791/CONTRIBUTING.md); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/76a030a5dc32ccf79b9c9a8393f1807d7df9d791/.github/workflows/test.yml) |
| Требуемые изменения | Разобрать большой накопленный PR по тестовым областям, сохранить авторство; не переписывать Pricing/Wallet/Platega |
| Зависимости | IN-15 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Миграции 019–036, admin deny, tariff/hold/refusal/topups/broadcast lock isolation |
| Физическое доказательство | Review каждой области, CI, migration doctor и merge SHA |
| Критерий приёмки | Нет миграционных коллизий; финансовые и admin-регрессии текущего SHA опубликованы; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-17

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-17 |
| EPIC_ID | IN |
| Название | Принять PR #17: Mini App и новый inbox |
| Описание | Ретаргет и регрессия Mini App, публичного image policy, inbox/defer; сохранить исправления поздних SHA |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/CONTRIBUTING.md); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/.github/workflows/test.yml) |
| Требуемые изменения | Ретаргет и регрессия Mini App, публичного image policy, inbox/defer; сохранить исправления поздних SHA |
| Зависимости | IN-16 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | 037–039, штатный CLODEX с HTTP fixture, replay/session/IDOR, inbox two-chat |
| Физическое доказательство | Точный CI 397-test baseline + актуальный полный прогон и review |
| Критерий приёмки | Новые проверки прошли; старый вывод о sync polling не перенесён без воспроизведения; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-18

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-18 |
| EPIC_ID | IN |
| Название | Согласовать фундамент и план как отдельные docs PR |
| Описание | Review #18 и TASK-PLAN-001; устранить расхождения единиц, этапов, env-названий через ADR; перенос только после approvals |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #18, `37337cc1538e26f91696be366908420d9dbb08d2`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/37337cc1538e26f91696be366908420d9dbb08d2/CONTRIBUTING.md); [.github/workflows/docs.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/37337cc1538e26f91696be366908420d9dbb08d2/.github/workflows/docs.yml) |
| Требуемые изменения | Review #18 и TASK-PLAN-001; устранить расхождения единиц, этапов, env-названий через ADR; перенос только после approvals |
| Зависимости | IN-02 |
| Owner decisions | D-01 D-02 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Docs CI, ссылки, контрактные ID, DAG и manifest schema |
| Физическое доказательство | Peer review и решение владельца о плане; docs merge SHA |
| Критерий приёмки | Назначения согласованы; DESIGN_DRAFT не назван внедрённым контрактом; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/docs.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IN-19

| Поле | Содержание |
| --- | --- |
| TASK_ID | IN-19 |
| EPIC_ID | IN |
| Название | Синхронизировать и запустить целую принятую сборку |
| Описание | Проверить всю main и код коллеги, обе машины независимо; не переносить незавершённые dev-коммиты в main |
| Приоритет | P0 |
| Этап | S0 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/CONTRIBUTING.md); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/.github/workflows/test.yml) |
| Требуемые изменения | Проверить всю main и код коллеги, обе машины независимо; не переносить незавершённые dev-коммиты в main |
| Зависимости | IN-17, IN-18 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | fetch; clean tree; ff-only; HEAD=origin/main; setup/test migrations в изолированной БД |
| Физическое доказательство | Два BRANCH_SYNC с SHA и health всей сборки |
| Критерий приёмки | Обе локальные main равны принятому main; недоступная машина честно NOT_PERFORMED; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия CONTRIBUTING.md, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## AR — Архитектура и общие application services

### AR-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | AR-01 |
| EPIC_ID | AR |
| Название | Зафиксировать реальные границы модулей и транзакций |
| Описание | Уточнить MODULAR_SYSTEM по интегрированному коду, определить query/command порты без переноса файлов ради структуры |
| Приоритет | P1 |
| Этап | S3 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-001, C-008, C-012, C-024, C-025; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/task_launch.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_launch.py); [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py) |
| Требуемые изменения | Уточнить MODULAR_SYSTEM по интегрированному коду, определить query/command порты без переноса файлов ради структуры |
| Зависимости | JO-03 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Dependency checks, одна транзакция quote+reserve+job |
| Физическое доказательство | Трасса одной команды из Telegram и HTTP с общими user/job/ledger |
| Критерий приёмки | Контракт одобрен; нет отдельного wallet или registry; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/core.py, src/elevenbot/task_launch.py, miniapp/backend/web.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### AR-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | AR-02 |
| EPIC_ID | AR |
| Название | Изолировать транспортные команды от финансовых деталей |
| Описание | Вынести только оставшиеся прямые UI-записи через существующие services; совместимость callbacks |
| Приоритет | P1 |
| Этап | S3 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-001, C-008, C-012, C-024, C-025; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/task_launch.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_launch.py); [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py) |
| Требуемые изменения | Вынести только оставшиеся прямые UI-записи через существующие services; совместимость callbacks |
| Зависимости | AR-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Telegram/HTTP parity и crash на commit boundary |
| Физическое доказательство | Одинаковые persistent эффекты двух клиентов |
| Критерий приёмки | UI не управляет провайдерским payload или ledger напрямую; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/core.py, src/elevenbot/task_launch.py, miniapp/backend/web.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## TG — Telegram Bot UX

### TG-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | TG-01 |
| EPIC_ID | TG |
| Название | Перевести главное меню и Back без потери старых маршрутов |
| Описание | Открыть студию/кабинет/информация, совместимые старые callbacks, edit fallback; referrals/support честно закрыты до API |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-001, C-002, C-004, C-017; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/telegram.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/telegram.py); [src/elevenbot/navigation.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/navigation.py); [src/elevenbot/progress.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/progress.py); [tests/test_navigation.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests/test_navigation.py) |
| Требуемые изменения | Открыть студию/кабинет/информация, совместимые старые callbacks, edit fallback; referrals/support честно закрыты до API |
| Зависимости | IN-19 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | PR-01, JO-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Два устройства, duplicate, long labels, edit failure, admin routes |
| Физическое доказательство | Запись Android/Desktop на тестовом боте + route table |
| Критерий приёмки | Один актуальный экран, Back сохраняет страницу; legacy маршруты работают; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/telegram.py, src/elevenbot/navigation.py, src/elevenbot/progress.py, tests/test_navigation.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### TG-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | TG-02 |
| EPIC_ID | TG |
| Название | Подключить документы и текущий consent к Telegram UX |
| Описание | Отправлять оба versioned MD как файлы, запретить устаревшее согласие и покупку при сбое доставки |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-001, C-002, C-004, C-017; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/telegram.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/telegram.py); [src/elevenbot/navigation.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/navigation.py); [src/elevenbot/progress.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/progress.py); [tests/test_navigation.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests/test_navigation.py) |
| Требуемые изменения | Отправлять оба versioned MD как файлы, запретить устаревшее согласие и покупку при сбое доставки |
| Зависимости | SL-01, TG-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Missing file, old callback, repeat /start, active paid job |
| Физическое доказательство | Видеопроход принятия и перепринятия версии |
| Критерий приёмки | Нет обхода gate, кошелёк и jobs не сбрасываются; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/telegram.py, src/elevenbot/navigation.py, src/elevenbot/progress.py, tests/test_navigation.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### TG-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | TG-03 |
| EPIC_ID | TG |
| Название | Личный кабинет и история общего кошелька |
| Описание | Показать доступный/резерв, профиль, статусы заказов и историю через общий query port |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-001, C-002, C-004, C-017; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/telegram.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/telegram.py); [src/elevenbot/navigation.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/navigation.py); [src/elevenbot/progress.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/progress.py); [tests/test_navigation.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests/test_navigation.py) |
| Требуемые изменения | Показать доступный/резерв, профиль, статусы заказов и историю через общий query port |
| Зависимости | PY-01, TG-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Pending не зачислен, pagination, два аккаунта |
| Физическое доказательство | Сверка экранов с ledger на тестовых данных |
| Критерий приёмки | Баланс и история совпадают с Mini App и сервером; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/telegram.py, src/elevenbot/navigation.py, src/elevenbot/progress.py, tests/test_navigation.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## MA — Telegram Mini App user

### MA-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | MA-01 |
| EPIC_ID | MA |
| Название | Принять существующую Mini App в Telegram по HTTPS |
| Описание | Сохранить read-mostly MVP, проверить launch c signed initData и fallback reply-keyboard; исправлять только подтверждённое |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-003, C-005, C-024; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [miniapp/frontend/app.js](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/frontend/app.js); [miniapp/frontend/style.css](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/frontend/style.css); [miniapp/tests/test_miniapp.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/tests/test_miniapp.py) |
| Требуемые изменения | Сохранить read-mostly MVP, проверить launch c signed initData и fallback reply-keyboard; исправлять только подтверждённое |
| Зависимости | IN-19, OP-01 |
| Owner decisions | D-05 |
| Допускаемый параллелизм | JO-02 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Два аккаунта; Android/Desktop; revoke/expiry/theme/catalogue/works |
| Физическое доказательство | Запись реальных WebView и HTTP owner-deny, без raw initData |
| Критерий приёмки | Оба клиента видят свой баланс/работы; чужой файл закрыт; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия miniapp/backend/web.py, miniapp/frontend/app.js, miniapp/frontend/style.css, miniapp/tests/test_miniapp.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### MA-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | MA-02 |
| EPIC_ID | MA |
| Название | Форма image quote и явное подтверждение |
| Описание | Существующий frontend потребляет server schemas и quote; loading/error/expired/insufficient states |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-003, C-005, C-024; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [miniapp/frontend/app.js](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/frontend/app.js); [miniapp/frontend/style.css](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/frontend/style.css); [miniapp/tests/test_miniapp.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/tests/test_miniapp.py) |
| Требуемые изменения | Существующий frontend потребляет server schemas и quote; loading/error/expired/insufficient states |
| Зависимости | AP-02, MA-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Disabled model, stale quote, double click, mobile keyboard |
| Физическое доказательство | Видео quote→confirm на fixture без оптимистического success |
| Критерий приёмки | Цена только с сервера, один semantic request ID на повтор; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия miniapp/backend/web.py, miniapp/frontend/app.js, miniapp/frontend/style.css, miniapp/tests/test_miniapp.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### MA-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | MA-03 |
| EPIC_ID | MA |
| Название | Карточка job и безопасная отмена |
| Описание | Показывать persisted status/uncertain и cancel только по policy; повтор не делает новый POST |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-003, C-005, C-024; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [miniapp/frontend/app.js](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/frontend/app.js); [miniapp/frontend/style.css](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/frontend/style.css); [miniapp/tests/test_miniapp.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/tests/test_miniapp.py) |
| Требуемые изменения | Показывать persisted status/uncertain и cancel только по policy; повтор не делает новый POST |
| Зависимости | MA-02, AP-03, JO-02 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Reload mid-job, cancel race, expired session |
| Физическое доказательство | Один job виден в Telegram и Mini App после рестарта |
| Критерий приёмки | Нет выдуманных процентов и успешной отмены при неизвестном провайдере; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия miniapp/backend/web.py, miniapp/frontend/app.js, miniapp/frontend/style.css, miniapp/tests/test_miniapp.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### MA-04

| Поле | Содержание |
| --- | --- |
| TASK_ID | MA-04 |
| EPIC_ID | MA |
| Название | Довести пользовательский parity и доступность |
| Описание | Собрать уже готовые экраны, исправить parity gaps, focus/contrast/reduced motion/narrow width |
| Приоритет | P1 |
| Этап | S8 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-003, C-005, C-024; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [miniapp/frontend/app.js](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/frontend/app.js); [miniapp/frontend/style.css](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/frontend/style.css); [miniapp/tests/test_miniapp.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/tests/test_miniapp.py) |
| Требуемые изменения | Собрать уже готовые экраны, исправить parity gaps, focus/contrast/reduced motion/narrow width |
| Зависимости | MA-03, VI-02, VO-02, MU-02, ML-03, RF-03, SL-03, PY-03 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Feature-by-feature bot/Mini App matrix, Android/Desktop, offline/error |
| Физическое доказательство | Записи полного пути каждого из четырёх типов |
| Критерий приёмки | Все обязательные пути представлены; ограничения явно видны; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия miniapp/backend/web.py, miniapp/frontend/app.js, miniapp/frontend/style.css, miniapp/tests/test_miniapp.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## AD — Mini App Admin

### AD-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | AD-01 |
| EPIC_ID | AD |
| Название | Серверные admin roles, chooser и read-only обзор |
| Описание | Добавить HTTP RBAC через общую identity; согласовать ADMIN_TELEGRAM_IDS alias; не переносить process-local парольную сессию |
| Приоритет | P1 |
| Этап | S6 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-003, C-020, C-021, C-026; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [miniapp/frontend/app.js](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/frontend/app.js); [src/elevenbot/admin_access.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/admin_access.py) |
| Требуемые изменения | Добавить HTTP RBAC через общую identity; согласовать ADMIN_TELEGRAM_IDS alias; не переносить process-local парольную сессию |
| Зависимости | AP-01, TA-01 |
| Owner decisions | D-04 |
| Допускаемый параллелизм | VI-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Forged role, allowlist/no role, direct /admin, revocation |
| Физическое доказательство | Матрица HTTP deny + разрешённая read-only сессия |
| Критерий приёмки | Все admin endpoints default deny независимо от скрытия UI; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия miniapp/backend/web.py, miniapp/frontend/app.js, src/elevenbot/admin_access.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### AD-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | AD-02 |
| EPIC_ID | AD |
| Название | Одна typed settings-мутация с аудитом и rollback |
| Описание | Whitelist low-risk visibility setting; preview/version/CAS/confirm/idempotency; без ключей и financial SQL |
| Приоритет | P1 |
| Этап | S6 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-003, C-020, C-021, C-026; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [miniapp/frontend/app.js](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/frontend/app.js); [src/elevenbot/admin_access.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/admin_access.py) |
| Требуемые изменения | Whitelist low-risk visibility setting; preview/version/CAS/confirm/idempotency; без ключей и financial SQL |
| Зависимости | AD-01, MC-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Stale version, double confirm, invalid config, role removal |
| Физическое доказательство | Before/after audit и rollback на тестовом сервере |
| Критерий приёмки | Изменение атомарно, старое значение восстановимо, аудит неизменяем; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия miniapp/backend/web.py, miniapp/frontend/app.js, src/elevenbot/admin_access.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### AD-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | AD-03 |
| EPIC_ID | AD |
| Название | Графические admin экраны по общему API |
| Описание | Добавлять users/jobs/queue/providers/models/pricing/payments/ledger/reports/audit по готовым read/write capabilities |
| Приоритет | P1 |
| Этап | S6 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-003, C-020, C-021, C-026; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [miniapp/frontend/app.js](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/frontend/app.js); [src/elevenbot/admin_access.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/admin_access.py) |
| Требуемые изменения | Добавлять users/jobs/queue/providers/models/pricing/payments/ledger/reports/audit по готовым read/write capabilities |
| Зависимости | AD-02, OB-02 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | RF-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Permissions per view, no plaintext secrets, dangerous action preview |
| Физическое доказательство | Ручная диагностика job ID без SQL и скринкаст rollback |
| Критерий приёмки | Все области имеют рабочий read view; опасные записи только через разрешённые команды; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия miniapp/backend/web.py, miniapp/frontend/app.js, src/elevenbot/admin_access.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## TA — Telegram Admin Edition

### TA-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | TA-01 |
| EPIC_ID | TA |
| Название | Зафиксировать compatibility inventory Admin Edition |
| Описание | Инвентаризация команд, scopes, экранов, sessions, broadcasts, тарифов, платежей и deny-тестов PR #16 без редактирования общего кода |
| Приоритет | P1 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-019, C-021; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/admin_access.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/admin_access.py); [src/elevenbot/tariff_admin.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/tariff_admin.py); [src/elevenbot/topup_ui.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/topup_ui.py); [src/elevenbot/broadcasts.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/broadcasts.py) |
| Требуемые изменения | Инвентаризация команд, scopes, экранов, sessions, broadcasts, тарифов, платежей и deny-тестов PR #16 без редактирования общего кода |
| Зависимости | IN-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | DC-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Проверить tests и immutable source refs, сопоставить audit findings |
| Физическое доказательство | Каталог команд с SHA и матрицей прав |
| Критерий приёмки | Каждая существующая admin-команда имеет регрессию/ограничение; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/admin_access.py, src/elevenbot/tariff_admin.py, src/elevenbot/topup_ui.py, src/elevenbot/broadcasts.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### TA-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | TA-02 |
| EPIC_ID | TA |
| Название | Сохранить Telegram admin при общих admin services |
| Описание | Только миграция вызовов settings на общий service; старые команды сохраняются |
| Приоритет | P1 |
| Этап | S6 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-019, C-021; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/admin_access.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/admin_access.py); [src/elevenbot/tariff_admin.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/tariff_admin.py); [src/elevenbot/topup_ui.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/topup_ui.py); [src/elevenbot/broadcasts.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/broadcasts.py) |
| Требуемые изменения | Только миграция вызовов settings на общий service; старые команды сохраняются |
| Зависимости | AD-02, TA-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Logout/stale button, unauthorized ID, два чата, broadcast lock |
| Физическое доказательство | Telegram admin и Mini App меняют одну настройку с единым audit |
| Критерий приёмки | Нет изменения баланса или навигации другого пользователя от admin-действия; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/admin_access.py, src/elevenbot/tariff_admin.py, src/elevenbot/topup_ui.py, src/elevenbot/broadcasts.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## PR — AI Provider Integrations

### PR-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | PR-01 |
| EPIC_ID | PR |
| Название | Расширить existing registry нормализованным manifest |
| Описание | Ввести schema/version/verified hosts/credential references и normalize sync/async errors поверх ProviderRegistry |
| Приоритет | P1 |
| Этап | S4 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-013, C-014, C-026, C-029; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/aggregate.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/aggregate.py); [src/elevenbot/provider_execution.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/provider_execution.py); [src/elevenbot/fal.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/fal.py); [tests/test_provider_extensibility.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests/test_provider_extensibility.py) |
| Требуемые изменения | Ввести schema/version/verified hosts/credential references и normalize sync/async errors поверх ProviderRegistry |
| Зависимости | AR-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | TG-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Две adapter-family fixtures, malformed output, NEEDS_ADAPTER |
| Физическое доказательство | Загрузка manifests без изменений Telegram/frontend |
| Критерий приёмки | Новый протокол требует reviewed adapter, нет произвольных scripts/URLs; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/aggregate.py, src/elevenbot/provider_execution.py, src/elevenbot/fal.py, tests/test_provider_extensibility.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### PR-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | PR-02 |
| EPIC_ID | PR |
| Название | Версии, health, staging и rollback провайдера |
| Описание | Добавить missing health/circuit/budgets/staging, сохранить pinned версии in-flight jobs |
| Приоритет | P1 |
| Этап | S4 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-013, C-014, C-026, C-029; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/aggregate.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/aggregate.py); [src/elevenbot/provider_execution.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/provider_execution.py); [src/elevenbot/fal.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/fal.py); [tests/test_provider_extensibility.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests/test_provider_extensibility.py) |
| Требуемые изменения | Добавить missing health/circuit/budgets/staging, сохранить pinned версии in-flight jobs |
| Зависимости | PR-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Disable/rollback while polling, key redaction, stale discovery |
| Физическое доказательство | Изолированный отказ одного провайдера при успешном другом |
| Критерий приёмки | Отключение не теряет jobs; unknown paid outcome без failover; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/aggregate.py, src/elevenbot/provider_execution.py, src/elevenbot/fal.py, tests/test_provider_extensibility.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### PR-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | PR-03 |
| EPIC_ID | PR |
| Название | Сверить live capability каждого включаемого адаптера |
| Описание | Для CLODEX, AnyModel, Fal проверить только утверждённые capability/model протоколы, цены и реальные ответы |
| Приоритет | P1 |
| Этап | S4 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-013, C-014, C-026, C-029; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/aggregate.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/aggregate.py); [src/elevenbot/provider_execution.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/provider_execution.py); [src/elevenbot/fal.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/fal.py); [tests/test_provider_extensibility.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests/test_provider_extensibility.py) |
| Требуемые изменения | Для CLODEX, AnyModel, Fal проверить только утверждённые capability/model протоколы, цены и реальные ответы |
| Зависимости | PR-02, IM-02 |
| Owner decisions | D-06 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Contract fixtures + отдельные разрешённые live probes |
| Физическое доказательство | Provider request IDs, redacted receipts, валидные сохранённые outputs |
| Критерий приёмки | Каждая продаваемая capability имеет свой live proof либо выключена; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/aggregate.py, src/elevenbot/provider_execution.py, src/elevenbot/fal.py, tests/test_provider_extensibility.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## MC — AI Model Catalog

### MC-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | MC-01 |
| EPIC_ID | MC |
| Название | Версионировать модель и capabilities без второго каталога |
| Описание | Расширить approved_models, входные схемы/лимиты и stage/publish; старые quotes pin версию |
| Приоритет | P1 |
| Этап | S4 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-006, C-014, C-015, C-029; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/model_policy.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/model_policy.py); [src/elevenbot/discovery.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/discovery.py); [src/elevenbot/aggregate.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/aggregate.py) |
| Требуемые изменения | Расширить approved_models, входные схемы/лимиты и stage/publish; старые quotes pin версию |
| Зависимости | PR-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Duplicate external key, disable, stale snapshot, cached recovery |
| Физическое доказательство | Одна модель публикуется и исчезает в обоих клиентах |
| Критерий приёмки | Неизвестные параметры запрещены, исторические jobs читаются; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/model_policy.py, src/elevenbot/discovery.py, src/elevenbot/aggregate.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### MC-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | MC-02 |
| EPIC_ID | MC |
| Название | Общие карточки и schema-driven параметры каталога |
| Описание | Убрать только оставшееся дублирование доступности/параметров из UI; сохранить existing labels |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-006, C-014, C-015, C-029; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/model_policy.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/model_policy.py); [src/elevenbot/discovery.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/discovery.py); [src/elevenbot/aggregate.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/aggregate.py) |
| Требуемые изменения | Убрать только оставшееся дублирование доступности/параметров из UI; сохранить existing labels |
| Зависимости | MC-01, MA-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | AP-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Price parity, empty/offline provider, pagination и параметры |
| Физическое доказательство | Одна публикация видна в боте/Mini App без хардкода |
| Критерий приёмки | UI не показывает недопущенные модели; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/model_policy.py, src/elevenbot/discovery.py, src/elevenbot/aggregate.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## PC — Pricing

### PC-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | PC-01 |
| EPIC_ID | PC |
| Название | Уточнить токены, XTR, RUB и immutable quote |
| Описание | Сохранить existing Pricing; устранить подтверждённые неоднозначности units/rounding/expiry и maximum variable cost |
| Приоритет | P0 |
| Этап | S1 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-007, C-008, C-015; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/pricing.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/pricing.py); [src/elevenbot/tariff_admin.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/tariff_admin.py); [src/elevenbot/model_policy.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/model_policy.py) |
| Требуемые изменения | Сохранить existing Pricing; устранить подтверждённые неоднозначности units/rounding/expiry и maximum variable cost |
| Зависимости | IN-19 |
| Owner decisions | D-02 |
| Допускаемый параллелизм | ML-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Concurrent tariff publish, stale/cross-user quote, bounds/rounding |
| Физическое доказательство | DB quote snapshot до/после смены тарифа |
| Критерий приёмки | Старый quote/job не пересчитан; float не определяет списание; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/pricing.py, src/elevenbot/tariff_admin.py, src/elevenbot/model_policy.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### PC-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | PC-02 |
| EPIC_ID | PC |
| Название | Preview и publish versioned тарифов |
| Описание | Развить tariff_admin через typed admin API; cost estimate отдельно от sale, audit/rollback |
| Приоритет | P1 |
| Этап | S6 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-007, C-008, C-015; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/pricing.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/pricing.py); [src/elevenbot/tariff_admin.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/tariff_admin.py); [src/elevenbot/model_policy.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/model_policy.py) |
| Требуемые изменения | Развить tariff_admin через typed admin API; cost estimate отдельно от sale, audit/rollback |
| Зависимости | PC-01, AD-02 |
| Owner decisions | D-02 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Provider/model overrides, currency mismatch, rollback |
| Физическое доказательство | Админ preview не тратит кредиты, publish сохраняет старые quotes |
| Критерий приёмки | Единый расчёт цены в обоих клиентах и отчётах; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/pricing.py, src/elevenbot/tariff_admin.py, src/elevenbot/model_policy.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## JO — Generation Orchestration

### JO-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | JO-01 |
| EPIC_ID | JO |
| Название | Доказать topology и закрыть missing lease/fencing |
| Описание | Сравнить worker/jobs и task_dispatch/pilot loops; добавить только недостающие durable claim/heartbeat/fence/limits |
| Приоритет | P0 |
| Этап | S2 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-012, C-018, C-025; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/task_launch.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_launch.py); [src/elevenbot/worker.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/worker.py); [src/elevenbot/inbox.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/inbox.py); [src/elevenbot/__main__.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/__main__.py) |
| Требуемые изменения | Сравнить worker/jobs и task_dispatch/pilot loops; добавить только недостающие durable claim/heartbeat/fence/limits |
| Зависимости | IM-02 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | TG-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Kill до POST/после accept/до commit, два workers, stale fence |
| Физическое доказательство | PostgreSQL process-kill trace с одним reserve/capture/provider POST |
| Критерий приёмки | Старый worker не завершает новый claim; unknown не повторён; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/task_launch.py, src/elevenbot/worker.py, src/elevenbot/inbox.py, src/elevenbot/__main__.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### JO-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | JO-02 |
| EPIC_ID | JO |
| Название | Bounded queue, fairness, cancellation и shutdown |
| Описание | Унифицировать resource budgets/backpressure/cancel policy и graceful shutdown без удаления пилотных guard |
| Приоритет | P0 |
| Этап | S2 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-012, C-018, C-025; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/task_launch.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_launch.py); [src/elevenbot/worker.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/worker.py); [src/elevenbot/inbox.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/inbox.py); [src/elevenbot/__main__.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/__main__.py) |
| Требуемые изменения | Унифицировать resource budgets/backpressure/cancel policy и graceful shutdown без удаления пилотных guard |
| Зависимости | JO-01 |
| Owner decisions | D-09 |
| Допускаемый параллелизм | MA-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | 10/50/100 users/requests, hot user, cancellation races, shutdown |
| Физическое доказательство | Метрики p95/throughput/queue/DB locks на эмуляторе |
| Критерий приёмки | Лимиты соблюдены, нет starving/duplicate charge; live load не заявлен; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/task_launch.py, src/elevenbot/worker.py, src/elevenbot/inbox.py, src/elevenbot/__main__.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### JO-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | JO-03 |
| EPIC_ID | JO |
| Название | Единый job projection и состояния четырёх типов |
| Описание | Совместимая проекция существующих type tables и recovery, общий stable job_id; без destructive rewrite |
| Приоритет | P1 |
| Этап | S3 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-012, C-018, C-025; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/task_launch.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_launch.py); [src/elevenbot/worker.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/worker.py); [src/elevenbot/inbox.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/inbox.py); [src/elevenbot/__main__.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/__main__.py) |
| Требуемые изменения | Совместимая проекция существующих type tables и recovery, общий stable job_id; без destructive rewrite |
| Зависимости | JO-02 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Sync/async/uncertain fixtures по четырём типам, старые IDs |
| Физическое доказательство | Восстановленные исторические jobs видны через единый status query |
| Критерий приёмки | State map и event IDs документированы; никаких дублирующих денег; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/task_launch.py, src/elevenbot/worker.py, src/elevenbot/inbox.py, src/elevenbot/__main__.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## IM — Image Studio

### IM-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | IM-01 |
| EPIC_ID | IM |
| Название | Повторить штатный image путь с ordinary user |
| Описание | Использовать исправленный public image policy PR #17, один конфиг/DB и настоящий adapter с HTTP fixture; фиксировать дефект только после воспроизведения |
| Приоритет | P0 |
| Этап | S1 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-007, C-012, C-013, C-016, C-018; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/interaction.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/interaction.py); [src/elevenbot/anymodel_image_jobs.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/anymodel_image_jobs.py); [tests/test_image_validation.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests/test_image_validation.py); [tests/test_public_image_topup.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests/test_public_image_topup.py) |
| Требуемые изменения | Использовать исправленный public image policy PR #17, один конфиг/DB и настоящий adapter с HTTP fixture; фиксировать дефект только после воспроизведения |
| Зависимости | IN-19, PC-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Topup fixture→hold→image→library→restart; duplicates; corrupt media |
| Физическое доказательство | Один provider POST, один settlement и сохранённый checksum; без платных вызовов |
| Критерий приёмки | Старый blocker 6504bd1 не объявляется текущим без reproduction; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/interaction.py, src/elevenbot/anymodel_image_jobs.py, tests/test_image_validation.py, tests/test_public_image_topup.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### IM-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | IM-02 |
| EPIC_ID | IM |
| Название | Три live изображения и временный отказ |
| Описание | Контролируемый provider/Telegram прогон с IDs/stages, форматом/сохранением/library/restart; лимиты не повышать вслепую |
| Приоритет | P0 |
| Этап | S1 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-007, C-012, C-013, C-016, C-018; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/interaction.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/interaction.py); [src/elevenbot/anymodel_image_jobs.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/anymodel_image_jobs.py); [tests/test_image_validation.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests/test_image_validation.py); [tests/test_public_image_topup.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests/test_public_image_topup.py) |
| Требуемые изменения | Контролируемый provider/Telegram прогон с IDs/stages, форматом/сохранением/library/restart; лимиты не повышать вслепую |
| Зависимости | IM-01, ML-01 |
| Owner decisions | D-06 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Три последовательных успеха; temporary failure; sendPhoto/document по необходимости |
| Физическое доказательство | Job/provider IDs, размеры/checksums, receipt, owner/library и проводки до/после рестарта |
| Критерий приёмки | 3 success + failure; no double debit; API receipt отдельно от USER_VISIBLE_NOT_PROVEN; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/interaction.py, src/elevenbot/anymodel_image_jobs.py, tests/test_image_validation.py, tests/test_public_image_topup.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## VI — Video Studio

### VI-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | VI-01 |
| EPIC_ID | VI |
| Название | Согласовать video create/poll и финальный расчёт |
| Описание | Расширить существующие Veo/Grok jobs для общего status/cancel/parameters, сохранить provider handles |
| Приоритет | P1 |
| Этап | S3 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-006, C-012, C-013, C-016; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/video.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/video.py); [src/elevenbot/anymodel_video.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/anymodel_video.py) |
| Требуемые изменения | Расширить существующие Veo/Grok jobs для общего status/cancel/parameters, сохранить provider handles |
| Зависимости | JO-03, PC-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | AD-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Duration/resolution bounds, delayed polling, restart, invalid MP4 |
| Физическое доказательство | Async process fixture, one create, valid video checksum |
| Критерий приёмки | Нет повторного create при timeout; итоговая цена pinned; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/video.py, src/elevenbot/anymodel_video.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### VI-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | VI-02 |
| EPIC_ID | VI |
| Название | Video формы двух клиентов и разрешённая приёмка |
| Описание | Переиспользовать video forms; подключить Mini App quote/status/library |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-006, C-012, C-013, C-016; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/video.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/video.py); [src/elevenbot/anymodel_video.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/anymodel_video.py) |
| Требуемые изменения | Переиспользовать video forms; подключить Mini App quote/status/library |
| Зависимости | VI-01, AP-03, MC-02 |
| Owner decisions | D-06 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Недопустимые параметры/credits, restart, Telegram delivery |
| Физическое доказательство | Один разрешённый live video по продаваемой capability + записи UI |
| Критерий приёмки | Video доступно из библиотеки обоих клиентов; live без доступа BLOCKED; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/video.py, src/elevenbot/anymodel_video.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## VO — Voice Studio

### VO-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | VO-01 |
| EPIC_ID | VO |
| Название | Нормализовать существующие TTS голоса и units |
| Описание | Свести AnyVoice/Fish/legacy speech в capability schema, UTF-16/language/voice pricing не угадывать |
| Приоритет | P1 |
| Этап | S3 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-006, C-012, C-013, C-016; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/anymodel_speech.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/anymodel_speech.py); [src/elevenbot/worker.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/worker.py); [src/elevenbot/providers.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/providers.py) |
| Требуемые изменения | Свести AnyVoice/Fish/legacy speech в capability schema, UTF-16/language/voice pricing не угадывать |
| Зависимости | JO-03, PC-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Surrogates/UTF-16, unavailable tariff/voice, corrupt audio, timeout |
| Физическое доказательство | Shared fixtures и восстановление сохранённого MP3 |
| Критерий приёмки | Без подтверждённого тарифа продажа закрыта; no double capture; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/anymodel_speech.py, src/elevenbot/worker.py, src/elevenbot/providers.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### VO-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | VO-02 |
| EPIC_ID | VO |
| Название | Voice UI и E2E двух клиентов |
| Описание | Формы текста/языка/голоса/параметров через каталог и общий quote |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-006, C-012, C-013, C-016; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/anymodel_speech.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/anymodel_speech.py); [src/elevenbot/worker.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/worker.py); [src/elevenbot/providers.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/providers.py) |
| Требуемые изменения | Формы текста/языка/голоса/параметров через каталог и общий quote |
| Зависимости | VO-01, AP-03, MC-02 |
| Owner decisions | D-06 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Границы длины, sample ownership, interrupted delivery |
| Физическое доказательство | Разрешённая озвучка, воспроизведение/скачивание после restart |
| Критерий приёмки | Сохранённый audio и проводки совпадают; цены не в UI; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/anymodel_speech.py, src/elevenbot/worker.py, src/elevenbot/providers.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## MU — Music Studio

### MU-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | MU-01 |
| EPIC_ID | MU |
| Название | Свести CLODEX/Fal music в общий lifecycle |
| Описание | Сохранить Leonardo/Lyria pilots, lyrics/duration/output multiplicity, licensing metadata; AnyModel music не выдумывать |
| Приоритет | P1 |
| Этап | S4 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-006, C-012, C-013, C-016; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/clodex_music.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/clodex_music.py); [src/elevenbot/fal.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/fal.py) |
| Требуемые изменения | Сохранить Leonardo/Lyria pilots, lyrics/duration/output multiplicity, licensing metadata; AnyModel music не выдумывать |
| Зависимости | JO-03, PR-01 |
| Owner decisions | D-02 D-08 |
| Допускаемый параллелизм | ML-03 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Async handles, n>1 partial output, malformed audio, unknown cost |
| Физическое доказательство | Fixture MP3s/checksums/settlement, approved model specs |
| Критерий приёмки | Один общий job с явной partial policy и pricing cap; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/clodex_music.py, src/elevenbot/fal.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### MU-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | MU-02 |
| EPIC_ID | MU |
| Название | Music UI, library и разрешённый live proof |
| Описание | Song/music формы и типизированная выдача в обоих клиентах |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-006, C-012, C-013, C-016; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/clodex_music.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/clodex_music.py); [src/elevenbot/fal.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/fal.py) |
| Требуемые изменения | Song/music формы и типизированная выдача в обоих клиентах |
| Зависимости | MU-01, AP-03, MC-02 |
| Owner decisions | D-06 D-08 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Lyrics bounds, unavailable model, multiple outputs, resend |
| Физическое доказательство | Разрешённый реальный output каждой включённой music capability |
| Критерий приёмки | Лицензия и ограничения показаны; нет продаж непроверенных возможностей; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/clodex_music.py, src/elevenbot/fal.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## ML — Media Library и доставка

### ML-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | ML-01 |
| EPIC_ID | ML |
| Название | Доказать сохранность image и восстановление доставки |
| Описание | Воспроизвести notify_attempts<3 на текущем коде; различить явный Telegram отказ и ambiguous send; bounded recovery и manual redelivery без regeneration |
| Приоритет | P0 |
| Этап | S1 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-016, C-017, C-018, C-030; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/storage.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/storage.py); [src/elevenbot/anymodel_image_jobs.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/anymodel_image_jobs.py); [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py) |
| Требуемые изменения | Воспроизвести notify_attempts<3 на текущем коде; различить явный Telegram отказ и ambiguous send; bounded recovery и manual redelivery без regeneration |
| Зависимости | IN-19 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | PC-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Три отказа sendPhoto, restart, sendDocument fallback, retry cap, cross-user |
| Физическое доказательство | Тот же image checksum из БД после restart, provider count=1 |
| Критерий приёмки | Файл доступен в library; известный отказ восстанавливаем, неизвестная доставка не спамит; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/core.py, src/elevenbot/storage.py, src/elevenbot/anymodel_image_jobs.py, miniapp/backend/web.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### ML-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | ML-02 |
| EPIC_ID | ML |
| Название | Общий LibraryItem для всех сохранённых типов |
| Описание | Проекция старых media tables, validation/checksum/final price/owner; не удалять bytes |
| Приоритет | P1 |
| Этап | S3 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-016, C-017, C-018, C-030; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/storage.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/storage.py); [src/elevenbot/anymodel_image_jobs.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/anymodel_image_jobs.py); [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py) |
| Требуемые изменения | Проекция старых media tables, validation/checksum/final price/owner; не удалять bytes |
| Зависимости | JO-03, ML-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Corrupt/missing asset, storage failure, ownership, multiasset |
| Физическое доказательство | Backup/restore сверка media bytes и metadata |
| Критерий приёмки | SUCCEEDED не возникает без durable owned assets; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/core.py, src/elevenbot/storage.py, src/elevenbot/anymodel_image_jobs.py, miniapp/backend/web.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### ML-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | ML-03 |
| EPIC_ID | ML |
| Название | Пять строк Telegram и карточки Mini App |
| Описание | В боте preview prompt + final price, ≤5/page; Mini App detail/download/resend/new quote |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-016, C-017, C-018, C-030; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/storage.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/storage.py); [src/elevenbot/anymodel_image_jobs.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/anymodel_image_jobs.py); [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py) |
| Требуемые изменения | В боте preview prompt + final price, ≤5/page; Mini App detail/download/resend/new quote |
| Зависимости | ML-02, MA-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | MU-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Long escaping, page bounds, historical price, resend no POST |
| Физическое доказательство | Одна работа открывается из обоих клиентов после restart |
| Критерий приёмки | Re-delivery не генерирует и не списывает; create similar явно новый quote; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/core.py, src/elevenbot/storage.py, src/elevenbot/anymodel_image_jobs.py, miniapp/backend/web.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## WL — Wallet & Ledger

### WL-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | WL-01 |
| EPIC_ID | WL |
| Название | Проверить атомарный reserve/capture/release/refund |
| Описание | Сохранить existing task_wallet, добавить только доказанно missing constraints/compensation; один migration writer |
| Приоритет | P0 |
| Этап | S7 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-008, C-011, C-025; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/task_wallet.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_wallet.py); [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [migrations/026_task_wallet.sql](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/migrations/026_task_wallet.sql); [migrations/034_topups.sql](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/migrations/034_topups.sql) |
| Требуемые изменения | Сохранить existing task_wallet, добавить только доказанно missing constraints/compensation; один migration writer |
| Зависимости | JO-03, PC-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | 20 concurrent reserve, double completion, crash before/after commit, unknown provider |
| Физическое доказательство | PostgreSQL transaction race trace и ledger reconciliation |
| Критерий приёмки | Баланс/резерв корректны, уникальный effect, нет release при unknown; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/task_wallet.py, src/elevenbot/core.py, migrations/026_task_wallet.sql, migrations/034_topups.sql; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### WL-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | WL-02 |
| EPIC_ID | WL |
| Название | Сверка ledger и контролируемые корректировки |
| Описание | Согласовать projection/double-entry target ADR; reconciliation jobs/holds/payments/debt, audited correction |
| Приоритет | P1 |
| Этап | S7 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-008, C-011, C-025; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/task_wallet.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_wallet.py); [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [migrations/026_task_wallet.sql](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/migrations/026_task_wallet.sql); [migrations/034_topups.sql](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/migrations/034_topups.sql) |
| Требуемые изменения | Согласовать projection/double-entry target ADR; reconciliation jobs/holds/payments/debt, audited correction |
| Зависимости | WL-01, PY-02 |
| Owner decisions | D-02 D-03 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Mismatch detection, partial refund, spent credit, repeated reconciliation |
| Физическое доказательство | Созданное в fixture расхождение обнаружено и исправлено компенсирующей записью |
| Критерий приёмки | Нет direct balance editing, отчёт различает факты/оценки; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/task_wallet.py, src/elevenbot/core.py, migrations/026_task_wallet.sql, migrations/034_topups.sql; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## PY — Payments

### PY-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | PY-01 |
| EPIC_ID | PY |
| Название | Проверить existing Stars checkout на одном конфиге |
| Описание | Объединить существующие XTR invoice/precheckout/payment/refund с common wallet; не создавать отдельный платёжный сервис |
| Приоритет | P0 |
| Этап | S1 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-008, C-009, C-031; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/telegram.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/telegram.py); [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/topups.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/topups.py); [src/elevenbot/platega.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/platega.py); [src/elevenbot/platega_web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/platega_web.py) |
| Требуемые изменения | Объединить существующие XTR invoice/precheckout/payment/refund с common wallet; не создавать отдельный платёжный сервис |
| Зависимости | IN-19, PC-01 |
| Owner decisions | D-02 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Duplicate successful_payment, wrong XTR/amount/charge/user, fixture topup→ordinary image |
| Физическое доказательство | Один credit и один image capture на неизменном конфиге |
| Критерий приёмки | Invoice и redirect не зачисляют; Stars digital flow включаем только по policy; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/telegram.py, src/elevenbot/core.py, src/elevenbot/topups.py, src/elevenbot/platega.py, src/elevenbot/platega_web.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### PY-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | PY-02 |
| EPIC_ID | PY |
| Название | Проверить Platega callback/reconcile без Telegram checkout |
| Описание | Проверить создание, callback, reconciliation, атомарный учёт, историю, пресеты и комиссии в рамках утверждённой политики. |
| Приоритет | P1 |
| Этап | S7 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-008, C-009, C-031; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/telegram.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/telegram.py); [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/topups.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/topups.py); [src/elevenbot/platega.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/platega.py); [src/elevenbot/platega_web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/platega_web.py) |
| Требуемые изменения | Проверить создание, callback, reconciliation, атомарный учёт, историю, пресеты и комиссии в рамках утверждённой политики. |
| Зависимости | IN-19 |
| Owner decisions | D-03 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Auth callback, mismatch, duplicate/out-of-order, create_unknown, restart mid-credit |
| Физическое доказательство | Изолированная HTTP/DB failure matrix; отдельный approved sandbox если доступен |
| Критерий приёмки | Ровно один credit; unknown не повторяется; Platega не обход Stars; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/telegram.py, src/elevenbot/core.py, src/elevenbot/topups.py, src/elevenbot/platega.py, src/elevenbot/platega_web.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### PY-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | PY-03 |
| EPIC_ID | PY |
| Название | Mini App Stars и payment history |
| Описание | Существующий checkout через API и Telegram invoice UI, pending/verify/history/paysupport |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-008, C-009, C-031; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/telegram.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/telegram.py); [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/topups.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/topups.py); [src/elevenbot/platega.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/platega.py); [src/elevenbot/platega_web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/platega_web.py) |
| Требуемые изменения | Существующий checkout через API и Telegram invoice UI, pending/verify/history/paysupport |
| Зависимости | AP-01, PY-01, MA-01 |
| Owner decisions | D-06 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Cancelled invoice, duplicate event, stale session, generation race |
| Физическое доказательство | Telegram Stars test environment + Mini App→bot same wallet |
| Критерий приёмки | Одна серверно подтверждённая проводка; real funds только отдельно; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/telegram.py, src/elevenbot/core.py, src/elevenbot/topups.py, src/elevenbot/platega.py, src/elevenbot/platega_web.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## RF — Referrals

### RF-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | RF-01 |
| EPIC_ID | RF |
| Название | Адаптировать immutable attribution из донора |
| Описание | Адаптировать привязку приглашённых и коды с проверкой доступа и конкуренции. |
| Приоритет | P1 |
| Этап | S7 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-010, C-011, C-008; target DESIGN_DRAFT до approval |
| Текущее состояние | NOT_STARTED; donor SOURCE_PRESENT, FLOW integration NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/task_wallet.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_wallet.py) |
| Требуемые изменения | Адаптировать привязку приглашённых и коды с проверкой доступа и конкуренции. |
| Зависимости | AR-01, SL-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | AD-03 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Self-referral, repeated /start, code collision, concurrent signup |
| Физическое доказательство | DB fixture attribution переживает restart и switch client |
| Критерий приёмки | Один referrer, чужие профили не раскрыты; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/core.py, src/elevenbot/task_wallet.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### RF-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | RF-02 |
| EPIC_ID | RF |
| Название | Rewards на capture и reversal/debt |
| Описание | Адаптировать вознаграждения, откаты и долги согласно утверждённой финансовой политике. |
| Приоритет | P1 |
| Этап | S7 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-010, C-011, C-008; target DESIGN_DRAFT до approval |
| Текущее состояние | NOT_STARTED; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/task_wallet.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_wallet.py) |
| Требуемые изменения | Адаптировать вознаграждения, откаты и долги согласно утверждённой финансовой политике. |
| Зависимости | RF-01, WL-01 |
| Owner decisions | D-07 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Duplicate capture, concurrent refund, spent bonus, version changes |
| Физическое доказательство | Ledger/reward invariant trace на PostgreSQL |
| Критерий приёмки | Один reward; refund компенсирован по approved debt policy; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/core.py, src/elevenbot/task_wallet.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### RF-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | RF-03 |
| EPIC_ID | RF |
| Название | Реферальные экраны и API обоих клиентов |
| Описание | Подключить реферальные интерфейсы обоих клиентов к общему сервису и разрешённой истории. |
| Приоритет | P1 |
| Этап | S7 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-010, C-011, C-008; target DESIGN_DRAFT до approval |
| Текущее состояние | NOT_STARTED; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/task_wallet.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_wallet.py) |
| Требуемые изменения | Подключить реферальные интерфейсы обоих клиентов к общему сервису и разрешённой истории. |
| Зависимости | RF-02, AP-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Cross-user, pagination, empty/reversed/debt states |
| Физическое доказательство | Один реферальный сценарий в Telegram и Mini App на синтетических аккаунтах |
| Критерий приёмки | UI совпадает с ledger; показана версия условий; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/core.py, src/elevenbot/task_wallet.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## SL — Support & Legal

### SL-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | SL-01 |
| EPIC_ID | SL |
| Название | Общее versioned consent и юридические MD |
| Описание | Расширить существующий accepted_at immutable версиями/hash, общая проверка обоих клиентов |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-001, C-002, C-022, C-030; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/config.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/config.py); [src/elevenbot/telegram.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/telegram.py) |
| Требуемые изменения | Расширить существующий accepted_at immutable версиями/hash, общая проверка обоих клиентов |
| Зависимости | AR-01 |
| Owner decisions | D-08 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Stale version, concurrent accept, failed document delivery, preserve history |
| Физическое доказательство | Реальная повторная авторизация при новой версии в тестовом окружении |
| Критерий приёмки | Нет покупки со старым consent; юридический текст утверждён отдельно; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/core.py, src/elevenbot/config.py, src/elevenbot/telegram.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### SL-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | SL-02 |
| EPIC_ID | SL |
| Название | Общий support ticket и operator workflow |
| Описание | Адаптировать общий support backend, маршрутизацию ответов и целостность медиагрупп с восстановлением. |
| Приоритет | P1 |
| Этап | S6 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-001, C-002, C-022, C-030; target DESIGN_DRAFT до approval |
| Текущее состояние | PARTIAL; help SOURCE_PRESENT, ticket lifecycle NOT_STARTED; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/config.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/config.py); [src/elevenbot/telegram.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/telegram.py) |
| Требуемые изменения | Адаптировать общий support backend, маршрутизацию ответов и целостность медиагрупп с восстановлением. |
| Зависимости | AD-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | IDOR, attachment bounds, duplicate reply, revoked support role |
| Физическое доказательство | Обращение пользователя и ответ оператора с audit ID |
| Критерий приёмки | Чужой тикет закрыт; support доступен без purchase consent; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/core.py, src/elevenbot/config.py, src/elevenbot/telegram.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### SL-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | SL-03 |
| EPIC_ID | SL |
| Название | Support/legal/profile в двух клиентах |
| Описание | Подключить обращения, вложения, статус и историю обоих клиентов к общему backend. |
| Приоритет | P1 |
| Этап | S6 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-001, C-002, C-022, C-030; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py); [src/elevenbot/config.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/config.py); [src/elevenbot/telegram.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/telegram.py) |
| Требуемые изменения | Подключить обращения, вложения, статус и историю обоих клиентов к общему backend. |
| Зависимости | SL-01, SL-02, MA-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Unaccepted user, suspended user, both clients, reply notifications |
| Физическое доказательство | Сквозной ticket/response, документы скачаны в клиентах |
| Критерий приёмки | Один ticket и consent state, понятный канал paysupport; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/core.py, src/elevenbot/config.py, src/elevenbot/telegram.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## SE — Security

### SE-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | SE-01 |
| EPIC_ID | SE |
| Название | Threat model и security boundary suite |
| Описание | Актуальная data-flow threat model: initData/session, RBAC, media SSRF/redirect/DNS, callbacks, resource budgets |
| Приоритет | P1 |
| Этап | S7 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-003, C-020, C-026, C-030; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/interaction.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/interaction.py); [src/elevenbot/admin_access.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/admin_access.py); [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [.dockerignore](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/.dockerignore) |
| Требуемые изменения | Актуальная data-flow threat model: initData/session, RBAC, media SSRF/redirect/DNS, callbacks, resource budgets |
| Зависимости | AR-01, AD-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Replay, IDOR, forged admin, DNS rebinding, oversized/decompression, unsafe paths |
| Физическое доказательство | Reproducible negative HTTP/DB probes с безопасными логами |
| Критерий приёмки | Каждой threat assigned mitigation/test; критичные findings закрыты или блокируют release; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/interaction.py, src/elevenbot/admin_access.py, miniapp/backend/web.py, .dockerignore; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### SE-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | SE-02 |
| EPIC_ID | SE |
| Название | Безопасные экспорт, логи и retention |
| Описание | Проверить архивирование allowlist, secret redaction, safe errors, legal hold/deletion по утверждённой policy |
| Приоритет | P1 |
| Этап | S7 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-003, C-020, C-026, C-030; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/interaction.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/interaction.py); [src/elevenbot/admin_access.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/admin_access.py); [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [.dockerignore](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/.dockerignore) |
| Требуемые изменения | Проверить архивирование allowlist, secret redaction, safe errors, legal hold/deletion по утверждённой policy |
| Зависимости | SE-01, ML-02 |
| Owner decisions | D-08 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Синтетический canary secret в исключённом файле, archive listing, log scans, retention hold |
| Физическое доказательство | Созданный безопасный тестовый архив не содержит canary; paid bytes не удалены раньше срока |
| Критерий приёмки | Никаких raw private logs или env в публичных artifacts; restore описан; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/interaction.py, src/elevenbot/admin_access.py, miniapp/backend/web.py, .dockerignore; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### SE-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | SE-03 |
| EPIC_ID | SE |
| Название | Независимая regression security двух клиентов |
| Описание | Проверить реальные HTTP/UI denies и command boundaries, не ограничиваться статическим сканером |
| Приоритет | P1 |
| Этап | S7 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-003, C-020, C-026, C-030; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/interaction.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/interaction.py); [src/elevenbot/admin_access.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/admin_access.py); [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [.dockerignore](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/.dockerignore) |
| Требуемые изменения | Проверить реальные HTTP/UI denies и command boundaries, не ограничиваться статическим сканером |
| Зависимости | SE-02, AD-03, MA-03 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | OP-02 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Two-user roles, revoke, stale session, forged price, upload abuse |
| Физическое доказательство | Записи отрицательных сценариев + серверные evidence IDs |
| Критерий приёмки | Нет обхода API через прямой URL/старую кнопку; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/interaction.py, src/elevenbot/admin_access.py, miniapp/backend/web.py, .dockerignore; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## TQ — Testing & Quality

### TQ-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | TQ-01 |
| EPIC_ID | TQ |
| Название | Закрепить CI profile и fixtures для интегрированной базы |
| Описание | Сохранить suite vankhu21, разделить unit/DB/contract/mock/live, записывать skips и checksum миграций |
| Приоритет | P1 |
| Этап | S0 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-012, C-013, C-024, C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [tests](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests); [miniapp/tests/test_miniapp.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/tests/test_miniapp.py); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/.github/workflows/test.yml) |
| Требуемые изменения | Сохранить suite vankhu21, разделить unit/DB/contract/mock/live, записывать skips и checksum миграций |
| Зависимости | IN-19 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Python 3.12, PostgreSQL16, ffmpeg, полный acceptance + docs |
| Физическое доказательство | Actions exact SHA и sanitized JUnit summary |
| Критерий приёмки | Нет скрытых skipped/infrastructure failures; mocks не называются live; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия tests, miniapp/tests/test_miniapp.py, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### TQ-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | TQ-02 |
| EPIC_ID | TQ |
| Название | Сквозная parity/regression matrix четырёх студий |
| Описание | Собрать уже существующие fixtures и live evidence в трассируемую acceptance matrix; воспроизводить только missing |
| Приоритет | P1 |
| Этап | S8 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-012, C-013, C-024, C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [tests](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/tests); [miniapp/tests/test_miniapp.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/tests/test_miniapp.py); [.github/workflows/test.yml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/.github/workflows/test.yml) |
| Требуемые изменения | Собрать уже существующие fixtures и live evidence в трассируемую acceptance matrix; воспроизводить только missing |
| Зависимости | MA-04, TA-02, WL-02, SE-03 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Happy/failure/uncertain/restart/resend для каждого включённого типа |
| Физическое доказательство | Ссылки test ID→contract→SHA→UI/provider evidence |
| Критерий приёмки | Обязательные сценарии покрыты; непроверенные capability выключены; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия tests, miniapp/tests/test_miniapp.py, .github/workflows/test.yml; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## OP — Infrastructure & Operations

### OP-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | OP-01 |
| EPIC_ID | OP |
| Название | Подготовить закрытый HTTPS test endpoint Mini App |
| Описание | Разрешённый DNS/reverse proxy/TLS к тестовому Mini App, health и same DB; без production rollout |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-027, C-026; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [compose.yaml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/compose.yaml); [compose.miniapp.yaml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/compose.miniapp.yaml); [deploy/ubuntu/backup.sh](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/deploy/ubuntu/backup.sh); [deploy/ubuntu/install.sh](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/deploy/ubuntu/install.sh); [scripts](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/scripts) |
| Требуемые изменения | Разрешённый DNS/reverse proxy/TLS к тестовому Mini App, health и same DB; без production rollout |
| Зависимости | IN-19 |
| Owner decisions | D-05 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Public HTTPS reachability, cert, unauthorized API 401, health |
| Физическое доказательство | Доступ с телефона вне LAN и build SHA в test environment |
| Критерий приёмки | Выделенный тестовый бот и два аккаунта готовы; ключи вне artifacts; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия compose.yaml, compose.miniapp.yaml, deploy/ubuntu/backup.sh, deploy/ubuntu/install.sh, scripts; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### OP-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | OP-02 |
| EPIC_ID | OP |
| Название | Проверить миграции и полный backup/restore |
| Описание | Развить existing Ubuntu scripts; media+DB+catalogue, runtime least privilege, RPO/RTO измерить |
| Приоритет | P1 |
| Этап | S7 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-027, C-026; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [compose.yaml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/compose.yaml); [compose.miniapp.yaml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/compose.miniapp.yaml); [deploy/ubuntu/backup.sh](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/deploy/ubuntu/backup.sh); [deploy/ubuntu/install.sh](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/deploy/ubuntu/install.sh); [scripts](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/scripts) |
| Требуемые изменения | Развить existing Ubuntu scripts; media+DB+catalogue, runtime least privilege, RPO/RTO измерить |
| Зависимости | ML-02, WL-01 |
| Owner decisions | D-09 |
| Допускаемый параллелизм | SE-03 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Upgrade копии 036→039+new, checksum doctor, restore isolated DB/volumes |
| Физическое доказательство | Восстановленные owner records, bytes hashes и ledger totals |
| Критерий приёмки | Restore работает, destructive downgrade не выдуман; measured RPO/RTO; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия compose.yaml, compose.miniapp.yaml, deploy/ubuntu/backup.sh, deploy/ubuntu/install.sh, scripts; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### OP-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | OP-03 |
| EPIC_ID | OP |
| Название | Принять Ubuntu release candidate и shutdown |
| Описание | Существующая Docker/systemd поставка, independent worker topology, reproducible build metadata |
| Приоритет | P1 |
| Этап | S8 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-027, C-026; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [compose.yaml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/compose.yaml); [compose.miniapp.yaml](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/compose.miniapp.yaml); [deploy/ubuntu/backup.sh](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/deploy/ubuntu/backup.sh); [deploy/ubuntu/install.sh](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/deploy/ubuntu/install.sh); [scripts](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/scripts) |
| Требуемые изменения | Существующая Docker/systemd поставка, independent worker topology, reproducible build metadata |
| Зависимости | OP-02, JO-02, SE-02 |
| Owner decisions | D-09 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Clean Ubuntu amd64, health/readiness, restart, bounded queue, migration failure |
| Физическое доказательство | Версии ОС/images/Python/PostgreSQL и полный health trace |
| Критерий приёмки | Восстановление и rollback приложения доказаны без потери данных; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия compose.yaml, compose.miniapp.yaml, deploy/ubuntu/backup.sh, deploy/ubuntu/install.sh, scripts; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## OB — Observability & Reporting

### OB-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | OB-01 |
| EPIC_ID | OB |
| Название | Единая safe timeline job и provider request |
| Описание | Дополнить existing trace_interaction correlation/events/stages, bounded metrics без prompt/key |
| Приоритет | P1 |
| Этап | S3 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-023, C-028; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/progress.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/progress.py); [src/elevenbot/pricing.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/pricing.py); [src/elevenbot/worker.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/worker.py) |
| Требуемые изменения | Дополнить existing trace_interaction correlation/events/stages, bounded metrics без prompt/key |
| Зависимости | JO-03 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Ошибки provider/media/store/delivery, IDs through restart |
| Физическое доказательство | По одному job ID видны все этапы с latency/error class |
| Критерий приёмки | API success и user-visible evidence различимы, лог без секретов; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/progress.py, src/elevenbot/pricing.py, src/elevenbot/worker.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### OB-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | OB-02 |
| EPIC_ID | OB |
| Название | Операционный и финансовый read API |
| Описание | Read models дней/моделей/провайдеров; payments/holds/capture/refund vs estimated costs, queue/uncertain |
| Приоритет | P1 |
| Этап | S6 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-023, C-028; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/progress.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/progress.py); [src/elevenbot/pricing.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/pricing.py); [src/elevenbot/worker.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/worker.py) |
| Требуемые изменения | Read models дней/моделей/провайдеров; payments/holds/capture/refund vs estimated costs, queue/uncertain |
| Зависимости | OB-01, AD-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Seeded aggregates, timezone boundaries, unknown cost, variance |
| Физическое доказательство | Сверка API с ledger fixture и job events |
| Критерий приёмки | Расчётная маржа не выдаётся за фактическую; operator видит причину; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/progress.py, src/elevenbot/pricing.py, src/elevenbot/worker.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### OB-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | OB-03 |
| EPIC_ID | OB |
| Название | Dashboard отчётов и управляемые incident alerts |
| Описание | UI reports/export и opt-in admin alerts с thresholds/dedup/cooldown; доступ к данным по role |
| Приоритет | P1 |
| Этап | S6 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-023, C-028; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [src/elevenbot/progress.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/progress.py); [src/elevenbot/pricing.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/pricing.py); [src/elevenbot/worker.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/worker.py) |
| Требуемые изменения | UI reports/export и opt-in admin alerts с thresholds/dedup/cooldown; доступ к данным по role |
| Зависимости | OB-02, AD-03 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Provider outage, stale queue, repeated alert, export redaction |
| Физическое доказательство | Инъекция тестового инцидента и одно адресное уведомление |
| Критерий приёмки | Финансы/операции разделены, alert не создаёт broadcast клиентам; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия src/elevenbot/progress.py, src/elevenbot/pricing.py, src/elevenbot/worker.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## DC — Documentation & Contracts

### DC-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | DC-01 |
| EPIC_ID | DC |
| Название | Устранить расхождения фундаментальных контрактов |
| Описание | В PR отдельно согласовать этапы S4 providers/S5 API/S6 admin/S7 hardening, token units, admin env и реестр C-031 |
| Приоритет | P1 |
| Этап | S0 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-001, C-008, C-012, C-013, C-024, C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [docs/contracts](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/docs/contracts); [docs/architecture](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/docs/architecture); [docs/operations](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/docs/operations); [docs/acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/docs/acceptance) |
| Требуемые изменения | В PR отдельно согласовать этапы S4 providers/S5 API/S6 admin/S7 hardening, token units, admin env и реестр C-031 |
| Зависимости | IN-18 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | TA-01 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Cross-doc consistency, 31 IDs, links; source/target labels |
| Физическое доказательство | ADR и review актуального SHA |
| Критерий приёмки | Нет RUB-wallet target без ADR; старая история не удалена; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия docs/contracts, docs/architecture, docs/operations, docs/acceptance; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### DC-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | DC-02 |
| EPIC_ID | DC |
| Название | Сверить финальные runbooks с реализацией |
| Описание | Актуализировать deployment/backup/incident/provider/billing/media/error/API/acceptance, не создавать дубликаты индексов |
| Приоритет | P1 |
| Этап | S8 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-001, C-008, C-012, C-013, C-024, C-027; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [docs/contracts](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/docs/contracts); [docs/architecture](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/docs/architecture); [docs/operations](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/docs/operations); [docs/acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/docs/acceptance) |
| Требуемые изменения | Актуализировать deployment/backup/incident/provider/billing/media/error/API/acceptance, не создавать дубликаты индексов |
| Зависимости | OP-03, TQ-02 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Команды runbook на чистом стенде, links и schema checks |
| Физическое доказательство | Другой разработчик воспроизводит запуск и диагностику по docs |
| Критерий приёмки | Документы различают implemented/planned и содержат точные версии; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия docs/contracts, docs/architecture, docs/operations, docs/acceptance; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## RL — Commercial Pilot & Release

### RL-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | RL-01 |
| EPIC_ID | RL |
| Название | Согласовать scope, цены и критерии пилота |
| Описание | Список включённых model/capability, caps/budgets, privacy/refund/retention/support, SLO и stop conditions |
| Приоритет | P1 |
| Этап | S8 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-027, C-028, C-030, C-031; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #18, `37337cc1538e26f91696be366908420d9dbb08d2`; [docs/acceptance/FOUNDATION_TEST_MATRIX.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/37337cc1538e26f91696be366908420d9dbb08d2/docs/acceptance/FOUNDATION_TEST_MATRIX.md); [docs/operations/DEPLOYMENT.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/37337cc1538e26f91696be366908420d9dbb08d2/docs/operations/DEPLOYMENT.md) |
| Требуемые изменения | Список включённых model/capability, caps/budgets, privacy/refund/retention/support, SLO и stop conditions |
| Зависимости | PR-03, WL-02, PY-03, SE-03 |
| Owner decisions | D-02 D-03 D-06 D-08 D-09 D-10 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Все обязательные evidence gates, blocked decisions review |
| Физическое доказательство | Подписанный owner go/no-go с capability exclusions |
| Критерий приёмки | Нет неподтверждённой live capability в продаже; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия docs/acceptance/FOUNDATION_TEST_MATRIX.md, docs/operations/DEPLOYMENT.md; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### RL-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | RL-02 |
| EPIC_ID | RL |
| Название | Провести ограниченный коммерческий user journey |
| Описание | Только отдельно разрешённый pilot: обычный user, Stars, генерация, доставка, library, поддержка/refund |
| Приоритет | P1 |
| Этап | S8 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027, C-028, C-030, C-031; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #18, `37337cc1538e26f91696be366908420d9dbb08d2`; [docs/acceptance/FOUNDATION_TEST_MATRIX.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/37337cc1538e26f91696be366908420d9dbb08d2/docs/acceptance/FOUNDATION_TEST_MATRIX.md); [docs/operations/DEPLOYMENT.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/37337cc1538e26f91696be366908420d9dbb08d2/docs/operations/DEPLOYMENT.md) |
| Требуемые изменения | Только отдельно разрешённый pilot: обычный user, Stars, генерация, доставка, library, поддержка/refund |
| Зависимости | RL-01, TQ-02, OP-03, OB-03 |
| Owner decisions | D-06 D-10 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Android/Desktop и оба канала, outage/restart/no duplicate charge |
| Физическое доказательство | Реальные обезличенные receipts/файлы/ledger и user-visible record |
| Критерий приёмки | Независимый аудитор принимает именно pilot scope, не весь будущий каталог; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия docs/acceptance/FOUNDATION_TEST_MATRIX.md, docs/operations/DEPLOYMENT.md; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### RL-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | RL-03 |
| EPIC_ID | RL |
| Название | Release decision и синхронизация двух полных сборок |
| Описание | Owner release approval, audit verdict, точный tag/build и обновление whole clones обоих авторов |
| Приоритет | P1 |
| Этап | S8 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-027, C-028, C-030, C-031; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #18, `37337cc1538e26f91696be366908420d9dbb08d2`; [docs/acceptance/FOUNDATION_TEST_MATRIX.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/37337cc1538e26f91696be366908420d9dbb08d2/docs/acceptance/FOUNDATION_TEST_MATRIX.md); [docs/operations/DEPLOYMENT.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/37337cc1538e26f91696be366908420d9dbb08d2/docs/operations/DEPLOYMENT.md) |
| Требуемые изменения | Owner release approval, audit verdict, точный tag/build и обновление whole clones обоих авторов |
| Зависимости | RL-02, DC-02 |
| Owner decisions | D-10 |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Final SHA CI, restore readiness, clean FF, includes teammate changes |
| Физическое доказательство | Release checklist и два BRANCH_SYNC с actual SHA |
| Критерий приёмки | Commercial pilot accepted только после owner/auditor; rollback готов; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия docs/acceptance/FOUNDATION_TEST_MATRIX.md, docs/operations/DEPLOYMENT.md; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## AP — Public API и Mini App backend foundation

### AP-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | AP-01 |
| EPIC_ID | AP |
| Название | Описать существующий API OpenAPI 3.1 и auth errors |
| Описание | Версионированная схема текущих session/catalogue/wallet/settings/works; aliases и error envelope без ломания MVP |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-003, C-007, C-012, C-024, C-025; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [src/elevenbot/task_launch.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_launch.py); [src/elevenbot/pricing.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/pricing.py); [miniapp/tests/test_miniapp.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/tests/test_miniapp.py) |
| Требуемые изменения | Версионированная схема текущих session/catalogue/wallet/settings/works; aliases и error envelope без ломания MVP |
| Зависимости | AR-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | MC-02 |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Response contract tests, auth/consent/IDOR, bounded input |
| Физическое доказательство | Спецификация сверена с реальными HTTP на fixture |
| Критерий приёмки | Нет объявленных endpoint без implementation или explicit proposed marker; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия miniapp/backend/web.py, src/elevenbot/task_launch.py, src/elevenbot/pricing.py, miniapp/tests/test_miniapp.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### AP-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | AP-02 |
| EPIC_ID | AP |
| Название | Transport-neutral quote и image job command |
| Описание | POST quotes/jobs через существующий Pricing/TaskLaunch с semantic idempotency, не fake Telegram update IDs |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-003, C-007, C-012, C-024, C-025; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [src/elevenbot/task_launch.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_launch.py); [src/elevenbot/pricing.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/pricing.py); [miniapp/tests/test_miniapp.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/tests/test_miniapp.py) |
| Требуемые изменения | POST quotes/jobs через существующий Pricing/TaskLaunch с semantic idempotency, не fake Telegram update IDs |
| Зависимости | AP-01, AR-02, PC-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Same key+changed payload conflict, bot/HTTP race, stale quote, rollback |
| Физическое доказательство | Одна common transaction reserve+job и один adapter POST |
| Критерий приёмки | Один wallet/job store; auth user authoritative; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия miniapp/backend/web.py, src/elevenbot/task_launch.py, src/elevenbot/pricing.py, miniapp/tests/test_miniapp.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 5 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### AP-03

| Поле | Содержание |
| --- | --- |
| TASK_ID | AP-03 |
| EPIC_ID | AP |
| Название | Owned job status, list и cancel API |
| Описание | GET job/status/list, permitted cancellation, shared query projection, safe polling |
| Приоритет | P1 |
| Этап | S5 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-003, C-007, C-012, C-024, C-025; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [miniapp/backend/web.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/backend/web.py); [src/elevenbot/task_launch.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/task_launch.py); [src/elevenbot/pricing.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/pricing.py); [miniapp/tests/test_miniapp.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/miniapp/tests/test_miniapp.py) |
| Требуемые изменения | GET job/status/list, permitted cancellation, shared query projection, safe polling |
| Зависимости | AP-02, JO-02 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Owner IDOR, cursor, UNCERTAIN, stale cancel, restart |
| Физическое доказательство | Telegram job читается HTTP, HTTP job виден Telegram |
| Критерий приёмки | Cancel не обещает возврат до подтверждения; нет повторного paid POST; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия miniapp/backend/web.py, src/elevenbot/task_launch.py, src/elevenbot/pricing.py, miniapp/tests/test_miniapp.py; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

## AU — Публикация аудиторских доказательств

### AU-01

| Поле | Содержание |
| --- | --- |
| TASK_ID | AU-01 |
| EPIC_ID | AU |
| Название | Согласовать audit-artifacts lifecycle и schema gate |
| Описание | Принять протокол TASK-PLAN-001, bootstrap отдельной ветки только через owner-approved PR; auditor read-only для разработчиков |
| Приоритет | P1 |
| Этап | S0 |
| Исполнитель | Burn2288 |
| Рецензент | vankhu21 |
| Integration owner | Burn2288 |
| Контракты | C-027, C-028; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [AGENTS.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/AGENTS.md); [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/CONTRIBUTING.md); [.github/pull_request_template.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/.github/pull_request_template.md) |
| Требуемые изменения | Принять протокол TASK-PLAN-001, bootstrap отдельной ветки только через owner-approved PR; auditor read-only для разработчиков |
| Зависимости | IN-18 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Manifest JSON Schema, negative fixtures, READY guard, links |
| Физическое доказательство | Draft docs PR + затем одобренный archive PR с SHA-пакетом |
| Критерий приёмки | Работа не READY до опубликованного пакета; нет self PASS; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия AGENTS.md, CONTRIBUTING.md, .github/pull_request_template.md; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |

### AU-02

| Поле | Содержание |
| --- | --- |
| TASK_ID | AU-02 |
| EPIC_ID | AU |
| Название | Доказать передачу и повторный аудит без потери истории |
| Описание | Одна синтетическая docs-задача revision r1→rejected→r2, immutable index и sha256 evidence inventory |
| Приоритет | P1 |
| Этап | S0 |
| Исполнитель | vankhu21 |
| Рецензент | Burn2288 |
| Integration owner | vankhu21 |
| Контракты | C-027, C-028; target DESIGN_DRAFT до approval |
| Текущее состояние | SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN; exact CI baseline в github-snapshot.json, не future test PASS |
| Существующий код | PR #17, `d691d54e0266c3d519d66575555fa45895ef40ac`; [AGENTS.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/AGENTS.md); [CONTRIBUTING.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/CONTRIBUTING.md); [.github/pull_request_template.md](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/.github/pull_request_template.md) |
| Требуемые изменения | Одна синтетическая docs-задача revision r1→rejected→r2, immutable index и sha256 evidence inventory |
| Зависимости | AU-01 |
| Owner decisions | Дополнительное policy решение не требуется; общие merge/live gates сохраняются |
| Допускаемый параллелизм | Только disjoint files после lock-check по PARALLEL_WORK_MATRIX; не blanket разрешение |
| Результат | Минимальный diff существующих компонентов, профильные проверки и актуальный контракт/runbook; для proof-only — код менять только при подтверждённом дефекте. |
| Проверка | Missing file/hash, bad schema, absent PR/CI, secret canary, prior verdict retention |
| Физическое доказательство | Постоянные SHA URLs на оба пакета и независимое решение |
| Критерий приёмки | Старое отрицательное заключение сохранено; archive не копирует application code; peer review + независимый audit + согласованная интеграция, полный evidence package |
| Риски | Регрессия AGENTS.md, CONTRIBUTING.md, .github/pull_request_template.md; не менять общий контракт/миграцию параллельно без lock/reservation. |
| Артефакты | Полный пакет MANIFEST + 10 MD, CI exact SHA, safe evidence/checksums, code PR и archive PR; для live — разрешение и redacted receipts. |
| Effort | 3 |
| Статус | Планируется; назначение предложено, запуск после approval/dependencies |
