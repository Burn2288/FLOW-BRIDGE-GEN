# LOCAL SYNC CHECKLIST

На каждой машине отдельно после разрешённого merge: сохранить текущие uncommitted изменения; `git status --short --branch`; `git fetch --prune origin`; `git switch main`; `git merge --ff-only origin/main`; проверить `git rev-parse HEAD` и `git rev-parse origin/main`. Записать оба SHA, версии Python/PostgreSQL, dependency setup, миграции на изолированной БД, integration suite, результаты passed/failed/skipped и health всей сборки. SHA не заменяет запуск. При грязном дереве/расхождении остановиться и сохранить обе версии.

В этой задаче полная синхронизация обеих рабочих машин и runtime тесты NOT_PERFORMED.
