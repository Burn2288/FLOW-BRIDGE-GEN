#!/usr/bin/env python3
"""Read-only CLODEX HTTP probe. No paid generations, no credentials in output."""
import argparse
import datetime
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

p = argparse.ArgumentParser(description='Read-only CLODEX endpoint probe; no paid calls')
p.add_argument('--base-url', default=os.environ.get('CLODEX_BASE_URL', 'https://clodex.xyz/v1'))
p.add_argument('--list-models', action='store_true', help='Probe GET /models on the configured base URL')
p.add_argument('--report', default='probe_report.json')
a = p.parse_args()
base = a.base_url.rstrip('/')
parts = urlparse(base)
if parts.scheme != 'https' or parts.hostname != 'clodex.xyz' or parts.username or parts.password:
    p.error('Only https://clodex.xyz is allowed; check base-url manually.')
report = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'base_url': base, 'tests': [], 'note':'GET /models is hypothetical until confirmed by CLODEX documentation or a live probe.'}
if not a.list_models:
    print('No request performed. Add --list-models for a read-only authorized GET.')
else:
    key = os.environ.get('CLODEX_API_KEY')
    if not key:
        p.error('Set CLODEX_API_KEY locally. No requests were sent.')
    url = base + '/models'
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + key, 'Accept': 'application/json', 'User-Agent': 'ClodexIntegrationAudit/0.1'}, method='GET')
    start = time.monotonic()
    item = {'method':'GET', 'path':'/models', 'url':url}
    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context()) as r:
            body = r.read(1024*1024)
            item.update({'http_status':r.status, 'elapsed_ms':round((time.monotonic()-start)*1000), 'content_type':r.headers.get('Content-Type'), 'body_bytes_read':len(body), 'truncated':len(body)==1024*1024})
            try:
                payload=json.loads(body)
                if isinstance(payload,dict) and isinstance(payload.get('data'),list):
                    item['models_count']=len(payload['data'])
                    item['model_ids']=[m.get('id') for m in payload['data'] if isinstance(m,dict) and isinstance(m.get('id'),str)]
                else:
                    item['shape']='JSON but not recognized OpenAI model list'
            except (ValueError,UnicodeDecodeError):
                item['shape']='Non-JSON or malformed JSON'
    except urllib.error.HTTPError as e:
        item.update({'http_status':e.code, 'elapsed_ms':round((time.monotonic()-start)*1000), 'status':'HTTP_ERROR', 'content_type':e.headers.get('Content-Type')})
    except Exception as e:
        item.update({'elapsed_ms':round((time.monotonic()-start)*1000), 'status':'TRANSPORT_ERROR', 'error_type':type(e).__name__})
    report['tests'].append(item)
    print('Probe result:', item.get('http_status', item.get('status')))
with open(a.report,'w',encoding='utf-8') as f:
    json.dump(report,f,indent=2,ensure_ascii=False)
print('Wrote',a.report)
