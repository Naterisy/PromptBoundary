"""Remove opaque provider continuation state from a shareable copy of synthetic journals.

This tool deliberately leaves delivered text, audit JSON, API IDs and token usage
intact. It is not a privacy filter for arbitrary user conversations.
"""
import argparse
import hashlib
import json
from pathlib import Path


def redact(record):
    changed = False
    for part in record.get("response", {}).get("output", []):
        if part.get("type") != "reasoning":
            continue
        for field in ("encrypted_content", "content", "summary"):
            if not part.get(field):
                continue
            v = part.pop(field)
            raw = (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, separators=(",",":"))).encode()
            part[field + "_redacted"] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
            changed = True
    return changed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path, help="path to the copy intended for sharing")
    p.add_argument("--check", action="store_true", help="only check for unredacted provider state")
    args = p.parse_args()
    modified = 0
    for path in args.directory.rglob("*.jsonl"):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        edits = sum(redact(r) for r in rows)
        modified += edits
        if edits and not args.check:
            tmp = path.with_suffix(".tmp")
            tmp.write_text("".join(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n" for r in rows), encoding="utf-8")
            tmp.replace(path)
    if modified and args.check:
        raise SystemExit(f"{modified} responses still contain provider continuation state")
    print(f"{modified} provider responses sanitized")


if __name__ == "__main__":
    main()
