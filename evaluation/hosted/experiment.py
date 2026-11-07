"""Run matched public synthetic probes via a verified OpenAI model inventory.

Run from the repository root with python -m evaluation.hosted.experiment --help.
Each cell has a durable append-only provider journal and one final row. Never
replay a partial cell automatically: its last request may have been billed.
"""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

from promptboundary.middleware import handle_chat
from promptboundary.responses import OpenAIResponses
from promptboundary.upstream import UpstreamError

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RELEASE = "cd5ee311c7637a6100a4c5392ea802419f16c3ed"
ORDER_SEED = 41
OUTPUT_LIMIT = 1024
ARMS = ("raw", "release", "patched")
# Standard USD per million: uncached input / cached read / cache write / output.
RATES = {"gpt-6.1-sol": (2, .10, 2.50, 10), "gpt-6-astra": (10, 1, 12.50, 50),
         "gpt-5.4-mini-2026-03-17": (.75, .075, .75, 4.50)}
MODELS = tuple(RATES)


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def amount(model, usage):
    details = usage.get("input_tokens_details") or {}
    cached = details.get("cached_tokens", 0)
    writes = details.get("cache_write_tokens", details.get("cache_creation_tokens", 0))
    total_in, total_out = usage["input_tokens"], usage["output_tokens"]
    ordinary = total_in - cached - writes
    if min(ordinary, cached, writes, total_out) < 0:
        raise ValueError("Unexpected token breakdown")
    rin, rc, rw, rout = RATES[model]
    return (ordinary*rin + cached*rc + writes*rw + total_out*rout)/1_000_000


def append(path, value):
    with path.open("a", encoding="utf-8") as f:
        f.write(compact(value) + "\n")
        f.flush()


class LoggedEndpoint(OpenAIResponses):
    def __init__(self, model, path):
        super().__init__("https://api.openai.com/v1", model, os.environ["OPENAI_API_KEY"], timeout=120)
        self.path = path
        self.count = 0
        self.failures = []
        self.served = set()
        self.truncated = False

    def exchange(self, body):
        self.count += 1
        if self.count > 24:
            raise UpstreamError("Per-cell stage call limit reached")
        append(self.path, {"n": self.count, "request": body})
        started = time.perf_counter()
        try:
            result = super().exchange(body)
        except UpstreamError as exc:
            self.failures.append(str(exc))
            append(self.path, {"n": self.count, "error": str(exc), "ms": round((time.perf_counter()-started)*1000, 3)})
            raise
        self.served.add(result.get("model"))
        self.truncated |= result.get("status") == "incomplete"
        append(self.path, {"n": self.count, "response": result, "ms": round((time.perf_counter()-started)*1000, 3)})
        return result


def load_release(path):
    # Resolve every old release module from the same pinned Git tree.
    package = path / "promptboundary"
    for file in ("__init__.py", "core.py", "middleware.py", "upstream.py"):
        original = subprocess.check_output(["git","show", f"{RELEASE}:promptboundary/{file}"], cwd=ROOT)
        if (package/file).read_bytes() != original:
            raise ValueError("Legacy checkout differs from released code")
    spec = importlib.util.spec_from_file_location("pb_release", package/"__init__.py",
                                                 submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    from pb_release.middleware import handle_chat as previous_handle
    return previous_handle


def cell(job, dest, release_handle):
    model, arm, case = job
    directory = dest/model/arm
    directory.mkdir(parents=True, exist_ok=True)
    row_path = directory/(case["id"]+".json")
    calls_path = directory/(case["id"]+".jsonl")
    if row_path.exists():
        return
    # Atomic claim prevents overwriting an interrupted or concurrent generation.
    with calls_path.open("x"):
        pass
    messages = [{"role":"system", "content":case["system"]}, *case["history"],
                {"role":"user","content":case["user_text"]}]
    endpoint = LoggedEndpoint(model, calls_path)
    params = {"messages": messages, "max_tokens": OUTPUT_LIMIT}
    started = time.perf_counter()
    answer, error, runtime_status = "", None, None
    try:
        if arm in ("raw", "smoke"):
            response = endpoint.complete(**params)
            choice = response["choices"][0]
            answer = choice["message"]["content"]
            runtime_status = "ok" if choice["finish_reason"]=="stop" else "incomplete"
        else:
            handler = release_handle if arm == "release" else handle_chat
            result, runtime_status, _ = handler(endpoint, {"model":model, **params}, max_retries=1)
            answer = result["choices"][0]["message"]["content"]
    except (ValueError, RuntimeError, KeyError, IndexError) as exc:
        error = str(exc)
    elapsed = round((time.perf_counter()-started)*1000, 3)
    status = runtime_status or "error"
    if endpoint.failures or error:
        status = "error"
    row = {"case":case["id"],"model":model,"served_models":sorted(endpoint.served),"arm":arm,
           "input_sha256":hashlib.sha256(compact(messages).encode()).hexdigest(),
           "answer":answer,"runtime_status":runtime_status,"status":status,"error":error or endpoint.failures,
           "stage_incomplete":endpoint.truncated,"elapsed_ms":elapsed,"calls":endpoint.count}
    temp = row_path.with_suffix(".tmp")
    temp.write_text(compact(row)+"\n")
    temp.replace(row_path)
    print(model,arm,case["id"],status,endpoint.count,flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--legacy", type=Path)
    p.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    p.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--execute", action="store_true", help="authorize billable requests")
    args = p.parse_args()
    catalog = json.loads(args.inventory.read_text())
    missing = set(args.models)-set(catalog["public_gpt_ids"])
    if missing:
        raise SystemExit(f"Model IDs absent from the verified catalog: {missing}")
    cases_path = HERE/"cases.json"
    cases = ([{"id":"transport","system":"Answer briefly.","history":[],"user_text":"Return the digit 7."}]
             if args.smoke else json.loads(cases_path.read_text()))
    arms = ["smoke"] if args.smoke else args.arms
    legacy = load_release(args.legacy) if "release" in arms and args.legacy else None
    if "release" in arms and legacy is None:
        p.error("Supply --legacy for the release arm")
    jobs = [(m,a,c) for m in args.models for a in arms for c in cases]
    random.Random(ORDER_SEED).shuffle(jobs)
    print("Matched cells:",len(jobs),"max output tokens per stage:",OUTPUT_LIMIT,flush=True)
    if not args.execute:
        return
    args.out.mkdir(exist_ok=True,parents=True)
    # Separate arm manifests allow the original arms to run while the fix is being implemented.
    for arm in arms:
        sources = [Path(__file__), ROOT/"promptboundary/responses.py"]
        if arm=="patched":
            sources.extend(ROOT/"promptboundary"/f for f in ("core.py","upstream.py","middleware.py"))
        manifest = {"arm":arm,"legacy_git_sha":RELEASE,"inventory_sha256":fingerprint(args.inventory),
                    "suite_sha256":fingerprint(cases_path) if not args.smoke else None,
                    "output_limit":OUTPUT_LIMIT,"reasoning":"low","shuffle_seed":ORDER_SEED,
                    "service_tier":"default","rates":RATES,
                    "sources":{str(x.relative_to(ROOT)): fingerprint(x) for x in sources}}
        name = args.out/(arm+"-manifest.json")
        encoded = json.dumps(manifest,indent=2)+"\n"
        if name.exists() and name.read_text() != encoded:
            raise SystemExit("Manifest mismatch, use a new output directory")
        name.write_text(encoded)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(lambda job:cell(job,args.out,legacy), jobs))


if __name__ == "__main__":
    main()
