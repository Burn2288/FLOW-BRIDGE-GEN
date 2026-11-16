# CI AND REVIEW GATES

На каждом PR: текущий GitHub head/base, список commits и migrations; полный применимый Documentation/Isolated acceptance Actions на точном SHA и результаты без скрытых skip; локальный PostgreSQL regression в изоляции и migration doctor где меняется схема. Reviewer — второй разработчик; IN-01 отдельно требует подтверждение vankhu21 сохранности своего кода/истории/миграций. Независимый аудитор проверяет evidence, а owner отдельно разрешает конкретный merge.

Доказательство CI на предыдущем base или до retarget не заменяет повторный прогон. Ревью, не привязанное к актуальному diff/SHA, требует переоценки. Источник действий и обсуждений — [GitHub snapshot](github-snapshot.json); timeline не является доказательством формального approval.

## IN-01-FIX-01 — открытый access gate

[ADR PROPOSED](PRIVATE_PILOT_ACCESS_ADR.md), [матрица сценариев](ACCESS_CONTROL_TEST_MATRIX.md), [semantic review и вопросы vankhu21](SEMANTIC_PRESERVATION_REVIEW.md). Режим private в #17 не доказывает запрет outsider до identity; owner approval и peer review NOT_PROVEN. После утверждения отдельная кодовая задача; этот PR не меняет runtime. До решения не считать поведенческую сохранность или командное согласование подтверждёнными.
