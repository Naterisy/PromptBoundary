"""Optional deterministic source-to-argument binding for host-defined copy tasks.

Bindings are application policy, not model output. They narrow existing grants
using original source fields. They do not establish that an external fact is true.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from .capabilities import CapabilitySession, SourceChunk, MAX_TEXT


class BindingError(ValueError):
    """A host field binding is unavailable, ambiguous or exceeds its original grant."""


@dataclass(frozen=True)
class SourceBinding:
    tool: str
    argument: str
    source_id: str
    format: str
    selector: str


@dataclass(frozen=True)
class BoundAuthorization:
    authorization: dict[str, Any]
    provenance: tuple[dict[str, Any], ...]


def bindings_from_spec(spec):
    """Parse a host-owned JSON binding sidecar; never accept this from the model."""
    fields = {"tool", "argument", "source_id", "format", "selector"}
    if not isinstance(spec, list):
        raise BindingError("Host binding metadata must be a list")
    result = []
    for row in spec:
        if not isinstance(row, dict) or set(row) != fields or any(not isinstance(v, str) for v in row.values()):
            raise BindingError("Host binding metadata has invalid fields")
        if any(not row[k] for k in ("tool", "argument", "source_id")) or row["format"] not in ("key_value", "labelled_line", "json_pointer"):
            raise BindingError("Host binding metadata contains an invalid target or grammar")
        result.append(SourceBinding(**row))
    return result


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BindingError("Duplicate key in source JSON")
        result[key] = value
    return result


def _reject_constant(value):
    raise BindingError("Nonfinite number in source JSON")


def extract_field(content: str, format: str, selector: str):
    """Read one scalar using an explicit grammar; refuse ambiguous data."""
    if format == "labelled_line":
        if not isinstance(selector, str) or not selector.strip() or any(x in selector for x in "\r\n"):
            raise BindingError("Invalid labelled-line selector")
        pattern = re.compile(r"^\s*" + re.escape(selector) + r"\s*[:=]\s*(.*)$")
        hits = [match.group(1).strip() for line in content.splitlines() if (match := pattern.fullmatch(line))]
        if len(hits) != 1:
            raise BindingError("Expected exactly one matching source field")
        return hits[0]
    if format == "key_value":
        if not isinstance(selector, str) or not selector or any(x in selector for x in "=\r\n"):
            raise BindingError("Invalid key-value selector")
        hits = []
        for line in content.splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == selector:
                hits.append(value.strip())
        if len(hits) != 1:
            raise BindingError("Expected exactly one matching source field")
        return hits[0]
    if format != "json_pointer":
        raise BindingError("Unsupported source grammar")
    if not isinstance(selector, str) or (selector and not selector.startswith("/")):
        raise BindingError("Invalid JSON Pointer")
    try:
        value = json.loads(content, object_pairs_hook=_unique, parse_constant=_reject_constant)
    except (ValueError, TypeError, RecursionError) as exc:
        raise BindingError("Source is not unambiguous finite JSON") from exc
    for raw in selector.split("/")[1:] if selector else []:
        if re.search(r"~(?![01])", raw):
            raise BindingError("Invalid JSON Pointer escape")
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", key) and int(key) < len(value):
            value = value[int(key)]
        else:
            raise BindingError("Source selector does not exist")
    if type(value) not in (str, bool, int, float, type(None)):
        raise BindingError("Source selector must name a scalar")
    return value


def bind_authorization(authorization, sources, bindings):
    """Resolve host-selected fields and intersect them with existing tool grants.

    No expected answer is accepted. Changing a source field changes the binding;
    provenance records its digest so that this fact is auditable.
    """
    # Validate and detach the original grant first. This API cannot broaden it.
    CapabilitySession.from_dict(authorization, session_id="binding-validation")
    result = json.loads(json.dumps(authorization, ensure_ascii=False, allow_nan=False))
    by_id = {}
    for source in sources:
        if isinstance(source, dict):
            if set(source) != {"kind", "id", "content"}:
                raise BindingError("Source must contain exactly kind, id, content")
            source = SourceChunk(**source)
        if not isinstance(source, SourceChunk) or source.id in by_id:
            raise BindingError("Source IDs must be unique")
        by_id[source.id] = source
    targets = set()
    provenance = []
    for binding in bindings:
        if not isinstance(binding, SourceBinding):
            raise BindingError("Bindings must be host-created SourceBinding objects")
        target = binding.tool, binding.argument
        if target in targets:
            raise BindingError("Multiple bindings for one tool argument")
        targets.add(target)
        if binding.tool not in result["tools"] or binding.argument not in result["tools"][binding.tool]:
            raise BindingError("Binding names an unauthorized tool or argument")
        source = by_id.get(binding.source_id)
        if source is None:
            raise BindingError("Bound source is unavailable")
        value = extract_field(source.content, binding.format, binding.selector)
        previous = result["tools"][binding.tool][binding.argument]
        permitted = (isinstance(value, str) and len(value) <= MAX_TEXT) if previous is None else any(
            type(value) is type(v) and value == v for v in previous)
        if not permitted:
            raise BindingError("Source value exceeds the original host grant")
        result["tools"][binding.tool][binding.argument] = [value]
        provenance.append({"tool": binding.tool, "argument": binding.argument,
                           "source_id": source.id, "source_kind": source.kind,
                           "source_sha256": hashlib.sha256(source.content.encode()).hexdigest(),
                           "format": binding.format, "selector": binding.selector,
                           "value_sha256": hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()})
    return BoundAuthorization(result, tuple(provenance))
