#!/usr/bin/env python3
"""Build/install the offline skill from this checkout; no downloads or API calls."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "promptboundary-tools"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _zip(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return output.getvalue()


def build(root=ROOT):
    root = Path(root)
    runtime = {p.relative_to(root).as_posix(): p.read_bytes()
               for p in sorted((root / "promptboundary").glob("*.py"))}
    if "promptboundary/skill_cli.py" not in runtime:
        raise ValueError("Expected complete PromptBoundary source checkout")
    skill = root / "skills" / NAME
    entries = {p.relative_to(skill).as_posix(): p.read_bytes()
               for p in sorted(skill.rglob("*")) if p.is_file() and
               "__pycache__" not in p.parts and p.suffix in (".py", ".md", ".yaml")}
    if "SKILL.md" not in entries or "scripts/guard.py" not in entries:
        raise ValueError("Missing Skill entrypoint or guard")
    entries["LICENSE"] = (root / "LICENSE").read_bytes()
    entries["runtime.zip"] = _zip(runtime)
    try:
        commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        dirty = bool(subprocess.check_output(["git", "-C", str(root), "status", "--porcelain", "--",
                    "promptboundary", "skills/promptboundary-tools", "scripts/package_skill.py", "LICENSE"],
                    stderr=subprocess.DEVNULL).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    hashes = {name: _sha(data) for name, data in sorted(entries.items())}
    source_hashes = {**{name: _sha(data) for name, data in runtime.items()},
                     **{f"skills/{NAME}/{name}": digest for name, digest in hashes.items() if name != "runtime.zip"},
                     "scripts/package_skill.py": _sha((root / "scripts/package_skill.py").read_bytes())}
    manifest = {"format": 1, "skill": NAME, "source_commit": commit,
                "source_dirty": dirty, "source_tree_sha256": _sha(json.dumps(source_hashes, sort_keys=True).encode()),
                "files": hashes,
                "integrity_note": "Hashes detect changes; they are not signatures. Verify the checkout/commit independently."}
    entries["manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    return entries, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--destination", type=Path, help="Skill parent directory, e.g. ~/.agents/skills")
    destination.add_argument("--archive", type=Path, help="Create a reproducible zip and .sha256 file")
    args = parser.parse_args(argv)
    entries, manifest = build()
    if args.destination:
        args.destination.mkdir(parents=True, exist_ok=True)
        target = args.destination / NAME
        if target.exists() or target.is_symlink():
            parser.error("Destination exists; review/remove it before installing a replacement")
        staging = Path(tempfile.mkdtemp(prefix=".promptboundary-", dir=args.destination))
        try:
            for name, data in entries.items():
                path = staging / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            staging.rename(target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        output = {"installed": str(target), "source_tree_sha256": manifest["source_tree_sha256"]}
    else:
        archive = _zip({f"{NAME}/{name}": data for name, data in entries.items()})
        target = args.archive
        checksum = target.with_name(target.name + ".sha256")
        if target.exists() or checksum.exists():
            parser.error("Archive/checksum exists; review/remove before replacing")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(archive)
        checksum.write_text(f"{_sha(archive)}  {target.name}\n", encoding="utf-8")
        output = {"archive": str(target), "sha256": _sha(archive), "bytes": len(archive)}
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
