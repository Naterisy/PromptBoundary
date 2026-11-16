"""Rebuild all outcomes from frozen cases, observable tool effects and API journals."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

from .score import score_case
from evaluation.agent_security.budget import cost


def ratio(rows,key):
    values=[r[key] for r in rows if r[key] is not None]
    n=len(values); k=sum(values)
    if not n:return {'count':0,'n':0,'rate':None,'wilson95':None}
    z=1.959963984540054; p=k/n; divisor=1+z*z/n
    center=(p+z*z/(2*n))/divisor
    delta=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/divisor
    return {'count':k,'n':n,'rate':round(p,8),'wilson95':[round(center-delta,8),round(center+delta,8)]}


def percentile(values,q):
    values=sorted(values)
    if not values:return None
    i=(len(values)-1)*q;low=math.floor(i);high=math.ceil(i)
    return round(values[low]+(values[high]-values[low])*(i-low),3)


def journal(path,model):
    value=Decimal(0);usage=Counter();calls=0;responses=0
    for line in path.read_text().splitlines():
        row=json.loads(line)
        if 'request' in row:calls+=1
        if 'response' in row:
            response=row['response']
            if response.get('usage') is not None:
                responses+=1;tokens=response['usage'];value+=cost(response['model'],tokens)
                usage['input_tokens']+=tokens['input_tokens'];usage['output_tokens']+=tokens['output_tokens']
    return {'calls':calls,'priced_responses':responses,'known_usd':str(value),'tokens':dict(usage)}


def paired(rows,first,second,key):
    indexes={arm:{r['case']:r for r in rows if r['arm']==arm} for arm in (first,second)}
    better=worse=ties=missing=0;diff=[]
    # Positive means fewer failures, or more utility for the second arm.
    failures=key in ('attack_success','false_refusal','source_fact_error')
    for cid in sorted(set(indexes[first]) & set(indexes[second])):
        a,b=indexes[first][cid][key],indexes[second][cid][key]
        if a is None and b is None:continue
        if a is None or b is None:missing+=1;continue
        gain=(int(a)-int(b)) if failures else (int(b)-int(a))
        diff.append(gain)
        if gain>0:better+=1
        elif gain<0:worse+=1
        else:ties+=1
    n=better+worse
    p=min(1.,2*sum(math.comb(n,i) for i in range(min(better,worse)+1))/(2**n)) if n else 1.
    return {'from':first,'to':second,'metric':key,'improved':better,'regressed':worse,'tied':ties,
            'missing_pairs':missing,'n':len(diff),'mean_gain':round(math.fsum(diff)/len(diff),8) if diff else None,
            'exact_mcnemar_p':round(p,10),'interpretation':'exploratory, no multiplicity correction; cases, not API calls, are units'}


def build(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    casefile=directory/'cases.json'
    if hashlib.sha256(casefile.read_bytes()).hexdigest()!=manifest['suite_sha256']:
        raise ValueError('Case snapshot changed')
    for source,digest in manifest['source_sha256'].items():
        if hashlib.sha256((directory/'code'/source).read_bytes()).hexdigest()!=digest:
            raise ValueError('Code snapshot changed: '+source)
    scorer=Path(__file__).with_name('score.py')
    if hashlib.sha256(scorer.read_bytes()).hexdigest()!=manifest['source_sha256']['evaluation/flow_security/score.py']:
        raise ValueError('Scorer differs from experiment freeze')
    cases=json.loads(casefile.read_text());rows=[];summaries={}
    keys=('attack_success','normal_pass','false_refusal','task_pass','unauthorized_effect','attack_refused','source_fact_error','reply_canary_leak')
    for model in manifest['models']:
        summaries[model]={}
        for arm in manifest['arms']:
            group=[];costs=Decimal(0);calls=0;priced=0;usage=Counter();latencies=[]
            for case in cases:
                path=directory/model/arm/(case['id']+'.json')
                if not path.exists():raise ValueError('Missing case: '+str(path))
                record=json.loads(path.read_text())
                attempts=[action for plan in record['plans'] for action in plan.get('actions',[])]
                score=score_case(case,record['executed_actions'],record['status'],attempts,record['reply'])
                if arm in ('flow','reviewed','hybrid'):score['attempted_attack']=None  # No action-plan proposal exists in this arm.
                j=journal(path.with_suffix('.jsonl'),model)
                review_journal=path.with_name(path.stem+'.review.jsonl')
                if review_journal.exists():
                    extra=journal(review_journal,'gpt-5.4-mini-2026-03-17')
                    j['calls']+=extra['calls'];j['priced_responses']+=extra['priced_responses']
                    j['known_usd']=str(Decimal(j['known_usd'])+Decimal(extra['known_usd']))
                    j['tokens']=dict(Counter(j['tokens'])+Counter(extra['tokens']))
                row={**score,'model':model,'arm':arm,'elapsed_ms':record['elapsed_ms'],**j}
                group.append(row);rows.append(row)
                costs+=Decimal(j['known_usd']);calls+=j['calls'];priced+=j['priced_responses'];usage.update(j['tokens']);latencies.append(record['elapsed_ms'])
            categories={c:{key:ratio([r for r in group if r['category']==c],key) for key in keys}
                        for c in sorted({r['category'] for r in group})}
            summaries[model][arm]={**{key:ratio(group,key) for key in keys},'categories':categories,
                'status_counts':dict(sorted(Counter(r['status_class'] or r['status'] for r in group).items())),
                'technical_errors':sum(r['transport_error'] for r in group),'total_cases':len(group),
                'calls':calls,'priced_responses':priced,'known_usd':str(costs),'tokens':dict(usage),
                'latency_ms':{'p50':percentile(latencies,.5),'p95':percentile(latencies,.95)}}
    pairs=[]
    for model in manifest['models']:
        selected=[r for r in rows if r['model']==model]
        for arm in manifest['arms']:
            if arm=='raw' or 'raw' not in manifest['arms']:continue
            for key in ('attack_success','normal_pass','false_refusal'):
                pairs.append({'model':model,**paired(selected,'raw',arm,key)})
        if 'capability' in manifest['arms'] and 'flow' in manifest['arms']:
            for key in ('attack_success','normal_pass'):
                pairs.append({'model':model,**paired(selected,'capability','flow',key)})
        if 'minimized' in manifest['arms'] and 'flow' in manifest['arms']:
            for key in ('attack_success','normal_pass'):
                pairs.append({'model':model,**paired(selected,'minimized','flow',key)})
        if 'reviewed' in manifest['arms']:
            for first in ('flow','capability','minimized'):
                if first in manifest['arms']:
                    for key in ('attack_success','normal_pass'):
                        pairs.append({'model':model,**paired(selected,first,'reviewed',key)})
    return {'suite_sha256':manifest['suite_sha256'],'models':summaries,'hybrid_reviewer_model':manifest.get('hybrid_reviewer_model'),'paired':pairs,'cases':rows,
            'notes':['Effect-based authored benchmark, not an official public benchmark score.',
                     'Fact predicates approximate utility and need independent semantic review.',
                     'Source-fact poisoning sentinels excluded from injection ASR and normal utility; reported separately.',
                     'Technical errors are missing behavioral evidence, not safe refusals.',
                     'Context minimization is an explicit architectural difference and separate ablation.',
                     'No claim of semantic integrity, source authenticity or protection against privileged host compromise.']}


def fraction(value):
    return f"{value['count']}/{value['n']}"


def markdown(result):
    text=['# Quarantined transform results','',*result['notes'], 'Hybrid reviewer: '+str(result.get('hybrid_reviewer_model')),'',
          '| Model / arm | Attacks | Normal pass | False refusal | Fact poisoning | Errors | p50 / p95 ms | API USD |',
          '|---|---:|---:|---:|---:|---:|---:|---:|']
    for model,arms in result['models'].items():
        for arm,row in arms.items():
            text.append(f"| {model} / {arm} | {fraction(row['attack_success'])} | {fraction(row['normal_pass'])} | {fraction(row['false_refusal'])} | {fraction(row['source_fact_error'])} | {row['technical_errors']} | {row['latency_ms']['p50']} / {row['latency_ms']['p95']} | {row['known_usd']} |")
    text += ['', 'All per-case outcomes and Wilson intervals are in SUMMARY.json. Paired exact tests are exploratory and unadjusted. Failed and refused cases remain included.', '']
    return '\n'.join(text)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
    result=build(a.directory)
    files={'SUMMARY.json':json.dumps(result,ensure_ascii=False,indent=2)+'\n','SUMMARY.md':markdown(result)}
    for name,content in files.items():
        path=a.directory/name
        if a.check:
            if path.read_text()!=content:raise ValueError('Stale report: '+str(path))
        else:path.write_text(content)
    print(markdown(result))


if __name__=='__main__':main()
