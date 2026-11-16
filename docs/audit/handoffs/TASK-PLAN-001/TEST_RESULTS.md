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

## Фактический результат на опубликованном content SHA

`6e0b7a63241f2eeb14204ec48f2592b64e908f90` / tree `ba85a4f70ab63c48ec4cb0214bf9d3875157ae8c`: локальный exact checkout, Python3.12.14/jsonschema4.25.1. Docs:65 файлов; registry:81 задач/27 epics/31 contracts, DAG ацикличен; anchors:193; manifest schema/11 files/hashes PASS; 6 invalid fixtures отвергнуты; diff --check exit0. Source paths261/261, original workplan bytes2/2 совпали. Это количества файлов/fixtures, не заявление о65 unit tests.

[GitHub Documentation CI](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/43873943770) completed/success, job133321990145: install/check_docs/check_planning success. [Безопасный воспроизводимый вывод](../../../planning/evidence/planning-validation.txt). Начальные failures документационных проверок и исправления сохранены в этом evidence, не скрыты. Final artifact commit CI хранится отдельным publication pointer в PR, а не невозможной self-reference.
