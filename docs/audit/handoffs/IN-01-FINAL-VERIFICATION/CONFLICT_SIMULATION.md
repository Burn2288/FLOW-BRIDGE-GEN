# Conflict simulation

`git merge-tree --write-tree 3815642b5abcf25b6c2206f72c29fd3b8928bdb0 d691d54e0266c3d519d66575555fa45895ef40ac`: four conflicts; command creates temporary Git objects but does not alter refs, index or worktree. No merge performed. Planning side is PR #20; code side is PR #17. Repeat on actual future integration SHAs.

| Path | Type | Planning / code side purpose | Preservation and future check |
| --- | --- | --- | --- |
| `.gitattributes` | add/add | Evidence byte preservation and JSON line ending rules / shell script line ending rule | Combine compatible patterns preserving evidence hashes and executable script behavior; verify SHA-256 and scripts on supported platforms. |
| `README.md` | content | Planning entry points and collaboration / application entry and operational overview | Retain current app instructions plus planning links; validate links and actual run commands in isolated setup. |
| `docs/README.md` | content | Planning index and contracts / code documentation catalog | Preserve both indexes and navigability; docs link check and reviewer verification. |
| `docs/ROADMAP.md` | content | Staged engineering plan / existing project roadmap | Reconcile both milestones without declaring unimplemented features complete; peer review and requirements trace. |

Losing either side can remove audit fidelity, code use instructions, navigation or historical scope. No blanket ours/theirs. Simulation is not a resolved or tested composite tree.
