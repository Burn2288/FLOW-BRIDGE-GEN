# CI AND REVIEW GATES

На каждом PR: текущий GitHub head/base, список commits и migrations; полный применимый Documentation/Isolated acceptance Actions на точном SHA и результаты без скрытых skip; локальный PostgreSQL regression в изоляции и migration doctor где меняется схема. Reviewer — второй разработчик; IN-01 отдельно требует подтверждение vankhu21 сохранности своего кода/истории/миграций. Независимый аудитор проверяет evidence, а owner отдельно разрешает конкретный merge.

Доказательство CI на предыдущем base или до retarget не заменяет повторный прогон. Ревью, не привязанное к актуальному diff/SHA, требует переоценки. Источник действий и обсуждений — [GitHub snapshot](github-snapshot.json); timeline не является доказательством формального approval.

## IN-01-FIX-01 — открытый access gate

[ADR OWNER_APPROVED](PRIVATE_PILOT_ACCESS_ADR.md), [матрица сценариев](ACCESS_CONTROL_TEST_MATRIX.md), [semantic review и вопросы vankhu21](SEMANTIC_PRESERVATION_REVIEW.md). Режим private в #17 не доказывает запрет outsider до identity; owner approval подтверждён; peer review NOT_PROVEN. После принятия базы отдельная кодовая задача; этот PR не меняет runtime. До peer review и испытаний не считать поведенческую сохранность или командное согласование подтверждёнными.

## IN-01-FIX-02 — OWNER_APPROVED / IMPLEMENTATION_PENDING / PEER_REVIEW_PENDING

[Решение владельца](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/20#issuecomment-6919575091) утверждает private: admin + отдельный PILOT_TELEGRAM_USER_IDS, outsider denied до создания identity/user/wallet; tester не получает admin rights. Public: обычная регистрация после consent, generation/model/payment gates отдельно. Серверный admission обязателен для Telegram, callbacks, Mini App и HTTP, с проверкой отзыва сессий. Existing jobs, paid events, wallet и reconciliation сохраняются. Код ещё не реализует эту политику, runtime NOT_TESTED. Ревью vankhu21 ожидается. [Отдельное задание](SEC-PILOT-01.md).
