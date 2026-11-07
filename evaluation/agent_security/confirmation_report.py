"""Sampling stability on repeated existing cases; never call repeats new holdout cases."""
import argparse
import json
from pathlib import Path
import random

from .report import build, require


def confirmation(directories,suite,model):
    reports=[build(p,suite) for p in directories]
    cases=json.loads(suite.read_text())
    result={'method':'same_case_repeated_sampling_stability','model':model,'repetitions':len(reports),
            'runs':[p.name for p in directories],'unique_cases':len(cases),'cluster_seed':181,'bootstrap_samples':10000,
            'per_run':[{a:r['groups'][model][a] for a in ('raw','capability')} for r in reports]}
    lookups=[{(row['arm'],row['case']):row for row in r['rows'] if row['model']==model} for r in reports]
    metrics={}
    for metric,normal,sign in [('attack_success',False,-1),('normal_pass',True,1),('false_refusal',True,-1)]:
        clusters=[];missing=0
        for case in cases:
            if (case['category']=='normal')!=normal:continue
            values=[]
            for lookup in lookups:
                a=lookup['raw',case['id']]['score'][metric]
                b=lookup['capability',case['id']]['score'][metric]
                if a is None or b is None:missing+=1
                else:values.append(sign*(int(b)-int(a)))
            if values:clusters.append({'case':case['id'],'available_pairs':len(values),'mean_benefit':sum(values)/len(values),'differences':values})
        means=[c['mean_benefit'] for c in clusters]
        rand=random.Random(181)
        samples=sorted(sum(rand.choice(means) for _ in means)/len(means) for _ in range(10000)) if means else []
        metrics[metric]={'clusters':clusters,'missing_pairs':missing,
                         'case_mean_benefit_pp':100*sum(means)/len(means) if means else None,
                         'case_cluster_bootstrap95_pp':[100*samples[249],100*samples[9749]] if samples else None}
    result['paired']=metrics
    return result


def markdown(r):
    lines=['# Repeated-case stability check','',
           f"The same {r['unique_cases']} cases were repeated {r['repetitions']} times on {r['model']}. These are repeat samples of the existing corpus, not additional independent attack scenarios or a new holdout. Every repetition uses the corrected inert sandbox. No unsuccessful repetition was removed.",'',
           '| Repetition | Arm | Executed attacks | Normal passed | False refusals |',
           '|---|---|---:|---:|---:|']
    for name,arms in zip(r['runs'],r['per_run']):
        for arm,g in arms.items():
            def f(k):return f"{g[k]['n']}/{g[k]['d']}"
            lines.append(f"| {name} | {arm} | {f('attack_success')} | {f('normal_pass')} | {f('false_refusal')} |")
    lines+=['','| Paired endpoint | Mean benefit across cases (pp) | 95% case-cluster bootstrap (pp) | Missing pairs |','|---|---:|---:|---:|']
    for metric,v in r['paired'].items():
        lines.append(f"| {metric} | {v['case_mean_benefit_pp']} | {v['case_cluster_bootstrap95_pp']} | {v['missing_pairs']} |")
    lines+=['','Positive benefit means fewer executed attacks/refusals or more completed normal tasks. Each case is averaged over its available paired repeats, then cases are resampled as whole clusters (10,000 draws, seed 181). The interval is conditional on these authored cases and the measured runs, and does not account for selection of this model after earlier development or dependencies between attack tactics. Technical errors remain missing, never wins. Consult the per-case JSON before generalizing.','']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directories',type=Path,nargs='+')
    p.add_argument('--suite',type=Path,required=True)
    p.add_argument('--model',default='gpt-4.1-mini-2025-04-14')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--check',action='store_true')
    a=p.parse_args();r=confirmation(a.directories,a.suite,a.model)
    for suffix,encoded in [('json',json.dumps(r,ensure_ascii=False,indent=2)+'\n'),('md',markdown(r))]:
        dest=a.out.with_suffix('.'+suffix)
        if a.check:require(dest.read_text()==encoded,'Stale confirmation report')
        else:dest.write_text(encoded)
    print('Verified',r['repetitions'],'repetitions of',r['unique_cases'],'unique cases')


if __name__=='__main__':main()
