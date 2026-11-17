#!/usr/bin/env python3
"""Isolated S2 acceptance runner. Never touches another Compose project.
Zero infrastructure SKIPs required; no commercial API/Stars operations.
"""
import subprocess,shutil,uuid,json,sys,datetime
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
project='elevenbot-s2-'+uuid.uuid4().hex[:12]
folder=root/'reports'/'s2_runs'/project;folder.mkdir(parents=True)
state={'project':project,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'engineering_ready':'BLOCKED','commands':[]}
def save():(folder/'result.json').write_text(json.dumps(state,indent=2))
def run(args,timeout=900):
    state['commands'].append(args);save()
    result=subprocess.run(args,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    (folder/f'command_{len(state["commands"]):02}.log').write_bytes(result.stdout)
    print(result.stdout.decode(errors='replace'),flush=True)
    return result.returncode
if not shutil.which('docker'):
    state['reason']='docker executable absent';save();print('BLOCKED: Docker not available');sys.exit(78)
base=['docker','compose','-p',project,'-f','compose.test.yaml']
try:
    if run(['docker','info','--format','{{.ServerVersion}}'],30)!=0:
        state['reason']='Docker daemon not reachable';save();sys.exit(78)
    code=run(base+['up','--build','--abort-on-container-exit','--exit-code-from','tests'])
    copied=run(base+['cp','tests:/tmp/test-results.xml',str(folder/'test-results.xml')],30)
    if copied==0:
        tree=ET.parse(folder/'test-results.xml')
        counts={k:sum(int(s.get(k,0)) for s in tree.iter('testsuite')) for k in ('tests','failures','errors','skipped')}
        state['tests']=counts
        expected=set(json.loads((root/'tests/required_s2_cases.json').read_text()))
        observed={x.get('classname')+'#'+x.get('name') for x in tree.iter('testcase')}
        missing=expected-observed;state['missing_cases']=sorted(missing)
        if code==0 and not missing and counts['tests']>=len(expected) and not any(counts[k] for k in ('failures','errors','skipped')):
            state['engineering_ready']='PASS';state['reason']='Full isolated PostgreSQL/process-MOCK/restore suite passed; LIVE gates remain unverified'
        else:state['engineering_ready']='FAIL';state['reason']='Nonzero test exit, missing tests or any FAIL/ERROR/SKIP'
    else:state['engineering_ready']='FAIL';state['reason']='Test evidence missing'
except (subprocess.TimeoutExpired,Exception) as e:
    state['reason']='Acceptance runner error: '+type(e).__name__;state['engineering_ready']='FAIL'
finally:
    try:run(base+['down','--remove-orphans'],60)
    except Exception:state['cleanup']='FAILED: remove only project '+project
    save()
print(json.dumps(state,indent=2));sys.exit(0 if state['engineering_ready']=='PASS' else 1)
