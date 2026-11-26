# FTL1-RF02-RECONCILIATION-01

[Burn2288 #22 | MASTER #56 | RF-02] — Rewards на capture и reversal/debt — LEVEL 1.

Integration baseline: `e2c0a19603df36a883c701ae3e076d72f0df9b74`, tree `1a733e4ad50ba18205baf554cb50ba50047c0223`.
Status: **OWNER_DECISION_REQUIRED**. Completed level: null.

## Findings

- RF-01 implements first-registration attribution, stable invitation codes and database immutability. See [service](../../src/elevenbot/referrals.py), [migration 044](../../migrations/044_referral_attribution.sql) and [FT022 regression](../../tests/test_ft022_referrals.py).
- RF-03 exposes the signed-in user's referral information in Mini App and Telegram. [PR #106](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/106) covers session and reload behavior. Financial reward history, reversal and debt views remain unproven.
- WL-01 has per-user reserve, capture and release in [task wallet](../../src/elevenbot/task_wallet.py). Provider refunds use [task receipts](../../src/elevenbot/task_receipts.py). These entries concern the charged user's task. They do not create or reverse a reward for the inviter. Top-up contracts are listed separately.
- [Historical RF-02](historical-tasks-v1.json) requires an approved versioned reward base after successful durable captured generation, excludes promotional/refunded amounts and requires unique event keys and an approved debt policy. [Contract index](../contracts/README.md) describes C-011 as a target. No approved D-07 was found in the reviewed sources. Historical [PR #17](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/17) and the attribution implementation are provenance, not reward proof.

## Owner decision D-07

Approve eligible capture events and funding sources, the versioned reward base/rate, currency or token units and rounding, effective date and policy version selection. Approve treatment of full and partial refunds, reversal identity, insufficient balance, debt recovery and exposure in both clients.

No reward ledger event, reward-to-capture link, refund reversal, debt accounting or reward authorization was demonstrated. Existing wallet and attribution idempotency cannot establish those properties. After D-07, verify duplicate and concurrent capture/refund, spent bonus, policy changes, exact arithmetic, immutable ledger history and cross-user isolation on disposable PostgreSQL 16.

Existing RF-01, RF-03 and wallet CI results are regression evidence only. The canonical task retains completed_level=null. This assessment provides no independent acceptance.
