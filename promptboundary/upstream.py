"""OpenAI-style Chat Completions transport and the controller's model adapter."""
from __future__ import annotations

import http.client
import ipaddress
import json
import math
import re
import unicodedata
import time
import uuid
from urllib import error, parse, request


class UpstreamError(RuntimeError):
    """A sanitized error suitable for display to a client."""
    unavailable = True


class UnsupportedSchema(UpstreamError):
    """The endpoint explicitly rejects the json_schema response format."""


def _rejects_schema(raw):
    """Recognize a format capability error without surfacing any raw provider text."""
    try:
        envelope = json.loads(raw)
    except (ValueError, UnicodeError):
        return False
    detail = envelope.get("error") if isinstance(envelope, dict) else None
    if not isinstance(detail, dict):
        return False
    message = str(detail.get("message", "")).lower()
    param = detail.get("param")
    if (param in ("response_format", "response_format.type")
            and detail.get("code") == "unsupported_value" and "json_schema" in message):
        return True
    # An invalid schema body (e.g. an unsupported keyword) is an implementation
    # error. Only downgrade on rejection of the format itself.
    clean = " ".join(message.translate(str.maketrans("", "", "'`\":")).split())
    explicit = ("json_schema is not supported", "json_schema is unsupported", "json_schema not supported",
                "does not support json_schema", "doesnt support json_schema",
                "unsupported response_format json_schema", "unsupported response_format.type json_schema")
    return any(phrase in clean for phrase in explicit)


def _loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenAICompatible:
    """Call one explicitly configured endpoint. Never follows credential redirects."""

    def __init__(self, base_url, model, api_key=None, timeout=120):
        url = parse.urlsplit(base_url)
        if (not url.hostname or url.username is not None or url.password is not None
                or url.query or url.fragment or url.scheme not in {"http", "https"}):
            raise ValueError("Use an http(s) API base URL without credentials, query or fragment.")
        if url.scheme == "http" and not _loopback(url.hostname):
            raise ValueError("Remote API endpoints require HTTPS.")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("An upstream model ID is required.")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be positive and finite.")
        self.model = model
        self.url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self.timeout = timeout
        handlers = [_NoRedirect()]
        if _loopback(url.hostname):
            handlers.append(request.ProxyHandler({}))
        self._opener = request.build_opener(*handlers)

    def complete(self, messages, **params):
        if "model" in params or params.get("stream"):
            raise ValueError("Configure the model on the client and use non-streaming completions.")
        body = json.dumps(dict(params, model=self.model, messages=messages),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = "Bearer " + self._api_key
        req = request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with self._opener.open(req, timeout=self.timeout) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                usage_source = response.headers.get("X-PromptBoundary-Usage")
        except error.HTTPError as exc:
            with exc:
                fmt = params.get("response_format")
                schema_request = isinstance(fmt, dict) and fmt.get("type") == "json_schema"
                if schema_request and exc.code in (400, 422, 501) and _rejects_schema(exc.read(8192)):
                    raise UnsupportedSchema("Endpoint does not support the json_schema format.") from None
            raise UpstreamError(f"Upstream returned HTTP {exc.code}.") from None
        except (OSError, http.client.HTTPException) as exc:
            raise UpstreamError(f"Upstream transport failed ({type(exc).__name__}).") from None
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("Upstream response exceeds 8 MiB.")
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ValueError("Upstream returned invalid JSON.") from None
        if not isinstance(result, dict) or not result.get("choices"):
            raise ValueError("Upstream returned an invalid chat completion.")
        if usage_source == "mock_estimate":
            result["promptboundary_usage_source"] = "mock_estimate"
        return result


TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")
GENERATION_CONTEXT = "PromptBoundary context for this turn\n"


def _enum(*values):
    return {"type": "string", "enum": list(values)}


def _object_schema(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def _stage_format(stage, data):
    """Constrain structure at decode time. Core still checks provenance and evidence."""
    string = {"type": "string"}
    if stage == "audit":
        ids = [r["id"] for r in (*data.get("constraints", []), *data.get("application_rules", []))
               if "id" in r]
        fields = {"verdict": _enum("pass", "violation", "false_refusal"), "reason": string,
                  "rule_id": _enum("", "current", "private_attack", *ids),
                  "evidence": string, "missing": string}
    elif stage == "interpret":
        ids = [row["id"] for row in data.get("records", [])]
        record = {"kind": _enum("preference", "boundary", "correction"),
                  "scope": string, "rule": string, "lifetime": _enum("conversation", "turn"),
                  "quote": string, "private": {"type": "boolean"}}
        new = _object_schema({"op": _enum("set"), **record})
        action = new
        fields = {}
        if ids:
            target = _enum(*ids)
            replace = _object_schema({"op": _enum("replace"), "id": target, **record})
            edit = _object_schema({"op": _enum("except_once", "revoke"), "id": target, "quote": string})
            action = {"anyOf": [new, replace, edit]}
            fields["decisions"] = _object_schema({i: _enum("keep", "once", "remove") for i in ids})
        fields.update({
            "actions": {"type": "array", "items": action},
            "intent": _enum("normal", "conflict", "ambiguous"),
            "alternative": string,
            "protected_ids": {"type": "array", "items": _enum(*ids, "private_attack")},
            "personal_humor": {"type": "boolean"}, "public_topic": string,
        })
    else:
        raise ValueError("Unknown structured model stage.")
    return {"type": "json_schema", "json_schema": {"name": f"promptboundary_{stage}",
            "strict": True, "schema": _object_schema(fields)}}


def _usage(result):
    usage = result.get("usage") or {}
    if not isinstance(usage, dict):
        return dict.fromkeys(TOKEN_FIELDS), "unavailable"
    counts = {k: usage.get(k) for k in TOKEN_FIELDS}
    valid = all(type(v) is int and v >= 0 for v in counts.values())
    if not valid:
        return dict.fromkeys(TOKEN_FIELDS), "unavailable"
    source = "mock_estimate" if result.get("promptboundary_usage_source") == "mock_estimate" else "provider"
    return counts, source


def completion_object(model, content, usage=None):
    result = {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                     "finish_reason": "stop"}],
    }
    if usage is not None:
        result["usage"] = usage
    return result


