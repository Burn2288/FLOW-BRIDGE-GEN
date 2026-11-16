# INTEGRATION EXECUTION PLAN

Статус PROPOSED; каждое решение о merge принадлежит владельцу, обеим review ролям и действующим правилам. Любое retarget меняет effective diff и требует нового CI и peer review.

| Шаг | Условия, исполнитель, PR | Проверка / аудит / фиксация | Восстановление |
| --- | --- | --- | --- |
| 1 | Burn2288 и vankhu21 согласуют правила и D-01; документ IN-01 и #19 на ревью | Peer review vankhu21, independent audit source-preservation, current head SHA | Разрешать разногласия в отдельном PR; не переписывать refs |
| 2 | После разрешения owner принять #1: Burn2288, reviewer vankhu21 | docs CI точного SHA, audit и recorded merge SHA | При ошибке отдельный revert PR, не force push |
| 3 | Автор vankhu21 и reviewer Burn2288: #8 затем #9–#17 по одному | current base/head, per-PR regressions, PostgreSQL migration checks, peer/audit и explicit owner approval до merge; далее retarget следующего | Конфликт: остановить, сохранить оба parent, отдельный integration branch и ручной review |
| 4 | При появлении документационных конфликтов Burn2288 + vankhu21 | Сравнить правила, исходники и Markdown отдельно; нельзя перезаписать документы/код | Разрешить в отдельном PR, независимая проверка diff |
| 5 | #18 после review #1 и согласованной базы | contracts/doc CI, второй reviewer/audit, explicit owner approval и SHA | revert PR при ошибке; сохранение истории |
| 6 | #19 после review #18 и owner-approved плана | два worklists и history, source-aware links, CI, audit; перенос в личные ветки их авторами | Исправляющий PR, не править чужую dev-ветку |
| 7 | После принятия code/docs: Burn2288 + vankhu21 | изолированный clean Ubuntu/PostgreSQL, полный suite, migration checks, восстановление, production не менять | восстановить тестовый backup; инцидент перед решением о релизе |
| 8 | После реальных разрешённых merge каждый разработчик на своей машине | fetch, clean, ff-only, origin/main SHA=HEAD, весь проект и integration tests, отдельное evidence | Не reset --hard; сохранить изменения и остановить при расхождении |

Поскольку #19 сейчас нацелен в ветку #18, предлагаемый порядок «сначала #18, затем #19» требует после интеграции #18 согласованного retarget #19 на новую общую базу с проверкой diff, без изменения истории. Альтернатива — сначала принять #19 в документационную ветку #18, затем принимать #18 как один расширенный пакет; выбор — отдельное решение владельца и обоих разработчиков. Эти альтернативы нельзя считать уже согласованными.

Структурная зависимость документации и кода не разрешает авто-merge ни одной ступени. Все реальные переходы и SHA регистрируются отдельно.
