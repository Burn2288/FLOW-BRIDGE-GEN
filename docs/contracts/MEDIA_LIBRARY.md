# C-016/C-017 — Media storage and user library
Status: DESIGN_DRAFT.

## Ownership and records
MediaAsset: asset_id, owner_id, source_job_id, kind (IMAGE/VIDEO/VOICE/MUSIC), MIME, size_bytes, checksum_sha256, storage_key, created_at, retention_until, validation_status, encryption/access policy, metadata (dimensions/duration). LibraryItem: item_id, user_id, job_id, asset_id, prompt_preview_sanitized, model_snapshot, actual_charged_minor/currency, created_at, visibility, status. Storage key is opaque, not a public filesystem path.
A paid job is complete only when its output is validated, durably stored and linked to owner; a Telegram message may be delivered later. Output may have multiple assets; track each atomically or by an explicit partial-success policy.

## Types
IMAGE: dimensions, image format, pixel limits; VIDEO: duration, codec/container, safe transcoding; VOICE: language, speaker, duration/codec; MUSIC: title/lyrics if applicable, duration, audio formats and usage rights/copyright-related provider restrictions. User-supplied reference media stored separately with explicit retention/privacy policy; never overwrite paid outputs.
Validate actual bytes, not only extension/Content-Type; strict allowed MIME, size, pixel/frame/bomb limits, malware scanning appropriate to runtime, safe temporary files, no path traversal or unsafe deserialization. URL result downloads use allowlisted DNS/IP, bound redirects and timeouts, streaming size cap and secure temp storage.

## Library API / bot
List by kind, page/cursor, filter, stable created_at+id sort; Telegram exactly ≤5 per page in user flow. Item label is sanitized truncated prompt + FINAL charged price, e.g. «Закат над морем… | 49 ₽»; never derived from current catalog price. Detail includes model/provider, timestamps, file preview, download and repeat-send. Mini App may use richer cards but same record, authorization and access policy.
Access to any item is resolved from authenticated user identity, never from route ID alone. Signed URLs bound to owner and short TTL; no indefinitely public media bucket URLs. Re-send is authorized, delivery outbox, **never another generation charge**. «Создать похожее» explicitly opens new quote and new charge flow.

## Storage lifecycle
TEMP_WRITTEN → VALIDATED → PERSISTED → LINKED → AVAILABLE; failures recorded with retry/recovery, orphan cleanup only after safe check. Paid media retention period is a product policy to approve; users must see the period before payment and in agreement. Never silently delete purchased content while advertised retention is valid. Backup and restore includes media bytes + DB ownership metadata and checksum; validate after restore.

## Tests
Duplicate result, missing file, checksum drift, delayed asset, media type mismatch, invalid redirect, oversized media, no disk, cache poisoning, cross-user IDOR, restart, repeat-send without provider call, deletion/legal hold, downloaded URL expiry and expired retention.
