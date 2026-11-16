"""Host-defined, revocable data-only transformations with labelled egress.

This is a small application-level control/data separation boundary, inspired by
CaMeL. It is not an OS sandbox, an arbitrary program interpreter, or a semantic
truth checker. The host and worker adapter are trusted Python code.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import threading
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .capabilities import CapabilitySession, Execution, MAX_TEXT, SourceChunk

_DESTINATIONS = {"send_email": "to", "write_file": "path", "set_record": "key", "update_record": "record_id"}
_MAX_SOURCE_BYTES = 262144
_MAX_SOURCES = 64


class FlowError(ValueError):
    """A fail-closed workflow error with a non-sensitive machine-readable code."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class WorkerRefusal(FlowError):
    """The adapter detected an explicit refusal; no output is delivered."""
    def __init__(self):
        super().__init__("worker_refusal")


def _digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _identifier(value, code):
    if not isinstance(value, str) or not value or len(value) > 512:
        raise FlowError(code)


def _readers(values):
    if values is None:
        return None
    if not isinstance(values, (tuple, list, set, frozenset)) or any(
        not isinstance(v, str) or not v or len(v) > 512 for v in values
    ):
        raise FlowError("invalid_destination_labels")
    return frozenset(values)


@dataclass(frozen=True)
class FlowSource:
    """The host supplies readers; source text cannot modify its own labels."""
    id: str
    content: str
    readers: frozenset[str] | None = None
    kind: str = "document"

    def __post_init__(self):
        SourceChunk(self.kind, self.id, self.content)
        if len(self.content.encode()) > _MAX_SOURCE_BYTES:
            raise FlowError("source_too_large")
        object.__setattr__(self, "readers", _readers(self.readers))

    def as_dict(self):
        return {"id": self.id, "kind": self.kind, "content": self.content,
                "authority": "none", "allowed_destinations":
                None if self.readers is None else sorted(self.readers)}


@dataclass(frozen=True)
class TransformSpec:
    """A trusted task contract, constructed before observing hostile text.

    Only output_argument is generated. Every other argument is fixed by the host.
    destination_argument maps a reader label to an actual fixed argument value.
    """
    task: str
    source_ids: tuple[str, ...]
    tool: str
    arguments: Mapping[str, Any]
    output_argument: str
    destination: str
    destination_argument: str | None = None

    def __post_init__(self):
        if not isinstance(self.task, str) or not self.task.strip() or len(self.task) > MAX_TEXT:
            raise FlowError("invalid_task")
        if not isinstance(self.source_ids, (tuple, list)) or not 1 <= len(self.source_ids) <= _MAX_SOURCES:
            raise FlowError("invalid_source_ids")
        if any(not isinstance(x, str) or not x for x in self.source_ids) or len(set(self.source_ids)) != len(self.source_ids):
            raise FlowError("invalid_source_ids")
        _identifier(self.destination, "invalid_destination")
        if not isinstance(self.arguments, Mapping) or self.output_argument in self.arguments:
            raise FlowError("invalid_fixed_arguments")
        try:
            args = json.loads(json.dumps(dict(self.arguments), allow_nan=False))
            rules = {key: [value] for key, value in args.items()}
            rules[self.output_argument] = None
            CapabilitySession({"tools": {self.tool: rules}}, session_id="spec-check")
        except (TypeError, ValueError, RecursionError) as error:
            raise FlowError("invalid_tool_contract") from error
        dest_arg = self.destination_argument or _DESTINATIONS.get(self.tool)
        if not isinstance(dest_arg, str) or dest_arg not in args or type(args[dest_arg]) is not str or args[dest_arg] != self.destination:
            raise FlowError("destination_argument_mismatch")
        object.__setattr__(self, "source_ids", tuple(self.source_ids))
        object.__setattr__(self, "arguments", MappingProxyType(args))
        object.__setattr__(self, "destination_argument", dest_arg)


@dataclass(frozen=True)
class WorkerRequest:
    """Only selected data and the host transformation; no tools or conversation."""
    task: str
    sources: tuple[FlowSource, ...]

    def as_dict(self):
        return {"task": self.task, "sources": [source.as_dict() for source in self.sources]}


@dataclass(frozen=True, eq=False)
class TurnHandle:
    """An in-process capability; serialized/copied handles have no authority."""
    epoch: int


@dataclass(frozen=True, eq=False)
class Artifact:
    """Generated text retains all source restrictions, never instruction authority."""
    text: str
    source_ids: tuple[str, ...]
    readers: frozenset[str] | None
    epoch: int


