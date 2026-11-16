#!/usr/bin/env python3
"""Load the exact offline runtime packaged beside this skill, then run its CLI."""
from pathlib import Path
import hashlib
from importlib.metadata import distribution, PackageNotFoundError
import json
import sys


def main():
    skill = Path(__file__).resolve().parents[1]
    manifest_path = skill / "manifest.json"
    try:
        if manifest_path.is_file():
            if manifest_path.stat().st_size > 1_048_576:
                raise ValueError("Invalid manifest")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries = manifest["files"]
            if not isinstance(entries, dict) or len(entries) > 128 or not {
                "runtime.zip", "scripts/guard.py", "SKILL.md", "LICENSE"
            } <= entries.keys():
                raise ValueError("Invalid manifest")
            for name, digest in entries.items():
                relative = Path(name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Invalid manifest path")
                target = skill / relative
                target.resolve().relative_to(skill)
                if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    raise ValueError("Package integrity check failed")
            sys.path.insert(0, str(skill / "runtime.zip"))
        else:
            # Direct use in a checkout uses authoritative source. An unbundled
            # copied or pip-installed Skill may use this exact installed version,
            # reporting that choice rather than pretending to be self-contained.
            repository = skill.parents[1]
            if (repository / "promptboundary" / "skill_cli.py").is_file():
                sys.path.insert(0, str(repository))
            else:
                installed = distribution("promptboundary")
                if installed.version != "0.4.0":
                    raise ValueError("Requires the matching PromptBoundary 0.4.0 package")
                print("Using installed PromptBoundary 0.4.0; this Skill copy has no bundled runtime.", file=sys.stderr)
        from promptboundary.skill_cli import main as run
        return run()
    except (OSError, ValueError, KeyError, TypeError, ImportError, PackageNotFoundError):
        print(json.dumps({"status": "error", "executed": False,
                          "message": "Skill runtime is missing, invalid or changed. Rebuild from a trusted checkout."}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
