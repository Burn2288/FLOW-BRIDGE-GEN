# Snapshot of 36 open public PRs — 2026-11-18

This is a **reconciliation inventory**, not a merge recommendation or proof of peer review. `main` at inventory: `60254e9ba24acb71d5694a230eebdb547f0e092e`. All below are OPEN; #11 is non-Draft and has one **APPROVED** review by Burn2288, other 35 are Draft. No blanket approval for stacked heads.

| PR | Owner | Integration treatment pending individual verification |
|---|---|---|
| #2, #4, #6, #7 | vankhu21 | Historical S0/image stack; test ancestry against #32 + joint, preserve unique fixes |
| #11 | vankhu21 | Approved review, still OPEN; candidate for first explicit integration/ancestry decision |
| #12–#17 | vankhu21 | Sequential video/FIBO/TTS/menu/admin/Mini App stack; #32 composite ancestry requires exact proof before superseding |
| #18–#22 | Burn2288 | Foundation/workplan/integration docs; reconcile with current contract decisions; do not mass-merge stale planning |
| #23–#26 | Burn2288 | Seeded migration, pilot+S2, image recovery, composite; verify ancestry and whether incorporated in #34/#41 |
| #27–#29 | Burn2288 | Audit register, HTTPS preflight, foundation contracts; docs and evidence require peer/collision review |
| #31 | Burn2288 | Contract evidence, staged on #29; review against current code/stack |
| #32 | vankhu21 | Composite #12–17 base, not a standalone final release without #40/#41/#43 resolution |
| #33 | Burn2288 | Disposable DB fixture safety; verify retained in integrated final candidate |
| #34 | Burn2288 | Main-based integration candidate; compare with vankhu21 `combined-live-smoke` and detect unique changes/conflicts |
| #35 | Burn2288 | Red diagnostics against old video delivery: retain as regression evidence, later supersede only after passing on integrated fix |
| #36–#39 | Burn2288 | Admission multiprocess → design → shadow store → privilege negative tests; candidate foundations, not production cutover |
| #40 | vankhu21 | Delivery ambiguity fix; needs integrated head regression/review |
| #41 | vankhu21 | Joins #38 and #40; ensure migration 040+041, receipt and admission shadow compatibility |
| #42 | Burn2288 | Restricted trusted-lock prototype; experimental, not production route or D-04 approval |
| #43 | vankhu21 | DEV fixture and split bot/worker execution; requires combined CI |
 
## Counts and procedure
- **36 open:** 14 vankhu21, 22 Burn2288 (check exact per-PR owner on each action). 35 Draft; one (#11) non-Draft and APPROVED. Historical approved PR #1 and #8–#10 are already merged and **not** in this inventory.
- No PR should be simply closed as an alternative to integration until its unique commits are proven included in the accepted final SHA or deliberately rejected with rationale.
- Decide the smallest safe sequence. Prefer one coherent integration PR from an exact SHA + documented supersession for redundant stacked drafts rather than merging the same code dozens of times.
- Verify `git merge-base`, parent history, changed-file inventory, migration checksums and full exact SHA CI; then owner-approved merge and a comment on each superseded PR linking the accepting commit.
- On both developer workstations, synchronize clean trees to accepted `main` before resuming feature tasks. No future work until that synchronized state is accepted.
