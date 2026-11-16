"""Account for every new API call, including interrupted development runs."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
from .budget import cost


def build(root,ledger_path):
    ledger=json.loads(ledger_path.read_text())
    seen={}; totals=Counter(); priced=Decimal(0)
    for path in root.rglob('*.jsonl'):
        pending={}
        for line in path.read_text().splitlines():
            row=json.loads(line)
            if 'request' in row:
                key=row['reservation']
                if key in seen:raise ValueError('Duplicate journal reservation')
                if key not in ledger['calls']:raise ValueError('Unbudgeted request')
                pending[row['n']]=key;seen[key]={'journal':str(path.relative_to(root)),'state':'pending'}
            elif row['n'] in pending:
                key=pending[row['n']]; saved=ledger['calls'][key]
                if 'response' in row and row['response'].get('usage') is not None:
                    usage=row['response']['usage']; value=cost(saved['model'],usage)
                    if saved.get('actual_usd')!=str(value):raise ValueError('Journal/ledger cost disagrees')
                    totals['input']+=usage['input_tokens'];totals['output']+=usage['output_tokens'];priced+=value
                    seen[key]['state']='known'
                else:seen[key]['state']='unknown'
    known=sum(Decimal(v.get('actual_usd','0')) for v in ledger['calls'].values())
    if known!=priced:raise ValueError('Ledger has billed response missing from journal')
    reserved=sum(Decimal(v['reserved_usd']) for v in ledger['calls'].values() if 'actual_usd' not in v)
    return {'reservations':len(ledger['calls']),'journal_requests':len(seen),
            'known_usd':str(known),'unknown_reserved_usd':str(reserved),'maximum_exposure_usd':str(known+reserved),
            'hard_cap_usd':ledger['cap_usd'],'tokens':dict(totals),'journal_states':dict(Counter(v['state'] for v in seen.values())),
            'unstarted_reservations':sorted(set(ledger['calls'])-set(seen))}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    p.add_argument('--check',action='store_true')
    a=p.parse_args();result=build(a.root,a.root/'budget.json')
    encoded=json.dumps(result,indent=2)+'\n';dest=a.root/'TOTAL_COST.json'
    if a.check:
        if dest.read_text()!=encoded:raise ValueError('Stale cumulative accounting')
    else:dest.write_text(encoded)
    print(encoded)


if __name__=='__main__':main()
