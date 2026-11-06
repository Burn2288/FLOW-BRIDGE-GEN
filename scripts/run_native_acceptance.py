#!/usr/bin/env python3
"""Full real PostgreSQL acceptance without Docker. Requires a dedicated LOCAL dev server.
Creates only darkflow_accept_<uuid>, uses existing tests, rejects all SKIP/missing cases.
No real Telegram, Clodex generation or payment. Never loads service .env.
"""
import argparse,asyncio,getpass,hashlib,json,os,re,shutil,subprocess,sys,uuid,xml.etree.ElementTree as ET
from pathlib import Path
import asyncpg

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from elevenbot.database_setup import connection_url,identifier

def sanitize(value,secrets_to_hide=()):
    for secret in sorted((x for x in secrets_to_hide if x),key=len,reverse=True):value=value.replace(secret,'[REDACTED]')
    value=re.sub(r'postgres(?:ql)?://[^\s\'"<>]+','[REDACTED_DSN]',value)
    return re.sub(r'\b\d{8,12}:[A-Za-z0-9_-]{30,}\b','[REDACTED_TOKEN]',value)

def assess(xml_path,required,exit_code):
    tree=ET.parse(xml_path);cases=list(tree.iter('testcase'))
    observed={x.get('classname')+'#'+x.get('name') for x in cases}
    counts={'total':len(cases),'failures':sum(x.find('failure') is not None for x in cases),'errors':sum(x.find('error') is not None for x in cases),'skipped':sum(x.find('skipped') is not None for x in cases)}
    missing=sorted(set(required)-observed)
    return {'status':'PASS' if exit_code==0 and not missing and counts['total']>=len(required) and not any(counts[k] for k in ('failures','errors','skipped')) else 'FAIL','tests':counts,'missing':missing}

def tools_path():
    env=dict(os.environ)
    if os.name=='nt':
        candidate=Path(os.getenv('ProgramFiles','C:/Program Files'))/'PostgreSQL'/'16'/'bin'
    else:candidate=Path('/usr/lib/postgresql/16/bin')
    if candidate.is_dir():env['PATH']=str(candidate)+os.pathsep+env.get('PATH','')
    for tool in ('pg_dump','pg_restore','ffprobe'):
        if not shutil.which(tool,path=env.get('PATH')):raise RuntimeError('Missing tool: '+tool)
    return env

