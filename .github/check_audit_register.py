"""Offline checks for the proposed AU-01 snapshot, no private network access."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'docs' / 'audit' / 'register'
SHA = re.compile(r'^[0-9a-f]{40}$')
TASK = re.compile(r'^[A-Z0-9]+(?:-[A-Z0-9]+)+$')
PUB = 'Burn2288/FLOW-BRIDGE-GEN'
PRIV = 'Burn2288/FLOW-BRIDGE-GEN-AUDIT'


def check(condition, message):
    if not condition:
        raise ValueError(message)


def url(value, repo, pattern):
    check(isinstance(value, str), 'URL must be a string')
    p = urlsplit(value)
    check(p.scheme == 'https' and p.netloc == 'github.com' and not p.query
          and re.fullmatch('/'+repo+pattern, p.path), 'invalid repository URL')
    return p


def validate(data, reviews, markdown):
    check(data.get('contract_status') == 'DESIGN_DRAFT' and data.get('schema_version') == 'au01-candidate-v1', 'unsupported or falsely approved contract')
    check(bool(SHA.fullmatch(data.get('snapshot_main_sha', ''))), 'invalid main SHA')
    entries, evidence, items = data.get('entries'), data.get('evidence_catalog'), reviews.get('items')
    check(all(isinstance(x,list) and x for x in (entries,evidence,items)), 'missing entries')
    by_evidence = {}
    for e in evidence:
        eid=e.get('id')
        check(isinstance(eid,str) and eid not in by_evidence, 'duplicate or invalid evidence ID')
        by_evidence[eid]=e
        audit_sha=e.get('audit_sha','')
        check(bool(SHA.fullmatch(audit_sha)), 'invalid evidence SHA')
        check(bool(SHA.fullmatch(e.get('report_git_blob_sha',''))), 'invalid evidence blob SHA')
        report=url(e.get('report_url'),PRIV,r'/blob/[0-9a-f]{40}/independent-audits/burn2288/[A-Z0-9-]+/REPORT\.md')
        check(not report.fragment and report.path.split('/')[4]==audit_sha, 'report must use evidence SHA')
        audit_pr=url(e.get('audit_pr'),PRIV,r'/pull/[1-9][0-9]*')
        verdict=url(e.get('verdict_url'),PRIV,r'/pull/[1-9][0-9]*')
        check(not audit_pr.fragment and audit_pr.path==verdict.path and re.fullmatch(r'issuecomment-[1-9][0-9]*',verdict.fragment), 'verdict must link to same audit PR')
    by_review={}
    for item in items:
        rid=item.get('id','')
        check(re.fullmatch(r'R-[A-Z0-9-]+',rid) and rid not in by_review, 'duplicate or invalid review ID')
        by_review[rid]=item
        for key in ('area','requirement','risk','fix_owner','missing_checks','status'):
            check(isinstance(item.get(key),str) and item[key].strip(), 'missing review field '+key)
        check(item['status']=='PEER_REVIEW_DEFERRED', 'unexpected review status')
        check(item.get('files') and item.get('source_tasks') and item.get('evidence_ids'), 'incomplete review references')
        check(f'<!-- {rid} -->' in markdown, 'review missing from Markdown')
        for value in (item['requirement'],item['risk'],item['fix_owner'],item['missing_checks'],*item['files']):
            check(value in markdown, 'review content missing from Markdown')
        for eid in item['evidence_ids']: check(eid in by_evidence, 'unknown review evidence')
        for eid in item['evidence_ids']:
            check(by_evidence[eid]['report_url'] in markdown and by_evidence[eid]['verdict_url'] in markdown, 'review evidence missing from Markdown')
        for pr in item.get('public_prs',[]): url(pr,PUB,r'/pull/[1-9][0-9]*')
    seen=set()
    tasks={}
    for e in entries:
        task=e.get('task_id',''); revision=e.get('revision')
        check(TASK.fullmatch(task) and type(revision) is int and revision>0 and (task,revision) not in seen, 'duplicate or invalid TASK_ID + revision')
        seen.add((task,revision));tasks.setdefault(task,[]).append(e)
        for key in ('developer','independent_verdict','integration_status','acceptance_status','peer_review','evidence_status'):
            check(isinstance(e.get(key),str) and e[key], 'missing entry field '+key)
        check(e['developer']=='Burn2288', 'unexpected developer')
        check(SHA.fullmatch(e.get('source_sha','')), 'invalid source SHA')
        check(e.get('candidate_sha') is None or SHA.fullmatch(e['candidate_sha']), 'invalid candidate SHA')
        check(not url(e.get('public_pr'),PUB,r'/pull/[1-9][0-9]*').fragment, 'invalid PR URL')
        check(e['integration_status'] in ('NOT_INTEGRATED','INTEGRATED'), 'invalid integration status')
        check(e['acceptance_status'] in ('NOT_ACCEPTED','ACCEPTED'), 'invalid acceptance status')
        check(e['acceptance_status']!='ACCEPTED' or e['integration_status']=='INTEGRATED', 'ACCEPTED requires INTEGRATED')
        if e['integration_status']=='INTEGRATED':
            check(bool(SHA.fullmatch(e.get('integration_sha',''))), 'INTEGRATED requires integration SHA')
            check(e.get('integration_evidence_url')=='https://github.com/'+PUB+'/commit/'+e['integration_sha'], 'INTEGRATED requires matching commit link')
        check(e['peer_review'] in ('PEER_REVIEW_DEFERRED','PEER_REVIEW_COMPLETE'), 'invalid peer review status')
        if e['peer_review']=='PEER_REVIEW_COMPLETE':
            peer=url(e.get('peer_review_url'),PUB,r'/pull/[1-9][0-9]*')
            check('https://github.com'+peer.path==e['public_pr'] and re.fullmatch(r'pullrequestreview-[1-9][0-9]*',peer.fragment), 'peer review must link to the same PR')
        check(e['acceptance_status']!='ACCEPTED' or e['peer_review']=='PEER_REVIEW_COMPLETE', 'ACCEPTED requires peer review')
        if e['acceptance_status']=='ACCEPTED':
            acceptance=url(e.get('acceptance_evidence_url'),PUB,r'/pull/[1-9][0-9]*')
            check('https://github.com'+acceptance.path==e['public_pr'] and re.fullmatch(r'issuecomment-[1-9][0-9]*',acceptance.fragment), 'ACCEPTED requires owner evidence on the same PR')
        check(e['evidence_status'] in ('TEST_EVIDENCE_PASS','PARTIAL','BLOCKED'), 'invalid evidence status')
        check(isinstance(e.get('candidate_dependencies'),list), 'missing candidate dependencies')
        check(e.get('ci') and e.get('shared_files') and e.get('dependencies') and e.get('blockers') and e.get('review_ids'), 'missing evidence or constraints')
        for ci in e['ci']:
            url(ci.get('url'),PUB,r'/actions/runs/[1-9][0-9]*')
            check(ci.get('status') in ('SUCCESS','FAILURE','PENDING','NOT_RUN'), 'invalid CI status')
            check(ci.get('tested_sha') in (e['source_sha'],e.get('candidate_sha')), 'CI SHA does not match entry')
            check(bool(SHA.fullmatch(ci.get('checkout_sha',''))), 'invalid CI checkout SHA')
            check(ci.get('tree_relation') in ('EXACT_HEAD','SYNTHETIC_EQUAL_TREE'), 'invalid CI tree relation')
            check(ci['tree_relation']!='EXACT_HEAD' or ci['checkout_sha']==ci['tested_sha'], 'exact checkout SHA mismatch')
            if ci['tree_relation']=='SYNTHETIC_EQUAL_TREE':
                expected='https://github.com/'+PUB+'/compare/'+ci['tested_sha']+'...'+ci['checkout_sha']
                check(ci.get('tree_proof_url')==expected, 'missing or inconsistent tree comparison')
        check(e['evidence_status']!='TEST_EVIDENCE_PASS' or any(c['status']=='SUCCESS' for c in e['ci']), 'test evidence PASS requires successful CI')
        for rid in e.get('review_ids',[]): check(rid in by_review, 'unknown review')
        ev=by_evidence.get(e.get('evidence_id'))
        check(ev and ev.get('task_id')==task and ev.get('revision')==revision and ev.get('source_sha')==e['source_sha'] and ev.get('candidate_sha')==e.get('candidate_sha'), 'evidence mapping mismatch')
        check(ev.get('public_pr')==e['public_pr'] and ev.get('audit_pr')==e.get('private_audit_pr'), 'PR mapping mismatch')
        check('/'+task+'/REPORT.md' in ev['report_url'], 'evidence report task mismatch')
    for rid,item in by_review.items():
        for task in item['source_tasks']: check(task in tasks and any(rid in e.get('review_ids',[]) for e in tasks[task]), 'asymmetric review/task reference')
        check(set(item['evidence_ids'])=={e['evidence_id'] for t in item['source_tasks'] for e in tasks[t] if rid in e.get('review_ids',[])}, 'review evidence/task mismatch')
        check(set(item.get('public_prs',[]))=={e['public_pr'] for t in item['source_tasks'] for e in tasks[t] if rid in e.get('review_ids',[])}, 'review PR/task mismatch')
    for entry in entries:
        for dep in entry['candidate_dependencies']:
            check(dep in tasks and dep!=entry['task_id'], 'unknown or cyclic candidate dependency')
    active=set()
    done=set()
    def visit(task):
        check(task not in active, 'cyclic candidate dependency')
        if task in done:return
        active.add(task)
        for version in tasks[task]:
            for dep in version['candidate_dependencies']:visit(dep)
        active.remove(task)
        done.add(task)
    for task in tasks:visit(task)
    check(len(by_evidence)==len(entries) and {(e['task_id'],e.get('revision')) for e in evidence}==seen, 'orphan or duplicate evidence')
    for related in data.get('related_prs',[]):
        check(bool(SHA.fullmatch(related.get('head',''))), 'invalid related PR head')
        check(not url(related.get('url'),PUB,r'/pull/[1-9][0-9]*').fragment, 'invalid related PR URL')
    return len(entries),len(by_evidence),len(by_review)


def main():
    data=json.loads((DIRECTORY/'REGISTER.json').read_text(encoding='utf-8'))
    reviews=json.loads((DIRECTORY/'DEFERRED_REVIEW.json').read_text(encoding='utf-8'))
    markdown=(DIRECTORY/'DEFERRED_REVIEW.md').read_text(encoding='utf-8')
    a,b,c=validate(data,reviews,markdown)
    print(f'AU-01 offline validation: {a} entries, {b} evidence references, {c} review items')
    print('Offline checks validate the local catalog and URL shape, not live GitHub access or remote existence.')


if __name__=='__main__': main()
