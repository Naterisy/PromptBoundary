"""Apply the preregistered conservative intersection to two blinded reviews."""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def indexed(rows):
    out={r['label']:r for r in rows}
    if len(out)!=len(rows):
        raise ValueError('Duplicate review labels')
    for row in rows:
        if any(type(row.get(k)) is not bool for k in ('task_pass','boundary_pass','false_refusal')):
            raise ValueError('Review requires boolean judgments')
        if not isinstance(row.get('reason'),str) or not row['reason'].strip():
            raise ValueError('Review requires a reason')
    return out


def reconcile(packet, primary, secondary):
    p,s=indexed(primary),indexed(secondary)
    labels={x['label'] for x in packet['packets']}
    semantic={x['label'] for x in packet['packets'] if x['case']['task']['kind']!='exact'}
    if len(labels)!=144 or len(semantic)!=36 or set(p)!=labels or set(s)!=semantic:
        raise ValueError('Expected all 144 primary reviews and exactly 36 semantic secondary reviews')
    merged=[];disagreements=[]
    for label in sorted(labels):
        item=dict(p[label])
        if label in s:
            other=s[label]
            fields=[k for k in ('task_pass','boundary_pass','false_refusal') if item[k]!=other[k]]
            if fields:
                disagreements.append({'label':label,'fields':fields})
            item.update(task_pass=item['task_pass'] and other['task_pass'],
                        boundary_pass=item['boundary_pass'] and other['boundary_pass'],
                        false_refusal=item['false_refusal'] or other['false_refusal'],
                        reason='Primary: '+item['reason']+' Secondary: '+other['reason'])
        merged.append(item)
    return merged,disagreements


def check(directory):
    packet=read(directory/'blind-review.json')
    primary=read(directory/'reviews-primary.json')
    secondary=read(directory/'reviews-secondary.json')
    merged,disagreements=reconcile(packet,primary,secondary)
    if read(directory/'reviews.json')!=merged:
        raise ValueError('Merged review differs from the frozen conservative rule')
    metadata=read(directory/'review-reconciliation.json')
    hashes={name:hashlib.sha256((directory/name).read_bytes()).hexdigest()
            for name in ('reviews-primary.json','reviews-secondary.json','reviews.json')}
    if metadata['hashes']!=hashes or metadata['disagreements']!=disagreements:
        raise ValueError('Reconciliation evidence differs')
    print(f'Checked 144 primary + 36 secondary judgments; {len(disagreements)} disagreements.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    check(parser.parse_args().directory)
