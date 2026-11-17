import asyncio,uuid,json,time,subprocess
from datetime import datetime,timezone
from .core import Service
from .providers import UnknownOutcome,DefinitiveFailure
from .storage import Storage
from .interaction import provider_request_id, trace_interaction

class Worker:
    def __init__(self,pool,cfg,provider,sender=None):
        self.pool,self.cfg,self.provider,self.sender=pool,cfg,provider,sender
        self.svc=Service(pool,cfg);self.storage=Storage(cfg.storage)
        self.recovery_cursor = None
    async def claim(self):
        if not self.cfg.generation_enabled:return None
        async with self.pool.acquire() as c,c.transaction():
            await c.execute('SELECT pg_advisory_xact_lock(921182)')
            if await c.fetchval('SELECT halted FROM settings WHERE id=1'):return None
            n=await c.fetchval("SELECT count(*) FROM jobs WHERE status='dispatching'")
            if n>=self.cfg.concurrency:return None
            r=await c.fetchrow("SELECT j.*,q.text_content,q.voice,q.speed FROM jobs j JOIN quotes q ON q.id=j.quote_id WHERE j.status='queued' AND j.mode=$1 ORDER BY j.created_at FOR UPDATE OF j SKIP LOCKED LIMIT 1",self.cfg.wallet_mode)
            if not r:return None
            fence=uuid.uuid4()
            model_id=self.cfg.clodex_model if r['mode']=='live' else 'demo'
            await c.execute("UPDATE jobs SET status='dispatching',fence=$2,lease_until=now()+interval '180 seconds',model_id=$3 WHERE id=$1",r['id'],fence,model_id)
            return dict(r)|{'fence':fence}
    async def uncertain(self,j,fence,code):
        async with self.pool.acquire() as c:
            await c.execute("UPDATE jobs SET status='uncertain',error_code=$3,lease_until=NULL WHERE id=$1 AND fence=$2 AND status='dispatching'",j,fence,code)
    async def run_one(self,fault=None):
        r=await self.claim()
        if not r:return False
        j,f=r['id'],r['fence']
        request_id=str(j)
        trace_interaction(request_id,'worker_started',operation='audio.speech',
                          model=self.cfg.clodex_model if r['mode']=='live' else 'demo',mode=r['mode'])
        stage='provider'
        if fault=='before_http':return True  # simulate process death, recover after lease
        try:
            token=provider_request_id.set(request_id)
            try:
                async with asyncio.timeout(150):
                    data=await self.provider.synthesize(r['text_content'],r['voice'],float(r['speed']))
            finally:
                provider_request_id.reset(token)
            trace_interaction(request_id,'audio_received',bytes=len(data))
            stage='provider_metadata'
            metadata=getattr(self.provider,'metadata',{})
            async with self.pool.acquire() as c:
                await c.execute("UPDATE jobs SET provider_request_id=$3,provider_usage_characters=$4 WHERE id=$1 AND fence=$2 AND status='dispatching'",j,f,metadata.get('request_id'),metadata.get('usage_characters'))
                if metadata.get('usage_characters') is not None and metadata['usage_characters']>len(r['text_content']):
                    await c.execute('UPDATE settings SET halted=true WHERE id=1')
            if fault in ('after_http','after_response'):return True
            stage='storage'
            artifact=await asyncio.to_thread(self.storage.save,j,f,data)
            trace_interaction(request_id,'audio_saved')
            if fault in ('after_file','before_commit'):return True
            stage='settlement'
            ok=await self.svc.settle(j,'capture',f,artifact)
            trace_interaction(request_id,'work_completed' if ok else 'work_uncertain')
            if not ok:await self.uncertain(j,f,'STALE_EXECUTOR')
            if fault=='after_commit':return True
        except DefinitiveFailure as error:
            trace_interaction(request_id,'generation_failed',failed_at=stage,error_type=type(error).__name__)
            await self.svc.settle(j,'release',f)
        except (UnknownOutcome,ValueError,TimeoutError,OSError,subprocess.SubprocessError) as error:
            trace_interaction(request_id,'work_uncertain',failed_at=stage,error_type=type(error).__name__)
            await self.uncertain(j,f,'RESULT_UNKNOWN')
            if self.cfg.mode=='clodex':
                async with self.pool.acquire() as c:await c.execute('UPDATE settings SET halted=true WHERE id=1')
        except Exception as error:
            trace_interaction(request_id,'worker_failed',failed_at=stage,error_type=type(error).__name__)
            raise
        # DB failures propagate to supervisor; persisted dispatching is never requeued.
        return True
    async def recover(self):
        async with self.pool.acquire() as c:
            await c.execute("UPDATE jobs SET status='uncertain',error_code='LEASE_EXPIRED',lease_until=NULL WHERE status='dispatching' AND lease_until<now()")
            await c.execute("UPDATE deliveries SET status='uncertain',lease_until=NULL WHERE status='sending' AND lease_until<now()")
    async def reconcile_saved(self):
        # A valid private artifact with the exact persisted job/fence is evidence of a
        # completed response. Never call provider during reconciliation.
        async with self.pool.acquire() as c:
            rows=await c.fetch(
                "SELECT id,fence FROM jobs WHERE status='uncertain' AND fence IS NOT NULL "
                "AND ($1::uuid IS NULL OR id>$1) ORDER BY id LIMIT 100", self.recovery_cursor)
        self.recovery_cursor = rows[-1]['id'] if len(rows) == 100 else None
        for r in rows:
            key=f"{r['id']}_{r['fence']}.mp3"
            path=self.storage.path(key)
            if path.is_file():
                try:
                    data=await asyncio.to_thread(path.read_bytes)
                    artifact=await asyncio.to_thread(self.storage.save,r['id'],r['fence'],data)
                    await self.svc.settle(r['id'],'capture',storage=artifact)
                except (ValueError,OSError,subprocess.SubprocessError):
                    pass  # Keep uncertainty; never re-generate or discard evidence.

    async def delivery_one(self):
        if not self.sender:return False
        async with self.pool.acquire() as c,c.transaction():
            r=await c.fetchrow("""SELECT d.*,f.storage_key,f.expires_at,f.deleted_at,i.external_id FROM deliveries d
                JOIN jobs j ON j.id=d.job_id JOIN files f ON f.job_id=j.id
                JOIN identities i ON i.user_id=j.user_id AND i.platform='telegram'
                WHERE d.status IN ('pending','retry') AND d.next_at<=now() ORDER BY d.next_at FOR UPDATE OF d SKIP LOCKED LIMIT 1""")
            if not r:return False
            if r['deleted_at'] or r['expires_at']<=datetime.now(timezone.utc) or r['attempts']>=8:
                await c.execute("UPDATE deliveries SET status='expired' WHERE job_id=$1",r['job_id']);return True
            f=uuid.uuid4()
            await c.execute("UPDATE deliveries SET status='sending',attempts=attempts+1,fence=$2,lease_until=now()+interval '180 seconds' WHERE job_id=$1",r['job_id'],f)
        try:
            async with asyncio.timeout(120):
                message_id=await self.sender.send_audio(r['external_id'],self.storage.path(r['storage_key']))
        except Exception:
            # Do not log exception object: SDK exception can include URL token/private data.
            async with self.pool.acquire() as c:
                await c.execute("UPDATE deliveries SET status='uncertain',lease_until=NULL WHERE job_id=$1 AND fence=$2 AND status='sending'",r['job_id'],f)
        else:
            async with self.pool.acquire() as c:
                await c.execute("UPDATE deliveries SET status='sent',platform_message_id=$3,lease_until=NULL WHERE job_id=$1 AND fence=$2 AND status='sending'",r['job_id'],f,message_id)
        return True
    async def cleanup(self):
        async with self.pool.acquire() as c,c.transaction():
            # Serialize deletion against explicit redelivery/claim using delivery row locks.
            rows=await c.fetch("SELECT f.* FROM files f JOIN deliveries d USING(job_id) WHERE f.expires_at<now() AND f.deleted_at IS NULL AND d.status<>'sending' FOR UPDATE OF f,d SKIP LOCKED")
            for r in rows:
                self.storage.path(r['storage_key']).unlink(missing_ok=True)
                await c.execute('UPDATE files SET deleted_at=now() WHERE job_id=$1',r['job_id'])
                await c.execute("UPDATE deliveries SET status='expired' WHERE job_id=$1",r['job_id'])
            await c.execute("UPDATE quotes SET text_content=NULL WHERE created_at<now()-interval '7 days' AND id NOT IN (SELECT quote_id FROM jobs WHERE status IN ('queued','dispatching','uncertain'))")
            known={r['storage_key'] for r in await c.fetch('SELECT storage_key FROM files')}
            active={str(r['id']) for r in await c.fetch("SELECT id FROM jobs WHERE status IN ('dispatching','uncertain')")}
            for path in self.storage.root.iterdir():
                if path.is_symlink() or not path.is_file():continue
                if path.name in known or path.name.split('_')[0] in active:continue
                if time.time()-path.stat().st_mtime>7*86400:path.unlink(missing_ok=True)
            await c.execute("UPDATE conversations SET aggregate_context=NULL,text_content=NULL,step='home' WHERE updated_at<now()-interval '1 day'")
            await c.execute("DELETE FROM image_works WHERE expires_at<=now()")
            await c.execute("DELETE FROM rate_limits WHERE minute<now()-interval '1 day'")
            await c.execute("DELETE FROM inbox WHERE done AND error_code IS NULL AND created_at<now()-interval '1 day'")
    async def _poll_work(self, operation):
        while True:
            await operation()
            await asyncio.sleep(1)

    async def _maintenance(self):
        last_cleanup = time.monotonic()
        while True:
            async with self.pool.acquire() as c:
                await c.execute("INSERT INTO heartbeat VALUES('worker',now()) ON CONFLICT(component) DO UPDATE SET seen_at=now()")
            await asyncio.sleep(15)
            await self.recover()
            await self.reconcile_saved()
            await self.svc.reconcile()
            if time.monotonic() - last_cleanup >= 300:
                await self.cleanup()
                last_cleanup = time.monotonic()

    async def loop(self):
        await self.recover()
        await self.reconcile_saved()
        await self.svc.reconcile()
        await self.cleanup()
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(self._poll_work(self.run_one))
            if self.sender:
                tasks.create_task(self._poll_work(self.delivery_one))
            tasks.create_task(self._maintenance())
