# EVIDENCE

Source references неизменны. Public GitHub repository metadata/PR refs/workflow conclusions получены подключением GitHub; Git clone с network approval затем дал actual commit graph и blobs. Загрузка исходников не равна запуску production.

- [Foundation source](https://github.com/Burn2288/FLOW-BRIDGE-GEN/tree/37337cc1538e26f91696be366908420d9dbb08d2) и [candidate source](https://github.com/Burn2288/FLOW-BRIDGE-GEN/tree/d691d54e0266c3d519d66575555fa45895ef40ac).
- [GitHub snapshot](../../../planning/evidence/github-snapshot.json): state/base/head каждого PR и successful CI requested SHA.
- [Branch HEADs](../../../planning/evidence/branch-heads.txt), [effective deltas](../../../planning/evidence/pr-deltas.json), [source symbols/lines](../../../planning/evidence/source-symbols.json), [migration checksums](../../../planning/evidence/migrations.json).
- [Workplan provenance](../../../planning/evidence/workplan-snapshots.json), [historical originals](../../../planning/history/README.md).
- [Auditor inventory](../../../planning/evidence/auditor-inventory.json), read-only audit branch exact SHA, исторические заключения не удалены.
- [CI397 safe summary](../../../planning/evidence/ci-397-summary.txt): только обезличенная итоговая строка job; сырые логи не опубликованы.
- [Base5601faa delta](../../../planning/evidence/5601faa-to-candidate.diffstat.txt): не подмена исходной версии.

Собственный documentation proof: вывод checker на frozen content SHA и успешный Documentation CI опубликованы в TEST_RESULTS/manifest/PR. Проверка публичного Draft PR и package URL — physical proof планировочной задачи. Provider image/Telegram actual display/Ubuntu deployment здесь NOT_TESTED, не заменяются этими evidence.

## Published documentation proof

[Content commit](https://github.com/Burn2288/FLOW-BRIDGE-GEN/commit/6e0b7a63241f2eeb14204ec48f2592b64e908f90), [Draft PR19](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/19), [CI](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/43873943770), [selected safe validation output](../../../planning/evidence/planning-validation.txt). Local draft и published commit имеют один treeSHA; другой commitSHA обусловлен публикацией через коннектор, не изменением содержимого. Final artifact SHA/CI проверяются по publication pointer в PR19.