async def run(args,password):
    suffix=uuid.uuid4().hex;database='darkflow_accept_'+suffix
    folder=ROOT/'reports'/'native_runs'/suffix;folder.mkdir(parents=True,mode=0o700)
    result={'status':'BLOCKED','database':database,'scope':'PostgreSQL + real bot/worker subprocesses + local Telegram HTTP stub + MOCK provider; NOT LIVE Telegram/Clodex/payment','cleanup':'NOT_NEEDED'}
    admin=None;created=False
    dsn=connection_url(args.host,args.port,args.user,password,database)
    try:
        env=tools_path()
        result['tool_versions']={}
        for name in ('pg_dump','pg_restore'):
            tool=subprocess.run([shutil.which(name,path=env.get('PATH')),'--version'],env=env,capture_output=True,text=True,timeout=10)
            if tool.returncode or not re.search(r'PostgreSQL\)? 16\.',tool.stdout):raise RuntimeError('PostgreSQL 16 client tools required')
            result['tool_versions'][name]=tool.stdout.strip().splitlines()[0]
        admin=await asyncpg.connect(connection_url(args.host,args.port,args.user,password,'postgres'),timeout=10)
        result['postgres_version']=await admin.fetchval('SHOW server_version')
        if int(await admin.fetchval('SHOW server_version_num'))//10000!=16:raise RuntimeError('PostgreSQL 16 required')
        if not await admin.fetchval('SELECT rolsuper FROM pg_roles WHERE rolname=current_user'):raise RuntimeError('Dedicated local test administrator required')
        databases=await admin.fetch('SELECT datname FROM pg_database WHERE NOT datistemplate')
        if any(r['datname']!='postgres' and not r['datname'].startswith('darkflow_') and not r['datname'].startswith('restore_test_') for r in databases):raise RuntimeError('Use dedicated dev instance; unrelated databases detected')
        await admin.execute(f'CREATE DATABASE {identifier(database)} TEMPLATE template0 ENCODING \'UTF8\'');created=True;result['cleanup']='PENDING'
        # Clear inherited paid/production/test-selection settings; no active .env is read.
        for key in list(env):
            if key.startswith(('CLODEX_','PLATEGA_','PYTEST_')) or key in ('DATABASE_URL','DATABASE_MIGRATION_URL','TELEGRAM_BOT_TOKEN','TELEGRAM_API_BASE','ADMIN_TELEGRAM_IDS','TEST_DATABASE_URL','ACCESS_MODE','ALLOW_LOCAL_TELEGRAM_STUB'):env.pop(key,None)
        env.update(TEST_DATABASE_URL=dsn,PROVIDER_MODE='mock',GENERATION_ENABLED='true',PAYMENTS_ENABLED='false',ECONOMY_VERIFIED='false',CATALOGUE_ENABLED='false',PYTHONPATH=str(ROOT/'src'),PYTHONUNBUFFERED='1')
        xml=folder/'test-results.xml';command=[sys.executable,'-m','pytest','-q','--junitxml='+str(xml)]
        print('Running full isolated PostgreSQL acceptance. Keep this window open.',flush=True)
        # Async subprocess keeps the administrative connection responsive.
        process=await asyncio.create_subprocess_exec(*command,cwd=ROOT,env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
        try:out,_=await asyncio.wait_for(process.communicate(),900)
        except (asyncio.TimeoutError,asyncio.CancelledError):
            process.terminate()
            try:await asyncio.wait_for(process.communicate(),10)
            except asyncio.TimeoutError:process.kill();await process.communicate()
            raise
        safe=sanitize(out.decode(errors='replace'),(password,dsn));(folder/'tests.log').write_text(safe,encoding='utf-8')
        print(safe[-2500:],flush=True)
        if not xml.exists():raise RuntimeError('JUnit evidence missing')
        xml.write_text(sanitize(xml.read_text(encoding='utf-8'),(password,dsn)),encoding='utf-8')
        result.update(assess(xml,json.loads((ROOT/'tests/required_s2_cases.json').read_text()),process.returncode))
        result['pytest_exit']=process.returncode
        result['git_revision']=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip() if shutil.which('git') and (ROOT/'.git').exists() else json.loads((ROOT/'RELEASE_METADATA.json').read_text()).get('commit','UNKNOWN') if (ROOT/'RELEASE_METADATA.json').exists() else 'UNKNOWN'
        result['migration_hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'migrations').glob('*.sql')}
    except BaseException as exc:
        result['error_type']=type(exc).__name__
        # Only known preflight RuntimeError labels are emitted; never raw DB exception text.
        if type(exc) is RuntimeError:result['reason']=sanitize(str(exc),(password,dsn))
        result['status']='FAIL' if created else 'BLOCKED'
    finally:
        if admin:
            if created:
                try:await admin.execute(f'DROP DATABASE {identifier(database)} WITH (FORCE)');result['cleanup']='PASS_OWN_SCRATCH_DB_ONLY'
                except Exception:result['cleanup']='FAILED_KEEP_FOR_REVIEW';result['status']='FAIL'
            await admin.close()
        (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True);print('Sanitized evidence: '+str(folder),flush=True)
    return 0 if result['status']=='PASS' else 78 if result['status']=='BLOCKED' else 1

def main():
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=5432);p.add_argument('--user',default='postgres');a=p.parse_args()
    try:password=getpass.getpass('Dedicated LOCAL PostgreSQL test administrator password (hidden, not saved): ');code=asyncio.run(run(a,password))
    except KeyboardInterrupt:code=130
    except Exception as exc:print(json.dumps({'status':'BLOCKED','error_type':type(exc).__name__}));code=78
    raise SystemExit(code)

if __name__=='__main__':main()
