"""OpenAI Responses API transport for the existing text-only StageModel interface."""
from __future__ import annotations

import http.client
import json
from urllib.error import HTTPError
from urllib.request import Request

from .upstream import OpenAICompatible, UpstreamError


def chat_result(response):
    """Extract assistant text or explicit refusal, ignoring non-message reasoning items."""
    parts, refusals = [], []
    if not isinstance(response, dict) or not isinstance(response.get("output"), list):
        raise UpstreamError("Malformed Responses API result.")
    for item in response["output"]:
        if item.get("type") == "message" and item.get("role") == "assistant":
            for part in item["content"]:
                if part.get("type") == "output_text":
                    parts.append(part["text"])
                elif part.get("type") == "refusal":
                    refusals.append(part["refusal"])
    status = response.get("status")
    if status == "completed":
        if not parts and not refusals:
            raise UpstreamError("Provider completed without assistant content.")
        finish = "stop"
    elif status == "incomplete":
        finish = "length" if (response.get("incomplete_details") or {}).get("reason") == "max_output_tokens" else "content_filter"
    else:
        raise UpstreamError(f"Unexpected Responses API status: {status!r}.")
    message = {"role": "assistant", "content": "".join(parts + refusals)}
    if refusals:
        message["refusal"] = "".join(refusals)
    usage = response.get("usage") or {}
    return {"model": response.get("model"), "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": usage.get("input_tokens"), "completion_tokens": usage.get("output_tokens"),
                      "total_tokens": usage.get("total_tokens")}}


class OpenAIResponses(OpenAICompatible):
    """Never follows redirects. Override exchange() to journal synthetic evaluation traffic."""
    def __init__(self, base_url, model, api_key=None, timeout=120, reasoning_effort="low"):
        super().__init__(base_url, model, api_key, timeout)
        self.url = base_url.rstrip("/") + "/responses"
        self.effort = reasoning_effort

    def complete(self, messages, **params):
        unsupported = params.keys() - {"max_tokens", "response_format", "temperature", "top_p"}
        if unsupported:
            raise ValueError(f"Unsupported Responses options: {sorted(unsupported)}")
        body = {"model": self.model, "input": messages, "store": False, "service_tier": "default",
                "reasoning": {"effort": self.effort}, "max_output_tokens": params.get("max_tokens", 1024)}
        for name in ("temperature", "top_p"):
            if name in params:
                body[name] = params[name]
        fmt = params.get("response_format")
        if fmt:
            body["text"] = {"format": ({"type": "json_schema", **fmt["json_schema"]}
                                       if fmt["type"] == "json_schema" else fmt)}
        return chat_result(self.exchange(body))

    def exchange(self, body):
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = "Bearer " + self._api_key
        request = Request(self.url, json.dumps(body, ensure_ascii=False, allow_nan=False).encode(), headers)
        try:
            with self._opener.open(request, timeout=self.timeout) as resp:
                raw = resp.read(8 * 1024 * 1024 + 1)
        except HTTPError as exc:
            with exc:
                try:
                    err = json.loads(exc.read(8192)).get("error", {})
                except (ValueError, AttributeError):
                    err = {}
                # Return the code/parameter for diagnosis, never credential-bearing free text.
                raise UpstreamError(f"Responses HTTP {exc.code}, code={err.get('code')!r}, param={err.get('param')!r}") from None
        except (OSError, http.client.HTTPException) as exc:
            raise UpstreamError(f"Responses transport failed ({type(exc).__name__}).") from None
        if len(raw) > 8 * 1024 * 1024:
            raise UpstreamError("Responses payload exceeds 8 MiB.")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise UpstreamError("Responses endpoint returned invalid JSON.") from None
