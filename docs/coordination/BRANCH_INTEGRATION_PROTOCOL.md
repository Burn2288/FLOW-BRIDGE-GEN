# GitHub protocol: coexistence and safe integration of two Codex developers

Status: DOCUMENTATION_PROPOSAL + summary of existing normative `CONTRIBUTING.md` and `AGENTS.md`; those two are the authoritative general rules in `docs/bootstrap`. Do not silently alter their ownership rules or personal workplans.

## Normative branch model
- `main` is only accepted common build after PR, independent peer review, current SHA CI and approval.
- `dev/burn2288`, `dev/vankhu21` store own plans and untested work; neither is implicitly accepted.
- `work/<login>/<task>` is an isolated reviewable change; target `main` after dependency resolution. Separate plan commits from code.
- Documentation staging: `docs/bootstrap` PR #1 targets `main`; documentation extension `docs/foundation-contracts-v1` PR #18 targets `docs/bootstrap` until foundation is accepted; revalidate base and retarget only in a planned integration step. Neither is currently merged.
- Independent `auditor` branch is historical evidence; audit does not substitute peer review.

## Observed historical deviation: stacked PRs
Feature PR #8 is against `main`; subsequent PRs #9–#17 are stacked one on the previous work branch, not the final `main` branch. Their diffs are reviewable individually, **but their code cannot be called accepted or locally synchronized common build** until prerequisites merge/rebase and final PR CI passes. Treat their effective changes as an ordered dependency graph, not independent merges. Owner and both developers must approve integration strategy. Avoid force push, automatic merge, cherry-pick of the entire cumulative HEAD, or dropping commits by comparing only file names.

Proposed order to validate (not an instruction to auto-merge): approve docs PR #1, determine exact base of #8; review #8 image integration, then #9 video, #10 AnyModel, #11 FIBO, #12 AnyModel video, #13 TTS, #14 welcome, #15 progress, #16 pricing/admin, #17 Mini App. Note other trial PRs (#2/#4/#6/#7) are separate proof branches and must be checked for supersession, not automatically combined. Each stage requires current SHA CI, peer review and diff consistency, then retarget next PR to updated `main` or recreate a clean equivalent work PR. No actual merge performed by this document.
When code is already superseded on later cumulative branch, preserve unique commits/behavior but avoid duplicate application of the same change; use compare/merge-base, tests and migration checksum.

## Every Codex task: preflight
1. Inspect `git status --short`, `git branch --show-current`, `git remote -v`, `git rev-parse HEAD`, `git fetch --prune origin`. Never discard uncommitted work.
2. Read `CONTRIBUTING.md`, `AGENTS.md`, `docs/FOUNDATION_INDEX.md`, related approved contract and developer's workplan, then pull/PR dependencies and latest actions. The workplan itself only changes under an authorized owner task.
3. Record expected base: accepted `origin/main` SHA and candidate branch SHAs. Establish whether a feature is IN_MAIN, PR_OPEN, STAND_ONLY, SOURCE_PRESENT or NOT_FOUND. Read actual code/test before proposing rewrite.
4. If touched module/schema overlaps teammate's work, stop coding and publish a dependency/conflict note with file paths and SHA. Resolve PR order and shared contract before editing.
5. Work in owner's own task branch based on accepted main unless explicitly an agreed stacked PR; make minimal vertical slice with new acceptance fixtures, no unrelated refactor.
6. Before PR: test affected module, regression suite, migration doctor/checksum, docs and CI current SHA. Report exact tested commands, environment, failures/skips, artifacts, changes and next step. PR needs peer review; no self-acceptance.
7. If PR open, synchronize **only accepted origin/main** on local main, protect unmerged work in personal branch, do not merge open PR code into local main as though approved.
8. Once merged, owner Codex synchronizes whole local clone: `git fetch --prune origin`; safe clean branch; `git switch main`; `git merge --ff-only origin/main`; compare `git rev-parse HEAD` and `git rev-parse origin/main`; reinstall/test dependency or DB migrations in authorized test environment, verify full app not only own module; update personal branch safely and record SHA. The other developer repeats process at next start/handoff; local devices are not accessible to auditor from GitHub alone.
9. No production mutation, paid provider request, irreversible DB migration, real payment, or merge without explicit owner approval.

## Evidence exchange format
TASK_ID; owner; baseline main SHA; external pending PR list; related contract IDs; affected files/migrations; dependency order; own PR SHA; exact CI URL/conclusion; peer reviewer and outcome; local sync main SHA; integration test evidence; residual NOT_PROVEN. Distinguish Git reachability, CI, and runtime separately.

## Cumulative code adoption rules
- Don't create parallel `Wallet`, `ProviderRegistry`, `MiniApp`, `TaskLaunch` if existing can be extended safely.
- Don't treat all ancestor stacked PRs as accepted. A work branch may include unreviewed parent commits.
- Do not `git merge main` over a dirty working tree; no `reset --hard`, force push or automatic conflict resolution destroying teammate work.
- Documentation PRs may advance in their own tree; once #1 accepted re-check the review base and linkages, ensure no contradiction with code at a new tested SHA.
