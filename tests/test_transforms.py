import copy
import json
import unittest

from promptboundary.quarantine import FlowSource, WorkerRequest, WorkerRefusal
from promptboundary.reviewed_worker import ReviewProtocolError
from promptboundary.responses import OpenAIResponses
from promptboundary.transforms import OpenAITextWorker, LIMIT, REVIEW_SYSTEM, WORKER_SYSTEM


class Endpoint:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []

    def complete(self, messages, **params):
        self.calls.append((copy.deepcopy(messages), params))
        answer = next(self.answers)
        if isinstance(answer, Exception):
            raise answer
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer)}}]}


class TransformAdapterTests(unittest.TestCase):
    def request(self):
        return WorkerRequest("Summarize the meeting time.", (FlowSource("agenda", "Starts 09:30."),))

    def test_each_request_is_data_only_with_no_tools_or_ambient_history(self):
        endpoint = Endpoint([{"text": "Starts at 09:30.", "refused": False}])
        worker = OpenAITextWorker(endpoint)
        self.assertEqual(worker(self.request()), "Starts at 09:30.")
        messages, params = endpoint.calls[0]
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        self.assertEqual(messages[0]["content"], WORKER_SYSTEM)
        self.assertEqual(json.loads(messages[1]["content"]), self.request().as_dict())
        self.assertEqual(params, {"max_tokens": LIMIT, "response_format": {"type": "json_object"}})
        self.assertEqual(worker.audit_log, [])

    def test_review_repairs_with_fresh_context_and_original_sources(self):
        endpoint = Endpoint([
            {"text": "Starts at 10:30.", "refused": False},
            {"verdict": "revise", "issues": [{"source_id": "agenda", "quote": "09:30", "explanation": "Time differs."}]},
            {"text": "Starts at 09:30.", "refused": False},
            {"verdict": "pass", "issues": []},
        ])
        worker = OpenAITextWorker(endpoint, review=True)
        self.assertEqual(worker(self.request()), "Starts at 09:30.")
        self.assertEqual(len(endpoint.calls), 4)
        for messages, params in endpoint.calls:
            self.assertEqual([m["role"] for m in messages], ["system", "user"])
            payload = json.loads(messages[1]["content"])
            self.assertEqual(payload["task"], self.request().task)
            self.assertEqual(payload["sources"], self.request().as_dict()["sources"])
            self.assertNotIn("tools", params)
            self.assertNotIn("previous_response_id", params)
        self.assertEqual(endpoint.calls[1][0][0]["content"], REVIEW_SYSTEM)
        self.assertEqual(json.loads(endpoint.calls[2][0][1]["content"])["revision_feedback"]["previous_draft"], "Starts at 10:30.")
        self.assertTrue(any(event["event"] == "reviewed" for event in worker.audit_log))
        with self.assertRaises(ReviewProtocolError):
            worker(self.request())

    def test_explicit_refusal_and_malformed_are_separate_failures(self):
        with self.assertRaises(WorkerRefusal):
            OpenAITextWorker(Endpoint([{"text": "Cannot perform this.", "refused": True}]))(self.request())
        for bad in [{"text": "A result", "refused": "false"}, {"text": "", "refused": False}, {"text": "A result"}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                OpenAITextWorker(Endpoint([bad]))(self.request())

    def test_separate_reviewer_endpoint_receives_only_review_requests(self):
        generator = Endpoint([{"text": "Starts at 09:30.", "refused": False}])
        reviewer = Endpoint([{"verdict": "pass", "issues": []}])
        worker = OpenAITextWorker(generator, review=True, review_endpoint=reviewer)
        self.assertEqual(worker(self.request()), "Starts at 09:30.")
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(len(reviewer.calls), 1)
        self.assertEqual(generator.calls[0][0][0]["content"], WORKER_SYSTEM)
        self.assertEqual(reviewer.calls[0][0][0]["content"], REVIEW_SYSTEM)
        self.assertNotIn("draft", json.loads(generator.calls[0][0][1]["content"]))
        self.assertEqual(json.loads(reviewer.calls[0][0][1]["content"])["draft"], "Starts at 09:30.")
        with self.assertRaises(ValueError):
            OpenAITextWorker(generator, review_endpoint=reviewer)

    def test_responses_omits_reasoning_for_nonreasoning_model(self):
        class Capture(OpenAIResponses):
            def exchange(self, body):
                self.body = body
                return {"status": "completed", "output": [{"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": "OK"}]}]}
        for effort in (None, "low"):
            endpoint = Capture("https://api.openai.com/v1", "account-verified-test-id", reasoning_effort=effort)
            endpoint.complete([{"role": "user", "content": "test"}])
            self.assertEqual("reasoning" in endpoint.body, effort is not None)
            if effort is not None:
                self.assertEqual(endpoint.body["reasoning"], {"effort": effort})


if __name__ == "__main__":
    unittest.main()
