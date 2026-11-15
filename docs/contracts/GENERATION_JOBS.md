# C-012/C-018 — Generation, billing authorization, job and delivery lifecycle
Status: DESIGN_DRAFT, BASE_DIRECTIVE.

## Generation types
IMAGE (text-to-image, image-to-image by capability), VIDEO (text-to-video, image-to-video), SPEECH (text-to-speech/voice), MUSIC (prompt-to-music/song). Model capabilities define input fields and output formats, not Telegram hardcoding.

## Command CreateGeneration
Input: actor (from validated session), model_id + pinned model_version, kind/capability, prompt or secure source_asset_ids, requested parameters, quote_id, idempotency_key, client_channel.
Server checks: consent, model enabled, capability/options bounds, prompt length and content policy, source ownership, quote freshness and owner/currency, exact amount and wallet available funds, rate limits. Return stable job_id + current state (idempotent on same key+same semantic payload; conflicting duplicate → CONFLICT). Never accept client-supplied authoritative cost.

## Canonical job state
CREATED → QUEUED → CLAIMED → EXECUTING → [WAITING_PROVIDER] → OUTPUT_VALIDATING → PERSISTING → SUCCEEDED
Other terminal states FAILED, CANCELED; UNCERTAIN is nonterminal and requires reconciliation / operator intervention. Detailed state map may evolve only by versioned ADR.
- Each attempt: attempt_no, adapter_version, provider_job_id, network request metadata (safe redaction), started/finished timestamps, error taxonomy.
- Atomic claim (DB lock/CAS), lease expiration, fencing token; stale worker must not commit result or charge user. Heartbeat and bounded retries.
- Sync provider: bounded request + response, normalized to result. Async provider: obtain provider job ID; poll/webhook with authenticated match, no blind create replay.
- Unknown response after paid provider request: mark UNCERTAIN, preserve hold, reconcile by provider transaction/job ID and safety policy; do not auto-trigger new provider or try another one.
- Cancellation: legal only before certain stages or with provider-supported cancellation; if provider may have incurred costs, explicit billing policy applies. Cancellation request does not automatically guarantee refund.

## Quote and money lifecycle
Quote selects output amount/duration/tier, currency and rate; stable snapshot. Reserve exactly once when accepted; capture after confirmed policy-defined success and durable media, release on proven no-charge failure; refund via separate compensated transaction. Job success and ledger action must be consistently linked with unique business keys. A delivered Telegram message is not a prerequisite for preserving a valid paid output.

## Media and delivery
Validated provider bytes/URLs → media type + dimensions/duration/size/checksum → safe media storage → canonical LibraryItem linked to job/user → committed status/outbox notification. Delivery worker uses sendPhoto/sendDocument/sendVideo/sendAudio depending on type and Telegram limits; retry with backoff; retain results for re-download/re-send regardless of message loss. Delivery receipt means Telegram API accepted it; visual display to human is a separate evidence grade. Re-delivery never calls provider.

## Errors
VALIDATION_ERROR, CONSENT_REQUIRED, MODEL_DISABLED, QUOTE_EXPIRED, INSUFFICIENT_FUNDS, RATE_LIMITED, PROVIDER_UNAVAILABLE, PROVIDER_TIMEOUT, PROVIDER_UNCERTAIN, PROVIDER_BAD_RESPONSE, MEDIA_INVALID, MEDIA_STORE_ERROR, DELIVERY_FAILED, LEDGER_CONFLICT, ACCESS_DENIED. User-facing messages localizable and sanitized. Operator diagnostics trace by correlation ID.

## Acceptance scenarios
Three live successive image generations with actual file, library access after process restart, Telegram confirmed delivery, correct attribution, no double charge; one transient provider outage, delayed async response, corrupted image, storage failure, worker crash after reserve/before capture, duplicate Telegram callback, stale fencing token, unknown paid outcome, delivery outage, resend without new cost. Mock tests never prove provider live. Load tests 10/50/100 with emulator.
