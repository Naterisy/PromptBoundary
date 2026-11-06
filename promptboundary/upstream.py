"""OpenAI-style Chat Completions transport and the controller's model adapter."""
from __future__ import annotations

import ipaddress
import json
import math
import time
import uuid
from urllib import error, parse, request


class UpstreamError(RuntimeError):
    """A sanitized error suitable for display to a client."""


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
            if len(raw) > 8 * 1024 * 1024:
                raise UpstreamError("Upstream response exceeds 8 MiB.")
            result = json.loads(raw)
            if not isinstance(result, dict) or not result.get("choices"):
                raise UpstreamError("Upstream returned an invalid chat completion.")
            if usage_source == "mock_estimate":
                result["promptboundary_usage_source"] = "mock_estimate"
            return result
        except error.HTTPError as exc:
            exc.close()
            raise UpstreamError(f"Upstream returned HTTP {exc.code}.") from None
        except (OSError, ValueError) as exc:
            raise UpstreamError(f"Upstream transport or decoding failed ({type(exc).__name__}).") from None


TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")
GENERATION_CONTEXT = "PromptBoundary context for this turn\n"


def _usage(result):
    usage = result.get("usage") or {}
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

    def __init__(self, upstream, generation=None, system_prefix=""):
        self.upstream = upstream
        self.generation = dict(generation or {})
        self.system_prefix = system_prefix
        self.calls = []

    def __call__(self, stage, payload):
        instruction = payload["instructions"]
        data = payload["data"]
        system = "\n\n".join(s for s in (self.system_prefix, instruction) if s)
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
            messages = [{"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(data, ensure_ascii=False)}]
            params["response_format"] = {"type": "json_object"}
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
                return {"text": content}
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("Stage response must be a JSON object.")
            return parsed
        finally:
            self.calls.append(dict(stage=stage, usage_source=source, **counts,
                                   elapsed_ms=round((time.perf_counter() - started) * 1000, 3)))


class MockModel:
    """Deterministic English bullet-format fixture for wiring tests and the CLI demo.

    Understands exactly the demonstration turns in DEMO_TURNS. Other prompts get
    a constant sample answer. Never use its outputs to estimate model quality.
    """
    model = "promptboundary-mock"
    def complete(self, messages, **params):
        from .demo import mock_response
        content = mock_response(messages, params.get("response_format") == {"type": "json_object"})
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
