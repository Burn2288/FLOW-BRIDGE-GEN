# CHANGES

Application source, migrations, provider/payments configuration: изменений нет. Полный точный перечень файлов фиксируется `MANIFEST.changed_files`, а затем проверяемым GitHub diff base→content SHA. Следующие группы описывают назначение, не заменяют перечень.

- docs/planning/: 10 обязательных planning документов, навигация, tasks.json, historical original workplans и SHA-bound GitHub/source/CI/migration evidence.
- docs/workplans/: два новых proposal worklist, dev branches не изменены.
- docs/audit/: manifest schema, handoff index и полный пакет самой задачи.
- AGENTS.md, CONTRIBUTING.md, .github/pull_request_template.md: помеченные PROPOSED дополнения по TASK_ID/evidence/audit/full sync; исходные нормы сохранены.
- .github/check_planning.py, requirements-docs.txt, workflows/docs.yml: schema/DAG/worklist/contract/hash/negative-fixture проверки. jsonschema только documentation tooling, runtime зависимости приложения не изменены.
- docs/README.md, PROJECT_STATE.md, DECISION_LOG.md: навигация и append-only предложение процесса; исторические записи не удалены.

Контракты C-001…C-031 покрыты задачами/owners, но текст target контрактов не объявлен implemented. Schema аудиторского пакета — отдельный tooling contract v1, не новая бизнес-схема БД. Новых migrations — 0.
