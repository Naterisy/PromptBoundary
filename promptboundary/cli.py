"""Command line entry points for the no-key demo and local HTTP middleware."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import BoundaryController, MockModel, OpenAICompatible, StageModel, State
from .demo import DEMO_TURNS
from .middleware import make_server
from .responses import OpenAIResponses


def parser():
    p = argparse.ArgumentParser(prog="promptboundary")
    commands = p.add_subparsers(dest="command", required=True)
    for name, help_text in (("demo", "Run five example turns"), ("chat", "Run a single turn"),
                            ("serve", "Start the loopback HTTP middleware")):
        cmd = commands.add_parser(name, help=help_text)
        transport = cmd.add_mutually_exclusive_group()
        transport.add_argument("--mock", action="store_true", help="Use the offline demo fixture (default)")
        transport.add_argument("--base-url", help="Explicit OpenAI-compatible API base URL including /v1")
        cmd.add_argument("--api", choices=["chat", "responses"], default="chat",
                         help="Upstream API protocol (default: chat)")
        cmd.add_argument("--model", help="Upstream model ID, required with --base-url")
        cmd.add_argument("--api-key-env", metavar="NAME", help="Read an optional bearer key from this variable")
        cmd.add_argument("--timeout", type=float, default=120, help="Upstream timeout in seconds (default 120)")
        cmd.add_argument("--skill", type=Path, help="Prepend this exact UTF-8 skill to stage instructions")
        cmd.add_argument("--max-retries", type=int, choices=range(4), default=1)
        if name == "serve":
            cmd.add_argument("--port", type=int, default=8080)
        else:
            cmd.add_argument("--temperature", type=float, help="Defaults to zero on Chat Completions; omit on reasoning endpoints")
            cmd.add_argument("--max-tokens", type=int, default=512, help="Per-stage completion token limit")
            cmd.add_argument("--json", action="store_true", help="Emit a JSON transcript with per-stage metrics")
        if name == "chat":
            cmd.add_argument("text", help="User request")
    return p


def _upstream(args):
    if args.base_url:
        if not args.model:
            raise ValueError("--base-url requires --model.")
        key = None
        if args.api_key_env:
            key = os.environ.get(args.api_key_env)
            if not key:
                raise ValueError("The explicitly selected API-key variable is empty.")
        transport = OpenAIResponses if args.api == "responses" else OpenAICompatible
        return transport(args.base_url, args.model, api_key=key, timeout=args.timeout)
    if args.api_key_env or args.model or args.api == "responses":
        raise ValueError("Use --base-url when selecting an upstream model or a key.")
    return MockModel()


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        upstream = _upstream(args)
        prefix = args.skill.read_bytes().decode("utf-8") if args.skill else ""
        if args.command == "serve":
            if not 0 <= args.port < 65536:
                raise ValueError("Port must be in the range 0–65535.")
            with make_server(upstream, port=args.port, system_prefix=prefix,
                             max_retries=args.max_retries) as server:
                print(f"Listening on http://127.0.0.1:{server.server_port}/v1 (model {upstream.model})",
                      file=sys.stderr, flush=True)
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
            return 0
        if (args.temperature is not None and not 0 <= args.temperature <= 2) or args.max_tokens < 1:
            raise ValueError("Use a temperature from 0 to 2 and a positive max-tokens value.")
        generation = {"max_tokens": args.max_tokens}
        if args.temperature is not None or args.api == "chat":
            generation["temperature"] = args.temperature or 0.0
        model = StageModel(upstream, generation, system_prefix=prefix)
        controller = BoundaryController(model, max_retries=args.max_retries)
        state = State()
        transcript = []
        if not args.json:
            print(f"Model  {upstream.model}")
        for user in (DEMO_TURNS if args.command == "demo" else [args.text]):
            result = controller.run(state, user)
            state = result.state
            transcript.append({"user": user, "answer": result.text, "status": result.status,
                               "attempts": result.attempts, "events": result.events})
            if not args.json:
                print(f"\nYou    {user}\nAgent  {result.text}\n       [{result.status}, {result.attempts} attempt(s)]")
        if args.json:
            print(json.dumps({"model": upstream.model, "turns": transcript, "calls": model.calls},
                             ensure_ascii=False, indent=2))
        return int(any(t["status"] == "fallback" for t in transcript))
    except (OSError, UnicodeError, ValueError) as exc:
        p.error(str(exc))


if __name__ == "__main__":
    sys.exit(main())
