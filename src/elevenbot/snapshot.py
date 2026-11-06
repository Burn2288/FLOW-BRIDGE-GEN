"""Native private backup / isolated restore drill. Never switches the live database."""
import argparse,asyncio,getpass,hashlib,json,os,shutil,subprocess,uuid
from pathlib import Path
from urllib.parse import urlsplit,unquote
import asyncpg
from .runtime_config import parse_env_file
from .database_setup import identifier,connection_url

def pg_env(dsn,database=None):
    p=urlsplit(dsn)
    if p.hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('Local PostgreSQL required')
    env={k:v for k,v in os.environ.items() if not k.startswith('PG')}
    env.update(PGHOST=p.hostname,PGPORT=str(p.port or 5432),PGUSER=unquote(p.username or ''),PGPASSWORD=unquote(p.password or ''),PGDATABASE=database or p.path.lstrip('/'))
    return env

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def verify(directory):
    root=Path(directory).resolve()
    if (root/'manifest.json').is_symlink():raise ValueError('Backup manifest symlink forbidden')
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema')!=1 or not isinstance(manifest.get('files'),dict):raise ValueError('Invalid backup manifest')
    if 'database.dump' not in manifest['files']:raise ValueError('Backup dump missing')
    for name,sha in manifest['files'].items():
        path=root/name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file() or digest(path)!=sha:raise ValueError('Backup integrity failure')
    return manifest

def verify_database_audio(rows,audio):
    root=Path(audio).resolve()
    for row in rows:
        key=row['storage_key']
        if not isinstance(key,str) or '/' in key or '\\' in key or not key.endswith('.mp3'):raise ValueError('Invalid audio key')
        path=root/key
        if path.is_symlink() or not path.is_file() or digest(path)!=row['sha256']:raise ValueError('Referenced audio missing or corrupt')


async def backup(config,output):
    values=parse_env_file(config);root=Path(output).resolve();root.mkdir(mode=0o700,parents=True,exist_ok=False)
    audio=Path(values.get('AUDIO_STORAGE_DIR','data/audio'))
    if not audio.is_absolute():audio=Path(config).resolve().parent/audio
    connection=await asyncpg.connect(values['DATABASE_URL'],timeout=10)
    try:rows=await connection.fetch('SELECT storage_key,sha256 FROM files WHERE deleted_at IS NULL AND expires_at>now()')
    finally:await connection.close()
    verify_database_audio(rows,audio)
    dump=root/'database.dump'
    fd=os.open(dump,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:
        r=subprocess.run(['pg_dump','-Fc','--no-password'],env=pg_env(values['DATABASE_URL']),stdout=f,stderr=subprocess.PIPE,timeout=300)
        f.flush();os.fsync(f.fileno())
    if r.returncode:raise RuntimeError('Backup command failed; private partial directory retained')
    target=root/'audio';target.mkdir(mode=0o700)
    if audio.is_symlink():raise ValueError('Audio symlink forbidden')
    if audio.exists():
        for p in audio.iterdir():
            if p.is_symlink() or not p.is_file():raise ValueError('Unexpected audio entry')
            if p.suffix!='.mp3':continue
            dest=target/p.name;shutil.copyfile(p,dest);os.chmod(dest,0o600)
            with dest.open('rb') as f:os.fsync(f.fileno())
    files={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file()}
    fd=os.open(root/'manifest.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        json.dump({'schema':1,'files':files,'scope':'private database and audio; runtime configuration not included'},f,indent=2)
        f.flush();os.fsync(f.fileno())
    verify(root)
    if os.name!='nt':
        fd=os.open(root,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    return {'status':'BACKUP_CREATED','file_count':len(files),'requires_quiesced_services':True}

async def restore_drill(directory,migration_config,password,admin_user="postgres"):
    root=Path(directory).resolve();verify(root)
    values=parse_env_file(migration_config);owner=urlsplit(values['DATABASE_URL']);owner_name=unquote(owner.username or '');identifier(owner_name)
    name='darkflow_restore_'+uuid.uuid4().hex;identifier(name)
    admin_dsn=connection_url(owner.hostname,owner.port or 5432,admin_user,password,'postgres')
    admin=await asyncpg.connect(admin_dsn,timeout=10);created=False
    try:
        await admin.execute(f'CREATE DATABASE {identifier(name)} OWNER {identifier(owner_name)} TEMPLATE template0');created=True
        env=pg_env(admin_dsn,name)
        command=['pg_restore','--exit-on-error','--no-password','--clean','--if-exists','--no-owner','--role',owner_name,'-d',name,str(root/'database.dump')]
        p=await asyncio.create_subprocess_exec(*command,env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:_,_=await asyncio.wait_for(p.communicate(),300)
        except BaseException:
            p.kill();await p.communicate();raise
        if p.returncode:raise RuntimeError('Restore failed; live database unchanged')
        target=connection_url(owner.hostname,owner.port or 5432,owner_name,unquote(owner.password or ''),name)
        pool=await asyncpg.create_pool(target,min_size=1,max_size=2)
        try:
            from .db import migrate
            await migrate(pool)
            async with pool.acquire() as c,c.transaction():
                await c.execute('UPDATE settings SET halted=true WHERE id=1')
                await c.execute("UPDATE jobs SET status='uncertain',error_code='RESTORE_REVIEW',lease_until=NULL WHERE status IN ('queued','dispatching')")
                await c.execute("UPDATE payments SET status='review' WHERE status='pending'")
                await c.execute("UPDATE deliveries SET status='uncertain',lease_until=NULL WHERE status IN ('sending','retry')")
            from .core import Service
            from .config import Config
            if await Service(pool,Config()).reconcile():raise RuntimeError('Restored financial mismatch')
            rows=await pool.fetch('SELECT storage_key,sha256 FROM files WHERE deleted_at IS NULL AND expires_at>now()')
            verify_database_audio(rows,root/'audio')
        finally:await pool.close()
        return {'status':'RESTORE_DRILL_PASS','live_database_changed':False,'restored_copy_halted':True,'audio_hashes_verified':True,'scratch_database_removed':True}
    finally:
        try:
            if created:await admin.execute(f'DROP DATABASE {identifier(name)} WITH (FORCE)')
        finally:await admin.close()

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('backup');b.add_argument('--config',required=True);b.add_argument('--output',required=True)
    r=sub.add_parser('restore-drill');r.add_argument('--backup',required=True);r.add_argument('--migration-config',required=True);r.add_argument('--user',default='postgres')
    a=p.parse_args()
    try:
        if a.command=='backup':result=asyncio.run(backup(a.config,a.output))
        else:result=asyncio.run(restore_drill(a.backup,a.migration_config,getpass.getpass('Local postgres administrator password (hidden, not saved): '),a.user))
        print(json.dumps(result))
    except (Exception,KeyboardInterrupt) as e:
        print(json.dumps({'status':'FAILED_OR_BLOCKED','error_type':type(e).__name__,'secret_details_hidden':True}));raise SystemExit(1)

if __name__=='__main__':main()
