# REGRESSION

Проверяются сохранность существующей работы и качество документации, а не runtime приложения.

1. Diff от foundation base ограничен docs/, AGENTS.md, CONTRIBUTING.md, .github documentation tooling/template/workflow. src/, miniapp/, migrations/, compose/deploy/runtime requirements не менялись.
2. Original dev workplan bytes сохранены и сверены SHA256 с Git blobs; обе dev ветки и auditor refs не изменялись исполнителем.
3. Existing CONTRIBUTING/AGENTS/PR template текст сохранён, изменения добавлены явно PROPOSED. Main и foundation не передвинуты; отдельная planning ветка.
4. Pre-existing docs checker выполняется вместе с новым schema/DAG checker. Новые задачи ссылаются на существующие PR SHA и не создают дубликаты Wallet/Registry/TaskLaunch/Mini App.
5. Устаревшие blockers аудита учтены по lineage: штатный image fixture исправлялся в0453995, inbox/defer вd691d54; они не представлены как неизменённые runtime дефекты.

App regression suite: NOT_TESTED в этом docs-only срезе. На code candidate исторический CI397 observed, это не новый regression run. Independent live regression остаётся будущей задачей по stage gates.
