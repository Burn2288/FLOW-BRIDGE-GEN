# EVIDENCE PUBLICATION PROTOCOL v1 — proposal

## Пути и роли

В рабочем code/docs PR канонический пакет: `docs/audit/handoffs/<TASK_ID>/` (именно этот путь требуется TASK-PLAN-001). Долгосрочный архив: branch `audit-artifacts`, путь `audit/handoffs/<TASK_ID>/<content_sha>/r<N>/`. Это явное отображение двух путей из постановки, не два независимых источника истины. [Schema](../audit/MANIFEST.schema.json), [index](../audit/handoffs/INDEX.md). В архив переносят пакет без изменения bytes и sha256 inventory; schema фиксируется той же версией под audit/schema/v1/. Относительные ссылки внутри пакета остаются локальными, внешние source links — immutable GitHub URLs.

Разработчики пишут только свои task/revision paths через reviewable PR. `auditor` read-only для разработчиков; независимые verdict публикует ChatGPT/аудитор, не исполнитель. Reviewer второго разработчика не заменяет независимый verdict.

## Создание audit-artifacts без скрытой смены правил

На текущем snapshot ветка отсутствует. В этой задаче подготовлена схема, ветка не создана и не интегрирована. После одобрения протокола владелец создаёт branch от согласованного main SHA (не orphan/force). Унаследованные файлы не удаляются; archive commits добавляют только audit/**, не копируют новое application code. Создаётся отдельная `work/<login>/audit-store-bootstrap` от выбранной archive base и Draft PR в `audit-artifacts`, содержащий README, schema, индекс и policy. Второй developer review, independent audit по необходимости и owner merge approval. Это явное согласуемое исключение к правилу work-from-main, не автоматическая смена CONTRIBUTING. Branch protection/rulesets, если доступны, require peer + schema/index CI; если workflow ещё не принят, проверка из bootstrap PR обязательна и ограничение явно указано.

## Публикация каждого задания

1. TASK_ID + approved scope; fresh fetch, base/head/main SHA и colleague baseline, lock-check. Секреты не входят ни в patch, ни в stdout evidence.
2. Выполнить change и relevant tests; зафиксировать implementation/content commit H. `MANIFEST.head_sha` означает именно проверяемый content SHA H. `head_branch` — рабочая ветка. Не вставлять сам SHA коммита, содержащего manifest, в его собственные bytes: это невозможная самоссылка. `base_sha` — база diff, `main_sha` — наблюдаемая accepted main, не догадка о future merge.
3. Добавить все 11 файлов пакета и evidence hashes. Для документационной задачи H содержит проверенный план и validator, последующие изменения пакета не изменяют H. Любое изменение плана/кода создаёт новый H и новый revision пакета. Test result хранит собственный `source_sha`, environment/type/status/counts/command/url. Скрипты checks SHA пакета проверяются отдельно.
4. Commit пакета A, опубликовать ветку и Draft PR; получить GitHub подтверждение H/A/PR URL. В PR description публикационный указатель содержит content SHA H, artifact SHA A и immutable manifest URL `blob/A/.../MANIFEST.json`. Это разрешает самоссылку без ложного head. CI результата A также указывается в PR, финальном сообщении и следующем publication/index record; не требуется бесконечный коммит нового SHA в самом себе.
5. Только когда пакет доступен, schema/structure/hash checks и необходимые CI успешны, `ready_for_audit=true`. Если PR ещё не создан при сборке шаблона — false; после создания заполнить `pr_url` и commit, ещё раз проверить final published revision. CI pending/FAIL соответствующего scope запрещает readiness. Mock/live/physical ограничения видны в TEST_RESULTS и EVIDENCE.
6. Отдельная archive task ветка/PR от current audit-artifacts добавляет immutable package `.../H/rN`, schema version/hash, индекс с task/H/A/archive commit/PR/owner/status/verdict link. Пакет не перезаписывается при ошибке — rN+1 с supersedes ссылкой. После review и owner merge — индекс получает confirmed destination SHA отдельным publication record. До merge архивного PR — ARCHIVE_PENDING, не «архивировано».
7. ChatGPT получает code PR, H, A, manifest и evidence URLs. Verdict указывает точный H/A, проверенные сценарии и ограничения. Исполнитель может READY, но не пишет за аудитора PASS. Новая проверка сохраняет прежний FAIL и указывает supersedes/verdict lineage.
8. После принятия и разрешённого code merge — whole local main sync по CONTRIBUTING на обеих машинах отдельно. Обновляется BRANCH_SYNC новым revision, никакой подмены candidate tree за accepted main.

## Обязательный пакет

MANIFEST.json; SUMMARY.md; SOURCE_BASELINE.md; CHANGES.md; TEST_RESULTS.md; CONTRACT_COMPLIANCE.md; EVIDENCE.md; REGRESSION.md; RISKS_AND_LIMITATIONS.md; BRANCH_SYNC.md; AUDIT_REQUEST.md. Допустимы source inventories, schemas, safe test output, screenshots/videos после redaction; нет raw initData, tokens, signed asset/payment URLs, personal data или private donor code. Публикуемые скриншоты проверять вручную; manifest evidence inventory sha256 фиксирует bytes.

## Проверка

`python -m pip install -r .github/requirements-docs.txt`, `python .github/check_docs.py`, `python .github/check_planning.py`, `git diff --check`. JSON Schema 2020-12 валидирует manifest; checker дополнительно проверяет DAG/owners/contract IDs/required files/evidence hashes/READY semantics. Отрицательные schema fixtures доказывают, что missing fields/invalid SHA/unpublished READY отвергаются. Внешняя доступность source/PR/CI проверяется GitHub API отдельно — локальная schema не доказывает сеть или независимую приёмку.
