import unittest
from evaluation.agent_security.report import interval,paired,rate

class ReportTests(unittest.TestCase):
    def test_zero_is_not_zero_uncertainty(self):
        low,high=interval(0,24)
        self.assertAlmostEqual(low,0)
        self.assertGreater(high,.13)
        self.assertIsNone(interval(0,0))

    def test_errors_not_credited(self):
        r=rate([True,False,None])
        self.assertEqual((r['n'],r['d'],r['missing']),(1,2,1))

    def test_pair_not_independent_samples(self):
        def rows(vals):return [{'case':str(i),'score':{'attack_success':v}} for i,v in enumerate(vals)]
        x=paired(rows([True]*8),rows([False]*8),'attack_success',False)
        self.assertEqual(x['benefit_pp'],100)
        self.assertEqual(x['exact_p_two_sided'],.0078125)
