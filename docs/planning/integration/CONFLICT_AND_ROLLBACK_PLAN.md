# CONFLICT AND ROLLBACK

До изменения refs: зафиксировать remote SHA, clean status, базу, diff и локальные незавершённые изменения. При конфликте остановить процесс, сохранить обе стороны и историю, дать автору PR отдельную интеграционную ветку с явными parents; reviewer проверяет каждую сторону, миграции и tests. Запрещены reset --hard и force push, изменение чужой ветки и автоматическое удаление конфликтов.

После ошибочного принятого merge использовать reviewable revert/forward-fix после согласования владельца. DB rollback не считать безопасным по аналогии с Git revert: восстановление только на копии из проверенного backup, отдельная оценка потери данных и разрешение на production. Старые audit findings и provenance сохраняются.

## IN-01-FIX-01 — открытый access gate

[ADR PROPOSED](PRIVATE_PILOT_ACCESS_ADR.md), [матрица сценариев](ACCESS_CONTROL_TEST_MATRIX.md), [semantic review и вопросы vankhu21](SEMANTIC_PRESERVATION_REVIEW.md). Режим private в #17 не доказывает запрет outsider до identity; owner approval и peer review NOT_PROVEN. После утверждения отдельная кодовая задача; этот PR не меняет runtime. До решения не считать поведенческую сохранность или командное согласование подтверждёнными.
