# Работа над Flow-Bridge-Gen в Codex

- Перед работой прочитай [правила команды](CONTRIBUTING.md), общую [дорожную карту](docs/ROADMAP.md) и критерии приёмки задачи. Установи, кто ведёт задачу, и проверь текущий клон и ветку.
- Сверяй личный план в `dev/burn2288` или `dev/vankhu21`. Черновая работа остаётся в ветке её автора. Для ревью используй ветку задачи и PR с проверками актуального SHA.
- После работы над задачей обнови весь локальный проект на машине автора по процедуре из `CONTRIBUTING.md`. Для принятой задачи проверь слияние, ревью второго разработчика и CI, затем подтяни общую `main` и сравни SHA. Если PR открыт, обнови локальную копию до последней принятой `main` и отметь, что задача ждёт приёмки.
- Перед переключением веток проверь рабочее дерево и сохрани незавершённые изменения в их ветке. При конфликте или расхождении истории зафиксируй препятствие и сохрани обе версии.
- Обнови личный план ссылками на PR и проверки. В итогах укажи SHA PR, SHA локальной `main` и статус синхронизации. Каждый Codex работает с клоном и GitHub-учётной записью своего разработчика.

- Режим владельца FUNCTIONAL_TEST и кандидат нового порядка см. в [регламенте уровней](docs/planning/COMPLETION_LEVELS.md). Для каждой отдельной задачи допускается самопроверка; обязательный глобальный аудит и решение о merge относятся к итоговому пакету. Действующие обязательные проверки GitHub не обходятся.

## Кандидат назначения одного исполнителя (2026-11-21)

- Current executor/integrator: Burn2288 for all 81 historical TASK_ID; original historical owner metadata is immutable. vankhu21 is temporarily unavailable. Read the separate [takeover candidate](docs/planning/OWNER_TAKEOVER_FTL1_001.md) and [assignment overlay](docs/planning/owner-takeover-ftl1-001.json).
- Continue implementation and independent task preparation without waiting for vankhu21. Do not rewrite, delete, or reassign historical commits, list positions, source branches, or author fields.
- This is a documentation candidate. Do not bypass current two-auditor process, mandatory GitHub checks, branch protection, or owner merge permission. Do not claim self-review is independent review.
