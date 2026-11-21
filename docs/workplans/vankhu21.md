> **Историческая личная ведомость:** задачи, их исходные владельцы, ID и позиции vankhu21 сохраняются для аудита и происхождения. На период его недоступности текущий исполнитель — Burn2288 по отдельному [assignment overlay](../planning/owner-takeover-ftl1-001.json). Это операционное назначение не меняет авторство, историю или статус завершения.

# vankhu21: functional-test task list — candidate

Позиции воспроизведены из исторического личного списка ce973001; все статусы ожидают сверки с main и доказательствами. Фактическая готовность и зависимости определяются [реестром](../planning/completion-level-register.json), а не порядком строк. Исторические формулировки сохранены в [исходном реестре](../planning/historical-tasks-v1.json). Действует [регламент уровней](../planning/COMPLETION_LEVELS.md).

## IMPLEMENTATION_STATUS и COMPLETED_LEVEL

`IMPLEMENTATION_STATUS` описывает ход работы и текущую готовность кандидата; `COMPLETED_LEVEL` остаётся `null`, пока кандидат не прошёл общую приёмку, не получил отдельное разрешение владельца и не включён в `main`. Успешный CI, локальный demo и включение в интеграционную ветку сами по себе уровень не закрывают.

| IMPLEMENTATION_STATUS | Значение |
| --- | --- |
| NOT_ASSESSED | Текущее состояние реализации ещё не установлено по проверяемым данным. |
| IN_PROGRESS | Работа над базовым или смежным функциональным срезом продолжается. |
| CANDIDATE_PREPARED | Частичный кандидат и физические доказательства подготовлены. |
| AWAITING_GLOBAL_ACCEPTANCE | Функциональный кандидат ждёт общей приёмки интеграционной сборки. |
| BLOCKED | Базовый безопасный сценарий требует внешнего решения или зависимости. |
| DEFERRED | Работа отложена с указанной причиной и следующим шагом. |

