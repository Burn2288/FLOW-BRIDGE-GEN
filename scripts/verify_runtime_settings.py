import tempfile,subprocess,os,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];os.chdir(root);python=sys.executable;result={}
with tempfile.TemporaryDirectory() as tmp:
 path=Path(tmp)/'.env'
 path.write_text('DATABASE_URL=postgresql://fixture:private-fixture@127.0.0.1:1/unreachable\nTELEGRAM_BOT_TOKEN=123456:fixture_placeholder_not_a_real_token_12345\nADMIN_TELEGRAM_IDS=100\nACCESS_MODE=private\nPROVIDER_MODE=catalogue\nGENERATION_ENABLED=false\nPAYMENTS_ENABLED=false\n',encoding='utf-8')
 env=dict(os.environ,PYTHONPATH=str(root/'src'))
 for key in ('DATABASE_URL','DATABASE_MIGRATION_URL','TELEGRAM_BOT_TOKEN','ADMIN_TELEGRAM_IDS','ACCESS_MODE','PROVIDER_MODE','GENERATION_ENABLED','PAYMENTS_ENABLED'):env.pop(key,None)
 code='import sys,json;from elevenbot.config import Config;c=Config.env(sys.argv[1]);print(json.dumps(dict(token_configured=bool(c.token),owners=len(c.admin_ids),mode=c.mode,access=c.access_mode)))'
 observations=[]
 for _ in range(2):
  p=subprocess.run([python,'-c',code,str(path)],env=env,capture_output=True,text=True,timeout=20,check=True)
  observations.append(json.loads(p.stdout))
 assert observations[0]==observations[1]
 result['separate_process_config_reload']={'status':'PASS_FIXTURE','observations':observations}
 p=subprocess.run([python,'-m','elevenbot','--env-file',str(path),'doctor'],env=env,capture_output=True,text=True,timeout=20)
 assert p.returncode==1 and 'private-fixture' not in p.stdout+p.stderr and 'fixture_placeholder' not in p.stdout+p.stderr
 result['doctor_unreachable_db_redaction']={'status':'PASS_EXPECTED_FAILURE','exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
result['scope']='Separate real Python processes with a local synthetic settings file; no real Telegram/DB connection'
Path('reports/SERVICE_PROCESS_CHECKS.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
