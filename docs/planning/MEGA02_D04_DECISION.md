# MEGA-02 D-04 decision record

Status: **OPTION_B APPROVED_FUNCTIONAL_TEST_ONLY**. Owner approval: Burn2288, OWNER DECISION — D-04 / ADMIN AUTHORITY v1, in the project conversation.

Source: [AD-01 preflight #107](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/107) and [revocation ADR](../testing/ADMISSION_REVOCATION_ADR.md). Historical [#100](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/100) cannot authorize a new HTTP role model.

| Criterion | A · Fenced rollout | B · PostgreSQL authority |
| --- | --- | --- |
| Authority | Approved deployment revision and durable fencing barrier | Current policy revision on the primary database |
| Revocation | Effective only after all old readers are fenced and the barrier commits | Effective for new requests after the authoritative change commits |
| Interrupted rollout or authority outage | Keep blocked until the coordinator can establish the barrier | Deny protected requests if the authority cannot be checked |
| Required infrastructure | Complete inventory of serving processes, control of direct ingress, restart fencing | Trusted bootstrap, role records, immutable revision audit, isolated writer |
| LEVEL 1 proof | Tests must prove stale processes cannot continue serving | Two app instances, revoke and stale session tests, forged role and direct access denial |

Historical recommendation adopted by the owner: B for the isolated LEVEL 1 prototype. Reuse verified identity and persistent sessions, default deny, check capability on each protected request. Limit the first candidate to a read-only capability and a chooser. Treat environment allowlists as existing pilot admission, not as HTTP roles. Preserve Telegram Admin Edition independently.

D-04 v1 establishes role names, scope, revocation and outage semantics. A deployment-specific bootstrap identity and isolated principal configuration are still required. Option A additionally needs an enforceable all-instance fencing design. The Draft now includes the capability-protected aggregate endpoint. Deliberate role delegation uses a trusted database operation. AD-02 requires selection of a concrete typed setting; SL-02 operator routes remain unimplemented.

## Approved scope and implementation progress

The owner approved PostgreSQL authority with four role names, append-only role audit and server-side revocation. The capability read and isolated bootstrap are implemented. No specific bootstrap identity has been assigned. Operator ticket operations, the preview/CAS/rollback visibility setting, chooser UI and trusted role-management workflow remain open. Existing Telegram admission is independent.
