"""Verify known historical source snapshots without reinterpreting old responses.

Only explicitly pinned source/hash pairs may fall back from the current checkout.
This is archival reconstruction, not permission to ignore changed experiment code.
"""
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESPONSES_SHA256 = '41628af4165ac7ef5bf14ec137ebcedf59d8f4e37217fe0745c990026877d19a'
SNAPSHOTS = {
    ('promptboundary/responses.py', RESPONSES_SHA256): Path(__file__).with_name('frozen') / 'responses.py',
}


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_snapshot_path(filename, expected_hash):
    """Return matching current code or the exact allowlisted historical snapshot."""
    relative = Path(filename)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Invalid experiment source path')
    current = ROOT / relative
    if current.is_file() and _hash(current) == expected_hash:
        return current
    archive = SNAPSHOTS.get((relative.as_posix(), expected_hash))
    if archive is None:
        raise ValueError('Source differs from manifest and has no pinned snapshot: ' + filename)
    if not archive.is_file() or _hash(archive) != expected_hash:
        raise ValueError('Historical source snapshot failed SHA-256 verification: ' + filename)
    return archive


def historical_chat_result():
    """Load the original decoder, retaining its historical phase handling exactly."""
    path = verified_snapshot_path('promptboundary/responses.py', RESPONSES_SHA256)
    spec = importlib.util.spec_from_file_location('promptboundary._responses_v02', path)
    if spec is None or spec.loader is None:
        raise ValueError('Cannot load verified historical Responses decoder')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.chat_result
