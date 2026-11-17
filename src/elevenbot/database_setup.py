"""Provision only a NEW local PostgreSQL database; never modify an existing one.
PostgreSQL must already be installed/running. Secrets never enter argv/reports.
"""
import argparse,asyncio,getpass,json,os,re,secrets,uuid
from pathlib import Path
from urllib.parse import quote
import asyncpg
from .db import migrate

class ProvisionError(Exception):pass

def identifier(name):
    if not isinstance(name,str) or not re.fullmatch(r'darkflow_[a-z0-9_]{1,40}',name):raise ProvisionError('Use a new darkflow_ database name')
    return '"'+name+'"'

def connection_url(host,port,user,password,database):
    if host not in ('127.0.0.1','localhost','::1') or not 1<=port<=65535:raise ProvisionError('Only local PostgreSQL allowed')
    host='['+host+']' if ':' in host else host
    return f'postgresql://{quote(user,safe="")}:{quote(password,safe="")}@{host}:{port}/{quote(database,safe="")}'

def private_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())

async def provision(host,port,admin_user,admin_password,database,folder):
    identifier(database)
    folder=Path(folder).resolve();credentials=folder/'database.credentials.json';report=folder/'database-result.json'
    if any((folder/name).exists() for name in ('database.credentials.json','database-result.json','database.env','migration.env')):raise ProvisionError('Existing provisioning files; nothing was changed')
    suffix=uuid.uuid4().hex[:12];owner='darkflow_owner_'+suffix;runtime='darkflow_app_'+suffix
    owner_password=secrets.token_hex(32);runtime_password=secrets.token_hex(32)
    owner_dsn=connection_url(host,port,owner,owner_password,database);runtime_dsn=connection_url(host,port,runtime,runtime_password,database)
    admin=await asyncpg.connect(connection_url(host,port,admin_user,admin_password,'postgres'),timeout=10)
    state={'database':database,'status':'NOT_CREATED','migration_status':'NOT_RUN','runtime_probe':'NOT_RUN'}
    try:
        major=int(await admin.fetchval('SHOW server_version_num'))//10000
        if major!=16:raise ProvisionError('This bootstrap targets PostgreSQL 16')
        if not await admin.fetchval('SELECT rolsuper FROM pg_roles WHERE rolname=current_user'):raise ProvisionError('Local database administrator required for provisioning')
        if await admin.fetchval('SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=$1)',database):raise ProvisionError('Database already exists; nothing was changed')
        # Save generated credentials before mutation, so partial failures can be investigated.
        # Never overwrite; this file is PRIVATE and must not be uploaded with reports.
        private_json(credentials,{'schema':1,'database':database,'DATABASE_URL':runtime_dsn,'DATABASE_MIGRATION_URL':owner_dsn})
        async with admin.transaction():
            await admin.execute("SET LOCAL password_encryption='scram-sha-256'")
            await admin.execute(f"CREATE ROLE {identifier(owner)} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '{owner_password}'")
            await admin.execute(f"CREATE ROLE {identifier(runtime)} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '{runtime_password}'")
        # PostgreSQL disallows CREATE DATABASE inside a transaction block.
        await admin.execute(f'CREATE DATABASE {identifier(database)} OWNER {identifier(owner)} TEMPLATE template0 ENCODING \'UTF8\'')
        state['status']='CREATED'
        await admin.execute(f'REVOKE ALL ON DATABASE {identifier(database)} FROM PUBLIC')
        await admin.execute(f'GRANT CONNECT ON DATABASE {identifier(database)} TO {identifier(owner)}, {identifier(runtime)}')
        owner_pool=await asyncpg.create_pool(owner_dsn,min_size=1,max_size=2)
        try:
            async with owner_pool.acquire() as c:
                await c.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
                await c.execute(f'GRANT USAGE ON SCHEMA public TO {identifier(runtime)}')
                await c.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO {identifier(runtime)}')
                await c.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO {identifier(runtime)}')
            await migrate(owner_pool);state['migration_status']='APPLIED'
        finally:await owner_pool.close()
        connection=await asyncpg.connect(runtime_dsn)
        try:
            async with connection.transaction():
                await connection.execute("INSERT INTO heartbeat(component,seen_at) VALUES('db_setup_probe',now())")
                assert await connection.fetchval("SELECT count(*) FROM heartbeat WHERE component='db_setup_probe'")==1
                await connection.execute("DELETE FROM heartbeat WHERE component='db_setup_probe'")
            assert not await connection.fetchval('SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname=current_user')
            try:await connection.execute('CREATE TABLE public.forbidden_probe(id int)')
            except asyncpg.InsufficientPrivilegeError:pass
            else:raise ProvisionError('Runtime role has unexpected DDL privileges')
            state['runtime_probe']='PASS';state['status']='READY'
        finally:await connection.close()
        # Write separate files; owner credentials are never loaded by bot/worker.
        for name,dsn in [('database.env',runtime_dsn),('migration.env',owner_dsn)]:
            path=folder/name
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w',encoding='utf-8') as f:f.write('DATABASE_URL='+dsn+'\n');f.flush();os.fsync(f.fileno())
        return state
    except Exception:
        state['status']='PARTIAL_REVIEW' if credentials.exists() else 'BLOCKED'
        raise
    finally:
        await admin.close()
        if credentials.exists():
            try:private_json(report,state)
            except FileExistsError:pass

def main():
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=5432);p.add_argument('--user',default='postgres');p.add_argument('--database',default='darkflow_service');p.add_argument('--folder',default='private-db');a=p.parse_args()
    try:
        password=getpass.getpass('LOCAL PostgreSQL administrator password (hidden, not saved): ')
        result=asyncio.run(provision(a.host,a.port,a.user,password,a.database,a.folder))
        print(json.dumps(result));print('Database configuration saved in the selected private folder. Keep credentials private; share only database-result.json.')
    except (Exception,KeyboardInterrupt) as e:
        print(json.dumps({'status':'BLOCKED_OR_FAILED','error_type':type(e).__name__,'details':'Secret values hidden. Check server availability and private-db/database-result.json if created. No existing database was intentionally changed.'}));raise SystemExit(1)

if __name__=='__main__':main()
