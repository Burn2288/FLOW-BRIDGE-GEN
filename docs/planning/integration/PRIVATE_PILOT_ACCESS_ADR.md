# ADR — доступ к закрытому пилоту

**PROPOSED / PENDING_OWNER / PEER_REVIEW_NOT_PROVEN.** Основание: [аудит](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/20#issuecomment-6919105866), PR #17 `d691d54e0266c3d519d66575555fa45895ef40ac`. Это предложение, не действующее поведение. Реализация — отдельный TASK_ID после утверждения ADR и принятия базы; оценка не допускает изменений приложения в PR #20.

## Факт и причина

В PR #2 test_private_access_denied_before_registration отвергал гостя до регистрации. В #17 test_non_admin_in_private_pilot_can_accept_terms_and_open_user_menu допускает гостя. [src/elevenbot/telegram.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/telegram.py) вызывает identity до общего пилотного допуска; [src/elevenbot/core.py](https://github.com/Burn2288/FLOW-BRIDGE-GEN/blob/d691d54e0266c3d519d66575555fa45895ef40ac/src/elevenbot/core.py) при новой identity создаёт пользователя, две записи wallet и conversation. Admin denial проверяется отдельно и не доказывает запрет регистрации. Наличие изменённого теста не подтверждает решение владельца. Последствия для работающего стенда и мотивация изменения NOT_PROVEN.

## Предлагаемое решение

В `ACCESS_MODE=private` допуск: `ADMIN_TELEGRAM_IDS` или отдельный `PILOT_TELEGRAM_USER_IDS` (имя и способ обновления предложены). Проверка сервером до создания identity/wallet на командах и callbacks; outsider получает закрытое сообщение и, если реализовано безопасно без identity, условия/контакты поддержки. Одно нахождение в pilot allowlist не создаёт admin session/role. При public регистрация и пользовательское меню допускаются после consent; платежи, модель, генерация и provider остаются под собственными независимыми policy/flags.

Mini App validates initData и при каждом запросе повторно проверяет актуальный admission; прямой URL/token не обходит его. При отзыве допуска новые команды/jobs/topups запрещены; порядок обработки незавершённых jobs и уже подтверждённых платежей согласовать отдельно: не отбрасывать authenticated payment events и не терять funds, выполнять reconciliation безопасно. Существующие пользователи и wallets не удаляются; revoke не является основанием для удаления данных или blind refund.

## Альтернативы и последствия

Текущая модель открытой регистрации в private сохраняет существующий UX, но не ограничивает создание аккаунтов; единый список admin для всех testers нарушает разделение ролей; сеть/UI-only gate обходится прямыми запросами. Предлагаемый отдельный список требует контролируемого хранения/обновления, политики удаления/отзыва, тестов конкурентности и миграционного анализа. Ни одно решение не принято этим текстом.

## Acceptance

Owner утверждает политику, режимы и конфигурацию; vankhu21 подтверждает намерение исторического изменения. Затем отдельный PR на базе принятого кода: матрица [13 сценариев](ACCESS_CONTROL_TEST_MATRIX.md), тесты PostgreSQL, Telegram callbacks, HTTP sessions, payment/job boundaries, restart и данные. Юридический канал/обработка уже выполненных платежей не принимаются предположением. Технический owner — Burn2288; reviewer — vankhu21. Независимый аудит и CI нового SHA обязательны.
