"""Conservative delivery receipts; never infer non-acceptance from a timeout."""
from uuid import uuid4


async def claim_delivery(conn, kind, job, user):
    claim=uuid4()
    await conn.execute("""
        INSERT INTO task_media_delivery(kind,job_id,user_id,claim_id,outcome)
        VALUES($1,$2,$3,$4,'unknown')
        ON CONFLICT(kind,job_id) DO UPDATE SET claim_id=EXCLUDED.claim_id,
            outcome='unknown',message_id=NULL,error_code=NULL,updated_at=now()
        """,kind,str(job),user,claim)
    return claim


async def finish_delivery(pool,kind,job,claim,outcome,*,message=None,error=None):
    await pool.execute("""
        UPDATE task_media_delivery SET outcome=$5,message_id=$6,error_code=$7,updated_at=now()
        WHERE kind=$1 AND job_id=$2 AND claim_id=$3 AND outcome=$4
        """,kind,str(job),claim,'unknown',outcome,getattr(message,'message_id',None),
        type(error).__name__ if error is not None else None)
