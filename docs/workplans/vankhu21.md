# vankhu21 — предлагаемый полный worklist

Статус PROPOSED; личная dev-ветка не изменена. [Полный реестр и все поля задач](../planning/MASTER_WORK_BREAKDOWN.md), [параллельные окна](../planning/PARALLEL_WORK_MATRIX.md), [первые действия](../planning/NEXT_ACTIONS.md), [история плана](../planning/history/vankhu21-original.txt). 41 задач; effort 121.

Существующие backend-наработки vankhu21 остаются у автора: интеграционный стэк, Pricing, Wallet atomicity и Platega. Burn2288 ведёт shared contracts/worker/API/security/infrastructure; второй разработчик — reviewer. Новые задания не переписывают существующие модули.

## IN-08 — Интегрировать PR #8 и доказать supersession ранних пилотов

[IN-08: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#in-08). P0, S0, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #8 SHA `eaadb892227e6b731e4cebccb071b23c1b209b3b`: `CONTRIBUTING.md`, `.github/workflows/test.yml`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Сохранить исходники/историю #2/#4/#6/#7; убрать только доказанное дублирование интеграции. Зависимости: IN-02. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Полный PostgreSQL CI; image validation/recovery; 001–012. Физическое доказательство: Одобренный diff, дерево миграций, review и merge SHA. Приёмка: В принятой main есть исходный image slice, уникальные тесты сохранены.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## IN-09 — Провести отдельную приёмку и интеграцию PR #9: Veo video

[IN-09: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#in-09). P0, S0, effort 1, reviewer Burn2288, integration owner vankhu21.

Использовать PR #9 SHA `b5c1368cf9663bd0be43a1e9c0b65816c51fe61d`: `CONTRIBUTING.md`, `.github/workflows/test.yml`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta video.py. Зависимости: IN-08. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Полный CI на новом SHA + профильные тесты video.py; миграционные checksum. Физическое доказательство: Review, новый base/head diff, checks и merge SHA. Приёмка: Предшественник принят; текущий PR прошёл ревью и CI после ретаргета.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## IN-10 — Провести отдельную приёмку и интеграцию PR #10: AnyModel registry

[IN-10: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#in-10). P0, S0, effort 1, reviewer Burn2288, integration owner vankhu21.

Использовать PR #10 SHA `eaa1a6fdc6eb19ed61a231ad05c9eb412c0d2496`: `CONTRIBUTING.md`, `.github/workflows/test.yml`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel.py. Зависимости: IN-09. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Полный CI на новом SHA + профильные тесты anymodel.py; миграционные checksum. Физическое доказательство: Review, новый base/head diff, checks и merge SHA. Приёмка: Предшественник принят; текущий PR прошёл ревью и CI после ретаргета.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## IN-11 — Провести отдельную приёмку и интеграцию PR #11: FIBO async image

[IN-11: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#in-11). P0, S0, effort 1, reviewer Burn2288, integration owner vankhu21.

Использовать PR #11 SHA `99c091476de23d998a3101bb0e39d199552f8838`: `CONTRIBUTING.md`, `.github/workflows/test.yml`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel_image_jobs.py. Зависимости: IN-10. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Полный CI на новом SHA + профильные тесты anymodel_image_jobs.py; миграционные checksum. Физическое доказательство: Review, новый base/head diff, checks и merge SHA. Приёмка: Предшественник принят; текущий PR прошёл ревью и CI после ретаргета.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## IN-12 — Провести отдельную приёмку и интеграцию PR #12: Grok video

[IN-12: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#in-12). P0, S0, effort 1, reviewer Burn2288, integration owner vankhu21.

Использовать PR #12 SHA `de4e5f1183ec9ee7b079977fda68f99e02d00dd7`: `CONTRIBUTING.md`, `.github/workflows/test.yml`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel_video.py. Зависимости: IN-11. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Полный CI на новом SHA + профильные тесты anymodel_video.py; миграционные checksum. Физическое доказательство: Review, новый base/head diff, checks и merge SHA. Приёмка: Предшественник принят; текущий PR прошёл ревью и CI после ретаргета.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## IN-13 — Провести отдельную приёмку и интеграцию PR #13: AnyModel speech

[IN-13: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#in-13). P0, S0, effort 1, reviewer Burn2288, integration owner vankhu21.

Использовать PR #13 SHA `6c82761c5e4c42e1129934884c5b23030df4e090`: `CONTRIBUTING.md`, `.github/workflows/test.yml`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta anymodel_speech.py. Зависимости: IN-12. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Полный CI на новом SHA + профильные тесты anymodel_speech.py; миграционные checksum. Физическое доказательство: Review, новый base/head diff, checks и merge SHA. Приёмка: Предшественник принят; текущий PR прошёл ревью и CI после ретаргета.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## IN-14 — Провести отдельную приёмку и интеграцию PR #14: Welcome/navigation

[IN-14: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#in-14). P0, S0, effort 1, reviewer Burn2288, integration owner vankhu21.

Использовать PR #14 SHA `742db84eb8663d5a4b7a7e50b2c10825e7b18a87`: `CONTRIBUTING.md`, `.github/workflows/test.yml`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta telegram.py. Зависимости: IN-13. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Полный CI на новом SHA + профильные тесты telegram.py; миграционные checksum. Физическое доказательство: Review, новый base/head diff, checks и merge SHA. Приёмка: Предшественник принят; текущий PR прошёл ревью и CI после ретаргета.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## IN-15 — Провести отдельную приёмку и интеграцию PR #15: Task progress

[IN-15: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#in-15). P0, S0, effort 1, reviewer Burn2288, integration owner vankhu21.

Использовать PR #15 SHA `5162e8e58ba91564c7989617567e24a18aa5f3da`: `CONTRIBUTING.md`, `.github/workflows/test.yml`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Ретаргет владельцем после предшественника; сохранить историю; пересмотреть только конфликтный delta progress.py. Зависимости: IN-14. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Полный CI на новом SHA + профильные тесты progress.py; миграционные checksum. Физическое доказательство: Review, новый base/head diff, checks и merge SHA. Приёмка: Предшественник принят; текущий PR прошёл ревью и CI после ретаргета.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## IN-16 — Принять PR #16: финансы, каталог и Telegram Admin

[IN-16: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#in-16). P0, S0, effort 5, reviewer Burn2288, integration owner vankhu21.

Использовать PR #16 SHA `76a030a5dc32ccf79b9c9a8393f1807d7df9d791`: `CONTRIBUTING.md`, `.github/workflows/test.yml`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Разобрать большой накопленный PR по тестовым областям, сохранить авторство; не переписывать Pricing/Wallet/Platega. Зависимости: IN-15. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Миграции 019–036, admin deny, tariff/hold/refusal/topups/broadcast lock isolation. Физическое доказательство: Review каждой области, CI, migration doctor и merge SHA. Приёмка: Нет миграционных коллизий; финансовые и admin-регрессии текущего SHA опубликованы.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## IN-17 — Принять PR #17: Mini App и новый inbox

[IN-17: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#in-17). P0, S0, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `CONTRIBUTING.md`, `.github/workflows/test.yml`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Ретаргет и регрессия Mini App, публичного image policy, inbox/defer; сохранить исправления поздних SHA. Зависимости: IN-16. Решения: общие gates. Параллельно: только по lock-check.

Проверки: 037–039, штатный CLODEX с HTTP fixture, replay/session/IDOR, inbox two-chat. Физическое доказательство: Точный CI 397-test baseline + актуальный полный прогон и review. Приёмка: Новые проверки прошли; старый вывод о sync polling не перенесён без воспроизведения.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## TG-01 — Перевести главное меню и Back без потери старых маршрутов

[TG-01: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#tg-01). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/telegram.py`, `src/elevenbot/navigation.py`, `src/elevenbot/progress.py`, `tests/test_navigation.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Открыть студию/кабинет/информация, совместимые старые callbacks, edit fallback; referrals/support честно закрыты до API. Зависимости: IN-19. Решения: общие gates. Параллельно: PR-01, JO-01.

Проверки: Два устройства, duplicate, long labels, edit failure, admin routes. Физическое доказательство: Запись Android/Desktop на тестовом боте + route table. Приёмка: Один актуальный экран, Back сохраняет страницу; legacy маршруты работают.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## TG-02 — Подключить документы и текущий consent к Telegram UX

[TG-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#tg-02). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/telegram.py`, `src/elevenbot/navigation.py`, `src/elevenbot/progress.py`, `tests/test_navigation.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Отправлять оба versioned MD как файлы, запретить устаревшее согласие и покупку при сбое доставки. Зависимости: SL-01, TG-01. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Missing file, old callback, repeat /start, active paid job. Физическое доказательство: Видеопроход принятия и перепринятия версии. Приёмка: Нет обхода gate, кошелёк и jobs не сбрасываются.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## TG-03 — Личный кабинет и история общего кошелька

[TG-03: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#tg-03). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/telegram.py`, `src/elevenbot/navigation.py`, `src/elevenbot/progress.py`, `tests/test_navigation.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Показать доступный/резерв, профиль, статусы заказов и историю через общий query port. Зависимости: PY-01, TG-01. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Pending не зачислен, pagination, два аккаунта. Физическое доказательство: Сверка экранов с ledger на тестовых данных. Приёмка: Баланс и история совпадают с Mini App и сервером.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## MA-01 — Принять существующую Mini App в Telegram по HTTPS

[MA-01: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#ma-01). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `miniapp/backend/web.py`, `miniapp/frontend/app.js`, `miniapp/frontend/style.css`, `miniapp/tests/test_miniapp.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Сохранить read-mostly MVP, проверить launch c signed initData и fallback reply-keyboard; исправлять только подтверждённое. Зависимости: IN-19, OP-01. Решения: D-05. Параллельно: JO-02.

Проверки: Два аккаунта; Android/Desktop; revoke/expiry/theme/catalogue/works. Физическое доказательство: Запись реальных WebView и HTTP owner-deny, без raw initData. Приёмка: Оба клиента видят свой баланс/работы; чужой файл закрыт.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## MA-02 — Форма image quote и явное подтверждение

[MA-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#ma-02). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `miniapp/backend/web.py`, `miniapp/frontend/app.js`, `miniapp/frontend/style.css`, `miniapp/tests/test_miniapp.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Существующий frontend потребляет server schemas и quote; loading/error/expired/insufficient states. Зависимости: AP-02, MA-01. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Disabled model, stale quote, double click, mobile keyboard. Физическое доказательство: Видео quote→confirm на fixture без оптимистического success. Приёмка: Цена только с сервера, один semantic request ID на повтор.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## MA-03 — Карточка job и безопасная отмена

[MA-03: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#ma-03). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `miniapp/backend/web.py`, `miniapp/frontend/app.js`, `miniapp/frontend/style.css`, `miniapp/tests/test_miniapp.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Показывать persisted status/uncertain и cancel только по policy; повтор не делает новый POST. Зависимости: MA-02, AP-03, JO-02. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Reload mid-job, cancel race, expired session. Физическое доказательство: Один job виден в Telegram и Mini App после рестарта. Приёмка: Нет выдуманных процентов и успешной отмены при неизвестном провайдере.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## MA-04 — Довести пользовательский parity и доступность

[MA-04: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#ma-04). P1, S8, effort 5, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `miniapp/backend/web.py`, `miniapp/frontend/app.js`, `miniapp/frontend/style.css`, `miniapp/tests/test_miniapp.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Собрать уже готовые экраны, исправить parity gaps, focus/contrast/reduced motion/narrow width. Зависимости: MA-03, VI-02, VO-02, MU-02, ML-03, RF-03, SL-03, PY-03. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Feature-by-feature bot/Mini App matrix, Android/Desktop, offline/error. Физическое доказательство: Записи полного пути каждого из четырёх типов. Приёмка: Все обязательные пути представлены; ограничения явно видны.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## AD-03 — Графические admin экраны по общему API

[AD-03: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#ad-03). P1, S6, effort 5, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `miniapp/backend/web.py`, `miniapp/frontend/app.js`, `src/elevenbot/admin_access.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Добавлять users/jobs/queue/providers/models/pricing/payments/ledger/reports/audit по готовым read/write capabilities. Зависимости: AD-02, OB-02. Решения: общие gates. Параллельно: RF-01.

Проверки: Permissions per view, no plaintext secrets, dangerous action preview. Физическое доказательство: Ручная диагностика job ID без SQL и скринкаст rollback. Приёмка: Все области имеют рабочий read view; опасные записи только через разрешённые команды.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## TA-01 — Зафиксировать compatibility inventory Admin Edition

[TA-01: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#ta-01). P1, S0, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/admin_access.py`, `src/elevenbot/tariff_admin.py`, `src/elevenbot/topup_ui.py`, `src/elevenbot/broadcasts.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Инвентаризация команд, scopes, экранов, sessions, broadcasts, тарифов, платежей и deny-тестов PR #16 без редактирования общего кода. Зависимости: IN-01. Решения: общие gates. Параллельно: DC-01.

Проверки: Проверить tests и immutable source refs, сопоставить audit findings. Физическое доказательство: Каталог команд с SHA и матрицей прав. Приёмка: Каждая существующая admin-команда имеет регрессию/ограничение.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## TA-02 — Сохранить Telegram admin при общих admin services

[TA-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#ta-02). P1, S6, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/admin_access.py`, `src/elevenbot/tariff_admin.py`, `src/elevenbot/topup_ui.py`, `src/elevenbot/broadcasts.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Только миграция вызовов settings на общий service; старые команды сохраняются. Зависимости: AD-02, TA-01. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Logout/stale button, unauthorized ID, два чата, broadcast lock. Физическое доказательство: Telegram admin и Mini App меняют одну настройку с единым audit. Приёмка: Нет изменения баланса или навигации другого пользователя от admin-действия.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## MC-02 — Общие карточки и schema-driven параметры каталога

[MC-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#mc-02). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/model_policy.py`, `src/elevenbot/discovery.py`, `src/elevenbot/aggregate.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Убрать только оставшееся дублирование доступности/параметров из UI; сохранить existing labels. Зависимости: MC-01, MA-01. Решения: общие gates. Параллельно: AP-01.

Проверки: Price parity, empty/offline provider, pagination и параметры. Физическое доказательство: Одна публикация видна в боте/Mini App без хардкода. Приёмка: UI не показывает недопущенные модели.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## PC-01 — Уточнить токены, XTR, RUB и immutable quote

[PC-01: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#pc-01). P0, S1, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/pricing.py`, `src/elevenbot/tariff_admin.py`, `src/elevenbot/model_policy.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Сохранить existing Pricing; устранить подтверждённые неоднозначности units/rounding/expiry и maximum variable cost. Зависимости: IN-19. Решения: D-02. Параллельно: ML-01.

Проверки: Concurrent tariff publish, stale/cross-user quote, bounds/rounding. Физическое доказательство: DB quote snapshot до/после смены тарифа. Приёмка: Старый quote/job не пересчитан; float не определяет списание.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## PC-02 — Preview и publish versioned тарифов

[PC-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#pc-02). P1, S6, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/pricing.py`, `src/elevenbot/tariff_admin.py`, `src/elevenbot/model_policy.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Развить tariff_admin через typed admin API; cost estimate отдельно от sale, audit/rollback. Зависимости: PC-01, AD-02. Решения: D-02. Параллельно: только по lock-check.

Проверки: Provider/model overrides, currency mismatch, rollback. Физическое доказательство: Админ preview не тратит кредиты, publish сохраняет старые quotes. Приёмка: Единый расчёт цены в обоих клиентах и отчётах.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## IM-01 — Повторить штатный image путь с ordinary user

[IM-01: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#im-01). P0, S1, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/interaction.py`, `src/elevenbot/anymodel_image_jobs.py`, `tests/test_image_validation.py`, `tests/test_public_image_topup.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Использовать исправленный public image policy PR #17, один конфиг/DB и настоящий adapter с HTTP fixture; фиксировать дефект только после воспроизведения. Зависимости: IN-19, PC-01. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Topup fixture→hold→image→library→restart; duplicates; corrupt media. Физическое доказательство: Один provider POST, один settlement и сохранённый checksum; без платных вызовов. Приёмка: Старый blocker 6504bd1 не объявляется текущим без reproduction.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## IM-02 — Три live изображения и временный отказ

[IM-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#im-02). P0, S1, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/interaction.py`, `src/elevenbot/anymodel_image_jobs.py`, `tests/test_image_validation.py`, `tests/test_public_image_topup.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Контролируемый provider/Telegram прогон с IDs/stages, форматом/сохранением/library/restart; лимиты не повышать вслепую. Зависимости: IM-01, ML-01. Решения: D-06. Параллельно: только по lock-check.

Проверки: Три последовательных успеха; temporary failure; sendPhoto/document по необходимости. Физическое доказательство: Job/provider IDs, размеры/checksums, receipt, owner/library и проводки до/после рестарта. Приёмка: 3 success + failure; no double debit; API receipt отдельно от USER_VISIBLE_NOT_PROVEN.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## VI-01 — Согласовать video create/poll и финальный расчёт

[VI-01: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#vi-01). P1, S3, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/video.py`, `src/elevenbot/anymodel_video.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Расширить существующие Veo/Grok jobs для общего status/cancel/parameters, сохранить provider handles. Зависимости: JO-03, PC-01. Решения: общие gates. Параллельно: AD-01.

Проверки: Duration/resolution bounds, delayed polling, restart, invalid MP4. Физическое доказательство: Async process fixture, one create, valid video checksum. Приёмка: Нет повторного create при timeout; итоговая цена pinned.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## VI-02 — Video формы двух клиентов и разрешённая приёмка

[VI-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#vi-02). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/video.py`, `src/elevenbot/anymodel_video.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Переиспользовать video forms; подключить Mini App quote/status/library. Зависимости: VI-01, AP-03, MC-02. Решения: D-06. Параллельно: только по lock-check.

Проверки: Недопустимые параметры/credits, restart, Telegram delivery. Физическое доказательство: Один разрешённый live video по продаваемой capability + записи UI. Приёмка: Video доступно из библиотеки обоих клиентов; live без доступа BLOCKED.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## VO-02 — Voice UI и E2E двух клиентов

[VO-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#vo-02). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/anymodel_speech.py`, `src/elevenbot/worker.py`, `src/elevenbot/providers.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Формы текста/языка/голоса/параметров через каталог и общий quote. Зависимости: VO-01, AP-03, MC-02. Решения: D-06. Параллельно: только по lock-check.

Проверки: Границы длины, sample ownership, interrupted delivery. Физическое доказательство: Разрешённая озвучка, воспроизведение/скачивание после restart. Приёмка: Сохранённый audio и проводки совпадают; цены не в UI.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## MU-02 — Music UI, library и разрешённый live proof

[MU-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#mu-02). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/clodex_music.py`, `src/elevenbot/fal.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Song/music формы и типизированная выдача в обоих клиентах. Зависимости: MU-01, AP-03, MC-02. Решения: D-06 D-08. Параллельно: только по lock-check.

Проверки: Lyrics bounds, unavailable model, multiple outputs, resend. Физическое доказательство: Разрешённый реальный output каждой включённой music capability. Приёмка: Лицензия и ограничения показаны; нет продаж непроверенных возможностей.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## ML-03 — Пять строк Telegram и карточки Mini App

[ML-03: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#ml-03). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/core.py`, `src/elevenbot/storage.py`, `src/elevenbot/anymodel_image_jobs.py`, `miniapp/backend/web.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: В боте preview prompt + final price, ≤5/page; Mini App detail/download/resend/new quote. Зависимости: ML-02, MA-01. Решения: общие gates. Параллельно: MU-01.

Проверки: Long escaping, page bounds, historical price, resend no POST. Физическое доказательство: Одна работа открывается из обоих клиентов после restart. Приёмка: Re-delivery не генерирует и не списывает; create similar явно новый quote.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## WL-01 — Проверить атомарный reserve/capture/release/refund

[WL-01: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#wl-01). P0, S7, effort 5, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/task_wallet.py`, `src/elevenbot/core.py`, `migrations/026_task_wallet.sql`, `migrations/034_topups.sql`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Сохранить existing task_wallet, добавить только доказанно missing constraints/compensation; один migration writer. Зависимости: JO-03, PC-01. Решения: общие gates. Параллельно: только по lock-check.

Проверки: 20 concurrent reserve, double completion, crash before/after commit, unknown provider. Физическое доказательство: PostgreSQL transaction race trace и ledger reconciliation. Приёмка: Баланс/резерв корректны, уникальный effect, нет release при unknown.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## PY-01 — Проверить existing Stars checkout на одном конфиге

[PY-01: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#py-01). P0, S1, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/telegram.py`, `src/elevenbot/core.py`, `src/elevenbot/topups.py`, `src/elevenbot/platega.py`, `src/elevenbot/platega_web.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Объединить существующие XTR invoice/precheckout/payment/refund с common wallet; не создавать отдельный платёжный сервис. Зависимости: IN-19, PC-01. Решения: D-02. Параллельно: только по lock-check.

Проверки: Duplicate successful_payment, wrong XTR/amount/charge/user, fixture topup→ordinary image. Физическое доказательство: Один credit и один image capture на неизменном конфиге. Приёмка: Invoice и redirect не зачисляют; Stars digital flow включаем только по policy.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## PY-02 — Проверить Platega callback/reconcile без Telegram checkout

[PY-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#py-02). P1, S7, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/telegram.py`, `src/elevenbot/core.py`, `src/elevenbot/topups.py`, `src/elevenbot/platega.py`, `src/elevenbot/platega_web.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Сохранить topups/chargeback/debt; исправлять только подтверждённое; закрыть запрещённый digital checkout. Зависимости: IN-19. Решения: D-03. Параллельно: только по lock-check.

Проверки: Auth callback, mismatch, duplicate/out-of-order, create_unknown, restart mid-credit. Физическое доказательство: Изолированная HTTP/DB failure matrix; отдельный approved sandbox если доступен. Приёмка: Ровно один credit; unknown не повторяется; Platega не обход Stars.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## PY-03 — Mini App Stars и payment history

[PY-03: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#py-03). P1, S5, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/telegram.py`, `src/elevenbot/core.py`, `src/elevenbot/topups.py`, `src/elevenbot/platega.py`, `src/elevenbot/platega_web.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Существующий checkout через API и Telegram invoice UI, pending/verify/history/paysupport. Зависимости: AP-01, PY-01, MA-01. Решения: D-06. Параллельно: только по lock-check.

Проверки: Cancelled invoice, duplicate event, stale session, generation race. Физическое доказательство: Telegram Stars test environment + Mini App→bot same wallet. Приёмка: Одна серверно подтверждённая проводка; real funds только отдельно.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## RF-03 — Реферальные экраны и API обоих клиентов

[RF-03: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#rf-03). P1, S7, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/core.py`, `src/elevenbot/task_wallet.py`. Состояние: NOT_STARTED.

Недостающий результат: Личная ссылка, invitees, reward history/terms через общий service; только разрешённые данные. Зависимости: RF-02, AP-01. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Cross-user, pagination, empty/reversed/debt states. Физическое доказательство: Один реферальный сценарий в Telegram и Mini App на синтетических аккаунтах. Приёмка: UI совпадает с ledger; показана версия условий.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## SL-03 — Support/legal/profile в двух клиентах

[SL-03: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#sl-03). P1, S6, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/core.py`, `src/elevenbot/config.py`, `src/elevenbot/telegram.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Подключить документы, профиль и историю обращений к общему API без второго account store. Зависимости: SL-01, SL-02, MA-01. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Unaccepted user, suspended user, both clients, reply notifications. Физическое доказательство: Сквозной ticket/response, документы скачаны в клиентах. Приёмка: Один ticket и consent state, понятный канал paysupport.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## SE-03 — Независимая regression security двух клиентов

[SE-03: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#se-03). P1, S7, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/interaction.py`, `src/elevenbot/admin_access.py`, `miniapp/backend/web.py`, `.dockerignore`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Проверить реальные HTTP/UI denies и command boundaries, не ограничиваться статическим сканером. Зависимости: SE-02, AD-03, MA-03. Решения: общие gates. Параллельно: OP-02.

Проверки: Two-user roles, revoke, stale session, forged price, upload abuse. Физическое доказательство: Записи отрицательных сценариев + серверные evidence IDs. Приёмка: Нет обхода API через прямой URL/старую кнопку.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## TQ-02 — Сквозная parity/regression matrix четырёх студий

[TQ-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#tq-02). P1, S8, effort 5, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `tests`, `miniapp/tests/test_miniapp.py`, `.github/workflows/test.yml`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Собрать уже существующие fixtures и live evidence в трассируемую acceptance matrix; воспроизводить только missing. Зависимости: MA-04, TA-02, WL-02, SE-03. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Happy/failure/uncertain/restart/resend для каждого включённого типа. Физическое доказательство: Ссылки test ID→contract→SHA→UI/provider evidence. Приёмка: Обязательные сценарии покрыты; непроверенные capability выключены.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## OB-03 — Dashboard отчётов и управляемые incident alerts

[OB-03: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#ob-03). P1, S6, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `src/elevenbot/progress.py`, `src/elevenbot/pricing.py`, `src/elevenbot/worker.py`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: UI reports/export и opt-in admin alerts с thresholds/dedup/cooldown; доступ к данным по role. Зависимости: OB-02, AD-03. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Provider outage, stale queue, repeated alert, export redaction. Физическое доказательство: Инъекция тестового инцидента и одно адресное уведомление. Приёмка: Финансы/операции разделены, alert не создаёт broadcast клиентам.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## RL-02 — Провести ограниченный коммерческий user journey

[RL-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#rl-02). P1, S8, effort 5, reviewer Burn2288, integration owner vankhu21.

Использовать PR #18 SHA `37337cc1538e26f91696be366908420d9dbb08d2`: `docs/acceptance/FOUNDATION_TEST_MATRIX.md`, `docs/operations/DEPLOYMENT.md`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Только отдельно разрешённый pilot: обычный user, Stars, генерация, доставка, library, поддержка/refund. Зависимости: RL-01, TQ-02, OP-03, OB-03. Решения: D-06 D-10. Параллельно: только по lock-check.

Проверки: Android/Desktop и оба канала, outage/restart/no duplicate charge. Физическое доказательство: Реальные обезличенные receipts/файлы/ledger и user-visible record. Приёмка: Независимый аудитор принимает именно pilot scope, не весь будущий каталог.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## AU-02 — Доказать передачу и повторный аудит без потери истории

[AU-02: полная карточка](../planning/MASTER_WORK_BREAKDOWN.md#au-02). P1, S0, effort 3, reviewer Burn2288, integration owner vankhu21.

Использовать PR #17 SHA `d691d54e0266c3d519d66575555fa45895ef40ac`: `AGENTS.md`, `CONTRIBUTING.md`, `.github/pull_request_template.md`. Состояние: SOURCE_PRESENT / PR_OPEN / PARTIAL / LIVE_NOT_PROVEN.

Недостающий результат: Одна синтетическая docs-задача revision r1→rejected→r2, immutable index и sha256 evidence inventory. Зависимости: AU-01. Решения: общие gates. Параллельно: только по lock-check.

Проверки: Missing file/hash, bad schema, absent PR/CI, secret canary, prior verdict retention. Физическое доказательство: Постоянные SHA URLs на оба пакета и независимое решение. Приёмка: Старое отрицательное заключение сохранено; archive не копирует application code.

Передача: code PR, exact base/head/main SHA, manifest и весь пакет по [протоколу](../planning/EVIDENCE_PUBLICATION_PROTOCOL.md), peer review и ChatGPT audit. Без published evidence не READY_FOR_AUDIT; без согласованной интеграции не ACCEPTED.

## Ревью коллеги

IN-01, IN-02, IN-18, IN-19, AR-01, AR-02, AD-01, AD-02, PR-01, PR-02, PR-03, MC-01, JO-01, JO-02, JO-03, VO-01, MU-01, ML-01, ML-02, WL-02, RF-01, RF-02, SL-01, SL-02, SE-01, SE-02, TQ-01, OP-01, OP-02, OP-03, OB-01, OB-02, DC-01, DC-02, RL-01, RL-03, AP-01, AP-02, AP-03, AU-01. Для каждого сверить границу контракта и migrations, актуальный SHA CI и regressions; не заменять независимый аудит.

## Перенос и sync

После owner approval владелец своей dev-ветки переносит только согласованную версию worklist через собственный PR/commit, записывает источник planning SHA и сохранённый historical blob SHA. После принятия кода обновляет всю локальную main по CONTRIBUTING, включая код коллеги. При открытом PR common main не содержит этого кода; второе устройство NOT_PERFORMED до фактической проверки.

## IN-01-FIX-04: повторное использование

RF-03, PY-02 и SL-03: исполнитель vankhu21, рецензент Burn2288. Подробности, проверки и порядок — в [функциональном плане](../reference/REUSE_FUNCTIONAL_PLAN.md); исходные зависимости сохраняются.

## PREP-FINAL-ALIGNMENT-01

Владелец утвердил базовое распределение: pricing, wallet/ledger, Platega и Telegram — зона vankhu21; общий файл каждого будущего PR получает одного writer и второго reviewer. Письменное принятие обоих разработчиков подтверждено. Этот документационный кандидат разрешён владельцем; merge и retarget PR #8–#20 не разрешены.
