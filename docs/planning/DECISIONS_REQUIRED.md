# DECISIONS REQUIRED

Это открытые решения, не вопросы с молчаливым согласием. Предлагаемые назначения вступают в силу после approval плана владельцем; second developer review обязателен. Принятые ограничения single backend/no blind paid retry не пересматриваются ради удобства.

| ID | Решение и предлагаемый безопасный вариант | Кто решает / reviewer | Что блокирует | Независимая работа до ответа |
| --- | --- | --- | --- | --- |
| D-01 | Порядок #1/#8–#18, docs stacked exception и разрешение merge каждой ступени. Предпочтение: сохранить ancestry и старые PR, отдельный retarget после каждого accepted main. | Burn2288 + vankhu21; ChatGPT audit | IN-01/18, интеграция; approval этой планировочной PR не разрешает auto-merge | Read-only graph, profiles, документальные предложения |
| D-02 | DarkFlow tokens как внутренняя единица; XTR и RUB только внешние settlement units. Prices, rates, deterministic rounding, quote max cost; никакой конверсии единиц без ADR/миграции. | Burn2288; vankhu21 finance author | PC-01/02, PY-01, MU-01, RL-01 | Existing price fixtures, schema draft |
| D-03 | Refund/capture timing, disputed/chargeback/debt/manual compensation; Platega только отдельно допустимый внешний канал, не Telegram digital checkout. | Burn2288; vankhu21 | WL-02/PY-02/RL-01 | Synthetic failure/reconciliation tests |
| D-04 | Сохранить ADMIN_TELEGRAM_IDS или вводить documented alias ADMIN_TELEGRAM_USER_IDS; server roles и sensitive-action policy. | Burn2288; vankhu21 | AD-01 | Existing auth inventory и deny fixtures |
| D-05 | Выделенный HTTPS URL/DNS/proxy + тестовый бот и два аккаунта; кто разрешает изменения тестового окружения. | Burn2288 | OP-01/MA-01 physical client proof | Local HTTP/session/owner tests |
| D-06 | Явное разрешение, точный бюджет и список live generation/Stars test vs real payments; provider/model/request cap, stop rules. | Burn2288 | IM-02/PR-03/VI-02/VO-02/MU-02/PY-03/RL-02 | Fixtures без реальных расходов |
| D-07 | Referral reward percent/base/version, exclude promo, hold, fraud, refund debt. Рекомендация — reward только от captured paid successful durable generation. | Burn2288; vankhu21 | RF-02, коммерческий referral rollout | RF-01 immutable binding, donor review без private publication |
| D-08 | Юридические тексты и версии, paid-media retention, input privacy/deletion/legal hold, content restrictions и licensing. | Burn2288 + подходящий профильный reviewer | SL-01/SE-02/MU-01/RL-01 | Consent mechanics и безопасные синтетические retention tests |
| D-09 | Test/Ubuntu environment, RPO/RTO, SLO, queue/user/provider caps, допустимые окна recovery. Числа установить до нагрузочной приёмки. | Burn2288; vankhu21 | JO-02 acceptance, OP-02/03, RL-01 | Reproducible load harness и измерения baseline |
| D-10 | Pilot capability scope, цены/аудит/оператор support, release authority и stop/rollback. | Burn2288 после peer + ChatGPT verdict | RL-01/02/03 | Закрытые тесты, runbooks, package preparation |

## Нормативные расхождения

CONTRIBUTING сейчас требует work/<login>/<task> от main. Пользователь TASK-PLAN-001 прямо разрешил planning от docs/foundation-contracts-v1 и Draft PR в документационную ветку: это исключение только этой документационной задачи. Новая долговременная ветка audit-artifacts и повторяющийся docs staging остаются предложением до review, не молчаливой отменой правил. Historical FOUNDATION_INDEX запрещал оценивать/назначать работы в старом пакете; текущий TASK-PLAN-001 явно расширяет scope, старое ограничение не отменяет новое поручение.

## Платёжная граница

На 2026-11-16 повторно проверены [официальные digital payments](https://core.telegram.org/bots/payments-stars) и [Developer Terms](https://telegram.org/tos/bot-developers). Внутри Telegram digital services оплачиваются Stars/XTR. Сохранение existing Platega кода не разрешает показывать такой checkout в этом продукте. Отдельные юридические/налоговые выводы в этой задаче не делаются.

## IN-01-FIX-02 — OWNER_APPROVED / IMPLEMENTATION_PENDING / PEER_REVIEW_PENDING

[Решение владельца](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/20#issuecomment-6919575091) утверждает private: admin + отдельный PILOT_TELEGRAM_USER_IDS, outsider denied до создания identity/user/wallet; tester не получает admin rights. Public: обычная регистрация после consent, generation/model/payment gates отдельно. Серверный admission обязателен для Telegram, callbacks, Mini App и HTTP, с проверкой отзыва сессий. Existing jobs, paid events, wallet и reconciliation сохраняются. Код ещё не реализует эту политику, runtime NOT_TESTED. Ревью vankhu21 ожидается. [Отдельное задание](integration/SEC-PILOT-01.md).
