# Отложенное ревью vankhu21

Кандидат реестра; ревью не запрошено и не считается одобрением. Машиночитаемые источники — [DEFERRED_REVIEW.json](DEFERRED_REVIEW.json) и [REGISTER.json](REGISTER.json).

<!-- R-TELEGRAM -->
## Telegram — R-TELEGRAM

**Проверить:** Проверить границы writer, маршруты сообщений/callback и доставку после отказа.
**Риск:** Пересечение доступа и доставки может менять поведение чужого маршрута.
**Файлы:** `src/elevenbot/telegram.py`, `src/elevenbot/anymodel_image_jobs.py`
**Публичные PR:** [24](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/24), [25](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/25), [26](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/26)
**Writer при исправлении:** Burn2288 предлагает исправление; writer общего файла согласовать с vankhu21.
**Доказательства:** [E-4 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/2062c2c55014770b27e96fed731ba7e6d5f08b79/independent-audits/burn2288/IN-19-SEC-PILOT-S2-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/9#issuecomment-6952722353), [E-5 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/8e50234d9f9f1fced3a2ccd6a0cfd98a90a117bf/independent-audits/burn2288/ML-01-IMAGE-RECOVERY-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/10#issuecomment-6953903755), [E-6 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/b8758fd78d9c34b101c6597fe8cc099fca7c56fd/independent-audits/burn2288/TQ-01-CI-REGRESSION-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/11#issuecomment-6954480564).
**Осталось:** Совместное ревью маршрутов и проверка на интеграционном SHA.
**Статус:** PEER_REVIEW_DEFERRED

<!-- R-HTTP -->
## HTTP/Mini App — R-HTTP

**Проверить:** Проверить подписи, сессии, допуск на каждом запросе и ownership.
**Риск:** Старая конфигурация или обход входа может сохранить доступ.
**Файлы:** `miniapp/backend/web.py`, `src/elevenbot/core.py`
**Публичные PR:** [17](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/17), [24](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/24), [26](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/26)
**Writer при исправлении:** Burn2288; границы HTTP и reviewer согласовать.
**Доказательства:** [E-2 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/89bce1e8f5140076e0c3b3fef7fc7a48e2beeb74/independent-audits/burn2288/IN-19-EVIDENCE-CLOSURE-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/7#issuecomment-6951436720), [E-4 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/2062c2c55014770b27e96fed731ba7e6d5f08b79/independent-audits/burn2288/IN-19-SEC-PILOT-S2-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/9#issuecomment-6952722353), [E-6 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/b8758fd78d9c34b101c6597fe8cc099fca7c56fd/independent-audits/burn2288/TQ-01-CI-REGRESSION-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/11#issuecomment-6954480564).
**Осталось:** Проверить отзыв на всех процессах и прямые запросы на целевом SHA.
**Статус:** PEER_REVIEW_DEFERRED

<!-- R-WALLET -->
## Wallet/Ledger — R-WALLET

**Проверить:** Проверить неизменность ledger, reserve/capture/release и поздние события оплаты.
**Риск:** Повторное списание, потеря события либо некорректная сверка.
**Файлы:** `src/elevenbot/core.py`, `src/elevenbot/task_wallet.py`, `src/elevenbot/topups.py`
**Публичные PR:** [23](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/23), [24](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/24), [25](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/25), [26](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/26)
**Writer при исправлении:** vankhu21 ведёт финансовый контракт; writer конкретного исправления согласовать.
**Доказательства:** [E-3 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/1c73ef05111451660227ae3e4cc8e00f3304f960/independent-audits/burn2288/IN-19-POSTGRESQL-REGRESSION-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/8#issuecomment-6952025493), [E-4 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/2062c2c55014770b27e96fed731ba7e6d5f08b79/independent-audits/burn2288/IN-19-SEC-PILOT-S2-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/9#issuecomment-6952722353), [E-5 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/8e50234d9f9f1fced3a2ccd6a0cfd98a90a117bf/independent-audits/burn2288/ML-01-IMAGE-RECOVERY-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/10#issuecomment-6953903755), [E-6 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/b8758fd78d9c34b101c6597fe8cc099fca7c56fd/independent-audits/burn2288/TQ-01-CI-REGRESSION-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/11#issuecomment-6954480564).
**Осталось:** Согласовать обработку подтверждённых событий при отзыве и смене режима; проверить на интеграционном SHA.
**Статус:** PEER_REVIEW_DEFERRED

<!-- R-MIGRATIONS -->
## Migrations — R-MIGRATIONS

**Проверить:** Проверить порядок 001–039, checksum и восстановление с данными.
**Риск:** Синтетический fixture не охватывает все исторические базы.
**Файлы:** `migrations/001_initial.sql`, `migrations/039_inbox_unprocessed.sql`, `verification/in19/test_seeded_upgrade.py`
**Публичные PR:** [17](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/17), [23](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/23), [26](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/26)
**Writer при исправлении:** Burn2288 координирует номера; writer конкретной миграции — назначенный автор.
**Доказательства:** [E-2 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/89bce1e8f5140076e0c3b3fef7fc7a48e2beeb74/independent-audits/burn2288/IN-19-EVIDENCE-CLOSURE-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/7#issuecomment-6951436720), [E-3 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/1c73ef05111451660227ae3e4cc8e00f3304f960/independent-audits/burn2288/IN-19-POSTGRESQL-REGRESSION-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/8#issuecomment-6952025493), [E-6 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/b8758fd78d9c34b101c6597fe8cc099fca7c56fd/independent-audits/burn2288/TQ-01-CI-REGRESSION-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/11#issuecomment-6954480564).
**Осталось:** Проверить поддерживаемые исторические состояния и восстановление на фактическом интеграционном SHA.
**Статус:** PEER_REVIEW_DEFERRED

<!-- R-PROVIDERS -->
## Provider/Jobs — R-PROVIDERS

**Проверить:** Проверить сохранение результатов, один POST, предел повторов и notify_attempts=3.
**Риск:** Неизвестная доставка может совпасть с третьим отказом либо подавить уведомление после сбоя.
**Файлы:** `src/elevenbot/anymodel_image_jobs.py`, `src/elevenbot/image_delivery.py`, `src/elevenbot/worker.py`
**Публичные PR:** [17](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/17), [23](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/23), [25](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/25), [26](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/26)
**Writer при исправлении:** Burn2288 для кандидата; границы worker/Telegram согласовать.
**Доказательства:** [E-1 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/2072b03bd31894a304d4ad39235ec0fd1d504281/independent-audits/burn2288/IN-19-PREFLIGHT-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/6#issuecomment-6951045809), [E-3 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/1c73ef05111451660227ae3e4cc8e00f3304f960/independent-audits/burn2288/IN-19-POSTGRESQL-REGRESSION-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/8#issuecomment-6952025493), [E-5 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/8e50234d9f9f1fced3a2ccd6a0cfd98a90a117bf/independent-audits/burn2288/ML-01-IMAGE-RECOVERY-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/10#issuecomment-6953903755), [E-6 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/b8758fd78d9c34b101c6597fe8cc099fca7c56fd/independent-audits/burn2288/TQ-01-CI-REGRESSION-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/11#issuecomment-6954480564).
**Осталось:** Проверить конкурирующие claims, lease, неопределённые ошибки и точки аварийного завершения.
**Статус:** PEER_REVIEW_DEFERRED

<!-- R-SECURITY -->
## Security — R-SECURITY

**Проверить:** Проверить отдельный tester allowlist, admin/RBAC и отзыв доступа.
**Риск:** Уже запущенный процесс использует устаревшую конфигурацию; завершение jobs после отзыва не определено.
**Файлы:** `src/elevenbot/admission.py`, `src/elevenbot/config.py`, `src/elevenbot/telegram.py`, `miniapp/backend/web.py`
**Публичные PR:** [17](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/17), [24](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/24), [26](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/26)
**Writer при исправлении:** Burn2288 для access/RBAC; совместные границы согласовать.
**Доказательства:** [E-2 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/89bce1e8f5140076e0c3b3fef7fc7a48e2beeb74/independent-audits/burn2288/IN-19-EVIDENCE-CLOSURE-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/7#issuecomment-6951436720), [E-4 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/2062c2c55014770b27e96fed731ba7e6d5f08b79/independent-audits/burn2288/IN-19-SEC-PILOT-S2-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/9#issuecomment-6952722353), [E-6 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/b8758fd78d9c34b101c6597fe8cc099fca7c56fd/independent-audits/burn2288/TQ-01-CI-REGRESSION-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/11#issuecomment-6954480564).
**Осталось:** Проверить координированную перезагрузку, in-flight jobs и границы аутентифицированных событий.
**Статус:** PEER_REVIEW_DEFERRED

<!-- R-INTEGRATION -->
## Интеграция и приёмка — R-INTEGRATION

**Проверить:** Сверить точные SHA, порядок PR и независимые gates до принятия.
**Риск:** Тестовый композит не объединяет историю PR #9–#17 и не равен принятой main.
**Файлы:** `docs/audit/register/REGISTER.json`, `src/elevenbot/telegram.py`
**Публичные PR:** [17](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/17), [23](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/23), [24](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/24), [25](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/25), [26](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/26)
**Writer при исправлении:** Burn2288 координирует; исправления — назначенный writer, второй reviewer.
**Доказательства:** [E-1 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/2072b03bd31894a304d4ad39235ec0fd1d504281/independent-audits/burn2288/IN-19-PREFLIGHT-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/6#issuecomment-6951045809), [E-2 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/89bce1e8f5140076e0c3b3fef7fc7a48e2beeb74/independent-audits/burn2288/IN-19-EVIDENCE-CLOSURE-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/7#issuecomment-6951436720), [E-3 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/1c73ef05111451660227ae3e4cc8e00f3304f960/independent-audits/burn2288/IN-19-POSTGRESQL-REGRESSION-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/8#issuecomment-6952025493), [E-4 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/2062c2c55014770b27e96fed731ba7e6d5f08b79/independent-audits/burn2288/IN-19-SEC-PILOT-S2-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/9#issuecomment-6952722353), [E-5 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/8e50234d9f9f1fced3a2ccd6a0cfd98a90a117bf/independent-audits/burn2288/ML-01-IMAGE-RECOVERY-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/10#issuecomment-6953903755), [E-6 отчёт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/blob/b8758fd78d9c34b101c6597fe8cc099fca7c56fd/independent-audits/burn2288/TQ-01-CI-REGRESSION-BATCH-01/REPORT.md) / [вердикт](https://github.com/Burn2288/FLOW-BRIDGE-GEN-AUDIT/pull/11#issuecomment-6954480564).
**Осталось:** Дождаться IN-18, интеграционных решений владельца, полного peer review и CI фактического дерева.
**Статус:** PEER_REVIEW_DEFERRED
