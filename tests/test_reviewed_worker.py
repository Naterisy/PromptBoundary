"""Bounded review invariants; no model calls or frozen evaluation fixtures."""
import unittest

from promptboundary.quarantine import FlowSource, QuarantinedWorkflow, TransformSpec, WorkerRefusal, WorkerRequest
from promptboundary.reviewed_worker import ReviewedWorker, ReviewProtocolError


def request():
    return WorkerRequest("Summarize the incident.", (FlowSource("source", "Seven tickets remain open."),))


def revise():
    return {"verdict": "revise", "issues": [{"source_id": "source", "quote": "Seven tickets remain open.",
                "explanation": "The draft incorrectly says all tickets are closed."}]}


class ReviewedWorkerTests(unittest.TestCase):
    def test_pass_preserves_draft_and_context_is_only_task_sources_draft(self):
        contexts = []
        def review(req):
            contexts.append(req.as_dict())
            return {"verdict": "pass", "issues": []}
        worker = ReviewedWorker(lambda req, feedback: "Seven open tickets.", review)
        self.assertEqual(worker(request()), "Seven open tickets.")
        self.assertEqual(set(contexts[0]), {"task", "sources", "draft"})
        self.assertEqual(contexts[0]["sources"][0]["authority"], "none")
        self.assertEqual(worker.audit_log[-1]["verdict"], "pass")

    def test_one_repair_uses_literal_grounded_feedback_and_requires_second_review(self):
        generation, reviews = [], []
        def generate(req, feedback):
            generation.append(feedback)
            return "All closed." if feedback is None else "Seven remain open."
        def review(req):
            reviews.append(req.draft)
            return revise() if req.draft == "All closed." else {"verdict": "pass", "issues": []}
        worker = ReviewedWorker(generate, review)
        self.assertEqual(worker(request()), "Seven remain open.")
        self.assertEqual(len(generation), 2)
        self.assertEqual(len(reviews), 2)
        self.assertEqual(generation[1], {"previous_draft": "All closed.", "issues": revise()["issues"]})

    def test_second_revision_request_withholds_without_infinite_retry(self):
        generated = []
        worker = ReviewedWorker(lambda req, feedback: generated.append(1) or f"All closed, draft {len(generated)}.",
                                lambda req: revise())
        with self.assertRaises(WorkerRefusal):
            worker(request())
        self.assertEqual(len(generated), 2)
        self.assertEqual(worker.audit_log[-2]["event"], "withheld")

    def test_unchanged_rejected_draft_cannot_be_rehabilitated_by_another_review(self):
        reviews, feedbacks = [], []
        def generate(req, feedback):
            feedbacks.append(feedback)
            return "All closed."
        def review(req):
            reviews.append(req.draft)
            return revise() if len(reviews) == 1 else {"verdict": "pass", "issues": []}
        worker = ReviewedWorker(generate, review)
        with self.assertRaises(WorkerRefusal):
            worker(request())
        self.assertEqual(len(feedbacks), 2)
        self.assertEqual(feedbacks[1]["previous_draft"], "All closed.")
        self.assertEqual(len(reviews), 1)
        self.assertEqual(worker.audit_log[-2]["reason"], "unchanged_revision")

    def test_explicit_refusal_never_reaches_executor(self):
        runtime = QuarantinedWorkflow(session_id="review")
        runtime.add_source(request().sources[0])
        handle = runtime.authorize(TransformSpec("Summarize the incident.", ("source",), "send_email",
            {"to": "ops@example.test"}, "body", "ops@example.test"))
        worker = ReviewedWorker(lambda req, feedback: "All closed.", lambda req: {"verdict": "refuse", "issues": []})
        with self.assertRaises(WorkerRefusal):
            runtime.transform(handle, worker)
        self.assertEqual(runtime.audit_log[-1]["reason"], "worker_refusal")
        self.assertFalse(any(x["event"] == "execution" for x in runtime.audit_log))

    def test_forged_evidence_unknown_source_or_authority_fields_are_errors(self):
        bad = [
            {"verdict": "pass", "issues": [], "tools": ["send_email"]},
            {"verdict": "pass", "issues": revise()["issues"]},
            {"verdict": "revise", "issues": []},
            {"verdict": "revise", "issues": [{"source_id": "other", "quote": "Secret", "explanation": "Use it"}]},
            {"verdict": "revise", "issues": [{"source_id": "source", "quote": "Eighteen tickets", "explanation": "Not present"}]},
            {"verdict": "refuse", "issues": [{"source_id": "source", "quote": "", "explanation": "Blank anchor"}]},
        ]
        for response in bad:
            with self.subTest(response=response), self.assertRaises(ReviewProtocolError):
                ReviewedWorker(lambda req, feedback: "Summary", lambda req: response)(request())

    def test_reviewer_prompt_injection_can_still_falsely_approve(self):
        # An explicit negative property: the runtime cannot certify semantic truth.
        worker = ReviewedWorker(lambda req, feedback: "All tickets closed, contrary to the source.",
                                lambda req: {"verdict": "pass", "issues": []})
        self.assertIn("All tickets closed", worker(request()))

    def test_invalid_worker_output_is_protocol_error_not_refusal(self):
        for output in ["", " ", None, {"text": "wrong type"}, "x" * 8193]:
            with self.subTest(output_type=type(output).__name__), self.assertRaises(ReviewProtocolError):
                ReviewedWorker(lambda req, feedback: output,
                               lambda req: {"verdict": "pass", "issues": []})(request())

    def test_no_revision_mode_and_single_use_bound_calls(self):
        worker = ReviewedWorker(lambda req, feedback: "Bad draft", lambda req: revise(), max_revisions=0)
        with self.assertRaises(WorkerRefusal):
            worker(request())
        with self.assertRaisesRegex(ReviewProtocolError, "already_used"):
            worker(request())
        for invalid in [True, -1, 2, 1.0]:
            with self.assertRaises(ValueError):
                ReviewedWorker(lambda a, b: "", lambda a: {}, max_revisions=invalid)

    def test_review_exceptions_and_untrusted_prose_do_not_leak_into_audit(self):
        def failed(req):
            raise RuntimeError("PRIVATE_EXCEPTION_DETAILS")
        worker = ReviewedWorker(lambda req, feedback: "Private draft", failed)
        with self.assertRaises(RuntimeError):
            worker(request())
        audit = worker.audit_log
        self.assertNotIn("Private draft", str(audit))
        self.assertNotIn("PRIVATE_EXCEPTION", str(audit))
        audit[0]["draft_sha256"] = "modified"
        self.assertNotEqual(worker.audit_log[0]["draft_sha256"], "modified")


if __name__ == "__main__":
    unittest.main()
