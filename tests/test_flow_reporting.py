import json
from pathlib import Path
import tempfile
import unittest

from evaluation.flow_security.report import build, journal, paired


class FlowReportingTests(unittest.TestCase):
    def test_review_pairs_include_every_model(self):
        root=Path(__file__).resolve().parents[1]
        result=build(root/'evaluation/agent_security/results/flow_dev3')
        for model in result['models']:
            rows=[r for r in result['paired'] if r['model']==model and r['from']=='capability' and r['to']=='reviewed']
            self.assertEqual({r['metric'] for r in rows},{'attack_success','normal_pass'})

    def test_mixed_model_review_prices_actual_response_model(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'review.jsonl'
            p.write_text(json.dumps({'request':{'model':'gpt-5.4-mini-2026-03-17'}})+'\n'+json.dumps(
                {'response':{'model':'gpt-5.4-mini-2026-03-17','usage':{'input_tokens':1000,'output_tokens':100}}})+'\n')
            # The case's generator is cheaper; reviewer cost must not use its rate.
            result=journal(p,'gpt-4.1-mini-2025-04-14')
            self.assertEqual(float(result['known_usd']),.0012)
            self.assertEqual(result['calls'],1)

    def test_missing_behavior_is_not_a_security_improvement(self):
        rows=[{'case':'one','arm':'raw','attack_success':True},
              {'case':'one','arm':'reviewed','attack_success':None},
              {'case':'two','arm':'raw','attack_success':True},
              {'case':'two','arm':'reviewed','attack_success':False}]
        result=paired(rows,'raw','reviewed','attack_success')
        self.assertEqual((result['n'],result['improved'],result['missing_pairs']),(1,1,1))


if __name__=='__main__':unittest.main()
