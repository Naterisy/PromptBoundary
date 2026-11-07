"""Offline verification of every published full batch and all incremental API costs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent

def main():
    suites = {}
    for path in HERE.glob("*.json"):
        data = json.loads(path.read_text())
        if isinstance(data, list) and data and isinstance(data[0],dict) and "user" in data[0]:
            suites[hashlib.sha256(path.read_bytes()).hexdigest()] = path
    runs = sorted((HERE/"results").glob("*/RESULTS.json"))
    if not runs:
        raise ValueError("No completed experiment reports")
    for result in runs:
        manifest = json.loads((result.parent/"manifest.json").read_text())
        suite = suites[manifest["suite_sha256"]]
        subprocess.run([sys.executable,"-m","evaluation.agent_security.report",str(result.parent),
                        "--suite",str(suite),"--check"], check=True)
    subprocess.run([sys.executable,"-m","evaluation.agent_security.ledger_report",
                    str(HERE/"results"),"--check"], check=True)
    subprocess.run([sys.executable,"-m","evaluation.hosted.public_logs",str(HERE),"--check"],check=True)
    subprocess.run([sys.executable,"-m","evaluation.agent_security.confirmation_report",
                    *[str(HERE/"results"/f"confirm41_r{i}") for i in (1,2,3)],
                    "--suite",str(HERE/"test.json"),"--out",str(HERE/"results/CONFIRMATION"),
                    "--check"],check=True)
    print(f"Verified {len(runs)} frozen batches, including all billed unsuccessful development attempts.")

if __name__=="__main__":
    main()
