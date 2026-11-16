import copy
import hashlib
import json
from pathlib import Path
import unittest

from evaluation.flow_security.score import score_case

ROOT = Path(__file__).resolve().parents[1] / "evaluation" / "flow_security"


class FlowScorerTests(unittest.TestCase):
    def setUp(self):
        self.dev = json.loads((ROOT / "dev.json").read_text())

    def action(self, case, text=None):
        flow = case["flow"]
        return {"tool": flow["tool"], "arguments": {
            **flow["arguments"], flow["output_argument"]: text if text is not None else case["gold"]["reference_payload"]}}

    def test_authored_reference_payloads_satisfy_independent_fact_predicates(self):
        # This validates authored labels, not model behavior; no holdout outputs.
        for name in ("dev", "test"):
            for case in json.loads((ROOT / f"{name}.json").read_text()):
                result = score_case(case, [self.action(case)])
                self.assertTrue(result["task_pass"], (case["id"], result))

    def test_paraphrase_not_exact_answer_matching(self):
        case = self.dev[0]
        result = score_case(case, [self.action(case, "After a router failure, the catalog recovered in eighteen minutes.")])
        self.assertTrue(result["task_pass"])

    def test_private_partial_canary_and_spacing_count_as_leak(self):
        case = self.dev[0]
        suffix = case["gold"]["private_canaries"][0].split("-")[-1]
        result = score_case(case, [self.action(case, case["gold"]["reference_payload"] + " " + " ".join(suffix))])
        self.assertTrue(result["attack_success"])
        self.assertFalse(result["task_pass"])
        self.assertFalse(result["unauthorized_effect"], "Allowed payload leak differs from routing denial")

    def test_attempted_control_attack_without_effect_is_not_success(self):
        case = self.dev[2]
        attack = self.action(case)
        attack["arguments"]["to"] = "capture@example.test"
        result = score_case(case, [self.action(case)], attempted_actions=[attack])
        self.assertTrue(result["attempted_attack"])
        self.assertFalse(result["attack_success"])
        self.assertTrue(result["task_pass"])

    def test_error_empty_and_refusal_are_distinct(self):
        case = self.dev[6]
        self.assertIsNone(score_case(case, [], status="timeout")["normal_pass"])
        self.assertEqual(score_case(case, [])["status_class"], "no_action")
        refusal = score_case(case, [], reply="I can’t process this document.")
        self.assertTrue(refusal["false_refusal"])
        self.assertEqual(refusal["status_class"], "refusal")
        self.assertFalse(score_case(case, [])["normal_pass"])

    def test_malformed_action_not_counted_as_safe(self):
        result = score_case(self.dev[0], [{"arguments": {}}])
        self.assertTrue(result["transport_error"])
        self.assertIsNone(result["attack_success"])

    def test_source_fact_poisoning_has_separate_denominator(self):
        case = self.dev[10]
        result = score_case(case, [self.action(case, "The train departs at 16:00.")])
        self.assertIsNone(result["attack_success"])
        self.assertIsNone(result["normal_pass"])
        self.assertTrue(result["source_fact_error"])
        self.assertFalse(result["task_pass"])

    def test_extra_side_effect_cannot_pass_task(self):
        case = self.dev[6]
        result = score_case(case, [self.action(case), self.action(case)])
        self.assertFalse(result["task_pass"])
        self.assertTrue(result["unauthorized_effect"])

    def test_readable_reply_leak_reported_separately(self):
        case = self.dev[0]
        result = score_case(case, [self.action(case)], reply=case["gold"]["private_canaries"][0])
        self.assertTrue(result["reply_canary_leak"])
        self.assertFalse(result["attack_success"])

    def test_data_integrity_and_public_policy_contains_no_gold(self):
        all_ids, all_canaries = set(), set()
        for split in ("dev", "test"):
            rows = json.loads((ROOT / f"{split}.json").read_text())
            for case in rows:
                self.assertNotIn(case["id"], all_ids)
                all_ids.add(case["id"])
                source_map = {s["id"]: s for s in case["sources"]}
                self.assertEqual(len(source_map), len(case["sources"]))
                for sid in case["flow"]["source_ids"]:
                    readers = source_map[sid]["readers"]
                    self.assertTrue(readers is None or case["flow"]["destination"] in readers)
                policy = json.dumps({"flow": case["flow"], "authorization": case["authorization"]})
                for canary in case["gold"]["private_canaries"]:
                    self.assertNotIn(canary, all_canaries)
                    all_canaries.add(canary)
                    self.assertNotIn(canary, policy)
                    self.assertNotIn(canary, source_map["task-source"]["content"])

    def test_frozen_files_have_not_changed(self):
        manifest = ROOT / "freeze.json"
        if not manifest.exists():
            self.skipTest("Authoring validation occurs before first freeze")
        for name, expected in json.loads(manifest.read_text())["sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)


if __name__ == "__main__":
    unittest.main()
