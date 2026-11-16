# RELEASE MILESTONES — S0–S8

Предлагаемые gate results, не текущая приёмка. [Задачи](MASTER_WORK_BREAKDOWN.md), [DAG](IMPLEMENTATION_DEPENDENCIES.md). Этапы согласованы с ROADMAP: S4 providers, S5 API, S6 admin, S7 hardening. Старые foundation test matrix S4/S5/S6 labels — historical discrepancy; DC-01 исправляет через review, не молча переопределяет контракт.

| Этап | Обязательный наблюдаемый результат / задачи | Проверки и критерий перехода | Владелец gate / reviewer |
| --- | --- | --- | --- |
| S0 | IN-01/02/08–19; DC-01; TA-01; TQ-01; AU-01/02 | История/PR inventory, migration checksums, clean accepted build, CI exact SHA и согласованный план. Старые PR могут сохранять исторический OPEN до решения, supersession явно утверждён. Нет runtime PASS по исходникам. | Burn2288 / vankhu21 |
| S1 | PC-01, PY-01, ML-01, IM-01/02 | Ordinary-user same-config fixture + три real image successes, один transient failure, durable library/restart, receipts и no double debit. Receipt Telegram отдельно от USER_VISIBLE_NOT_PROVEN. При внешнем blocker сохранить точную границу и reproducible test; дальнейшие независимые offline работы допустимы, S1 не закрыт. | vankhu21 / Burn2288 |
| S2 | JO-01/02 | Atomic claim/lease/heartbeat/fence, bounds/fairness/backpressure/cancel/timeout/graceful shutdown, emulator 10 users + 50/100 concurrent requests, process kill и no blind POST replay. p95/throughput/queue/locks и критерии SLO согласовать до прогона (D-09). | Burn2288 / vankhu21 |
| S3 | JO-03, AR-01/02, ML-02, VI-01, VO-01, OB-01 | Четыре типа через общий job/service projection с preserved old IDs; crash/uncertain transitions, one wallet. Миграции на копии, backward compatibility. | Burn2288 / vankhu21 |
| S4 | PR-01/02/03, MC-01, MU-01 | Два разных adapter contracts, manifest staging/rollback, per-provider health; real probes каждой продаваемой capability отдельно. Нет unknown failover или arbitrary API scripts. | Burn2288 / vankhu21 |
| S5 | AP-01/02/03, MA-01/02/03, TG-01/02/03, MC-02, ML-03, VI-02/VO-02/MU-02, PY-03, SL-01 | OpenAPI 3.1 соответствует implemented endpoints; HTTPS WebView двух аккаунтов, quote/job/idempotency, same balance/library, negative auth/owner tests. Полный parity завершается MA-04 перед S8, будущие support/referrals помечены зависимостями. | vankhu21 / Burn2288 |
| S6 | AD-01/02/03, TA-02, PC-02, SL-02/03, OB-02/03 | Server RBAC, role revoke, один typed mutation preview/audit/rollback, diagnostic job ID без SQL, preserved Telegram Admin, reports/alerts и support. | Burn2288 / vankhu21 |
| S7 | WL-01/02, PY-02, RF-01/02/03, SE-01/02/03, OP-02 | Transaction races/reconciliation/refund/debt, callback auth, threat-model probes, secret-safe export, paid media retention, DB+media restore. Owner financial/legal decisions утверждены. | Burn2288 / vankhu21 |
| S8 | MA-04, TQ-02, OP-03, DC-02, RL-01/02/03 | Ubuntu amd64 reproducible release, весь клиентский путь включённых capabilities, independent audit, owner go/no-go, stop/rollback/support, две whole-clone sync. Commercial pilot scope явно ограничен. | Burn2288 / vankhu21 |

После любого этапа публикуется ответ: проблема; факт; evidence; root cause (либо N/A/unconfirmed); code/doc change; physical check; regression; NOT_PROVEN; next stage. Gate не считается пройденным до пакета и независимого решения. Оплата, платные probes, DNS/production/deploy/release не разрешены самим этим планом.
