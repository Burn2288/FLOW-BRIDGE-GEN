# AUDIT GATES

| Gate | Когда | Требуемые доказательства | Кто разрешает переход |
| --- | --- | --- | --- |
| G0 Scope/base | До edits | TASK_ID, actual main/base/head, colleague PR/code, contract versions, locks/decisions | Task owner + второй разработчик для пересечений |
| G1 Fact/root cause | До defect fix | Reproducer, expected/actual, safe trace; новый feature N/A; без подтверждения ROOT_CAUSE_UNCONFIRMED | Peer проверяет факт; не переносить старый audit на новый SHA автоматически |
| G2 Software proof | После минимального diff | Unit/contract/PostgreSQL/process-kill по задаче; commands/env/pass/fail/skip/excluded отдельно; full relevant regression | CI exact SHA + peer review |
| G3 Physical/live | При внешней функциональности | Разрешённая среда/операции, реальные provider/Telegram IDs, persisted result/ledger; UI record отдельно | Независимый аудитор; BLOCKED_EXTERNAL без доступа |
| G4 READY_FOR_AUDIT | Перед передачей | Public code/docs PR и immutable SHA package всех 11 файлов, валидный MANIFEST, CI URLs, known limits, publication pointer; все требования задачи покрыты либо explicitly blocked | Codex только объявляет readiness, не свой независимый PASS |
| G5 Independent acceptance | После проверки ChatGPT | PASS/PARTIAL/FAIL/BLOCKED/NOT_PROVEN/NOT_TESTED на exact SHA/контракт, негативная история сохранена | ChatGPT verdict + peer review + owner approval; READY не verdict |
| G6 Integration/archive | До/после согласованного merge | Updated base/head CI, code review; artifact PR → audit-artifacts + индекс exact artifact SHA/hash; no auto-merge | Owner и действующие правила команды |
| G7 Whole clone sync | После принятия | origin/main до/после, local HEAD, clean tree, полный код обоих, deps/DB/test health; каждое устройство отдельно | Owner Codex каждой машины; недоступное NOT_PERFORMED |

Документационная TASK-PLAN-001 требует физически доступный Draft PR, сохранённые SHA baseline, schema/DAG/link/doc checks и пакет, а не provider live. Приложение не запускалось — NOT_TESTED и это корректный out-of-scope, не software FAIL. Статус READY возможен до merge в долгосрочную audit-artifacts только когда пакет уже опубликован в рабочем PR по immutable SHA; archive transfer остаётся отдельным gate, нельзя скрывать pending.

Для каждого S0–S8 отдельный контроль milestone из RELEASE_MILESTONES. Cross-stage offline preparation допустима, acceptance gate прежнего этапа не закрывается от этого. Статусы не сводятся в один общий «всё PASS». Любой новый content SHA, влияющий на доказательство, требует актуального CI и нового аудитного revision. Pure artifact/publication commits имеют отдельный SHA и checks, не маскируют изменение tested content.
