# Tests

Offline PR graph и документационные проверки выполняются локально. Git ancestry и blob checks являются source proof; runtime PostgreSQL/migration и приложение NOT_TESTED. CI нового PR будет зафиксирован отдельно.

Документационный CI успешен на 81a79c3ab7cf2e681d1732b939a189ca4ac2ae7f; runtime и DDL upgrade NOT_TESTED.

[CI 43884125910](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/43884125910) FAILED на SHA 7020715d5e8216bcf0db25c3438471df0be58d03: повторяющиеся пути в manifest changed_files, schema uniqueItems. Исправлено удалением дублей; новая проверка CI обязательна.
