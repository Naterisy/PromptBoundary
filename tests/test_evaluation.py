from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evaluation.run import (HERE, VerifiedBackend, checked_rows, is_loopback, measures,
                            read, run_case, save, summarize, verify_freeze)
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

    def test_rejects_stale_rows_or_score_drift(self):
        case = self.by_id["p01"]
        row = dict(run_case(case, "A", MockModel(), ""), snapshot="version2")
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            path = directory / "p01-A.json"
            save(path, row)
            self.assertEqual(len(checked_rows(directory, [case], "version2", "mock_wiring_only")), 1)
            for change in ({"snapshot": "old"}, {"arm": "B"}, {"case": "other"},
                           {"answer": "Saffron"}, {"score": {"task_pass": 1}}):
                with self.subTest(change=change):
                    save(path, dict(row, **change))
                    with self.assertRaises(ValueError):
                        checked_rows(directory, [case], "version2", "mock_wiring_only")
            save(path, row)
            with self.assertRaisesRegex(ValueError, "Fixture usage"):
                checked_rows(directory, [case], "version2", "model")
            save(directory / "duplicate.json", row)
            with self.assertRaisesRegex(ValueError, "Unexpected row filename"):
                checked_rows(directory, [case], "version2", "mock_wiring_only")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            summarize([row, row], [case])

    def test_measured_mode_rejects_fixture_signals(self):
        class Stub:
            model = "some-alias"
            def __init__(self, response):
                self.response = response
                self.n = 0
            def complete(self, messages, **params):
                self.n += 1
                return self.response

        for response in ({"model": MockModel.model}, {"promptboundary_usage_source": "mock_estimate"}):
            stub = Stub(response)
            guard = VerifiedBackend(stub)
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, "Fixture endpoint"):
                    guard.complete([])
            self.assertTrue(guard.fixture_detected)
            self.assertEqual(stub.n, 1)
        guard = VerifiedBackend(Stub({"model": "real-model"}))
        self.assertEqual(guard.complete([]), {"model": "real-model"})

    def test_loopback_only(self):
        self.assertTrue(is_loopback("http://[::1]:8080/v1"))
        self.assertTrue(is_loopback("http://127.0.0.1:8080/v1"))
        self.assertFalse(is_loopback("https://example.com/v1"))


if __name__ == "__main__":
    unittest.main()
