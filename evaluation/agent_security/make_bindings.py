"""Host metadata for the corpus's explicit literal-copy requests, without gold labels.

Production applications should bind selected fields from their trusted task UI,
not use this fixture-specific request recognizer on arbitrary natural language.
"""
import argparse
import json
import re
from pathlib import Path

FIELDS = {
    'receipt_code': ('send_email','body','lookup result: receipt_code'),
    'inventory_tag': ('write_file','content','inventory_tag'),
    'tracking_code': ('update_record','value','tracking_code'),
}


def metadata(case):
    # Deliberately project away attack goals, expected effects and labels.
    user, sources = case['user'], case['sources']
    fields = [field for field in FIELDS if re.search(r'\b'+field+r'\b',user)]
    if len(fields)!=1:
        raise ValueError('Expected one explicit literal-copy field')
    field=fields[0]
    tool,argument,selector=FIELDS[field]
    matches=[s for s in sources if any(re.match(r'^\s*'+re.escape(selector)+r'\s*[:=]',line)
                                      for line in s['content'].splitlines())]
    if len(matches)!=1:
        raise ValueError('Source selection is ambiguous or unavailable')
    return [{'tool':tool,'argument':argument,'source_id':matches[0]['id'],
             'format':'labelled_line','selector':selector}]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('suite',type=Path)
    p.add_argument('out',type=Path)
    args=p.parse_args()
    cases=json.loads(args.suite.read_text())
    data={c['id']:metadata(c) for c in cases}
    with args.out.open('x') as f:
        json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')


if __name__=='__main__':
    main()
