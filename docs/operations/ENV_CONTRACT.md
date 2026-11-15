# C-026/C-029 — Configuration and .env contract
Status: DESIGN_DRAFT. Names are proposed for FLOW-BRIDGE-GEN; no guarantee loader exists. Actual secrets NEVER entered into repo.

## Immutable bootstrap env, with example placeholder values
BOT_TOKEN=CHANGE_ME
DATABASE_URL=postgresql://user:password@localhost:5432/flow_bridge_gen
MINI_APP_PUBLIC_URL=https://example.invalid
MINI_APP_ALLOWED_ORIGINS=https://example.invalid
ADMIN_TELEGRAM_USER_IDS=111111111,222222222
PUBLIC_API_BASE_URL=https://example.invalid/api/v1
APP_ENV=development
APP_LOG_LEVEL=INFO
APP_TIMEZONE=UTC
PLATEGA_ENABLED=false
PLATEGA_MERCHANT_ID=CHANGE_ME
PLATEGA_SECRET=CHANGE_ME
PLATEGA_BASE_URL=https://app.platega.io
PLATEGA_CALLBACK_ENABLED=false
PLATEGA_CALLBACK_PATH=/api/v1/platega/callback
PROVIDER_SECRET_STORE=env
MEDIA_STORAGE_BACKEND=local
MEDIA_STORAGE_LOCAL_ROOT=.local/media
MEDIA_SIGNING_SECRET=CHANGE_ME
ENCRYPTION_KEY=CHANGE_ME
FEATURE_MINI_APP_ENABLED=false
FEATURE_MUSIC_ENABLED=false
FEATURE_VIDEO_ENABLED=false
FEATURE_REFERRALS_ENABLED=false

## Admin allowlist contract
ADMIN_TELEGRAM_USER_IDS is comma-separated list of strictly positive Telegram numeric IDs; whitespace trimmed, reject invalid/duplicate IDs on startup, forbid empty if admin mode enabled. The IDs are eligibility to show entry chooser, not full permission grants. Runtime verifies signed initData and server role on every admin API request. Missing/empty list safely disables admin entry, never grants access. Never fallback to all users. May require restart when env changes; document and test reload.
The two sample IDs above are NOT real or assigned IDs. Do not default to a specific developer's account or assume both developers should be administrators.

## Configuration stratification
Environment secrets: bot token, Platega credentials, signing/encryption keys, provider API tokens, DB URL. DB configurable audited settings: provider enabled state, model catalog and pricing, referral percent, balance presets, rate limits, UI labels and ordering, admin preferences. Env flags can disable risky subsystem regardless of DB; dynamic admin changes cannot overwrite restricted secrets. Validated config loader defines precedence and safe startup behavior. Sensitive values redacted in logs, exports and diagnostics.
Credentials registry maps provider_id + secret_ref to secure storage (env/secret manager) without revealing raw key in admin. Newly entered secrets require secure channel, masked display, tested rotation, audit without values.

## Fail-closed behavior
Invalid bot token or DB config → refuse startup. No Platega credentials → payment disabled, other services available. Invalid admin IDs → startup validation error or admin disabled (choose and lock policy before code). Invalid media backend → affected generators unavailable without losing accepted jobs; retain recovery queue. Missing provider credential → only its capabilities disabled. Neither bot nor Mini App should claim payment/generation succeeded based on feature flag.

## Deployment/secret hygiene
Use .env.example only with placeholders; .env and dump files in .gitignore; host secrets injected via systemd credentials/environment or secure secret manager. Compose and CI use fake keys and no production network payments. Explicit approval required for real paid tests or production changes. Do not automatically rotate credentials in this documentation phase.

## Acceptance
Configuration parse tests, admin allowlist spoof test, missing credentials graceful degradation, no token in logs/PR/artifacts, secret rotation staging, environment vs settings precedence, restart behavior and stale session revocation.
