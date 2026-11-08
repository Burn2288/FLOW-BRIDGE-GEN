"""Reserve the live wallet before dispatch and settle from durable outcomes."""

from .core import Rejected


async def check_task_balance(conn, user, amount):
    available = await conn.fetchval("""
        SELECT available FROM wallets WHERE user_id=$1 AND mode='live' FOR UPDATE
        """, user)
    if not available or available < amount:
        raise Rejected('Недостаточно токенов')


async def reserve_task_tokens(conn, user, quote_id, amount):
    if amount:
        await conn.execute("""
            INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,task_quote_id)
            VALUES(gen_random_uuid(),$1,'live','task-reserve:'||$2::uuid,'task_reserve',-$3::bigint,$3,$2)
            """, user, quote_id, amount)


async def settle_task_tokens(conn, quote_id=None):
    # Completed work is charged even when Telegram delivery has to be retried.
    # Ambiguous provider outcomes retain their hold for reconciliation.
    await conn.execute("""
        WITH terminal AS (
            SELECT r.user_id,r.task_quote_id,r.dr AS amount,
                CASE
                    WHEN d.state='completed' OR v.status='succeeded' OR i.status IN ('ready','delivered')
                        THEN 'task_capture'
                    WHEN d.state IN ('interrupted','rejected') OR v.status='failed' OR i.status='failed'
                        THEN 'task_release'
                END AS kind
            FROM ledger r
            JOIN task_dispatch d ON d.quote_id=r.task_quote_id
            JOIN task_price_quotes q ON q.id=d.quote_id
            LEFT JOIN video_jobs v ON v.id=d.quote_id
            LEFT JOIN anymodel_image_jobs i ON i.update_id=q.update_id AND i.user_id=q.user_id
            WHERE r.kind='task_reserve'
              AND ($1::uuid IS NULL OR d.quote_id=$1)
              AND d.state IN ('completed','delegated','interrupted','uncertain','rejected')
              AND NOT EXISTS (
                  SELECT 1 FROM ledger s WHERE s.task_quote_id=r.task_quote_id
                      AND s.kind IN ('task_capture','task_release')
              )
        )
        INSERT INTO ledger(id,user_id,mode,event_key,kind,da,dr,task_quote_id)
        SELECT gen_random_uuid(),user_id,'live','task-settlement:'||task_quote_id,kind,
            CASE WHEN kind='task_release' THEN amount ELSE 0 END,-amount,task_quote_id
        FROM terminal WHERE kind IS NOT NULL ORDER BY user_id,task_quote_id
        ON CONFLICT (event_key) DO NOTHING
        """, quote_id)
