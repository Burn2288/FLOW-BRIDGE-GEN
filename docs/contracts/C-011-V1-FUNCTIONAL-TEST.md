# D-07 / C-011 v1 · FUNCTIONAL_TEST

Burn2288 approved this policy for LEVEL 1 in the owner decision for
FTL1-RF02-IMPLEMENTATION-01. The 500 bps rate is a test parameter.
Production rates and production operation require separate approval.

## Funding and capture

RF-01 attribution is immutable and single level. A successful stored
generation with a durable capture can create one reward from proven paid
spend. Top-ups, reserves, releases, cancellations, uncertain outcomes,
promotional funds, referral credits and unknown funds yield no reward.
Disputed or refunded payment funds are ineligible. The platform funds the
reward in internal tokens that may be spent on generation. Withdrawal,
conversion to money and transfers are prohibited.

Spend PROMOTIONAL, then REFERRAL, then PAID. The implementation order
places UNKNOWN_LEGACY last, so legacy funds remain spendable without
treating their provenance as proven. Existing balances remain intact.
Reservation must preserve its funding allocation and the immutable
version and rate, and settlement must use that snapshot.

## Refund and debt

Allocate the cumulative credited refund in proportion to the original
capture. Use highest averages with stable ties in category order
PROMOTIONAL, REFERRAL, PAID, UNKNOWN_LEGACY. Each category receives a
nondecreasing share bounded by its original capture. A full refund
restores the original composition. Recompute the permitted reward on
remaining eligible paid spend using the original rate and round down.
The reversal is the difference between recognized and permitted reward.

Record compensating entries, use available referral funds only, and record
any shortfall as separate referral debt. Future rewards repay that debt.
Purchased funds, reserved bonuses and payment debt protections retain
their separate treatment. Referral debt alone does not block purchases
or paid generation.

## Chargeback and implementation boundary

Preserve existing payment chargeback behavior. Track affected historical
rewards for financial reconciliation. Automated historical reversal is
deferred and is a production release blocker.

The existing task refund ledger guard requires a full provider refund
and a matching full original charge. Partial provider receipts enter
reconciliation. The allocation helper does not authorize payments or
convert such a receipt into a wallet credit. Persistent funding
provenance, reward and reversal transactions, debt and the authorized
read service require separate implementation proof.
