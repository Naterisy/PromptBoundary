import json
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from evaluation.agent_security.budget import Ledger, BudgetExceeded, cost, reservation
from evaluation.agent_security.run import decode


class BudgetTests(unittest.TestCase):
    def test_actual_cost_caches_not_double_counted(self):
        self.assertEqual(cost('gpt-6-astra',{'input_tokens':1000,'output_tokens':100,'input_tokens_details':{'cached_tokens':200,'cache_write_tokens':100}}),Decimal('.01345'))

    def test_concurrent_reservations_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'budget.json'
            body={'max_output_tokens':768,'input':'hello'}
            def reserve(_):return Ledger(path).reserve('gpt-6-astra',body,'test')
            with ThreadPoolExecutor(max_workers=4) as pool:ids=list(pool.map(reserve,range(12)))
            self.assertEqual(len(set(ids)),12)
            ledger=Ledger(path)
            self.assertEqual(ledger.snapshot()['calls'],12)
            ledger.settle(ids[0],{'model':'gpt-6-astra','service_tier':'default','usage':{'input_tokens':10,'output_tokens':2}})
            self.assertEqual(Ledger(path).snapshot()['unsettled'],11)
            self.assertLess(Decimal(ledger.snapshot()['exposure_usd']),12*reservation('gpt-6-astra',body))

    def test_stop_before_cap_and_keep_unknown_reservations(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=Ledger(Path(d)/'budget.json')
            body={'max_output_tokens':768,'input':'x'*700000}
            ident=ledger.reserve('gpt-6-astra',body,'large')
            ledger.settle(ident,{})
            with self.assertRaises(BudgetExceeded):ledger.reserve('gpt-6-astra',body,'would exceed')
            self.assertEqual(ledger.snapshot()['unsettled'],1)

    def test_unpriced_response_persists_halt(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=Ledger(Path(d)/'budget.json');body={'max_output_tokens':768}
            ident=ledger.reserve('gpt-6-astra',body,'x')
            with self.assertRaises(BudgetExceeded):ledger.settle(ident,{'model':'wrong','service_tier':'default','usage':{'input_tokens':1,'output_tokens':1}})
            with self.assertRaises(BudgetExceeded):Ledger(ledger.path).reserve('gpt-6-astra',body,'later')

    def test_response_above_reservation_persists_true_usage_and_halts(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=Ledger(Path(d)/'budget.json');body={'max_output_tokens':1}
            ident=ledger.reserve('gpt-6-astra',body,'x')
            with self.assertRaises(BudgetExceeded):ledger.settle(ident,{'model':'gpt-6-astra','service_tier':'default','usage':{'input_tokens':100000,'output_tokens':1}})
            self.assertGreater(Decimal(ledger.snapshot()['known_usd']),1)
            with self.assertRaises(BudgetExceeded):ledger.reserve('gpt-6-astra',body,'later')

    def test_plan_envelope_no_hidden_extra_fields(self):
        self.assertEqual(decode('{"actions":[]}'),{'actions':[]})
        for invalid in ['[]','{"actions":null}','{"actions":[],"permissions":{}}','{"actions":[{"tool":"mail","arguments":[],"extra":1}]}']:
            with self.assertRaises(ValueError):decode(invalid)
