"""SDK and HTTP integration tests. All sockets are loopback and use synthetic data."""
import contextlib
import io
import json
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request

from promptboundary import BoundaryController, MockModel, OpenAICompatible, StageModel, State, UpstreamError
from promptboundary.cli import main
from promptboundary.demo import DEMO_TURNS, SAMPLE, SET_RULE
from promptboundary.middleware import ClientError, handle_chat, make_server
from promptboundary.upstream import GENERATION_CONTEXT, completion_object


@contextlib.contextmanager
def running(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def body(*messages):
    return {"model": MockModel.model, "messages": list(messages)}


def msg(role, content):
    return {"role": role, "content": content}


class SDKTests(unittest.TestCase):
    def test_mock_demo_one_turn_exception_then_revocation(self):
        model = StageModel(MockModel())
        controller = BoundaryController(model)
        state = State()
        outputs = []
        for user in (*DEMO_TURNS, "What is a comet?"):
            turn = controller.run(state, user)
            self.assertEqual(turn.status, "ok")
            state = State.from_dict(turn.state.to_dict())
            outputs.append(turn.text.startswith("- "))
        self.assertEqual(outputs, [True, True, False, True, False, False])
        self.assertEqual(len(model.calls), 18)
        self.assertEqual({c["usage_source"] for c in model.calls}, {"mock_estimate"})

    def test_each_call_including_failed_json_has_context_and_usage(self):
        class Malformed:
            def complete(self, messages, **params):
                self.messages, self.params = messages, params
                return completion_object("test", "bad-json",
                                         {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9})

        provider = Malformed()
        stage = StageModel(provider, generation={"temperature": 0.1}, system_prefix="frozen")
        with self.assertRaises(ValueError):
            stage("audit", {"instructions": "audit protocol", "data": {"candidate": "private"}})
        self.assertEqual(provider.messages[0], msg("system", "frozen\n\naudit protocol"))
        self.assertEqual(provider.params["temperature"], 0.1)
        fmt = provider.params["response_format"]
        self.assertEqual(fmt["type"], "json_schema")
        self.assertTrue(fmt["json_schema"]["strict"])
        schema = fmt["json_schema"]["schema"]
        self.assertEqual(set(schema["required"]), {"verdict", "reason", "rule_id", "evidence", "missing"})
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(stage.calls[0]["total_tokens"], 9)
        self.assertEqual(stage.calls[0]["usage_source"], "provider")
        self.assertNotIn("private", str(stage.calls))

    def test_truncation_and_unavailable_counts(self):
        class Truncated:
            def complete(self, messages, **params):
                result = completion_object("test", "{}")
                result["choices"][0]["finish_reason"] = "length"
                return result

        stage = StageModel(Truncated())
        with self.assertRaises(ValueError):
            stage("interpret", {"instructions": "i", "data": {}})
        self.assertIsNone(stage.calls[0]["total_tokens"])
        self.assertEqual(stage.calls[0]["usage_source"], "unavailable")

    def test_interpret_schema_only_allows_existing_targets(self):
        class Recorder:
            def complete(self, messages, **params):
                self.schema = params["response_format"]["json_schema"]["schema"]
                return completion_object("test", "{}")

        provider = Recorder()
        stage = StageModel(provider)
        for ids in ([], ["r2", "r5"]):
            data = {"records": [{"id": i} for i in ids]}
            stage("interpret", {"instructions": "classify", "data": data})
            props = provider.schema["properties"]
            action = props["actions"]["items"]
            if not ids:
                self.assertNotIn("decisions", props)
                self.assertEqual(action["properties"]["op"]["enum"], ["set"])
                continue
            self.assertEqual(props["decisions"]["required"], ids)
            self.assertEqual(props["protected_ids"]["items"]["enum"], [*ids, "private_attack"])
            new, replace, edit = action["anyOf"]
            self.assertNotIn("id", new["properties"])
            self.assertEqual(replace["properties"]["id"]["enum"], ids)
            self.assertEqual(set(edit["required"]), {"op", "id", "quote"})
            self.assertTrue(all(not obj["additionalProperties"] for obj in action["anyOf"]))

    def test_explicit_unsupported_schema_falls_back_once_and_counts_each_attempt(self):
        url = "http://127.0.0.1/v1"
        backend = OpenAICompatible(url, "test")
        stage = StageModel(backend)
        payload = {"instructions": "review", "data": {}}
        detail = {"error": {"message": "response_format of type 'json_schema' is not supported by this model.",
                            "param": "response_format"}}
        reject = error.HTTPError(url, 400, "", {}, io.BytesIO(json.dumps(detail).encode()))

        def success():
            value = completion_object("test", "{}", {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7})
            response = io.BytesIO(json.dumps(value).encode())
            response.headers = {}
            return response

        with patch.object(backend._opener, "open", side_effect=[reject, success(), success()]) as http:
            self.assertEqual(stage("audit", payload), {})
            self.assertEqual(stage("audit", payload), {})
        formats = [json.loads(call.args[0].data)["response_format"]["type"] for call in http.call_args_list]
        self.assertEqual(formats, ["json_schema", "json_object", "json_object"])
        self.assertEqual([c["response_format"] for c in stage.calls], formats)
        self.assertEqual([c["total_tokens"] for c in stage.calls], [None, 7, 7])
        self.assertEqual([c["usage_source"] for c in stage.calls], ["unavailable", "provider", "provider"])

    def test_other_upstream_errors_do_not_downgrade(self):
        url = "http://127.0.0.1/v1"
        for code, message in [(400, "json_schema: unsupported keyword bad_field (secret)"),
                              (500, "json_schema is not supported (secret)"),
                              (429, "rate limit (secret)")]:
            backend = OpenAICompatible(url, "test")
            stage = StageModel(backend)
            raw = io.BytesIO(json.dumps({"error": {"message": message}}).encode())
            err = error.HTTPError(url, code, "", {}, raw)
            with self.subTest(code=code), patch.object(backend._opener, "open", side_effect=err):
                with self.assertRaises(UpstreamError) as captured:
                    stage("audit", {"instructions": "review", "data": {}})
                self.assertTrue(captured.exception.unavailable)
                self.assertNotIn("secret", str(captured.exception))
                self.assertEqual(len(stage.calls), 1)
                self.assertEqual(stage.calls[0]["response_format"], "json_schema")

    def test_generation_preserves_roles_and_literal_answer(self):
        class Recorder:
            def complete(self, messages, **params):
                self.messages, self.params = messages, params
                return completion_object("test", 'Here is a literal {"text":"field"}.')

        backend = Recorder()
        model = StageModel(backend, {"temperature": 0.25}, system_prefix="frozen skill")
        history = [msg("system", "app system"), msg("developer", "app instructions"),
                   msg("user", "I have a parrot."), msg("assistant", "I see.")]
        data = {"history": history, "user_text": "Write a caption.", "mode": "conflict",
                "constraints": [{"kind": "correction", "rule": "Bird is a parrot.", "scope": "photo",
                                 "quote": "private evidence is not a system instruction"}],
                "alternative": "Caption the bird.", "feedback": "Write in English."}
        result = model("generate", {"instructions": "Write naturally.", "data": data})
        self.assertEqual(backend.params, {"temperature": 0.25})
        self.assertEqual(backend.messages[1:5], history)
        self.assertTrue(backend.messages[0]["content"].startswith("frozen skill\n\nWrite naturally."))
        self.assertEqual(backend.messages[-1], msg("user", data["user_text"]))
        self.assertEqual(backend.messages[-2]["role"], "user")
        context = json.loads(backend.messages[-2]["content"].removeprefix(GENERATION_CONTEXT))
        self.assertEqual(context["constraints"], [{"kind": "correction", "scope": "photo",
                                                   "rule": "Bird is a parrot."}])
        self.assertEqual(context["feedback"], data["feedback"])
        self.assertEqual(context["mode"], "conflict")
        self.assertEqual(result, {"text": 'Here is a literal {"text":"field"}.'})
        self.assertEqual(model.calls[0]["stage"], "generate")

    def test_cli_output_is_machine_readable(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["demo", "--mock", "--json"]), 0)
        run = json.loads(out.getvalue())
        self.assertEqual(len(run["turns"]), 5)
        self.assertEqual(len(run["calls"]), 15)

    def test_transport_and_listener_reject_insecure_configuration(self):
        for url in ("http://example.org/v1", "https://me:key@example.org/v1",
                    "file:///tmp/service", "https://example.org/v1?key=secret"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OpenAICompatible(url, "test")
        with self.assertRaises(ValueError):
            make_server(MockModel(), "0.0.0.0")

    def test_request_subset(self):
        good = body(msg("user", "hello"))
        for changes in ({"stream": True}, {"n": 2}, {"tools": []}, {"model": "other"},
                        {"messages": [msg("tool", "test")]}, {"messages": [msg("user", [])]},
                        {"seed": True}, {"temperature": "1"}, {"max_tokens": 0}):
            with self.subTest(changes=changes), self.assertRaises(ClientError):
                handle_chat(MockModel(), dict(good, **changes))

    def test_replay_accounting_and_isolation(self):
        class Spy(MockModel):
            def __init__(self):
                self.calls = []

            def complete(self, messages, **params):
                result = super().complete(messages, **params)
                # Structured stages carry history in their JSON input, while
                # the draft receives it directly as native conversation messages.
                history = json.loads(messages[-1]["content"])["history"] if "response_format" in params else messages
                self.calls.append((history, result["usage"]))
                return result

        spy = Spy()
        instruction = msg("developer", "Use plain English.")
        history = [instruction, msg("user", SET_RULE), msg("assistant", "Understood.")]
        current = msg("user", "What is a comet?")
        answer, status, source = handle_chat(spy, body(*history, current))
        self.assertEqual(answer["choices"][0]["message"]["content"], "- " + SAMPLE)
        self.assertEqual((status, source), ("ok", "mock_estimate"))
        self.assertEqual(len(spy.calls), 4)
        self.assertEqual(answer["usage"]["total_tokens"], sum(u["total_tokens"] for _, u in spy.calls))
        self.assertTrue(all(instruction in history for history, _ in spy.calls))
        other, _, _ = handle_chat(spy, body(current))
        self.assertEqual(other["choices"][0]["message"]["content"], SAMPLE)


class HTTPTests(unittest.TestCase):
    def test_real_http_sdk_to_middleware(self):
        with running(make_server(MockModel(), port=0)) as url:
            client = OpenAICompatible(url + "/v1", MockModel.model)
            answer = client.complete([msg("user", "What is a comet?")])
            self.assertEqual(answer["choices"][0]["message"]["content"], SAMPLE)
            self.assertGreater(answer["usage"]["total_tokens"], 0)
            with request.urlopen(url + "/v1/models") as response:
                self.assertEqual(json.load(response)["data"][0]["id"], MockModel.model)
            data = json.dumps(dict(body(msg("user", "hello")), stream=True)).encode()
            req = request.Request(url + "/v1/chat/completions", data,
                                  {"Content-Type": "application/json"})
            with self.assertRaises(error.HTTPError) as got:
                request.urlopen(req)
            with got.exception as response:
                self.assertEqual(response.code, 400)
                self.assertEqual(json.load(response)["error"]["type"], "invalid_request_error")

    def test_no_credential_redirect(self):
        visited = []
        class Redirect(BaseHTTPRequestHandler):
            def do_POST(self):
                visited.append(self.path)
                self.send_response(302)
                self.send_header("Location", "/leak")
                self.end_headers()

            def do_GET(self):
                visited.append(self.path)
                self.send_response(418)
                self.end_headers()

            def log_message(self, *args):
                pass

        with running(ThreadingHTTPServer(("127.0.0.1", 0), Redirect)) as url:
            client = OpenAICompatible(url + "/v1", "test", api_key="synthetic-test-key")
            with self.assertRaisesRegex(UpstreamError, "302"):
                client.complete([msg("user", "hello")])
        self.assertEqual(visited, ["/v1/chat/completions"])


if __name__ == "__main__":
    unittest.main()
