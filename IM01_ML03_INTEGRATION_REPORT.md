# IM-01 / ML-03: отчёт интеграции и FT-039-FIX-01

База `main`: `a889d8306c743c0046b710b950608052eabfdc78`. PR #104 остаётся открытым Draft, целевая ветка — `main`; merge не выполнялся.

## Статус реализации

`IMPLEMENTED_WITH_MOCKS`

- Ограниченное сохранение оригинальных provider image bytes; распознанные форматы получают соответствующее имя, нераспознанные сохраняются как `result.bin` и выдаются как документ/attachment. JSON/HTML/XML/errors, пустые и чрезмерные ответы отвергаются. HTTPS, DNS pinning, SSRF/access и лимиты сохранены.
- PostgreSQL image/refund E2E проходит quote → reserve → один mock provider POST → повреждённый файл → сохранение оригинала → mock financial receipt → settlement. Pre-capture full refund освобождает только резерв; post-capture full refund создаёт ровно одну `task_refund`. Неизвестный результат не вызывает автозачисление и не удаляет файл.
- Receipt привязывается к доступным доказательствам операции: provider/job/quote, charge operation ID, точным amount и unit. Отсутствующий provider job ID не придумывается; такая генерация регистрируется для ручной сверки.
- Операторская команда `/price_account <quote> manual-review <operation_id> <amount> <unit> <evidence_ref>` ограничена admin session, проверяет поля и идемпотентность, пишет immutable audit и закрывает кейс `manual_reviewed_no_credit` без движения кошелька.
- Проверены повторы, поздний refund, неизвестный исход и конкурентные вызовы. Существующие workflow IM-01, ML-02/03, Stars, referrals, FT-037, Telegram/Mini App и общий регрессионный набор сохранены.

`NOT_PROVEN_REAL_PROVIDER`

Production financial adapter для AnyModel/Clodex не зарегистрирован. Mock receipt подтверждает только тестовую логику; реальные возвраты, платные API и production поведение не проверялись.

`DEFERRED`

Физический прогон Telegram/Mini App на реальных клиентах и независимый финальный аудит.

`BLOCKED`

Подтверждаемая автоматическая сверка реальных provider refunds ждёт machine-readable API/контракт от провайдера. Тестовый уровень завершён без подключения реального API.

## FT-039-FIX-02: ручной lifecycle

Ручное изучение доказательства больше не скрывает неурегулированный случай: manual-review оставляет его required в рабочей очереди. Явно доказанное отсутствие provider refund закрывается отдельной operator action no-refund как resolved_no_refund без проводки. Поздний доверенный full refund после review или такого закрытия выполняет обычную идемпотентную компенсацию, переводит случай в resolved и сохраняет первоначальный immutable audit.

## FT-039-FIX-03: terminal reconciliation и CI

FIX-03 проверяет наличие одного корректного task_reserve и ровно одного согласованного task_capture/task_release перед resolved_no_refund. При незавершённом резерве case остаётся required. Поиск immutable receipts выполняется до закрытия: подтверждённый partial refund оставляет case в очереди, а full refund проходит через reconcile_generation, включая позднюю идемпотентную компенсацию и сохранение операторского audit.

Снимок FIX-02: HEAD 513e013f126ba85c65fdc567779d80c13971dfa7, tree 7d187eba9e9379983a17575b6a49993dfd455dcf; [PostgreSQL IM01/ML03](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/44829070680), [OP01 Chromium](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/44829070733).

FIX-03 implementation HEAD 09cc0d14aff991a4237afb4460da474b9fcea1ec, tree 8576b9741ea9c3aa0a4074fd368bfb2bffbfd832. [Профильный PostgreSQL — 70 passed](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/44886076961), [OP01 Chromium](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/44886076946), [TQ01 composite regression](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/44886077182). Итоговый документальный commit и обязательные CI на нём будут записаны в PR #104 после завершения workflow.

## Финальная проверка

Проверенный SHA: `61a968cbf9cbee230874aa13ce638b053346e636`; tree: `8bc421cc67336f55186720c972c59025cb25aa21`.

- Профильный PostgreSQL workflow IM01/ML03: `70 passed`.
- Chromium OP01: success.
- Общие GitHub Actions на этом SHA: `40/40 success`.
- Платные API и production не вызывались.
- Merge в main не выполнялся.
