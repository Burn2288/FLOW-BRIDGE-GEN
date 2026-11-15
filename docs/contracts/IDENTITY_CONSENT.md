# C-001/C-002/C-003 — Identity, legal consent, sessions
Status: DESIGN_DRAFT. Sources: OWNER_REQUIREMENT, AI-SHOP-BOT source pattern, BASE_DIRECTIVE.

## Registration and trust boundaries
- Canonical identity is a server-assigned internal user UUID and a unique Telegram user ID (bigint). Telegram username and display names are mutable, never authorization keys.
- Telegram DM /start: validate chat type; upsert profile and immutable created_at; process referral deep-link only for first valid binding; preserve wallet, agreements and referral even after repeated /start.
- New user remains CONSENT_REQUIRED until acceptance of current legal documents. Show both user agreement and privacy policy as actual .md files, then an explicit acceptance action. Failure to deliver either file must not allow acceptance.
- Store immutable consent evidence: user_id, agreement_version, privacy_version, hashes, accepted_at UTC, source (bot|mini_app), evidence/session correlation. Never accept consent using stale callback, missing version or only a visual toggle. Retain historical acceptance events according to legal retention.
- Product actions behind consent gate: catalog purchase, quote, job, library, wallet operations, referrals rewards and Mini App business endpoints. Unaccepted user may access consent documents, support/contact and data-related requests.
- Editing an agreement creates a new canonical version and forces acceptance upon next protected action. Effective date and source-of-truth file version documented; privacy update re-consent policy to be approved.

## Mini App authentication
- Receive Telegram WebApp.initData as a short-lived credential; verify integrity with Telegram-recommended server-side algorithm and BOT_TOKEN. Validate auth_date age, replay policy, the entire signed field set and strictly bind the authenticated Telegram ID to canonical user.
- Do not trust initDataUnsafe, query arguments, user_id from client, UI role, a copied bot callback or a static admin flag.
- Issue short-lived HttpOnly Secure SameSite session cookie or short-lived bearer token with CSRF controls appropriate to chosen mechanism; protect every API request and websocket/SSE channel. Session revocation, expiration, device limits and invalid-token error are documented in API foundation.
- Bot and Mini App reuse consent/user state: no separate registration or wallet.

## Lifecycle and errors
NEW → CONSENT_REQUIRED → ACTIVE; LEGAL_VERSION_OUTDATED → CONSENT_REQUIRED; SUSPENDED/BLOCKED (only audited admin command). Auth errors: AUTH_INVALID, AUTH_EXPIRED, CONSENT_REQUIRED, CONSENT_STALE, ACCESS_REVOKED. Race: two simultaneous /start/accept requests produce one canonical user and at most one acceptance per user/version; no lost referral binding.

## Acceptance
Tests: repeated /start, referral deep link, idempotent consent, changed file hash, callback replay, privacy document unavailable, invalid/tampered/expired initData, spoofed user ID, suspended account, concurrent requests. Evidence must include commit SHA and environment. No runtime state confirmed in FLOW-BRIDGE-GEN.
