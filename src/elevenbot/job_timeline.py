"""Owned generation timeline derived from existing rows, without event storage."""
from uuid import UUID

from .core import Rejected

# Only fixed messages are returned to clients; provider errors never leave the server.
LABELS = {
    'queued': 'В очереди', 'dispatching': 'Выполняется', 'succeeded': 'Готово',
    'failed': 'Не удалось выполнить задачу.', 'cancelled': 'Отменено',
    'uncertain': 'Результат требует проверки.',
}


def canonical(status):
    return {'submitting': 'dispatching', 'polling': 'dispatching',
            'pending': 'queued', 'interrupted': 'failed', 'rejected': 'failed',
            'completed': 'succeeded', 'delegated': 'dispatching'}.get(status, status if status in LABELS else 'uncertain')


def summarize(row):
    status = canonical(row['status'])
    created_label = 'Результат сохранён' if row['saved_only'] else 'Задание создано'
    events = [{'label': created_label, 'at': row['created_at'].isoformat() if row['created_at'] else None}]
    events.append({'label': LABELS[status], 'at': row['completed_at'].isoformat() if row['completed_at'] else None})
    return {'id': str(row['id']), 'kind': row['kind'], 'model': row['model_id'],
            'status': status, 'events': events,
            'error': LABELS[status] if status in ('failed', 'uncertain') else None}


async def get_timeline(pool, service, user_id, kind, raw_id):
    try:
        job_id = UUID(str(raw_id))
    except (ValueError, TypeError, AttributeError):
        raise Rejected('Работа не найдена.') from None
    if kind not in ('image', 'audio', 'video', 'chat'):
        raise Rejected('Работа не найдена.')
    async with pool.acquire() as conn:
        await service.authorize(conn, user_id)
        row = None
        if kind == 'audio':
            row = await conn.fetchrow("""
                SELECT id, 'audio' AS kind, model_id, status, created_at, completed_at, false AS saved_only
                FROM jobs WHERE id=$1 AND user_id=$2
            """, job_id, user_id)
            if not row:
                row = await conn.fetchrow("""
                    SELECT id, 'audio' AS kind, model_id, 'succeeded' AS status,
                           created_at, NULL::timestamptz AS completed_at, true AS saved_only
                    FROM task_speech_works WHERE id=$1 AND user_id=$2 AND audio IS NOT NULL AND expires_at>now()
                """, job_id, user_id)
        elif kind == 'image':
            row = await conn.fetchrow("""
                SELECT id, 'image' AS kind, model_id, 'succeeded' AS status,
                       created_at, NULL::timestamptz AS completed_at, true AS saved_only
                FROM image_works WHERE id=$1 AND user_id=$2 AND expires_at>now()
            """, job_id, user_id)
        elif kind == 'video':
            row = await conn.fetchrow("""
                SELECT id, 'video' AS kind, model_id, status, created_at,
                       NULL::timestamptz AS completed_at, false AS saved_only
                FROM video_jobs WHERE id=$1 AND user_id=$2
            """, job_id, user_id)
        elif kind == 'chat':
            row = await conn.fetchrow("""
                SELECT q.id, 'chat' AS kind, q.model_id, 'succeeded' AS status,
                       w.created_at, NULL::timestamptz AS completed_at, true AS saved_only
                FROM task_chat_works w JOIN task_price_quotes q ON q.id=w.quote_id
                WHERE q.id=$1 AND q.user_id=$2 AND w.expires_at>now()
            """, job_id, user_id)
        if not row and kind in ('chat', 'audio'):
            operation = 'chat' if kind == 'chat' else 'audio.speech'
            row = await conn.fetchrow("""
                SELECT q.id, $4::text AS kind, q.model_id, d.state AS status,
                       q.accepted_at AS created_at, NULL::timestamptz AS completed_at, false AS saved_only
                FROM task_dispatch d JOIN task_price_quotes q ON q.id=d.quote_id
                WHERE q.id=$1 AND q.user_id=$2 AND q.operation=$3 AND q.accepted_at IS NOT NULL
            """, job_id, user_id, operation, kind)
        if not row:
            raise Rejected('Работа не найдена.')
        return summarize(row)
