# PARALLEL WORK MATRIX

Назначения предложены до owner approval. [Полные задачи](MASTER_WORK_BREAKDOWN.md). Effort 1/3/5 учитывает сложность, а не только количество; code авторство не отнимается. Ревью каждого задания делает другой разработчик, integration owner указан в карточке.

| Разработчик | Задач | Effort | Основная ответственность |
| --- | --- | --- | --- |
| Burn2288 | 40 | 142 | Worker/shared API/contracts, infrastructure, security, observability, referral backend |
| vankhu21 | 41 | 121 | Existing stack + Pricing/Wallet atomicity/Platega, Telegram, Mini App, studios, UI E2E |

## Конкретные параллельные окна

| Burn2288 | vankhu21 | Что должно быть готово | Изоляция / handoff |
| --- | --- | --- | --- |
| DC-01 | TA-01 | IN-18, IN-01 | Разные файлы/fixtures; при общем core.py/API — UI только на frozen schema fixture, интеграционный edit позже одним writer |
| ML-01 | PC-01 | IN-19 | Разные файлы/fixtures; при общем core.py/API — UI только на frozen schema fixture, интеграционный edit позже одним writer |
| PR-01 | TG-01 | AR-01, IN-19 | Разные файлы/fixtures; при общем core.py/API — UI только на frozen schema fixture, интеграционный edit позже одним writer |
| JO-01 | TG-01 | IM-02, IN-19 | Разные файлы/fixtures; при общем core.py/API — UI только на frozen schema fixture, интеграционный edit позже одним writer |
| JO-02 | MA-01 | JO-01, IN-19, OP-01 | Разные файлы/fixtures; при общем core.py/API — UI только на frozen schema fixture, интеграционный edit позже одним writer |
| AP-01 | MC-02 | AR-01, MC-01, MA-01 | Разные файлы/fixtures; при общем core.py/API — UI только на frozen schema fixture, интеграционный edit позже одним writer |
| AD-01 | VI-01 | AP-01, TA-01, JO-03, PC-01 | Разные файлы/fixtures; при общем core.py/API — UI только на frozen schema fixture, интеграционный edit позже одним writer |
| MU-01 | ML-03 | JO-03, PR-01, ML-02, MA-01 | Разные файлы/fixtures; при общем core.py/API — UI только на frozen schema fixture, интеграционный edit позже одним writer |
| RF-01 | AD-03 | AR-01, SL-01, AD-02, OB-02 | Разные файлы/fixtures; при общем core.py/API — UI только на frozen schema fixture, интеграционный edit позже одним writer |
| OP-02 | SE-03 | ML-02, WL-01, SE-02, AD-03, MA-03 | Разные файлы/fixtures; при общем core.py/API — UI только на frozen schema fixture, интеграционный edit позже одним writer |

## Обязательные locks и review owners

| Общая область | Основной владелец | Reviewer | Режим |
| --- | --- | --- | --- |
| Wallet/task_wallet/core financial transaction | vankhu21 | Burn2288 | WL-01 раньше WL-02/RF-02; один writer, no split atomic operation |
| Pricing/quote/tariffs | vankhu21 | Burn2288 | PC-01 freezes quote schema до AP-02; AP-02 вызывает порт, не меняет формулу |
| ProviderRegistry/manifest/capabilities | Burn2288 | vankhu21 | PR-01 freeze до schema UI MC-02; adapter-specific work через отдельные файлы |
| Job identity/state/worker | Burn2288 | vankhu21 | JO-03 freeze до API/studio migration; старые IDs совместимы |
| HTTP OpenAPI/session/admin | Burn2288 | vankhu21 | Единственный writer web.py; UI работает с frozen responses, backend changes serial |
| Telegram routing/navigation/admin UI | vankhu21 | Burn2288 | TG/TA/MA Telegram entry не меняются одновременно; template review отдельно |
| All PostgreSQL migrations | Burn2288 coordinator; конкретный task author writer | Второй разработчик | Резервировать следующий номер в PR по latest main, serial apply; never edit applied SQL |
| Settings/RBAC/event schema | Burn2288 | vankhu21 | AD-01/02 и API gate до UI; не заменять Telegram password session HTTP ролью |
| Audit schema/protocol | Burn2288 | vankhu21 | Изменение версии только review; каждый пакет в своём TASK_ID/revision path |

Перед началом владелец фиксирует точные файлы, contract/schema version и migration reservation в PR/task. Независимость task names не разрешает общий writer. При обнаружении пересечения выполняется только read-only анализ, fixture/UI на согласованной схеме или другая ready задача. Решение о контракте блокирует только его потребителя, а не всю команду. Каждый разработчик берёт одну крупную implementing задачу, второй ревьюирует ограниченный готовый срез; размер PR не раздувается до всего epic. Ни одно окно не обходится без собственных DAG dependencies и stage/live gates.

[Владельцы и reviewer всех 31 общих интерфейсов](CONTRACT_OWNERSHIP.md).

## FIX-01: семантика и нагрузка

`parallel_with` — симметричное разрешение независимой работы; задачи без зависимости и общих путей. `paths` трактуются консервативно как возможная запись: пересечение запрещает пару; исключения не поддерживаются. Подготовка только чтением не объявляется независимой задачей и не разрешает параллельный merge. IN-01/TA-01, AP-02/PC-02, VO-02/OB-02, RF-02/SL-03 исключены; последовательность определяется зависимостями и блокировкой общего файла.

Оценка 142 против 121 — условные баллы, разница 17,4%, не сроки: Burn2288 ведёт общие архитектурные контракты, worker, API, безопасность и эксплуатацию; vankhu21 сохраняет сложный существующий финансовый код, интеграцию стэка и ручную UI-приёмку. Критические точки Burn2288: IN-01/19, JO-01–03, AR-01/02, AP-01–03, инфраструктура и security. vankhu21 блокируется последовательным #8–17, принятием API/контрактов и доступом к HTTPS/провайдерам. До готовности допустимы независимые read-only исследования и fixtures на зафиксированном контракте, без параллельной записи и merge. Ревью второго разработчика учитывается отдельной ёмкостью при планировании каждой итерации. Если очередь ревью или критический путь задерживает следующую итерацию, оба разработчика сверяют оставшиеся оценки, доступность и пересечения и согласуют перенос готового независимого среза с обновлением владельца, reviewer и evidence; авторство существующего кода сохраняется. При отсутствии API, документации или доступа фиксируют BLOCKED с конкретной причиной и воспроизводимым тестом; выбирают независимую готовую задачу, не обходя неопределённые платные исходы.
