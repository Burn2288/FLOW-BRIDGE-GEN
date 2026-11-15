# C-010/C-011 — Referral system adaptation from AI-SHOP-BOT
Status: DESIGN_DRAFT. Source SHA: Burn2288/AI-SHOP-BOT 494ab81f5552be836a37ec3aa685e6be8308076c.

## Source functionality confirmed by file inspection
- Cryptographically random stable referral code, link https://t.me/<bot_username>?start=ref_<code>; donor app/repositories/referrals.py.
- /start resolves code, binds referred_by only on new user, forbids self-referral, repeat registration preserves original; donor app/handlers/start.py and app/repositories/users.py.
- Referral page lists personalized link, count, delivered-purchase turnover, pagination up to 10, reward percent; donor app/handlers/referrals.py + app/services/referrals.py.
- Configurable reward percent 0..100, default 10 in app/repositories/referral_settings.py; default is DONOR value, not approval for FLOW.
- app/repositories/referral_rewards.py supports idempotent credit per purchase with unique business keys, integer rounding (amount*percent+50)//100, debt offset, reversal on refund and unrecovered-debt tracking. Confirmed code presence, not tested behavior.
- Donor docs/USER_FLOWS.md contains an older description mentioning a non-accrual phase and delivered-purchase stats; code now includes reward repository. Use exact SHA and source-code checks rather than treat all historical descriptions as simultaneous current behavior.

## Adaptation to an AI generation platform
Referral qualification must be clearly defined by owner. Proposed default: one-time binding on initial valid signup; no reward for invitation or topup; reward on net user charge for a SUCCEEDED paid GenerationJob with durable LibraryItem, after billing CAPTURE; exclude free/promotional spend and amounts refunded. Alternative bases (first topup, total paid, percentage of profit) need explicit ADR and finance tests.
Referral attribution is immutable per user and server-only. Invitees cannot self-refer, recursively or via repeated /start change original referrer. External Telegram identity and referral code are not the same entity.
Referral program version holds reward percent, eligibility, max cap, hold period, fraud checks, start/end date. Historical rewards retain the rule version active at qualifying event. If amount is charged in RUB minor units, calculate deterministic integer minor-unit bonus using approved rounding; no floats.

## Contract
Attribution(user_id,referrer_user_id,source,created_at) unique user; Reward(reward_id,source_job_id,beneficiary_id,invitee_id,rule_version,base_minor,percent,calculated_minor,credited_minor,reversed_minor,status,created_at). Credit once per eligible captured job with unique job/reward key. Refund is an explicit reverse event, idempotent; if inviter has already spent bonus, do not make regular balance negative. Track referral_debt ledger and offset later bonuses with transparent user-facing accounting, subject to product-policy approval.
Admin controls: referral enabled flag, percent bounds and effective date, eligible charge types, hold/dispute policy, anti-abuse limits, preview impact; all audited.

## UI (both clients)
Personal link/copy/share, total invited, completed qualifying generations/turnover, earned/paid bonus and outstanding reversals where relevant, terms, paginated invitees and reward history, Back. Hide private invitee details unless necessary and permitted by privacy policy. Referral tracking must survive switch between DM and Mini App.

## Tests
Forged deep link, self referral, same user repeatedly using new code, duplicate captured job, concurrent refund and capture, incorrect rule version, spend-before-refund with referral debt, cancellation/failed paid job, multiple referrals, privacy restrictions, code uniqueness under concurrency, cross-user access, fraud thresholds.