class QuarantinedWorkflow:
    """One authorized transformation per turn, with revocation and one-shot egress.

    The worker callback must start a fresh model request containing only the
    WorkerRequest. Do not give it ambient history, previous_response_id, tools,
    secrets or privileged callbacks. This library cannot sandbox Python callbacks.
    """
    def __init__(self, *, session_id: str):
        _identifier(session_id, "invalid_session_id")
        if len(session_id) > 100:
            raise FlowError("invalid_session_id")
        self.session_id = session_id
        self._epoch = 0
        self._sources: dict[str, FlowSource] = {}
        self._lineage: dict[str, tuple[str, ...]] = {}
        self._events: list[dict] = []
        self._current: TurnHandle | None = None
        self._spec: TransformSpec | None = None
        self._artifact: Artifact | None = None
        self._capability: CapabilitySession | None = None
        self._busy = False
        self._lock = threading.RLock()

    @property
    def audit_log(self):
        with self._lock:
            return json.loads(json.dumps(self._events))

    def _event(self, event, **details):
        self._events.append({"event": event, "session_id": self.session_id,
                             "epoch": self._epoch, **details})

    def add_source(self, source: FlowSource):
        if not isinstance(source, FlowSource):
            raise FlowError("expected_flow_source")
        with self._lock:
            if source.id in self._sources:
                raise FlowError("source_id_already_registered")
            if len(self._sources) >= _MAX_SOURCES:
                raise FlowError("source_limit")
            self._sources[source.id] = source
            self._lineage[source.id] = (source.id,)
        return source

    def _check(self, handle):
        if not isinstance(handle, TurnHandle) or handle is not self._current:
            raise FlowError("stale_or_foreign_handle")

    def authorize(self, spec: TransformSpec):
        """Authenticated host call only; even a denied new contract revokes the old turn.

        If constructing TransformSpec itself fails before this method is called,
        the host must call revoke() when accepting a replacement user request.
        """
        with self._lock:
            self._epoch += 1
            self._current = self._spec = self._artifact = self._capability = None
            self._busy = False
            if not isinstance(spec, TransformSpec):
                self._event("authorization_denied", reason="expected_transform_spec")
                raise FlowError("expected_transform_spec")
            missing = set(spec.source_ids) - set(self._sources)
            if missing:
                raise FlowError("source_unavailable")
            sources = [self._sources[x] for x in spec.source_ids]
            if any(source.readers is not None and spec.destination not in source.readers for source in sources):
                self._event("authorization_denied", reason="source_destination_denied")
                raise FlowError("source_destination_denied")
            if sum(len(source.content.encode()) for source in sources) > _MAX_SOURCE_BYTES:
                raise FlowError("input_too_large")
            self._current = TurnHandle(self._epoch)
            self._spec = spec
            self._artifact = None
            self._busy = False
            rules = {key: [value] for key, value in spec.arguments.items()}
            rules[spec.output_argument] = None
            self._capability = CapabilitySession({"tools": {spec.tool: rules}},
                                                 session_id=f"{self.session_id}:{self._epoch}")
            for source in sources:
                self._capability.add_source(SourceChunk(source.kind, source.id, source.content))
            self._event("authorized", tool=spec.tool, destination=spec.destination,
                        source_ids=list(spec.source_ids), task_sha256=_digest(spec.task))
            return self._current

    def revoke(self):
        """Invalidate pending work; effects already begun cannot be rolled back."""
        with self._lock:
            self._epoch += 1
            self._current = self._spec = self._artifact = self._capability = None
            self._busy = False
            self._event("revoked")

    def prepare(self, handle: TurnHandle):
        with self._lock:
            self._check(handle)
            return WorkerRequest(self._spec.task, tuple(self._sources[x] for x in self._spec.source_ids))

    def transform(self, handle: TurnHandle, worker: Callable[[WorkerRequest], str]):
        """Run a data-only callback; explicit WorkerRefusal never yields an artifact."""
        with self._lock:
            self._check(handle)
            if self._busy or self._artifact is not None:
                raise FlowError("transformation_already_started")
            request = self.prepare(handle)
            self._busy = True
        try:
            text = worker(request)
            if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
                raise FlowError("invalid_worker_output")
        except Exception as error:
            with self._lock:
                if handle is self._current:
                    self._busy = False
                self._event("worker_failed", handle_epoch=handle.epoch,
                            reason=error.code if isinstance(error, FlowError) else type(error).__name__)
            raise
        with self._lock:
            self._check(handle)  # Reauthorization during the request discards the result.
            self._busy = False
            restricted = [s.readers for s in request.sources if s.readers is not None]
            readers = frozenset.intersection(*restricted) if restricted else None
            lineage = tuple(dict.fromkeys(x for s in request.sources for x in self._lineage[s.id]))
            self._artifact = Artifact(text, lineage, readers, self._epoch)
            self._event("transformed", output_sha256=_digest(text), source_ids=list(lineage),
                        allowed_destinations=None if readers is None else sorted(readers))
            return self._artifact

    def retain(self, handle: TurnHandle, artifact: Artifact, *, source_id: str):
        """Host opt-in reuse as data. Provenance and restrictions survive chaining."""
        with self._lock:
            self._check_artifact(handle, artifact)
            source = FlowSource(source_id, artifact.text, artifact.readers, kind="assistant")
            self.add_source(source)
            self._lineage[source_id] = artifact.source_ids
            self._event("retained_as_data", source_id=source_id,
                        ancestors=list(artifact.source_ids), authority="none")
            return source

    def _check_artifact(self, handle, artifact):
        self._check(handle)
        if not isinstance(artifact, Artifact) or artifact is not self._artifact:
            raise FlowError("foreign_or_forged_artifact")
        if artifact.readers is not None and self._spec.destination not in artifact.readers:
            raise FlowError("artifact_destination_denied")

    def execute(self, handle: TurnHandle, artifact: Artifact,
                registry: Mapping[str, Callable[..., Any]]) -> Execution:
        """Compose one fixed action. Worker text is never parsed as an action plan."""
        with self._lock:
            self._check_artifact(handle, artifact)
            args = dict(self._spec.arguments)
            args[self._spec.output_argument] = artifact.text
            plan = {"actions": [{"tool": self._spec.tool, "arguments": args}]}
            result = self._capability.execute(plan, registry)
            self._event("execution", authorized=result.authorized, completed=result.completed,
                        reasons=list(result.decision.reasons), error=result.error,
                        output_sha256=_digest(artifact.text))
            return result
