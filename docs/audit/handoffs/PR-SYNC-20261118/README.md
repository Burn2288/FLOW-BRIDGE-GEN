# PR-SYNC-20261118 — owner-directed integration freeze and backlog reconciliation

**Owner directive, 2026-11-18:** suspend all new feature/task implementation for Burn2288 and vankhu21. Prioritize reconciling every accumulated open PR, peer reviews, exact-SHA acceptance, and synchronized copies of one accepted project. This overrides the earlier assumption that the two developers continue unrestricted independent task generation. **Do not discard approved history or claim all 36 are ready to merge.**

## Verified snapshot
- Repository: `Burn2288/FLOW-BRIDGE-GEN`; `main` `60254e9ba24acb71d5694a230eebdb547f0e092e`.
- 36 public PRs are open as of this inventory (see `PR_REGISTER.md`); most are Draft and stacked on non-main branches. One PR #11 was APPROVED by Burn2288 on 2026-11-17 but is still open, and that approval does **not** approve the later combined commit.
- vankhu21 combined branch: `work/vankhu21/combined-live-smoke` HEAD `f37f647a5d168098c2bbaed4097d7ad5fcd2ccd0`, tree `ebeef1ee0e427295bb3781905f78c6993511769c`; parents PR #41 `337bf05875c518bd05308ce9edec8849fbc607e5`, #42 `37d35a501f6db9a58a24ce8057132f77d8f4d84a`, #43 `0cdda8c86676288e9b0d47d1b14e7ba8598aaafa`. GitHub comparison against main: 101 commits ahead, 0 behind, 170 changed files. This is a candidate, **not** an accepted replacement for main.
- At inventory time, exact SHA `f37f647a` has **0 GitHub check runs**, and no commit-associated PR workflow runs were returned. The user-provided report attributes 11 local mock/PostgreSQL tests and live stand `flowbridge-live-smoke-joint` to the SHA; this is encouraging evidence, not full exact-head CI, not a public HTTPS Mini App acceptance test, and not proof of production safety.
- User-provided joint-build report states Mini App local HTTP 200 but `MINIAPP_URL` empty: Telegram entry into Mini App is NOT_TESTED on that stand. It reports a real `/menu` and opening one pre-existing image in Telegram, with mock tests for other paths. No claim of real paid provider or payment acceptance.
- Option B PostgreSQL admission is owner-approved **as direction**, shadow primitives not live; D-04 / cutover remain open. VIDEO-DELIVERY-AMBIGUITY requires integration-level independent verification (PR #40 corrective candidate and PR #35 diagnostic test).

## New precedence, effective now
1. Freeze all new non-integration tasks. Do not create additional feature PRs or autonomous task batches. Work that directly repairs a listed integration blocker is allowed only as a bounded correction in the synchronization process.
2. Inventory and categorize every open PR: **MERGE_CANDIDATE**, **SUPERSEDED_BY_PROVEN_ANCESTRY**, **FIX_REQUIRED**, **DOCUMENT_ONLY**, **OWNER_DECISION**, **RETAIN_UNMERGED**. Superseded does not mean safe to close until commit ancestry, unique diff and acceptance evidence are recorded.
3. Use `work/vankhu21/combined-live-smoke` as one reference candidate, *not* an automatic final baseline. Check collisions against Burn2288 PR #34–39 and document #18–22/#27/#29/#31, not just #41–43.
4. Run complete exact-HEAD CI/S2, migration upgrades with populated backup/restore, authorization/delivery negative tests, and local real Telegram smoke for selected paths. Test payment/provider with mocks only. Separate staging network and public HTTPS checks; never mislabel a local 200 as public reachability.
5. Publish written specific findings by owner in `VANKHU21_FIX_REQUEST.md` and public PR review comments. vankhu21 fixes only vankhu21-owned files; Burn2288 handles own security/test/doc files. Shared files require designated single writer and peer reviewer.
6. First integrate **one reviewed, reproducible, coherent release candidate** to main through agreed PR process. Only then close earlier redundant Draft PRs with an explicit supersession comment/sha. Never mass-merge stacks or close all old PRs blindly.
7. After acceptance, synchronize both developers' complete local trees to the exact accepted main SHA and verify clean working trees, migrations, and standalone test run on both. Mark inaccessible machine NOT_PERFORMED, not PASS.
8. No production deployment, real banking, paid AI calls, credential exposure, retarget or force push under this instruction.

## Release blockers and ownership
- **VANKHU21**: use `VANKHU21_FIX_REQUEST.md` for delivery acceptance, joint candidate evidence, live Telegram/Mini App HTTPS smoke, and shared UI/worker review.
- **BURN2288**: option-B safe read/lock, DB roles and bootstrap/rollbacks, all-integration CI, docs/inventory and branch synchronization. Preserve `CUTOVER_NOT_AUTHORIZED`.
- **OWNER**: final meaning of remaining D-04, paid-result retrieval and in-flight settlement; approve exact integrated SHA/merge and environment activation separately.

## Closeout ledger
For each PR keep fields: PR number; exact HEAD/base; owner; status; overlaps/ancestry; finding file; CI SHA; peer approval; intended destination; action (`merge`, `supersede/close`, `retain`); merge/closure SHA; both local-sync SHAs. No `DONE` while any required field is unproven.

**State at creation: FREEZE_ACTIVE / RECONCILIATION_PENDING / NO_MERGE_PERFORMED.**
