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

## Финальная проверка

Проверенный SHA: `61a968cbf9cbee230874aa13ce638b053346e636`; tree: `8bc421cc67336f55186720c972c59025cb25aa21`.

- Профильный PostgreSQL workflow IM01/ML03: `70 passed`.
- Chromium OP01: success.
- Общие GitHub Actions на этом SHA: `40/40 success`.
- Платные API и production не вызывались.
- Merge в main не выполнялся.
