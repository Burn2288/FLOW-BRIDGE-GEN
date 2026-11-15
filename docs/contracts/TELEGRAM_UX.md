# C-004 — Telegram DM UX navigation contract
Status: DESIGN_DRAFT. Primary source: OWNER_REQUIREMENT. Additional nodes explicitly DESIGN_PROPOSAL.

## Navigation principles
- Private-chat user-facing bot; one canonical menu message per session where practicable. Prefer editMessageText/editMessageCaption/editMessageMedia with inline keyboard; preserve a stable screen and message ID. If edit unavailable/deleted/outdated, send exactly one replacement menu and update session pointer; do not spam messages.
- Use brief labels, consistent Back, explicit loading and errors. Telegram supports button styling only where current Bot API/client makes it available; intended green positive, blue account, red Back are DESIGN INTENT, not guaranteed styling. Use approved API-supported styling after verification; fallback to emoji/neutral buttons.
- Reply keyboard reserved for nonessential, high-frequency entry points (e.g. «🏠 Меню», «🎨 Открыть студию», «👤 Личный кабинет», «🆘 Поддержка»). Do not duplicate every inline menu item. Reply-keyboard text must be router-safe and must never bypass consent/authorization.
- Callback payload length bounded by Telegram platform; store complex navigation in server session, use compact route IDs/opaque state references; never put trusted price/user_id in callback.
- User content prompts are separate messages or FSM captures; on completion delete/hide input only with platform permissions and clear user disclosure. New /start resets obsolete FSM without cancelling a running paid job.

## Required screens (OWNER_REQUIREMENT)
ENTRY: /start → upsert identity → send agreement .md + privacy .md → explicit Accept → MAIN.
MAIN:
  [🟢 Открыть студию] [🔵 Личный кабинет]
  [Реферальная система]
  [Тех. поддержка]
  [Информация]
STUDIO:
  [🟢 Моя библиотека]
  [Фото студия] [Видео студия]
  [Озвучка текста] [Создание песен]
  [🔴 Назад] → MAIN
LIBRARY:
  [🖼 Фото] [📹 Видео]
  [🗣 Озвучка текста] [🎧 Музыка]
  [🔴 Назад] → STUDIO
LIBRARY_CATEGORY (photo/video/tts/music):
  Rows: «<обрезанный безопасный prompt preview> | <фактическая стоимость>»
  Maximum five results per page; next/previous only when page exists; Back → LIBRARY.
  Selecting entry → details, preview/download, resend without regeneration; price for a historical result is final amount, not today's price.
INFORMATION:
  [Пользовательское соглашение] → sends current .md
  [Политика конфиденциальности] → sends current .md
  [🔴 Назад] → MAIN
PROFILE:
  [Мой баланс] → BALANCE
  [Мои генерации] → JOBS (DESIGN_PROPOSAL)
  [Настройки] → SETTINGS (DESIGN_PROPOSAL)
  [🔴 Назад] → MAIN
BALANCE:
  [Пополнить баланс] → TOPUP
  [История транзакций] → WALLET_HISTORY
  [Активные платежи] → PAYMENT_INTENTS (DESIGN_PROPOSAL)
  [🔴 Назад] → PROFILE
REFERRALS:
  [Моя ссылка] [Приглашённые] [История вознаграждений]
  [Условия программы] [🔴 Назад] → MAIN
SUPPORT:
  [Создать обращение] [Мои обращения] [🔴 Назад] → MAIN
STUDIO_TYPE (photo/video/tts/music):
  Catalog of active compatible models with price and capability badge, five per page; model detail → input wizard → server quote → confirm → job status.
MODEL_WIZARD (proposed): prompt → type-specific options → expected amount/confirmation → generate. On error stay at last valid step.

## Screen contracts
Every screen declares stable route ID, required permission, input/output view model, parent/back route, own page cursor, empty/error/loading state, events, tracking, acceptance test. Pagination uses stable sort (created_at DESC, id DESC), 1-based page; page resets on filter change; price display in rubles/minor-unit rounding determined by Pricing.
Suggested routes: main, studio, studio.catalog, studio.model, studio.prompt, studio.quote, studio.job, library.index, library.list, library.detail, profile, wallet.index, wallet.topup, wallet.history, referrals.index, referrals.list, referrals.rewards, support.index, info.index. Routes are internal contract identifiers, not necessarily callback literals.

## Interface consistency
- Successful screen navigation edits canonical message; document delivery/new generated media legitimately sends separate messages.
- Back must restore prior filter/page when valid; expired data returns nearest safe parent.
- Intro and agreement pages remain reachable without purchase privileges.
- Never show admin controls just from an inline UI flag; authoritative server check.
- Alerts provide recoverable action for failure; «Проверить статус» only queries provider/payment, never creates another paid request.
- Each studio and library item provides title/model, final cost where applicable, status and readable error; avoid leaking raw prompts to logs.

## Contract tests
Table-driven routing + Back, ≤5 results/page, page boundaries, 1024 caption limit, UTF-8/HTML escaping, long model names/prompt previews, duplicate callbacks, edit-not-modified, edit errors/fallback no duplicate, multiple devices, consent lock, empty library, active jobs and unknown payment.
