# MEGA-02 D-04 decision record

Status: **BLOCKED_PENDING_OWNER_DECISION**. AD-01 HTTP RBAC remains disabled. Owner approval reference: pending.

Source: [AD-01 preflight #107](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/107) and [revocation ADR](../testing/ADMISSION_REVOCATION_ADR.md). Historical [#100](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/100) cannot authorize a new HTTP role model.

| Criterion | A · Fenced rollout | B · PostgreSQL authority |
| --- | --- | --- |
| Authority | Approved deployment revision and durable fencing barrier | Current policy revision on the primary database |
| Revocation | Effective only after all old readers are fenced and the barrier commits | Effective for new requests after the authoritative change commits |
| Interrupted rollout or authority outage | Keep blocked until the coordinator can establish the barrier | Deny protected requests if the authority cannot be checked |
| Required infrastructure | Complete inventory of serving processes, control of direct ingress, restart fencing | Trusted bootstrap, role records, immutable revision audit, isolated writer |
| LEVEL 1 proof | Tests must prove stale processes cannot continue serving | Two app instances, revoke and stale session tests, forged role and direct access denial |

Proposal for owner decision: choose B for the isolated LEVEL 1 prototype. Reuse verified identity and persistent sessions, default deny, check capability on each protected request. Limit the first candidate to a read-only capability and a chooser. Treat environment allowlists as existing pilot admission, not as HTTP roles. Preserve Telegram Admin Edition independently.

Approval must specify bootstrap identity, role names and scope, revocation and outage semantics, env compatibility, audited policy writers and rollback. Option A additionally needs an enforceable all-instance fencing design. Until approved, expose operational aggregates only through the existing internal service and CLI. AD-02 live writes and SL-02 operator routes remain blocked.
