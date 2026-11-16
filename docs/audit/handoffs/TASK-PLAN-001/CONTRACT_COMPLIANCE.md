# CONTRACT COMPLIANCE

| Требование TASK-PLAN-001 | Реализация / evidence | Граница |
| --- | --- | --- |
| Оба исходных workplans изучены | history original blobs + SHA256/source refs | Новые версии proposals, личные dev-ветки сохранены |
| Актуальные PR8–17/SHA/CI и прочие ветки | github-snapshot, branch-heads, pr-deltas, source-symbols | CI не live; state отдельно |
| WBS всего продукта | 27 epics /81 detailed cards, tasks.json и FEATURE_COVERAGE | Нет ACCEPTED до integration/audit |
| Owner/reviewer/deps/checks/artifacts каждой задачи | MASTER + два worklist; checker | Назначения требуют owner approval |
| Параллелизм/контракты/миграции | PARALLEL_WORK_MATRIX и DAG | Shared file writer сериализован |
| Не создавать существующие модули повторно | ProviderRegistry/TaskLaunch/Pricing/Wallet/Admin/Mini App reused | Target gaps отдельными задачами |
| Безопасная integration sequence | IN tasks, PR base/head таблица, supersession | Merge/retarget не выполнены |
| Публикация evidence | Протокол, schema, docs workflow, handoff index | audit-artifacts bootstrap/transfer предложены, не выполнены |
| Нормативные дополнения | AGENTS/CONTRIBUTING/PR template marked PROPOSED | Старая модель веток сохранена |
| Все deliverables/link/schema checks | docs/planning + workplans + 11 package files | Результат exact SHA в TEST_RESULTS/MANIFEST |
| Draft PR и public package | PR и immutable links в MANIFEST/publication pointer | До подтверждения публикации readiness false |
| Source app untouched | Документальный allowlist diff, migrations=[] | Runtime acceptance не заявлена |
| Нет ложного sync/live/merge | BRANCH_SYNC/RISKS | Второй компьютер NOT_PERFORMED |

Контракты C-001…031: machine checker проверяет все references; [coverage](../../../planning/FEATURE_COVERAGE_MATRIX.md) связывает продуктовые области и задачи. Это проверка качества планирования, не приёмка реализации всех 31 контрактов.
