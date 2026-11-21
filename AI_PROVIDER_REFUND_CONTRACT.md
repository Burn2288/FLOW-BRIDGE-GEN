# Контракт результата AI и компенсации

## Принципы

Сохранять оригинальные полученные байты успешного provider media поля без трансформации. Не повторять генерацию из-за повреждённого заголовка. Проверять источник поля, пустые данные, размер, распознаваемый формат и безопасность URL. При ошибке Telegram на отправке изображения использовать документ; ошибка транспортной доставки сама по себе не считается успешной доставкой.

Компенсация за возврат генерации — отдельное финансовое событие, не связанное с возвратом пополнения. Допустимы только проверяемые, привязанные к конкретному quote и исходному charge события. Повтор и гонка не должны создавать повторные ledger postings. Ручная сверка не кредитует кошелёк.

## Статус

`IMPLEMENTED_WITH_MOCKS`

- Успешные media bytes сохраняются без преобразования: распознанные PNG/JPEG получают соответствующее расширение, неизвестный бинарный формат — безопасное имя `result.bin` и выдачу как attachment. Пустые, превышающие 5 MiB, JSON, HTML/XML и error payload отвергаются. URL скачивается только с HTTPS/проверками DNS и доступа; допускаются image media и `application/octet-stream`.
- Получены сквозные PostgreSQL тесты: quote/reserve, один provider POST, повреждённый результат, сохранение и повторная выдача оригинальных байтов, подтверждённый refund до capture (только release) и после capture (ровно одна `task_refund`). Неизвестный receipt оставляет результат доступным и не создаёт автозачисление.
- Финансовая запись проверяется по provider, quote/job identity, исходному charge operation ID, сумме и валюте/единице. Full refund должен равняться исходному charge. DB guard и immutable receipts защищают связь и повторную запись.
- При отсутствии стабильного provider job ID он не синтезируется: случай идёт на reconciliation без автоматического refund. Для оператора доступна команда `/price_account <quote> manual-review <operation_id> <amount> <unit> <evidence_ref>` за admin session. Она фиксирует операцию, сумму, единицу, доказательство и оператора в неизменяемом аудите и закрывает кейс `manual_reviewed_no_credit`, не меняя баланс.
- Финансовые unknown/duplicate/late/concurrent случаи остаются идемпотентными и не повторяют provider POST.

`NOT_PROVEN_REAL_PROVIDER`

Production adapter для финансового API AnyModel/Clodex не зарегистрирован. Тесты используют доверенные fixtures; они не доказывают контракт, подпись или фактический возврат настоящего агрегатора. Платные API, платежи и production не проверялись.

`DEFERRED`

Физическая проверка Telegram/Mini App на реальных клиентах и независимый финальный аудит.

## FT-039-FIX-02: жизненный цикл ручной сверки

manual-review фиксирует неизменяемое доказательство оператора, но не завершает финансовый случай: его статус остаётся required, поэтому он продолжает отображаться в task_financial_reconciliation_queue. Команда no-refund требует отдельные operation ID и ссылку на доказательство подтверждённого отсутствия возврата, записывает отдельную неизменяемую audit-запись и завершает кейс как resolved_no_refund без движения кошелька.

Поздний доверенный full_refund имеет приоритет над ручным результатом resolved_no_refund: он сохраняется как provider receipt, выполняет ровно одну компенсацию согласно состоянию capture и переводит кейс в resolved. Ручные audit-записи при этом не меняются.

## Проверяемые снимки FIX-02 / FIX-03

- FIX-02: HEAD 513e013f126ba85c65fdc567779d80c13971dfa7, tree 7d187eba9e9379983a17575b6a49993dfd455dcf. [PostgreSQL IM01/ML03](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/44829070680), [OP01 Chromium](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/44829070733).
- FIX-03 implementation: HEAD 09cc0d14aff991a4237afb4460da474b9fcea1ec, tree 8576b9741ea9c3aa0a4074fd368bfb2bffbfd832. [PostgreSQL IM01/ML03 — 70 passed](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/44886076961), [OP01 Chromium](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/44886076946), [TQ01 composite regression](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/44886077182).
- Итоговый SHA после синхронизации этих документов и полный результат обязательных workflow записываются в описание PR #104 после завершения CI.

`BLOCKED`

Автоматическое получение реального подтверждения refund заблокировано отсутствием проверяемого provider financial API/контракта. Это не блокирует тестовый функциональный уровень.

## Проверки

На SHA `61a968cbf9cbee230874aa13ce638b053346e636` целевой PostgreSQL workflow IM01/ML03 завершился `70 passed`; Chromium OP01 и все 40 PR workflows завершились успешно. Этот SHA — проверенный кодовый срез; PR #104 остаётся Draft, merge в main не выполнялся.
