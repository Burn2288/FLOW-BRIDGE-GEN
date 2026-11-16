## Срез и результат

- Задача / срез
- Что изменилось и какие контракты затронуты
- SHA, команды проверки, ссылки на тесты или артефакты
- Сценарий отказа, ограничения и риски
- Следующий шаг

## Перед слиянием

- [ ] Обновлены относящиеся к задаче документы.
- [ ] Успешны обязательные проверки актуального коммита.
- [ ] Второй разработчик проверил изменения и доказательства.
- [ ] Проверено отсутствие секретов, персональных данных и сырых артефактов.

## TASK-PLAN-001 — предлагаемые дополнения процесса

Статус PROPOSED: эти дополнения проходят документационный PR и согласование; действующие правила веток не отменены. TASK-PLAN-001 отдельно разрешает planning/team-workplans-v1 от docs/foundation-contracts-v1 и Draft PR в эту документационную ветку. Личные dev-ветки коллеги не изменять.

Цикл: TASK_ID → fresh accepted base → изучить PR/код коллеги → минимальный change → тесты и регрессия → опубликованный code/docs PR + аудиторский пакет → peer review → независимый ChatGPT audit → согласованная приёмка → разрешённый merge → синхронизация **всего** локального проекта, включая принятый код коллеги.

Для каждой задачи обязательны MANIFEST по JSON Schema и все 10 MD из [протокола доказательств](../docs/planning/EVIDENCE_PUBLICATION_PROTOCOL.md). Без public immutable artifact URL задача не READY_FOR_AUDIT. READY не заменяет независимый PASS. Пакеты разработчиков передаются в предложенную audit-artifacts через отдельный reviewable PR; auditor остаётся веткой независимых заключений. Сохранять предыдущие отрицательные результаты и новый SHA/revision при исправлении.

Фиксировать content SHA, artifact SHA и actual PR HEAD раздельно; не выдумывать самоссылку manifest на собственный commit. Не публиковать secrets, raw initData, персональные/платёжные данные, signed URLs, private donor code или необезличенные логи.

После принятия задачи Codex автора обновляет всю local main до origin/main с сохранением незавершённой работы, проверкой чистоты, ff-only, сравнением SHA и relevant environment/DB checks. Открытый PR не часть accepted main. Если машина второго разработчика недоступна — её sync NOT_PERFORMED; GitHub API не доказывает обновление компьютера.

- [ ] TASK_ID, исполнитель/reviewer, exact base/content/artifact/main SHA и зависимости указаны.
- [ ] Manifest URL по immutable SHA, schema check, commands/results/skips и CI URLs опубликованы.
- [ ] Existing code коллеги переиспользован, migration writer/contract version согласованы.
- [ ] MOCK/DB/LIVE/USER_VISIBLE доказательства разделены, limitations сохранены.
- [ ] Peer review и независимый audit verdict не подменены READY.
- [ ] Архивный PR/индекс или ARCHIVE_PENDING явно указан; auditor не изменён.
- [ ] Whole-clone sync обеих машин описан фактически, не заявлен до merge.
