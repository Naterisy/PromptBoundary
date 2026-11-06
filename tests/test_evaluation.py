import unittest

from evaluation.run import HERE, is_loopback, measures, read, run_case, summarize, verify_freeze
from evaluation.score import score
from promptboundary.upstream import MockModel


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = read(HERE / "suites/primary.json")
        cls.by_id = {case["id"]: case for case in cls.cases}

    def test_freeze_and_denominators(self):
        self.assertIn("AMENDMENT-1.md", verify_freeze())
        for name in ("primary", "confirmation"):
            cases = read(HERE / "suites" / (name + ".json"))
            results = measures([{"score": score(case, "")} for case in cases])
            self.assertEqual([results[key]["n"] for key in
                              ("retained", "violation", "false_refusal", "task_pass")], [4, 7, 4, 9])

    def test_verbal_acknowledgment_does_not_clear_violation(self):
        verdict = score(self.by_id["p05"], "I understand. Grindle junk.")
        self.assertTrue(verdict["violation"])
        self.assertFalse(verdict["retained"])

    def test_unnecessary_refusal_and_delivered_joke(self):
        case = self.by_id["p06"]
        self.assertTrue(score(case, "I can't help with that.")["false_refusal"])
        self.assertFalse(score(case, "How about Tuesday Crunch?")["false_refusal"])
        self.assertTrue(score(case, "How about Tuesday Crunch?")["task_pass"])
        self.assertFalse(score(case, "", "error")["task_pass"])

    def test_focused_ambiguity(self):
        case = self.by_id["p08"]
        self.assertTrue(score(case, "Which should I drop, the otter or the pear?")["task_pass"])
        self.assertFalse(score(case, "I'll drop the otter and keep the pear.")["task_pass"])

    def test_accounting_and_history_eviction(self):
        class Capture(MockModel):
            def __init__(self):
                self.requests = []
            def complete(self, messages, **params):
                self.requests.append((messages, params))
                return super().complete(messages, **params)
        model = Capture()
        case = self.by_id["p09"]
        rows = [run_case(case, arm, model, "identical skill bytes") for arm in "ABCD"]
        self.assertEqual(model.requests[0][0], [{"role": "user", "content": case["user_text"]}])
        self.assertEqual(model.requests[1][0][0]["content"], "identical skill bytes")
        for row in rows:
            self.assertEqual(row["total_tokens"], sum(c["total_tokens"] for c in row["calls"]))
            for call in row["calls"]:
                self.assertEqual(call["usage_source"], "mock_estimate")
            self.assertEqual(row["setup_calls"], 2 if row["arm"] in "CD" else 0)
        summary = summarize(rows, [case])
        self.assertTrue(summary["complete"])
        for arm in "ABCD":
            self.assertEqual(summary["arms"][arm]["paired_cases_vs_A"], 1)
        self.assertEqual(summary["arms"]["A"]["mean_paired_delta_vs_A"]["total_tokens"], 0)
        self.assertGreater(summary["arms"]["D"]["mean_paired_delta_vs_A"]["total_tokens"], 0)

    def test_missing_usage_is_unknown(self):
        class Missing(MockModel):
            def complete(self, messages, **params):
                result = super().complete(messages, **params)
                result.pop("usage")
                return result
        case = self.by_id["p07"]
        a = run_case(case, "A", MockModel(), "")
        c = run_case(case, "C", Missing(), "")
        summary = summarize([a, c], [case])
        self.assertFalse(summary["complete"])
        self.assertIsNone(summary["arms"]["C"]["mean"]["total_tokens"])
        self.assertIsNone(summary["arms"]["C"]["mean_paired_delta_vs_A"]["total_tokens"])

    def test_loopback_only(self):
        self.assertTrue(is_loopback("http://[::1]:8080/v1"))
        self.assertTrue(is_loopback("http://127.0.0.1:8080/v1"))
        self.assertFalse(is_loopback("https://example.com/v1"))


if __name__ == "__main__":
    unittest.main()