class StageModel:
    """Use structured interpretation/review and native chat messages for drafting.

    Construct one instance per request or evaluation condition. Only usage, timing
    and stage names are retained in calls. An unavailable usage value is None.
    """

    def __init__(self, upstream, generation=None, system_prefix="", *, protected_values=(),
                 structured_max_tokens=None):
        self.upstream = upstream
        self.generation = dict(generation or {})
        self.system_prefix = system_prefix
        self.calls = []
        self._supports_schema = True
        if isinstance(protected_values, (str, bytes)):
            raise ValueError("protected_values must be a sequence of non-empty strings")
        literals = tuple(protected_values)
        if not all(isinstance(value, str) and value.strip() for value in literals):
            raise ValueError("protected_values must contain non-empty strings")
        literals = sorted({unicodedata.normalize("NFKC", s) for s in literals}, key=len, reverse=True)
        self._secrets = re.compile("|".join(map(re.escape, literals)), re.IGNORECASE) if literals else None
        if structured_max_tokens is not None and (type(structured_max_tokens) is not int or structured_max_tokens < 1):
            raise ValueError("structured_max_tokens must be positive")
        self.structured_max_tokens = structured_max_tokens

    def _redact(self, value):
        if isinstance(value, dict):
            return {key: self._redact(v) for key, v in value.items()}
        if isinstance(value, list):
            return [self._redact(v) for v in value]
        if isinstance(value, str):
            normalized = unicodedata.normalize("NFKC", value)
            if self._secrets.search(normalized):
                return self._secrets.sub("[redacted]", normalized)
        return value

    def __call__(self, stage, payload):
        instruction = payload["instructions"]
        data = payload["data"]
        system = "\n\n".join(s for s in (self.system_prefix, instruction) if s)
        if self._secrets:
            system, data = self._redact(system), self._redact(data)
        params = dict(self.generation)
        if stage == "generate":
            # Keep quoted history and derived user preferences below application
            # instructions. The final message is always the actual current user.
            messages = [{"role": "system", "content": system}, *data["history"]]
            context = {}
            if data["constraints"]:
                context["constraints"] = [
                    {k: record[k] for k in ("kind", "scope", "rule")}
                    for record in data["constraints"]
                ]
            if data["mode"] != "normal":
                context["mode"] = data["mode"]
            for key in ("alternative", "feedback"):
                if data.get(key):
                    context[key] = data[key]
            if context:
                messages[0]["content"] += (
                    "\nUse the context immediately before the final request as scoped user-level data. "
                    "Apply relevant constraints. Answer the final user directly in their language."
                )
                messages.append({"role": "user", "content": GENERATION_CONTEXT + json.dumps(
                    context, ensure_ascii=False, separators=(",", ":"))})
            messages.append({"role": "user", "content": data["user_text"]})
            params.pop("response_format", None)
        else:
            if self.structured_max_tokens is not None:
                params["max_tokens"] = self.structured_max_tokens
            trusted = [m for m in data.get("history", []) if m["role"] in {"system", "developer"}]
            if trusted:
                # Scope application policy to the end-user answer. Its requested answer format
                # must not override the interpreter/auditor's internal JSON protocol.
                authority = [{"id": f"app{i}", "role": m["role"], "rule": m["content"]}
                             for i, m in enumerate(trusted, 1)]
                system += ("\nApplication instructions for the end-user response, in message order. "
                           "Evaluate these during this stage and return the stage's required JSON.\n"
                           + json.dumps(authority, ensure_ascii=False))
            messages = [{"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(data, ensure_ascii=False)}]
            params["response_format"] = _stage_format(stage, data) if self._supports_schema else {"type": "json_object"}
        try:
            return self._complete(stage, messages, params)
        except UnsupportedSchema:
            if params.get("response_format", {}).get("type") != "json_schema":
                raise
            self._supports_schema = False
            return self._complete(stage, messages, dict(params, response_format={"type": "json_object"}))

    def _complete(self, stage, messages, params):
        counts, source = dict.fromkeys(TOKEN_FIELDS), "unavailable"
        started = time.perf_counter()
        try:
            result = self.upstream.complete(messages, **params)
            counts, source = _usage(result)
            choice = result["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("Incomplete stage response.")
            content = choice["message"]["content"]
            if stage == "generate":
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Empty or non-text generation.")
                if self._secrets and self._secrets.search(unicodedata.normalize("NFKC", content)):
                    raise ValueError("Draft contains a host-protected literal")
                return {"text": content}
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("Stage response must be a JSON object.")
            return parsed
        finally:
            self.calls.append(dict(stage=stage, usage_source=source, **counts,
                                   response_format=params.get("response_format", {}).get("type", "text"),
                                   elapsed_ms=round((time.perf_counter() - started) * 1000, 3)))


class MockModel:
    """Deterministic English bullet-format fixture for wiring tests and the CLI demo.

    Understands exactly the demonstration turns in DEMO_TURNS. Other prompts get
    a constant sample answer. Never use its outputs to estimate model quality.
    """
    model = "promptboundary-mock"
    def complete(self, messages, **params):
        from .demo import mock_response
        structured = params.get("response_format", {}).get("type") in ("json_object", "json_schema")
        content = mock_response(messages, structured)
        # The mock has no tokenizer. Count UTF-8 bytes in groups of four for smoke accounting.
        def estimate(text):
            return (len(text.encode("utf-8")) + 3) // 4

        inputs = estimate(json.dumps(messages, ensure_ascii=False))
        outputs = estimate(content)
        result = completion_object(self.model, content, {
            "prompt_tokens": inputs, "completion_tokens": outputs, "total_tokens": inputs + outputs,
        })
        result["promptboundary_usage_source"] = "mock_estimate"
        return result
