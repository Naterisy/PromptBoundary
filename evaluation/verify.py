"""Recompute a published run's scores and costs from its delivered replies."""
import argparse
import math
from pathlib import Path

from .run import ARMS, HERE, digest, fingerprint, read, summarize, total
from .score import score
from promptboundary.upstream import TOKEN_FIELDS


def verify(directory):
    manifest = read(directory / "run.json")
    for name, expected in manifest["frozen"].items():
        if digest(HERE / name) != expected:
            raise ValueError(f"Frozen input differs: {name}")
    cases = read(HERE / "suites" / (manifest["suite"] + ".json"))
    expected = {f"{case['id']}-{arm}.json": (case, arm) for case in cases for arm in ARMS}
    paths = list((directory / "rows").glob("*.json"))
    if {p.name for p in paths} != set(expected):
        raise ValueError("Run has missing or unexpected cells.")
    rows = []
    for path in paths:
        row = read(path)
        case, arm = expected[path.name]
        if row["case"] != case["id"] or row["arm"] != arm:
            raise ValueError(f"Wrong cell identity: {path.name}")
        if "snapshot" in row and row["snapshot"] != fingerprint(manifest):
            raise ValueError(f"Wrong run snapshot: {path.name}")
        if score(case, row["answer"], row["status"]) != row["score"]:
            raise ValueError(f"Score differs: {path.name}")
        if manifest["mode"] == "model" and any(c["usage_source"] == "mock_estimate" for c in row["calls"]):
            raise ValueError(f"Mock accounting in measured run: {path.name}")
        if any(row[key] != total(row["calls"], key) for key in TOKEN_FIELDS):
            raise ValueError(f"Call accounting differs: {path.name}")
        if not math.isclose(row["elapsed_ms"], row["setup_ms"] + row["reply_ms"], abs_tol=0.002):
            raise ValueError(f"Timing components differ: {path.name}")
        rows.append(row)
    reported = read(directory / "summary.json")
    actual = summarize(rows, cases)
    for arm in ARMS:
        for key in ("overall", "full_history", "evicted", "mean", "mean_paired_delta_vs_A"):
            if actual["arms"][arm][key] != reported["arms"][arm][key]:
                raise ValueError(f"Summary differs: {arm}/{key}")
    if actual.get("validation3_gates") != reported.get("validation3_gates"):
        raise ValueError("Decision rule differs.")
    print(f"Verified {len(rows)} replies, scores and cost traces in {directory}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", nargs="+", type=Path)
    for selected in parser.parse_args().directories:
        verify(selected)
