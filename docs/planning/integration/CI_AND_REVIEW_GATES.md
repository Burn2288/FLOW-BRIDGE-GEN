# CI AND REVIEW GATES

На каждом PR: текущий GitHub head/base, список commits и migrations; полный применимый Documentation/Isolated acceptance Actions на точном SHA и результаты без скрытых skip; локальный PostgreSQL regression в изоляции и migration doctor где меняется схема. Reviewer — второй разработчик; IN-01 отдельно требует подтверждение vankhu21 сохранности своего кода/истории/миграций. Независимый аудитор проверяет evidence, а owner отдельно разрешает конкретный merge.

Доказательство CI на предыдущем base или до retarget не заменяет повторный прогон. Ревью, не привязанное к актуальному diff/SHA, требует переоценки. Источник действий и обсуждений — [GitHub snapshot](github-snapshot.json); timeline не является доказательством формального approval.
