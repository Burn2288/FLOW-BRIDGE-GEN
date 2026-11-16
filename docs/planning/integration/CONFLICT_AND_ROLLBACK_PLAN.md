# CONFLICT AND ROLLBACK

До изменения refs: зафиксировать remote SHA, clean status, базу, diff и локальные незавершённые изменения. При конфликте остановить процесс, сохранить обе стороны и историю, дать автору PR отдельную интеграционную ветку с явными parents; reviewer проверяет каждую сторону, миграции и tests. Запрещены reset --hard и force push, изменение чужой ветки и автоматическое удаление конфликтов.

После ошибочного принятого merge использовать reviewable revert/forward-fix после согласования владельца. DB rollback не считать безопасным по аналогии с Git revert: восстановление только на копии из проверенного backup, отдельная оценка потери данных и разрешение на production. Старые audit findings и provenance сохраняются.

## IN-01-FIX-01 — открытый access gate

[ADR OWNER_APPROVED](PRIVATE_PILOT_ACCESS_ADR.md), [матрица сценариев](ACCESS_CONTROL_TEST_MATRIX.md), [semantic review и вопросы vankhu21](SEMANTIC_PRESERVATION_REVIEW.md). Режим private в #17 не доказывает запрет outsider до identity; owner approval подтверждён; peer review NOT_PROVEN. После принятия базы отдельная кодовая задача; этот PR не меняет runtime. До peer review и испытаний не считать поведенческую сохранность или командное согласование подтверждёнными.

## IN-01-FIX-02 — OWNER_APPROVED / IMPLEMENTATION_PENDING / PEER_REVIEW_PENDING

[Решение владельца](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/20#issuecomment-6919575091) утверждает private: admin + отдельный PILOT_TELEGRAM_USER_IDS, outsider denied до создания identity/user/wallet; tester не получает admin rights. Public: обычная регистрация после consent, generation/model/payment gates отдельно. Серверный admission обязателен для Telegram, callbacks, Mini App и HTTP, с проверкой отзыва сессий. Existing jobs, paid events, wallet и reconciliation сохраняются. Код ещё не реализует эту политику, runtime NOT_TESTED. Ревью vankhu21 ожидается. [Отдельное задание](SEC-PILOT-01.md).
