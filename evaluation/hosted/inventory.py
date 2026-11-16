"""Discover actual OpenAI model IDs. Never include credentials or private fine-tune IDs in logs."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, build_opener

from promptboundary.upstream import _NoRedirect

def inventory():
    req = Request("https://api.openai.com/v1/models", headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
    with build_opener(_NoRedirect()).open(req, timeout=45) as response:
        payload = json.load(response)
    ids = sorted({row["id"] for row in payload["data"]})
    families = {"sol": "gpt-6.1-sol", "astra": "gpt-6-astra", "control": "gpt-5.4-mini"}
    return {"endpoint": req.full_url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "count": len(ids), "all_ids_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
            "public_gpt_ids": [m for m in ids if m.startswith("gpt-")],
            "requested_families": {k:[m for m in ids if m == stem or m.startswith(stem+"-")]
                                   for k,stem in families.items()}}

if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, type=Path)
    out=p.parse_args().out
    result=inventory()
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("x") as f:
        json.dump(result,f,indent=2)
        f.write("\n")
    print(json.dumps(result["requested_families"],ensure_ascii=False))
