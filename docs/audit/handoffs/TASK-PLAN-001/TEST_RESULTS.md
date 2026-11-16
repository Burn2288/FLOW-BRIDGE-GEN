# TEST RESULTS

До публикации и content freeze результаты этой задачи обновляются отдельной записью, привязанной к content SHA; MANIFEST — machine index фактических проверок. Отсутствие runtime/live тестов не скрывается.

## Среда и команды

Windows PowerShell, Git; bundled Python3.12 и jsonschema4.25.1 из локальной .local/doc-deps. На обычном PATH python.exe — недоступный WindowsApps alias; использован bundled executable, не ошибка приложения. CI Ubuntu использует python3 и .github/requirements-docs.txt.

```sh
python -m pip install -r .github/requirements-docs.txt
python .github/check_docs.py
python .github/check_planning.py
git diff --check
```

При локальной установке dependency в .local/doc-deps задан PYTHONPATH, директория ignored. Проверки: relative Markdown links, обязательные документы, 81 task / 27 epics, unique IDs, acyclic DAG, два worklist, contract IDs C-001…031, exact source SHA snapshot, 11 package files, JSON Schema2020-12, evidence hashes, шесть invalid manifest fixtures. Task-anchor checks дополняют pre-existing link checker. Внешние URLs не доказываются regex: GitHub repository/PR/CI metadata отдельно прочитаны API.

Unit приложения: NOT_TESTED. PostgreSQL integration приложения: NOT_TESTED. Mock-provider suite в этой задаче: NOT_TESTED. Live provider/Telegram/payment: NOT_TESTED. Historical CI397 — read-only наблюдение, не собственный новый запуск. Production/migrations/paid requests: 0.
