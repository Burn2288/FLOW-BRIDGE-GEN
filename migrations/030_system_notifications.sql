ALTER TABLE identities DROP COLUMN broadcast_opt_out;

-- Keep prior delivery totals and record skipped deliveries as stopped.
WITH skipped AS (
    UPDATE telegram_broadcast_deliveries SET status='stopped'
    WHERE status='opted_out' RETURNING broadcast_id
)
UPDATE telegram_broadcasts SET changed_at=clock_timestamp()
WHERE id IN (SELECT broadcast_id FROM skipped);

ALTER TABLE telegram_broadcast_deliveries
    DROP CONSTRAINT telegram_broadcast_deliveries_status_check,
    ADD CHECK (status IN ('pending','sending','sent','unavailable','error','unknown','stopped'));

-- Older users may have accepted the terms before a welcome message was stored.
WITH private_chats AS (
    SELECT payload#>>'{message,chat,id}' AS chat_id
    FROM inbox WHERE done AND payload#>>'{message,chat,type}'='private'
      AND payload#>>'{message,chat,id}'=payload#>>'{message,from,id}'
    UNION
    SELECT payload#>>'{callback_query,message,chat,id}' AS chat_id
    FROM inbox WHERE done AND payload#>>'{callback_query,message,chat,type}'='private'
      AND payload#>>'{callback_query,message,chat,id}'=payload#>>'{callback_query,from,id}'
)
UPDATE identities i SET telegram_private=true
FROM private_chats c WHERE i.platform='telegram' AND NOT i.telegram_private
  AND i.terms_version='1' AND i.accepted_at IS NOT NULL AND i.external_id::text=c.chat_id;
