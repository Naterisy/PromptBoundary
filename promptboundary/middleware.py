"""Stateless, loopback-only OpenAI-style Chat Completions HTTP middleware."""
from __future__ import annotations

import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import BoundaryController, ProtocolError, State
from .upstream import StageModel, TOKEN_FIELDS, completion_object


class ClientError(ValueError):
    """Invalid or unsupported chat request."""


MAX_BYTES = 256 * 1024
MAX_MESSAGES = 32
ALLOWED_OPTIONS = {"temperature", "top_p", "max_tokens", "seed"}
ALLOWED_FIELDS = {"model", "messages", "n", "stream", *ALLOWED_OPTIONS}


def _messages(value):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_MESSAGES:
        raise ClientError(f"Provide between 1 and {MAX_MESSAGES} text messages.")
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"role", "content"}:
            raise ClientError("Each message must contain exactly role and content.")
        role, content = item["role"], item["content"]
        if role not in ("user", "assistant", "developer", "system") or not isinstance(content, str):
            raise ClientError("Only user, assistant, developer and system text messages are supported.")
        result.append({"role": role, "content": content})
    if result[-1]["role"] != "user" or not result[-1]["content"].strip():
        raise ClientError("The final message must contain user text.")
    return result


def _generation(body):
    if not isinstance(body, dict):
        raise ClientError("The request must be a JSON object.")
    if set(body) - ALLOWED_FIELDS:
        raise ClientError("Unsupported request field. See the documented chat subset.")
    if body.get("stream", False) is not False:
        raise ClientError("Only non-streaming completions are supported.")
    if type(body.get("n", 1)) is not int or body.get("n", 1) != 1:
        raise ClientError("Only one choice per request is supported.")
    opts = {k: body[k] for k in ALLOWED_OPTIONS if k in body}
    for key, maximum in (("temperature", 2), ("top_p", 1)):
        if key in opts and (type(opts[key]) not in (int, float) or
                            not (0 <= opts[key] <= maximum) or not math.isfinite(opts[key])):
            raise ClientError(f"{key} must be a number between 0 and {maximum}.")
    if "seed" in opts and type(opts["seed"]) is not int:
        raise ClientError("seed must be an integer.")
    if "max_tokens" in opts and (type(opts["max_tokens"]) is not int or opts["max_tokens"] <= 0):
        raise ClientError("max_tokens must be a positive integer.")
    return opts


def handle_chat(upstream, body, *, system_prefix="", max_retries=1, protected_values=()):
    """Return (OpenAI completion, boundary status, usage source). No shared conversation state."""
    opts = _generation(body)
    if body.get("model") != upstream.model:
        raise ClientError("Use the model ID listed by GET /v1/models.")
    messages = _messages(body.get("messages"))
    # The HTTP client's max_tokens controls the user-visible answer. Internal JSON
    # decisions need room to express a grounded verdict, even for a one-word task.
    structured_limit = max(512, opts["max_tokens"]) if "max_tokens" in opts else None
    model = StageModel(upstream, opts, system_prefix=system_prefix, protected_values=protected_values,
                       structured_max_tokens=structured_limit)
    controller = BoundaryController(model, max_retries=max_retries)
    state = State()
    history = messages[:-1]
    for i, message in enumerate(history):
        if message["role"] == "user":
            state = controller.observe(state, message["content"], history=history[:i])
    turn = controller.run(state, messages[-1]["content"], history=history)
    sources = {c["usage_source"] for c in model.calls}
    usage = None
    if model.calls and "unavailable" not in sources:
        usage = {k: sum(c[k] for c in model.calls) for k in TOKEN_FIELDS}
    source = next(iter(sources)) if len(sources) == 1 else "mixed_or_unavailable"
    return completion_object(upstream.model, turn.text, usage), turn.status, source


def make_server(upstream, host="127.0.0.1", port=8080, *, system_prefix="", max_retries=1, protected_values=()):
    """Create the loopback server. The caller controls serve_forever/shutdown."""
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("The middleware binds to IPv4 loopback only.")

    # Materialize once: request-local adapters must all receive the same policy,
    # including when the host supplied a generator.
    if isinstance(protected_values, (str, bytes)):
        raise ValueError("protected_values must be a sequence of non-empty strings")
    protected_values = tuple(protected_values)

    class Handler(BaseHTTPRequestHandler):
        server_version = "PromptBoundary/0.1"

        def log_message(self, format, *args):
            # Paths, bodies and incoming credentials must stay out of logs.
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def _reply(self, status, value, headers=None):
            data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for key, val in (headers or {}).items():
                self.send_header(key, val)
            self.end_headers()
            self.wfile.write(data)

        def _error(self, status, message, kind="invalid_request_error"):
            self._reply(status, {"error": {"message": message, "type": kind,
                                          "param": None, "code": None}})

        def _valid_host(self):
            h = self.headers.get("Host", "").split(":", 1)[0].lower()
            if h in ("localhost", "127.0.0.1"):
                return True
            self._error(403, "Use a loopback Host header.")
            return False

        def do_GET(self):
            if not self._valid_host():
                return
            if self.path != "/v1/models":
                return self._error(404, "Unknown path.")
            self._reply(200, {"object": "list", "data": [{"object": "model", "id": upstream.model,
                                                          "created": 0, "owned_by": "local"}]})

        def do_POST(self):
            if not self._valid_host():
                return
            if self.path != "/v1/chat/completions":
                return self._error(404, "Unknown path.")
            if self.headers.get_content_type() != "application/json":
                return self._error(415, "Use application/json.")
            if "Transfer-Encoding" in self.headers:
                return self._error(400, "Chunked request bodies are unsupported.")
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return self._error(411, "A Content-Length is required.")
            if not 0 < length <= MAX_BYTES:
                return self._error(413, "Supply a body at most 256 KiB.")
            try:
                body = json.loads(self.rfile.read(length))
                response, status, source = handle_chat(upstream, body, system_prefix=system_prefix,
                                                       max_retries=max_retries, protected_values=protected_values)
            except (json.JSONDecodeError, UnicodeError, RecursionError):
                return self._error(400, "Invalid JSON.")
            except ClientError as error:
                return self._error(400, str(error))
            except ProtocolError:
                return self._error(502, "Could not reconstruct prior instructions.", "upstream_error")
            except Exception:
                # Never leak requests, credentials, provider bodies or server traces.
                return self._error(502, "Model processing failed.", "upstream_error")
            self._reply(200, response, {"X-PromptBoundary-Status": status,
                                        "X-PromptBoundary-Usage": source})

    return ThreadingHTTPServer((host, port), Handler)
