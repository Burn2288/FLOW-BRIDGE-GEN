# ACCESS CONTROL TEST MATRIX — OWNER_APPROVED / IMPLEMENTATION_PENDING / NOT_TESTED

| Сценарий | Ожидаемое поведение по утверждённому ADR | Данные и побочные эффекты |
| --- | --- | --- |
| Администратор private | допуск до identity; admin только после существующей проверки роли/сессии | создать только один аккаунт/кошелёк |
| Разрешённый tester private | допуск и обычное меню после consent; admin denied | один кошелёк без admin grants |
| Посторонний private | отказ до identity; safe notice/legal/support | нет новой identity/users/wallets |
| Пользователь public | обычная регистрация и consent; feature flags отдельно | один аккаунт/кошелёк |
| Повторный /start | повторная проверка допуска; идемпотентный вход | не сбрасывать баланс/jobs |
| Consent и повторное принятие | сохранять правильную версию, отказ устаревшей | история сохраняется |
| Прямой callback | проверить admission до identity и обработчика | нет побочной записи/резерва |
| Прямой Mini App | подпись initData и admission на сервере | нет создания identity от outsider |
| HTTP API напрямую | account + актуальный admission + ресурсные права | чужие файлы/кошелёк недоступны |
| Генерация/пополнение без допуска | запрет до резервирования/нового платного POST | нет новой финансовой проводки; учесть уже подтверждённые события |
| Отзыв при живой сессии | следующий запрос denied; сессия перестаёт давать доступ | сохранить существующие данные и reconcile paid events |
| Смена режима и рестарт | политика заново применяется по актуальной конфигурации | не удалять данные, сохранить входящие события |
| Tester без admin прав | обычный end-to-end путь; admin команды и API denied | нет повышения роли; один кошелёк |

Все строки — будущая приёмка, не результаты. Каждый тест включает Telegram, callback или HTTP где применимо, PostgreSQL до/после, fixture provider/payment счётчики, рестарт и повтор. Live user/payment не выполнялись.

## IN-01-FIX-02 — OWNER_APPROVED / IMPLEMENTATION_PENDING / PEER_REVIEW_PENDING

[Решение владельца](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/20#issuecomment-6919575091) утверждает private: admin + отдельный PILOT_TELEGRAM_USER_IDS, outsider denied до создания identity/user/wallet; tester не получает admin rights. Public: обычная регистрация после consent, generation/model/payment gates отдельно. Серверный admission обязателен для Telegram, callbacks, Mini App и HTTP, с проверкой отзыва сессий. Existing jobs, paid events, wallet и reconciliation сохраняются. Код ещё не реализует эту политику, runtime NOT_TESTED. Ревью vankhu21 ожидается. [Отдельное задание](SEC-PILOT-01.md).
