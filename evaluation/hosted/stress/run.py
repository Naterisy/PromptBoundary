"""Exercise real hosted reviewers with a fixed generator fault and matched benign controls."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import random
import time

from ..experiment import (LoggedEndpoint, MODELS, OUTPUT_LIMIT, RELEASE, ROOT, RATES,
                          compact, fingerprint, handle_chat, load_release)
from promptboundary.upstream import completion_object

HERE = Path(__file__).resolve().parent


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class FixedDraft(LoggedEndpoint):
    def __init__(self, model, journal, draft):
        super().__init__(model, journal)
        self.draft = draft
        self.injected = []

    def complete(self, messages, **params):
        if params.get("response_format"):
            return super().complete(messages, **params)
        # Interpose only on generation and revision. Never spoof a paid API response.
        self.injected.append({"source": "fixture_not_api", "messages": messages,
                              "params": params, "draft": self.draft})
        return completion_object(self.model, self.draft)


def run_cell(job, out, legacy):
    model, arm, case = job
    folder = out/model/arm
    folder.mkdir(exist_ok=True, parents=True)
    path = folder/(case["id"]+".json")
    if path.exists():
        return
    journal = path.with_suffix(".jsonl")
    with journal.open("x"):
        pass
    ep = FixedDraft(model, journal, case["draft"])
    messages = [{"role":"system","content":case["system"]},{"role":"user","content":case["user_text"]}]
    started = time.perf_counter()
    answer, runtime_status, error = "", None, None
    try:
        result, runtime_status, _ = (legacy if arm == "release" else handle_chat)(
            ep, {"model":model,"messages":messages,"max_tokens":OUTPUT_LIMIT}, max_retries=1)
        answer = result["choices"][0]["message"]["content"]
    except (ValueError, RuntimeError, IndexError, KeyError) as exc:
        error = str(exc)
    row = {"case": case["id"], "model":model, "served_models":sorted(ep.served), "arm":arm,
           "input_sha256":digest(compact(messages)), "draft_sha256":digest(case["draft"]),
           "answer":answer, "runtime_status":runtime_status,
           "status":"error" if ep.failures or error else runtime_status, "error":error or ep.failures,
           "stage_incomplete":ep.truncated, "elapsed_ms":round(1000*(time.perf_counter()-started),3),
           "calls":ep.count, "draft_count":len(ep.injected)}
    path.with_suffix(".drafts.json").write_text(compact(ep.injected)+"\n",encoding="utf-8")
    temp = path.with_suffix(".tmp")
    temp.write_text(compact(row)+"\n",encoding="utf-8")
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text())
    if set(MODELS) - set(inventory["public_gpt_ids"]):
        raise ValueError("Missing verified model")
    cases = json.loads((HERE/"cases.json").read_text())
    if len(cases)!=8 or len({c["id"] for c in cases})!=8 or sum(bool(c["forbidden"]) for c in cases)!=4:
        raise ValueError("Expected four preselected bad drafts and four good controls")
    if not all(c["needed"] in c["draft"] and c["forbidden"] in c["draft"] for c in cases):
        raise ValueError("Fixture must contain all specified literals")
    legacy = load_release(args.legacy)
    jobs = [(model,arm,case) for model in MODELS for arm in ("release","patched") for case in cases]
    random.Random(43).shuffle(jobs)
    print(len(jobs),"reviewer cells; generation is fixed, interpretation and audit are billable", flush=True)
    if not args.execute:
        return
    args.out.mkdir(parents=True, exist_ok=True)
    sources = [Path(__file__),ROOT/"evaluation/hosted/experiment.py",*[
        ROOT/"promptboundary"/f for f in ("core.py","middleware.py","upstream.py","responses.py")]]
    manifest = {"legacy_git_sha":RELEASE, "inventory_sha256":fingerprint(args.inventory),
                "suite_sha256":fingerprint(HERE/"cases.json"),"models":list(MODELS),"rates":RATES,
                "output_limit":OUTPUT_LIMIT,"reasoning":"low","shuffle_seed":43,"workers":args.workers,
                "sources":{str(f.relative_to(ROOT)):fingerprint(f) for f in sources}}
    dest = args.out/"manifest.json"
    if dest.exists() and json.loads(dest.read_text()) != json.loads(compact(manifest)):
        raise ValueError("Manifest mismatch; use a fresh output path")
    dest.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(lambda j:run_cell(j,args.out,legacy),jobs))


if __name__ == "__main__":
    main()
