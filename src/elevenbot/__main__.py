import argparse,asyncio,json,os,sys
from .config import Config
from .db import connect,migrate
from .core import Service,uid,Rejected

async def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['migrate','bot','worker','health','metrics','reconcile','release-uncertain','reconcile-stars','platega-webhook','catalog-refresh','anymodel-catalog-refresh','doctor','speech-pilot-credit','voice-candidates'])
    p.add_argument('--component',default='worker');p.add_argument('--job');p.add_argument('--reason');p.add_argument('--telegram-id',type=int);p.add_argument('--credits',type=int,default=300)
    p.add_argument('--env-file',help='Explicit UTF-8 KEY=value file; exported environment takes priority')
    a=p.parse_args();cfg=Config.env(a.env_file)
    if a.command=='anymodel-catalog-refresh':
        from .anymodel import refresh_anymodel
        if not cfg.anymodel_test_enabled:
            raise ValueError('AnyModel pilot disabled')
        data=await refresh_anymodel(cfg,once=True)
        print(json.dumps({'models':len(data['models']),'scope':data['sources'][0]['scope'],
                          'refresh_error':data.get('refresh_error'),
                          'refresh_error_code':data.get('refresh_error_code'),
                          'refresh_error_endpoint':data.get('refresh_error_endpoint'),
                          'version':data['version']},ensure_ascii=False))
        return
    if a.command=='catalog-refresh':
        from .aggregate import refresh_aggregate
        data=await refresh_aggregate(cfg,once=True)
        print(json.dumps({'brand':cfg.brand,'models':len(data['models']),'functions':len(data.get('functions',[])),
                          'sources':data.get('sources',[]),'version':data['version']},ensure_ascii=False))
        return
    if a.command=='voice-candidates':
        from .providers import voice_candidates
        print(json.dumps(await voice_candidates(cfg.clodex_key),ensure_ascii=False))
        return
    pool=await connect((cfg.migration_dsn or cfg.dsn) if a.command=="migrate" else cfg.dsn)
    try:
        if a.command=='doctor':
            import hashlib,shutil
            from pathlib import Path
            async with pool.acquire() as c:
                version=await c.fetchval('SHOW server_version')
                applied={r['version']:r['sha256'] for r in await c.fetch('SELECT version,sha256 FROM schema_migrations')}
            files=list((Path(__file__).resolve().parents[2]/'migrations').glob('*.sql'))
            if not files:raise RuntimeError('Migration files unavailable')
            missing=[p.name for p in files if applied.get(p.name)!=hashlib.sha256(p.read_bytes()).hexdigest()]
            print(json.dumps({'database':'connected','postgres_version':version,'migration_mismatches':missing,
                'token_configured':bool(cfg.token),'access_mode':cfg.access_mode,'owners_configured':len(cfg.admin_ids),
                'mode':cfg.mode,'generation_enabled':cfg.generation_enabled,'payments_enabled':cfg.payments_enabled,
                'ffprobe_available':bool(shutil.which('ffprobe')),'configuration_source':'file' if a.env_file else 'environment'}))
            if missing or not cfg.token:raise RuntimeError('Migrations/token required')
            return
        if a.command=='migrate':await migrate(pool);print('migrations applied');return
        if a.command=='health':
            async with pool.acquire() as c:
                ok=await c.fetchval("SELECT EXISTS(SELECT 1 FROM heartbeat WHERE component=$1 AND seen_at>now()-interval '240 seconds')",a.component)
            if not ok:raise RuntimeError('stale heartbeat')
            print('healthy');return
        if a.command=='speech-pilot-credit':
            applied=await Service(pool,cfg).grant_speech_pilot_credit(a.telegram_id,a.credits)
            print('Pilot credits granted' if applied else 'Pilot credits already granted')
            return
        if a.command=='reconcile':
            print(json.dumps({'wallet_mismatches':await Service(pool,cfg).reconcile()}));return
        if a.command=='metrics':
            async with pool.acquire() as c:
                rows=await c.fetch('SELECT status,count(*) n FROM jobs GROUP BY status')
                wallets=await c.fetch('SELECT mode,sum(available) available,sum(reserved) reserved FROM wallets GROUP BY mode')
            print(json.dumps({'jobs':{r['status']:r['n'] for r in rows},'wallets':[dict(x) for x in wallets]},default=str));return
        if a.command=='release-uncertain':
            if not a.job or not a.reason:raise ValueError('--job and --reason required; operator accepts possible provider cost')
            await Service(pool,cfg).settle(uid(a.job),'release',operator_release=True)
            print('reserve released; provider cost may remain');return
        from .providers import MockProvider,ClodexProvider,DisabledProvider
        from .worker import Worker
        from .telegram import poll,reconcile_stars,make_bot,buttons
        if a.command=='platega-webhook':
            from .platega_web import serve
            await serve(pool,cfg);return
        if a.command=='reconcile-stars':
            if not cfg.token:raise ValueError('TELEGRAM_BOT_TOKEN required')
            async with make_bot(cfg) as bot:print(json.dumps(await reconcile_stars(pool,bot)))
            return
        if a.command=='bot':
            if not cfg.token:raise ValueError('TELEGRAM_BOT_TOKEN required')
            async with make_bot(cfg) as bot:
                tasks=[]
                if cfg.catalogue_enabled:
                    from .discovery import refresh_loop
                    tasks.append(asyncio.create_task(refresh_loop(cfg)))
                if cfg.anymodel_test_enabled:
                    from .anymodel import refresh_anymodel
                    tasks.append(asyncio.create_task(refresh_anymodel(cfg)))
                    if cfg.anymodel_key:
                        from .anymodel_image_jobs import AnyModelImageJobs
                        tasks.append(asyncio.create_task(AnyModelImageJobs(pool,cfg).loop(bot)))
                        from .anymodel_video import AnyModelVideoPilot
                        tasks.append(asyncio.create_task(AnyModelVideoPilot(pool,cfg).loop(bot)))
                if cfg.video_pilot:
                    from .video import VideoPilot
                    tasks.append(asyncio.create_task(VideoPilot(pool,cfg).loop(bot)))
                from .progress import TaskProgress
                tasks.append(asyncio.create_task(TaskProgress(bot,pool).loop()))
                if cfg.clodex_music_owner:
                    from .clodex_music import MusicPilot
                    tasks.append(asyncio.create_task(MusicPilot(pool,cfg).loop(bot)))
                if cfg.fal_key and cfg.fal_music_owner:
                    from .fal import FalMusicPilot
                    tasks.append(asyncio.create_task(FalMusicPilot(pool,cfg).loop(bot)))
                from .broadcasts import Broadcasts,BroadcastWorker
                tasks.append(asyncio.create_task(BroadcastWorker(Broadcasts(pool),bot,buttons).loop()))
                try:await poll(pool,cfg,bot)
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks,return_exceptions=True)
        else:
            provider=MockProvider() if cfg.mode=='mock' else DisabledProvider() if cfg.mode=='catalogue' else ClodexProvider(cfg)
            try:
                await Worker(pool,cfg,provider).loop()
            finally:
                if hasattr(provider,'close'):await provider.close()
    finally:await pool.close()

if __name__=='__main__':
    try:asyncio.run(main())
    except KeyboardInterrupt:pass
    except Exception as e:
        # Never expose DB DSN, credentials or provider response contents in default logs.
        print(json.dumps({'event':'process_stopped','error_type':type(e).__name__}),file=sys.stderr)
        sys.exit(1)
