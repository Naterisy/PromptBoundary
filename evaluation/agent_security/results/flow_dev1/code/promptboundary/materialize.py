"""Materialize host-declared literal-copy arguments from already resolved sources.

This deterministic data operation never adds actions or grants. Always pass its
result through CapabilitySession.execute before using a real tool callback.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

from .capabilities import MAX_ACTIONS, MAX_PLAN_BYTES, MAX_TEXT
from .source_binding import BoundAuthorization


class MaterializationError(ValueError):
    """The plan cannot be safely treated as a well-formed literal-copy proposal."""


@dataclass(frozen=True)
class MaterializedPlan:
    plan: dict[str, Any]
    replacements: tuple[dict[str, Any], ...]
    reply_removed: bool = False


def _encode(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError) as error:
        raise MaterializationError("Plan must be finite JSON") from error


def _digest(value):
    return hashlib.sha256(_encode(value).encode()).hexdigest()


def _scalar(value):
    return value is None or type(value) in (str, int, bool) or (type(value) is float and math.isfinite(value))


def materialize_bound_plan(plan, bound: BoundAuthorization):
    """Replace only existing, explicitly bound literal-copy arguments.

    The original host binding was resolved without an expected-answer oracle.
    Unknown tools and other unauthorized argument values remain unauthorized;
    this function is not a permission checker and performs no side effects.
    """
    if not isinstance(bound, BoundAuthorization):
        raise MaterializationError("Expected a host-resolved BoundAuthorization")
    encoded = _encode(plan)
    if len(encoded.encode()) > MAX_PLAN_BYTES:
        raise MaterializationError("Plan exceeds the size limit")
    detached = json.loads(encoded)
    if not isinstance(detached, dict) or "actions" not in detached or set(detached) - {"actions", "reply"}:
        raise MaterializationError("Invalid plan fields")
    if "reply" in detached and (not isinstance(detached["reply"], str) or len(detached["reply"]) > MAX_TEXT):
        raise MaterializationError("Invalid reply")
    actions = detached["actions"]
    if not isinstance(actions, list) or len(actions) > MAX_ACTIONS:
        raise MaterializationError("Invalid actions")
    targets = {}
    for evidence in bound.provenance:
        target = evidence["tool"], evidence["argument"]
        if target in targets:
            raise MaterializationError("Ambiguous binding target")
        try:
            choices = bound.authorization["tools"][target[0]][target[1]]
        except (KeyError, TypeError) as error:
            raise MaterializationError("Binding does not name a resolved authorized argument") from error
        if not isinstance(choices, list) or len(choices) != 1 or not _scalar(choices[0]):
            raise MaterializationError("Binding must resolve to one scalar")
        targets[target] = choices[0], evidence
    replacements = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or set(action) != {"tool", "arguments"}:
            raise MaterializationError("Invalid action fields")
        tool, arguments = action["tool"], action["arguments"]
        if not isinstance(tool, str) or not isinstance(arguments, dict) or any(
            not isinstance(k, str) or not _scalar(v) for k, v in arguments.items()
        ):
            raise MaterializationError("Invalid tool or argument types")
        for (target_tool, argument), (canonical, evidence) in targets.items():
            if tool != target_tool:
                continue
            if argument not in arguments:
                raise MaterializationError("Cannot synthesize a missing bound argument")
            previous = arguments[argument]
            if type(previous) is not type(canonical):
                raise MaterializationError("Bound argument has the wrong JSON type")
            if previous != canonical:
                arguments[argument] = canonical
                replacements.append({"action_index": index, "tool": tool, "argument": argument,
                                     "previous_sha256": _digest(previous), "resolved_sha256": _digest(canonical),
                                     "source_id": evidence["source_id"], "source_sha256": evidence["source_sha256"],
                                     "format": evidence["format"], "selector": evidence["selector"]})
    # A model acknowledgement may describe the pre-materialization action. The
    # host can issue a factual receipt only after the real callback completes.
    reply_removed = bool(replacements) and "reply" in detached
    if reply_removed:
        detached.pop("reply")
    if len(_encode(detached).encode()) > MAX_PLAN_BYTES:
        raise MaterializationError("Materialized plan exceeds the size limit")
    return MaterializedPlan(detached, tuple(replacements), reply_removed)
