import shutil,subprocess,json,os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
r={'docker':shutil.which('docker'),'wsl':shutil.which('wsl.exe'),'uid':os.getuid() if hasattr(os,'getuid') else None,
   'docker_socket':any(Path(x).exists() for x in ['/var/run/docker.sock','/run/docker.sock'])}
for key in ('uid_map','gid_map'):
    path=Path('/proc/self')/key;r[key]=path.read_text().strip() if path.exists() else None
pg=Path('/usr/lib/postgresql/16/bin/postgres')
if pg.exists():
    for label,args in [('postgres_version',[str(pg),'--version']),('postgres_root_start',[str(pg),'-D','/tmp/elevenbot-s2-unused'])]:
        # Root check fails before reading/writing a data directory. No root bypass.
        if label=='postgres_root_start' and r['uid']!=0:continue
        result=subprocess.run(args,capture_output=True,text=True,timeout=10);r[label]={'exit':result.returncode,'stdout':result.stdout.strip(),'stderr':result.stderr.strip()}
(rdir:=root/'reports').mkdir(exist_ok=True);(rdir/'S2_ENVIRONMENT.json').write_text(json.dumps(r,indent=2))
print(json.dumps(r,indent=2))