| LIST_POSITION | MASTER_POSITION | TASK_ID | Задача | Зависимости | IMPLEMENTATION_STATUS | TARGET_LEVEL | COMPLETED_LEVEL |
| --- | --- | --- | --- |
| 1 | 3 | IN-08 | Интегрировать PR #8 и доказать supersession ранних пилотов | IN-02 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 2 | 4 | IN-09 | Провести отдельную приёмку и интеграцию PR #9: Veo video | IN-08 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 3 | 5 | IN-10 | Провести отдельную приёмку и интеграцию PR #10: AnyModel registry | IN-09 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 4 | 6 | IN-11 | Провести отдельную приёмку и интеграцию PR #11: FIBO async image | IN-10 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 5 | 7 | IN-12 | Провести отдельную приёмку и интеграцию PR #12: Grok video | IN-11 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 6 | 8 | IN-13 | Провести отдельную приёмку и интеграцию PR #13: AnyModel speech | IN-12 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 7 | 9 | IN-14 | Провести отдельную приёмку и интеграцию PR #14: Welcome/navigation | IN-13 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 8 | 10 | IN-15 | Провести отдельную приёмку и интеграцию PR #15: Task progress | IN-14 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 9 | 11 | IN-16 | Принять PR #16: финансы, каталог и Telegram Admin | IN-15 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 10 | 12 | IN-17 | Принять PR #17: Mini App и новый inbox | IN-16 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 11 | 17 | TG-01 | Перевести главное меню и Back без потери старых маршрутов | IN-19 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 12 | 18 | TG-02 | Подключить документы и текущий consent к Telegram UX | SL-01, TG-01 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 13 | 19 | TG-03 | Личный кабинет и история общего кошелька | PY-01, TG-01 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 14 | 20 | MA-01 | Принять существующую Mini App в Telegram по HTTPS | IN-19, OP-01 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 15 | 21 | MA-02 | Форма image quote и явное подтверждение | AP-02, MA-01 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 16 | 22 | MA-03 | Карточка job и безопасная отмена | MA-02, AP-03, JO-02 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 17 | 23 | MA-04 | Довести пользовательский parity и доступность | MA-03, VI-02, VO-02, MU-02, ML-03, RF-03, SL-03, PY-03 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 18 | 26 | AD-03 | Графические admin экраны по общему API | AD-02, OB-02 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 19 | 27 | TA-01 | Зафиксировать compatibility inventory Admin Edition | IN-01 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 20 | 28 | TA-02 | Сохранить Telegram admin при общих admin services | AD-02, TA-01 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 21 | 33 | MC-02 | Общие карточки и schema-driven параметры каталога | MC-01, MA-01 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 22 | 34 | PC-01 | Уточнить токены, XTR, RUB и immutable quote | IN-19 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 23 | 35 | PC-02 | Preview и publish versioned тарифов | PC-01, AD-02 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 24 | 39 | IM-01 | Повторить штатный image путь с ordinary user | IN-19, PC-01 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 25 | 40 | IM-02 | Три live изображения и временный отказ | IM-01, ML-01 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 26 | 41 | VI-01 | Согласовать video create/poll и финальный расчёт | JO-03, PC-01 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 27 | 42 | VI-02 | Video формы двух клиентов и разрешённая приёмка | VI-01, AP-03, MC-02 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 28 | 44 | VO-02 | Voice UI и E2E двух клиентов | VO-01, AP-03, MC-02 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 29 | 46 | MU-02 | Music UI, library и разрешённый live proof | MU-01, AP-03, MC-02 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 30 | 49 | ML-03 | Пять строк Telegram и карточки Mini App | ML-02, MA-01 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 31 | 50 | WL-01 | Проверить атомарный reserve/capture/release/refund | JO-03, PC-01 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 32 | 52 | PY-01 | Проверить existing Stars checkout на одном конфиге | IN-19, PC-01 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 33 | 53 | PY-02 | Проверить Platega callback/reconcile без Telegram checkout | IN-19 | CANDIDATE_PREPARED | FUNCTIONAL_TEST | — |
| 34 | 54 | PY-03 | Mini App Stars и payment history | AP-01, PY-01, MA-01 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 35 | 57 | RF-03 | Реферальные экраны и API обоих клиентов | RF-02, AP-01 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 36 | 60 | SL-03 | Support/legal/profile в двух клиентах | SL-01, SL-02, MA-01 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 37 | 63 | SE-03 | Независимая regression security двух клиентов | SE-02, AD-03, MA-03 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 38 | 65 | TQ-02 | Сквозная parity/regression matrix четырёх студий | MA-04, TA-02, WL-02, SE-03 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 39 | 71 | OB-03 | Dashboard отчётов и управляемые incident alerts | OB-02, AD-03 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 40 | 75 | RL-02 | Провести ограниченный коммерческий user journey | RL-01, TQ-02, OP-03, OB-03 | NOT_ASSESSED | FUNCTIONAL_TEST | — |
| 41 | 81 | AU-02 | Доказать передачу и повторный аудит без потери истории | AU-01 | NOT_ASSESSED | FUNCTIONAL_TEST | — |

## PY-02 · №33 · ограниченная сверка — 19.11.2026

Владелец: vankhu21. Продолжение [Draft PR #77](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/77)
в ветке `vankhu21/py02-callback-reconcile`, исходный HEAD `fd30ed08cd3e6dec900f4c138b585a91eef0a925`.

На исходном коде новый тест `test_reconcile_limit_does_not_starve_confirmed_legacy_payment`
после четырёх вызовов `reconcile_pending(limit=1)` получил баланс 0 вместо 2000: старый неопределённый заказ постоянно занимал пакет.
Исправлен только порядок обхода: курсор `(created_at, id)` продолжает со следующего заказа и оборачивается к началу.
Пустой ответ или ошибка поиска также продвигают курсор; состояние платежа не меняется.
Курсор живёт в экземпляре сервиса: после его пересоздания обход начинается заново с самого раннего заказа.
Миграции и финансовые правила не изменены.

После исправления на одноразовой PostgreSQL 16.15 с HTTP-эмулятором прошли **91 тест за 25,24 с**:
`tests/test_platega_db.py tests/test_platega_unit.py tests/test_topups.py tests/test_platega_restart.py tests/test_public_image_topup.py tests/test_navigation.py tests/test_financial.py`.
Новый заказ зачисляет 2000 один раз, старый остаётся неопределённым без зачисления;
когда экспорт провайдера становится доступен, старый зачисляет 1000 один раз. Всего два исходных запроса создания, две проводки, баланс 3000.
Ссылки на итоговый SHA и CI публикуются в протоколе PR #77 после push.
Статус: реализовано, ожидает проверки CI и пакетной приёмки. Реальные платежи и ручная приёмка отложены; merge решает владелец.
