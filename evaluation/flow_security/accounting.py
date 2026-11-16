"""Verify continuation costs against every full batch and the earlier frozen ledger total."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
SHARED=HERE.parents[1]/'evaluation/agent_security/results'


def build():
    previous=json.loads((HERE/'PREVIOUS_BUDGET_TOTAL.json').read_text())
    current=json.loads((SHARED/'TOTAL_COST.json').read_text())
    calls=0;known=Decimal(0);tokens=Counter();runs=[]
    for p in sorted(SHARED.glob('flow_*/SUMMARY.json')):
        runs.append(p.parent.name)
        for arms in json.loads(p.read_text())['models'].values():
            for group in arms.values():
                calls+=group['calls'];known+=Decimal(group['known_usd']);tokens.update(group['tokens'])
    if calls!=current['journal_requests']-previous['journal_requests']:
        raise ValueError('Continuation calls do not reconcile with cumulative journals')
    if known!=Decimal(current['known_usd'])-Decimal(previous['known_usd']):
        raise ValueError('Continuation cost does not reconcile with cumulative ledger')
    for key in ('input','output'):
        if tokens[key+'_tokens']!=current['tokens'][key]-previous['tokens'][key]:
            raise ValueError('Continuation tokens do not reconcile')
    return {'runs':runs,'calls':calls,'usage_priced_usd':str(known.normalize()),'tokens':dict(tokens),
            'previous_budget_usage_usd':previous['known_usd'],'cumulative_budget_usage_usd':current['known_usd'],
            'authorized_cap_usd':'10.00','admission_cap_usd':current['hard_cap_usd'],
            'unknown_reserved_usd':current['unknown_reserved_usd']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    data=json.dumps(build(),indent=2)+'\n';dest=SHARED/'FLOW_CONTINUATION_COST.json'
    if args.check:
        if dest.read_text()!=data:raise ValueError('Stale continuation accounting')
    else:dest.write_text(data)
    print(data)


if __name__=='__main__':main()
