"""Run preregistered A/B/C/D cases with one OpenAI-compatible model on loopback."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
from statistics import mean
import time
from urllib.parse import urlsplit

from .score import score
from promptboundary.core import BoundaryController, State
from promptboundary.upstream import MockModel, OpenAICompatible, StageModel, TOKEN_FIELDS

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
ARMS = "ABCD"
GENERATION = {"temperature": 0, "max_tokens": 384}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")
    temp.replace(path)


def verify_freeze(directory=HERE):
    manifest = read(directory / "freeze.json")
    for name, expected in manifest.items():
        if digest(directory / name) != expected:
            raise ValueError(f"Frozen evaluation file changed: {name}")
    return manifest


def total(calls, key):
    if not calls or any(c[key] is None for c in calls):
        return None
    return sum(c[key] for c in calls)


def raw_reply(upstream, messages, calls):
    t = time.perf_counter()
    counter = dict.fromkeys(TOKEN_FIELDS)
    source = "unavailable"
    try:
        completion = upstream.complete(messages, **GENERATION)
        usage = completion.get("usage", {})
        if all(type(usage.get(k)) is int and usage[k] >= 0 for k in TOKEN_FIELDS):
            source = completion.get("promptboundary_usage_source", "provider")
            counter = {k: usage[k] for k in TOKEN_FIELDS}
        choice = completion["choices"][0]
        text = choice["message"]["content"]
        if not isinstance(text, str):
            raise ValueError("Missing response text")
        return text, choice.get("finish_reason")
    finally:
        calls.append(dict(stage="chat", usage_source=source, **counter,
                          elapsed_ms=round((time.perf_counter() - t) * 1000, 3)))


def run_case(case, arm, upstream, skill):
    history = case["history"]
    visible = [] if case["evict_after_observe"] else history
    prefix = skill if arm in "BD" else ""
    staged = StageModel(upstream, generation=GENERATION, system_prefix=prefix)
    calls = staged.calls
    status, reply, events, attempts = "ok", "", [], 0
    setup_calls, setup_ms = 0, 0.0
    started = time.perf_counter()
    try:
        if arm in "CD":
            controller = BoundaryController(staged, max_retries=1)
            state = State()
            try:
                for index, earlier in enumerate(history):
                    if earlier["role"] == "user":
                        state = controller.observe(state, earlier["content"], history[:index])
                if case["evict_after_observe"]:
                    serialized = state.to_dict()
                    serialized["history"] = []
                    state = State.from_dict(serialized)
            finally:
                setup_calls = len(calls)
                setup_ms = (time.perf_counter() - started) * 1000
            result = controller.run(state, case["user_text"], visible)
            status, reply, events, attempts = result.status, result.text, result.events, result.attempts
        else:
            messages = [{"role": "system", "content": prefix}] if prefix else []
            messages += [*visible, {"role": "user", "content": case["user_text"]}]
            reply, reason = raw_reply(upstream, messages, calls)
            events = [f"finish:{reason}"]
            attempts = 1
    except Exception as exc:
        status = "error"
        events.append(f"runtime:{type(exc).__name__}")
    elapsed = (time.perf_counter() - started) * 1000
    return dict(case=case["id"], behavior=case["behavior"], arm=arm, evicted=case["evict_after_observe"],
                status=status, answer=reply, events=events, attempts=attempts,
                score=score(case, reply, status), calls=calls, setup_calls=setup_calls,
                setup_ms=round(setup_ms, 3), reply_ms=round(elapsed - setup_ms, 3),
                elapsed_ms=round(elapsed, 3), **{k: total(calls, k) for k in TOKEN_FIELDS})


def measures(rows):
    measures = {}
    for metric in ("retained", "violation", "false_refusal", "task_pass"):
        flags = [r["score"][metric] for r in rows if r["score"][metric] is not None]
        measures[metric] = {"count": sum(flags), "n": len(flags),
                            "rate": round(mean(flags), 6) if flags else None}
    return measures


def summarize(rows, cases):
    result = {"complete": len(rows) == len(cases) * len(ARMS), "rows": len(rows), "arms": {}}
    baseline = {r["case"]: r for r in rows if r["arm"] == "A"}
    for arm in ARMS:
        subset = [r for r in rows if r["arm"] == arm]
        if not subset:
            continue
        metrics = dict(n=len(subset), overall=measures(subset),
                       full_history=measures([r for r in subset if not r["evicted"]]),
                       evicted=measures([r for r in subset if r["evicted"]]),
                       errors=sum(r["status"] == "error" for r in subset),
                       fallbacks=sum(r["status"] == "fallback" for r in subset))
        pairs = [(r, baseline[r["case"]]) for r in subset if r["case"] in baseline]
        metrics["paired_cases_vs_A"] = len(pairs)
        metrics["mean"] = {}
        metrics["mean_paired_delta_vs_A"] = {}
        for field in ("elapsed_ms", "setup_ms", "reply_ms", *TOKEN_FIELDS):
            values = [r[field] for r in subset]
            metrics["mean"][field] = round(mean(values), 3) if None not in values else None
            known = all(r[field] is not None and a[field] is not None for r, a in pairs)
            delta = mean(r[field] - a[field] for r, a in pairs) if pairs and known else None
            metrics["mean_paired_delta_vs_A"][field] = round(delta, 3) if delta is not None else None
        result["arms"][arm] = metrics
    return result


def is_loopback(url):
    host = urlsplit(url).hostname
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18764/v1")
    parser.add_argument("--model", default="pb-qwen")
    parser.add_argument("--mock", action="store_true", help="Run fixture-only smoke; creates a distinct namespace")
    parser.add_argument("--suite", choices=["primary", "confirmation"], default="primary")
    parser.add_argument("--out", type=Path, required=True, help="Run root, e.g. evaluation/results/v1")
    parser.add_argument("--arms", default=ARMS, help="Subset, e.g. AB; use same directory to finish")
    parser.add_argument("--backend-id", default="", help="Exact weights/checksum and inference build for provenance")
    args = parser.parse_args()
    if not args.arms or any(a not in ARMS for a in args.arms) or len(set(args.arms)) != len(args.arms):
        parser.error("Use a nonempty, unique subset of ABCD.")
    if not args.mock and not is_loopback(args.base_url):
        parser.error("This evaluation runner only contacts a loopback endpoint.")
    frozen = verify_freeze()
    cases = read(HERE / "suites" / (args.suite + ".json"))
    upstream = MockModel() if args.mock else OpenAICompatible(args.base_url, args.model)
    skill_path = PROJECT / "SKILL.md"
    skill = skill_path.read_text(encoding="utf-8")
    mode = "mock_wiring_only" if args.mock else "model"
    dest = args.out / mode / args.suite
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "rows").mkdir(exist_ok=True)
    sources = [HERE / "run.py", PROJECT / "promptboundary/core.py", PROJECT / "promptboundary/upstream.py", skill_path]
    if args.mock:
        sources.append(PROJECT / "promptboundary/demo.py")
    provenance = dict(suite=args.suite, mode=mode, model=upstream.model, backend_id=args.backend_id,
                      base_url=None if args.mock else args.base_url, generation=GENERATION, retries=1,
                      frozen=frozen, sources={str(p.relative_to(PROJECT)): digest(p) for p in sources})
    stamp = dest / "run.json"
    if stamp.exists() and read(stamp) != provenance:
        parser.error("Snapshot mismatch. Resume identical code/configuration or choose a fresh --out.")
    save(stamp, provenance)
    for i, case in enumerate(cases):
        start = i % len(ARMS)
        for arm in ARMS[start:] + ARMS[:start]:
            path = dest / "rows" / f"{case['id']}-{arm}.json"
            if arm not in args.arms or path.is_file():
                continue
            row = run_case(case, arm, upstream, skill)
            save(path, row)
            print(f"{case['id']} {arm} {row['status']} {row['elapsed_ms']:.0f} ms", flush=True)
    rows = [read(path) for path in sorted((dest / "rows").glob("*.json"))]
    summary = dict(mode=mode, suite=args.suite, **summarize(rows, cases))
    save(dest / "summary.json", summary)
    print(f"Saved {len(rows)}/{len(cases)*4} terminal replies to {dest}", flush=True)


if __name__ == "__main__":
    main()
