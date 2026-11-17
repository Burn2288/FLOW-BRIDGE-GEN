# C-005/C-020 — Telegram Mini App UX and administrator entry

> **Новая сверка с фактическим кодом (PR #17, SHA d691d54e…; 2026-11-15):** Mini App уже существует в `miniapp/backend/web.py` и `miniapp/frontend/*`: Telegram initData подписано и ограничено 300 с, bearer-сессия 600 с; доступны каталог, кошелёк, работы, файлы и изменение темы. Нет HTTP создания генераций/платежей и Mini App admin. Ниже приведён TARGET расширения, не требование переписать приложение. Состояние этого кода — SOURCE_PRESENT_UNMERGED + CI_PASS, не принятая main. [Полная инвентаризация](../audit/VANKHU21_IMPLEMENTATION_BASELINE.md).
Status: DESIGN_DRAFT. Source: OWNER_REQUIREMENT. No reference image provided; visual specification is a proposal, not an exact reproduction.

## Core rule
Mini App and DM bot implement functionally identical product operations through the same API. Mini App is an alternative presentation, not a second backend, wallet or job store. User may switch channels mid-job and see consistent status/library/balance.

## Public routes and information architecture
/launch → verify initData/consent → /home (or /entry-mode for allowlisted admin)
/home → studio (hero CTA), account (balance chip), library, referrals, support, information
/studio → /studio/images, /studio/videos, /studio/voice, /studio/music
/studio/:kind → model cards with capability/price/provider filters
/model/:id → model details and schema-rendered prompt form, input options, quote and Generate
/jobs/:id → progress, cancel where supported, error recovery and library link
/library → tab filter (Images / Videos / Voice / Music), search or date filter, card grid/list
/library/:item → preview, model, parameters, actual final amount, created date, download, resend
/account → wallet, payment history, profile, linked support
/account/wallet → amount presets/custom policy, external Platega payment handoff, verify status
/referrals → invite link, counts, reward history, terms
/support → ticket submission and history
/legal → agreement/privacy as documents
Admin area: /admin routes isolated from / routes; see ADMIN_CONTROL.

## Admin-specific launch chooser
TARGET: an entry chooser requires verified identity and server authorization. Existing source Config reads `ADMIN_TELEGRAM_IDS`; the proposed `ADMIN_TELEGRAM_USER_IDS` does not exist in the checked source and is not an alias. D-04 requires an owner decision. For authorized users show:
  [Войти в админ-панель] [Войти как пользователь].
Non-allowlisted users go directly to /home. Choice never self-escalates: each /admin request validates server identity, allowlist, RBAC and, where applicable, elevated authentication. Admin may return to user mode without loss of own wallet. UI cannot choose another actor. User mode is a normal user context, not administrator impersonation.

## UX quality thesis (text-only beta)
- Clear mobile-first hierarchy: home hero, 4 studios, quick balance, recent results; grid responsive to Telegram WebView width.
- Accessible contrast, concise typography scale, generous touch targets, visible focus, respect prefers-reduced-motion and Telegram theme dark/light.
- Color semantics consistent with DM intent (green Create/Studio; blue Account; red Back/destructive) without dependence on hue alone.
- Skeleton loading, optimistic UI limited to harmless navigation; never optimistic payment success or completed generation.
- Model cards: provider logo/name, media kind, capabilities, price unit, status/availability. A model variant with unsupported parameters hides/disables invalid controls.
- Pricing always shown before irreversible submission, includes quantity/duration/output size and exact quote expiration. Price changes require new quote and explicit consent.
- Job progress displays persisted status and uncertainty; no invented percentages if provider does not supply progress.
- Media preview uses signed, short-lived authorized URLs; rich viewing without exposing internal storage.
- All critical actions reachable with ≤3-4 obvious navigational decisions (goal, not measured guarantee).

## Layout skeleton
Bottom navigation (mobile): Studio | Library | Wallet | Profile. Home and support reachable from header/profile; no hidden financial or legal screens.
Admin: persistent sidebar or top segmented nav for Overview, Users, Jobs, Providers, Models, Pricing, Payments, Wallet/Ledger, Referrals, Reports, Settings, Audit. Adapt to narrow viewport.
State design: empty library, no provider, provider outage, insufficient balance, quote expired, running job, saved-but-not-delivered, payment pending, payment unknown/manual-review, blocked/suspended. Each includes actionable recovery.

## Required parity matrix
Each feature row must have bot route, Mini App route, API endpoint, role, tests and evidence in subsequent iterations. Both channels consume the same live model registry; neither hardcodes model/price definitions.

## Security and acceptance
Tampered/expired initData, forged allowlist, URL deep-link /admin, missing consent, stale session, SSRF media URL, cross-user library access, replay form, duplicate click, charge under race are tested. Mini App is NOT accepted merely because /home visually renders: validate physical Telegram launch and E2E user/payment/job paths separately.

## IN-01-FIX-02 — OWNER_APPROVED / IMPLEMENTATION_PENDING / PEER_REVIEW_PENDING

[Решение владельца](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/20#issuecomment-6919575091) утверждает private: admin + отдельный PILOT_TELEGRAM_USER_IDS, outsider denied до создания identity/user/wallet; tester не получает admin rights. Public: обычная регистрация после consent, generation/model/payment gates отдельно. Серверный admission обязателен для Telegram, callbacks, Mini App и HTTP, с проверкой отзыва сессий. Existing jobs, paid events, wallet и reconciliation сохраняются. Код ещё не реализует эту политику, runtime NOT_TESTED. Ревью vankhu21 ожидается. [Отдельное задание](../planning/integration/SEC-PILOT-01.md).
