# Early PR preservation

At code head `d691d54e0266c3d519d66575555fa45895ef40ac`, each historical #2/#4/#6/#7 head is a Git ancestor: historical commits PRESERVED, not proof of current behavior. For paths changed by each PR, compare old tree blobs to #17:

| PR | Changed paths at PR | Unchanged blobs at #17 | Different blobs | Absent paths | Assessment |
| --- | ---: | ---: | ---: | ---: | --- |
| #2 | 126 | 99 | 27 | 0 | PRESERVED history; changed semantics NOT_PROVEN except separately examined access case |
| #4 | 6 | 5 | 1 | 0 | PRESERVED history; changed path NOT_PROVEN |
| #6 | 7 | 4 | 3 | 0 | PRESERVED history; changed paths NOT_PROVEN |
| #7 | 14 | 9 | 5 | 0 | PRESERVED history; changed paths NOT_PROVEN |

No changed test path from these PRs was absent in #17; this is path presence, not preserved test assertions. At #2 `tests/test_runtime_service.py` defines `test_private_access_denied_before_registration`; at #17 it instead defines `test_non_admin_in_private_pilot_can_accept_terms_and_open_user_menu`. The owner later approved a future admission policy, but current behavior and approved target are different; semantic parity is NOT_PROVEN. At #17 `tests/required_s2_cases.json` still names the old test, and `scripts/run_s2.py` and `scripts/run_native_acceptance.py` reference that registry; whether this affects the actual S2/native gate is NOT_PROVEN and needs review, not inferred from green isolated CI. Preserve explicit before-registration denial/tester/admin/public/callback/Mini App regression cases after implementation is authorized.

No unmerged unique commits outside the candidate were found for the four heads as ancestry, but changed blobs require per-change semantics review. No blanket SUPERSEDED_WITH_EVIDENCE classification is claimed for uninspected changes.
