# AD-01 HTTP RBAC — scoped functional preflight

**Status: BLOCKED_PENDING_OWNER_CONTRACT_DECISION**  
**Assessment base:** accepted `main` `a889d8306c743c0046b710b950608052eabfdc78`  
**Scope:** AD-01 HTTP default-deny, trusted identity, admin read-only capability, revocation boundary. This is an executor preflight, not independent acceptance.

## Finding

AD-01 cannot yet be implemented safely under the approved project contract because no approved HTTP administrator role/authority or revocation semantics exist. The foundation contract map says C-019's target RBAC model is unapproved, C-020's HTTP session does not inherit Telegram Admin Edition, and D-04 remains open. `docs/testing/ADMISSION_REVOCATION_ADR.md` is explicitly `PROPOSED / OWNER_DECISION_REQUIRED`; it says both the fenced rollout (A) and centralized authoritative policy (B) are not approved or implemented.

The current runtime has verified Telegram Mini App identity and a persisted, revocable user bearer session in `miniapp/backend/web.py`. `account()` resolves that session to the server-side Telegram identity and rechecks pilot admission and consent. It does not produce an admin role. The registered HTTP routes contain no `/api/v1/admin/*` capability endpoint. `src/elevenbot/admin_access.py` stores Telegram Admin Edition password sessions in process-local memory; that state is not an HTTP credential and must not be reused as one. `ADMIN_TELEGRAM_IDS` is an existing configuration allowlist used for private admission and Telegram-side privileges; `docs/operations/DEPLOYMENT.md` does not establish it as a shared HTTP RBAC contract. A local config-only check would not establish immediate revocation across independently running processes.

Historical PR #100 is a diagnostic for AD-03 at its then-base `d5adbc404006aec27269f7386cc148ed7a18a77b`; its missing-route observations are historical and are not represented as runtime test evidence for this assessment base.

## Acceptance matrix at this base

| Criterion | Current evidence | Result |
|---|---|---|
| HTTP admin defaults to deny | No admin routes registered in `web.py`; direct routes therefore do not exist. No positive admin endpoint exists to guard. | Partial: absence only; no usable RBAC endpoint |
| Missing/invalid session | Existing user `account()` rejects missing or malformed bearer tokens; no admin route to exercise | Existing session boundary present; admin matrix not tested |
| Ordinary user denied admin capability | No admin capability endpoint or role check exists | Not implemented |
| Client cannot forge a role | No client role is consumed by current `account()`; no admin capability endpoint exists | No current escalation path found; no positive-path test |
| Revocation considered by server | User sessions have a persisted `revoked` flag and admission is rechecked. Admin roles/revocation authority and cross-process effective-time semantics are not specified. | Blocked by contract |
| Telegram Admin session not reused | `AdminAccess` is process-local and separate; Mini App session is independently persisted | Confirmed by code inspection; not end-to-end tested here |
| Read-only admin API | No route exists | Not implemented |
| Financial side effects | No AD-01 code or tests run in this preflight | No behavior claimed |

## Required owner decision

Choose and approve one authority model before implementation:

1. **Fenced configuration rollout (ADR A):** explicitly authorize the existing server allowlist as the source for HTTP admin identity and define an enforceable deployment barrier that drains/fences every serving process before revocation is considered effective. Define `ADMIN_TELEGRAM_IDS` compatibility and whether an alias is permitted. Restart alone is not a fleet-wide revocation proof.
2. **Centralized policy (ADR B):** approve a durable server-side admin membership/policy source, bootstrap and break-glass ownership, audit requirements, effective-time semantics, fail-closed behavior on DB/policy outage, migration/rollback, and D-04 compatibility. This is a new security contract and needs explicit approval before schema or write paths are introduced.

After that decision, implement only a minimal read-only capability endpoint and its server-side guard; keep all admin endpoints default-deny, reject forged client roles, and test allow/deny/revocation with isolated PostgreSQL 16 accounts and unchanged financial ledger. Do not add tariff, secret, or financial mutation APIs in AD-01.

## Downstream ordering from historical register

- **AD-02** depends on AD-01 and MC-01; its preview/version/CAS/confirm/audit/rollback mutation must wait for an approved admin authority and contract.
- **AD-03** depends on AD-02 and OB-02; admin screens should wait until both guarded read/write capabilities and their operational data contracts exist. PR #100 remains a historical diagnostic, not AD-01 implementation.
- **SL-02** depends on AD-01; the support operator query/reply/status path needs a trusted operator role and IDOR/revocation checks. User-side help text exists, ticket lifecycle does not.
- **SL-03** depends on SL-01, SL-02, and MA-01; shared two-client ticket/profile/legal history follows the ticket lifecycle and Mini App contract. Do not build a second account store.

The safe execution order is contract decision → AD-01 → AD-02 (alongside MC-01) → AD-03 (after OB-02); SL-02 can proceed only after AD-01 and SL-03 after SL-01/SL-02/MA-01. No downstream implementation is included here.

## Verification limits

This package is based on exact-main source/document inspection and the canonical historical task/completion registers. No new application code was changed and no PostgreSQL, Chromium, or Telegram Admin Edition suite was run on this preflight. The source PR #100 evidence is tied to its own historical base. A future AD-01 implementation requires the owner decision above, dedicated PostgreSQL 16 regression, direct unauthorized-route/forged-role cases, revocation across the approved serving topology, ledger invariance, and `tests/test_admin_access.py` regression.
