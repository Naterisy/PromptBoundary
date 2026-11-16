"""Optional bounded semantic review of a data-only worker's text.

A model's verdict is a fallible quality check, never authority to act. The hard
execution boundary remains QuarantinedWorkflow. No API calls occur here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import threading
from typing import Callable

from .capabilities import MAX_TEXT
from .quarantine import WorkerRequest, WorkerRefusal


class ReviewProtocolError(ValueError):
    """Malformed or ungrounded review: classify as an error, not safe refusal."""


@dataclass(frozen=True)
class ReviewRequest:
    """Fresh reviewer context: original selected sources, task and untrusted draft."""
    task: str
    sources: tuple
    draft: str

    def as_dict(self):
        return {"task": self.task, "sources": [source.as_dict() for source in self.sources],
                "draft": self.draft}


def _digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        raise ReviewProtocolError("invalid_worker_output")
    return value


def _review(value, request):
    """Validate only syntax and quoted evidence, not semantic correctness."""
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode()) > 32768:
            raise ValueError("oversized")
        result = json.loads(encoded)
    except (TypeError, ValueError, RecursionError) as error:
        raise ReviewProtocolError("invalid_review_json") from error
    if (not isinstance(result, dict) or set(result) != {"verdict", "issues"}
            or result["verdict"] not in ("pass", "revise", "refuse")
            or not isinstance(result["issues"], list) or len(result["issues"]) > 8):
        raise ReviewProtocolError("invalid_review_envelope")
    if result["verdict"] == "pass" and result["issues"]:
        raise ReviewProtocolError("pass_with_unresolved_issues")
    if result["verdict"] == "revise" and not result["issues"]:
        raise ReviewProtocolError("revision_requires_evidence")
    sources = {source.id: source.content for source in request.sources}
    for issue in result["issues"]:
        if (not isinstance(issue, dict) or set(issue) != {"source_id", "quote", "explanation"}
                or any(not isinstance(v, str) for v in issue.values())
                or issue["source_id"] not in sources
                or not issue["quote"].strip() or len(issue["quote"]) > 2048
                or not issue["explanation"].strip() or len(issue["explanation"]) > 2048):
            raise ReviewProtocolError("invalid_review_issue")
        if issue["quote"] not in sources[issue["source_id"]]:
            raise ReviewProtocolError("review_quote_not_in_source")
    return result


class ReviewedWorker:
    """Single-use worker: draft, review, at most one revision, final explicit pass.

    generate(request: WorkerRequest, feedback: dict | None) -> str
    review(request: ReviewRequest) -> {verdict, issues}

    Each callback must use a fresh, data-only context with no tools or ambient
    history. Feedback is untrusted data; never promote it to system authority.
    The caller meters/journals every model call, including refusals and failures.
    A new instance is required for another host-authorized transformation.
    """
    def __init__(self, generate: Callable, review: Callable, *, max_revisions: int = 1):
        if not callable(generate) or not callable(review):
            raise ValueError("Expected generation and review callbacks")
        if type(max_revisions) is not int or max_revisions not in (0, 1):
            raise ValueError("Only zero or one revision is supported")
        self._generate = generate
        self._review = review
        self._max_revisions = max_revisions
        self._events = []
        self._started = False
        self._lock = threading.Lock()

    @property
    def audit_log(self):
        with self._lock:
            return json.loads(json.dumps(self._events))

    def _event(self, event, **details):
        with self._lock:
            self._events.append({"event": event, **details})

    def __call__(self, request: WorkerRequest):
        with self._lock:
            if self._started:
                raise ReviewProtocolError("reviewed_worker_already_used")
            self._started = True
        if not isinstance(request, WorkerRequest):
            raise ReviewProtocolError("expected_worker_request")
        feedback = None
        try:
            for revision in range(self._max_revisions + 1):
                draft = _text(self._generate(request, feedback))
                self._event("drafted", revision=revision, draft_sha256=_digest(draft))
                if feedback is not None and draft == feedback["previous_draft"]:
                    # A later stochastic pass must not erase an earlier rejection
                    # without any change to the rejected candidate.
                    self._event("withheld", reason="unchanged_revision", revision=revision)
                    raise WorkerRefusal()
                review_request = ReviewRequest(request.task, request.sources, draft)
                result = _review(self._review(review_request), review_request)
                self._event("reviewed", revision=revision, verdict=result["verdict"],
                            issues=[{"source_id": issue["source_id"],
                                     "quote_sha256": _digest(issue["quote"]),
                                     "explanation_sha256": _digest(issue["explanation"])}
                                    for issue in result["issues"]])
                if result["verdict"] == "pass":
                    return draft
                if result["verdict"] == "refuse" or revision == self._max_revisions:
                    self._event("withheld", reason="review_no_pass", revision=revision)
                    raise WorkerRefusal()
                # This object is data from the reviewer, not a grant or a new task.
                feedback = {"previous_draft": draft, "issues": result["issues"]}
        except Exception as error:
            self._event("failed", error=type(error).__name__)
            raise
